from __future__ import annotations

from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda


def _make_state(**kwargs):
    base = {
        "question": "test question",
        "generation": "",
        "documents": [],
        "doc_id": "test_doc",
        "retry_count": 0,
        "route": "",
        "grounded": False,
        "error": "",
        "session_id": "",
    }
    base.update(kwargs)
    return base


def _fake_doc(content="Some relevant content."):
    return Document(
        page_content=content,
        metadata={"doc_id": "test_doc", "ref": "ref1", "page": 1, "chunk_id": 0, "source": "test.pdf"},
    )


# Router tests

def test_router_routes_greeting():
    from rag.agents.router import route_query

    result = route_query(_make_state(question="hello"))
    assert result["route"] == "direct"


def test_router_routes_document_question():
    from rag.agents.router import route_query

    result = route_query(_make_state(question="What are the technical skills listed?"))
    assert result["route"] == "retrieve"


def test_router_falls_back_to_retrieve_on_error():
    from rag.agents.router import route_query

    result = route_query(_make_state(question="anything"))
    assert result["route"] == "retrieve"


# Grader tests

def test_grader_filters_irrelevant_docs():
    from rag.agents.grader import grade_documents

    docs = [_fake_doc("relevant content"), _fake_doc("irrelevant content"), _fake_doc("also relevant")]
    state = _make_state(question="What is the topic?", documents=docs)

    fake_llm = RunnableLambda(lambda x: AIMessage(content='["yes", "no", "yes"]'))
    with patch("rag.agents.grader.get_llm", return_value=fake_llm):
        result = grade_documents(state)

    assert len(result["documents"]) == 2
    assert result["documents"][0].page_content == "relevant content"
    assert result["documents"][1].page_content == "also relevant"


def test_grader_keeps_all_docs_on_llm_error():
    from rag.agents.grader import grade_documents

    docs = [_fake_doc("doc 1"), _fake_doc("doc 2")]
    state = _make_state(documents=docs)

    with patch("rag.agents.grader.get_llm", side_effect=RuntimeError("API down")):
        result = grade_documents(state)

    assert len(result["documents"]) == 2


# Hallucination checker tests

def test_hallucination_checker_catches_ungrounded_answer():
    from rag.agents.hallucination import check_hallucination, GroundednessScore

    state = _make_state(
        documents=[_fake_doc("The sky is blue.")],
        generation="The sky is green and made of cheese.",
        retry_count=0,
    )
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = RunnableLambda(
        lambda x: GroundednessScore(grounded="no")
    )
    with patch("rag.agents.hallucination.get_llm", return_value=mock_llm):
        result = check_hallucination(state)

    assert result["grounded"] is False
    assert result["retry_count"] == 1
    assert result["generation"] == ""


def test_hallucination_checker_passes_grounded_answer():
    from rag.agents.hallucination import check_hallucination, GroundednessScore

    state = _make_state(
        documents=[_fake_doc("The sky is blue.")],
        generation="According to the document, the sky is blue.",
    )
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = RunnableLambda(
        lambda x: GroundednessScore(grounded="yes")
    )
    with patch("rag.agents.hallucination.get_llm", return_value=mock_llm):
        result = check_hallucination(state)

    assert result["grounded"] is True


# Retry / conditional edge tests

def test_retry_loop_stops_at_max_retries():
    from rag.agents.graph import decide_after_grading

    state = _make_state(documents=[], retry_count=3, error="")
    assert decide_after_grading(state) == "fallback"


def test_retry_loop_rewrites_when_below_max():
    from rag.agents.graph import decide_after_grading

    state = _make_state(documents=[], retry_count=1, error="")
    assert decide_after_grading(state) == "rewrite_query"


def test_not_indexed_error_goes_to_fallback():
    from rag.agents.graph import decide_after_grading

    state = _make_state(documents=[], retry_count=0, error="No documents indexed.")
    assert decide_after_grading(state) == "fallback"


def test_hallucination_routes_to_end_when_grounded():
    from langgraph.graph import END
    from rag.agents.graph import decide_after_hallucination

    state = _make_state(grounded=True, retry_count=0)
    assert decide_after_hallucination(state) == END


def test_hallucination_routes_to_generate_when_not_grounded():
    from rag.agents.graph import decide_after_hallucination

    state = _make_state(grounded=False, retry_count=1)
    assert decide_after_hallucination(state) == "generate"


# Full pipeline test (mocked LLM nodes)

def test_full_pipeline_end_to_end(tmp_path, monkeypatch):
    """Full graph run with mocked store + embedding, all LLM nodes mocked."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    doc_id = "pipeline_doc"
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir(parents=True)
    (pdf_dir / f"{doc_id}.pdf").write_bytes(b"placeholder")

    from unstructured.documents.elements import NarrativeText
    from types import SimpleNamespace
    _el = NarrativeText(text="Python is a programming language.")
    _el.metadata = SimpleNamespace(page_number=1)
    with patch("rag.ingest.extract_elements", return_value=[_el]), \
         patch("rag.ingest.clear_document"), \
         patch("rag.ingest.add_documents"):
        from rag.ingest import index_document
        index_document(doc_id)

    from rag.agents.graph import build_graph
    fake_doc = _fake_doc("Python is a programming language.")

    with patch("rag.agents.graph.route_query", return_value={"route": "retrieve"}), \
         patch("rag.agents.graph.retrieve", return_value={"documents": [fake_doc], "hyde_triggered": False}), \
         patch("rag.agents.graph.grade_documents", return_value={"documents": [fake_doc]}), \
         patch("rag.agents.graph.generate", return_value={"generation": "Python is a language."}), \
         patch("rag.agents.graph.check_hallucination", return_value={"grounded": True}):

        build_graph.cache_clear()
        result = build_graph().invoke(_make_state(question="What is Python?", doc_id=doc_id))

    build_graph.cache_clear()

    assert result["generation"] == "Python is a language."
    assert result["grounded"] is True


# Conversation memory tests

def test_conversation_memory_stores_and_retrieves():
    from rag.agents.memory import get_memory, clear_memory

    session_id = "test_session_abc"
    clear_memory(session_id)

    mem = get_memory(session_id)
    mem.add_user_message("What is this document about?")
    mem.add_ai_message("It is about machine learning.")

    mem2 = get_memory(session_id)
    assert len(mem2.messages) == 2
    assert mem2.messages[0].content == "What is this document about?"
    assert mem2.messages[1].content == "It is about machine learning."

    clear_memory(session_id)
    assert len(get_memory(session_id).messages) == 0


def test_conversation_memory_different_sessions_are_isolated():
    from rag.agents.memory import get_memory, clear_memory

    clear_memory("session_a")
    clear_memory("session_b")

    get_memory("session_a").add_user_message("Session A question")
    get_memory("session_b").add_user_message("Session B question")

    assert len(get_memory("session_a").messages) == 1
    assert len(get_memory("session_b").messages) == 1
    assert get_memory("session_a").messages[0].content == "Session A question"
    assert get_memory("session_b").messages[0].content == "Session B question"

    clear_memory("session_a")
    clear_memory("session_b")
