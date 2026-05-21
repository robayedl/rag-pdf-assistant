from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document


def _doc(content="test content", ref="ref1"):
    return Document(
        page_content=content,
        metadata={"doc_id": "test", "ref": ref, "page": 1, "chunk_id": 0, "source": "test.pdf"},
    )


# rerank_with_score

def test_rerank_with_score_returns_correct_top_score():
    from rag.chains.rerank import rerank_with_score

    docs = [_doc("doc a", "a"), _doc("doc b", "b")]
    mock_encoder = MagicMock()
    mock_encoder.predict.return_value = [0.8, 0.3]

    with patch("rag.chains.rerank._get_cross_encoder", return_value=mock_encoder):
        result_docs, top_score = rerank_with_score("query", docs, top_k=2)

    assert top_score == pytest.approx(0.8, abs=1e-4)
    assert result_docs[0].metadata["ref"] == "a"
    assert result_docs[1].metadata["ref"] == "b"


def test_rerank_with_score_empty_input():
    from rag.chains.rerank import rerank_with_score

    docs, score = rerank_with_score("query", [])
    assert docs == []
    assert score == 0.0


# semantic cache

def test_cache_lookup_graceful_when_redis_down():
    from rag import cache

    with patch("rag.cache._get_client", side_effect=ConnectionError("Redis down")):
        assert cache.lookup("any query", "doc-1") is None


def test_cache_store_graceful_when_redis_down():
    from rag import cache

    with patch("rag.cache._get_client", side_effect=ConnectionError("Redis down")):
        cache.store("q", "doc-1", "answer", [])  # must not raise


def test_cache_lookup_returns_none_on_empty_results():
    from rag import cache

    mock_client = MagicMock()
    mock_client.ft.return_value.info.return_value = {}
    mock_client.ft.return_value.search.return_value = MagicMock(docs=[])

    with patch("rag.cache._get_client", return_value=mock_client), \
         patch("rag.cache._embed", return_value=[0.0] * 768):
        assert cache.lookup("unknown query", "doc-1") is None


def test_cache_lookup_hit_above_threshold():
    from rag import cache

    citations = [{"ref": "r1", "page": 1, "chunk_id": 0, "source": "f.pdf"}]
    mock_doc = MagicMock()
    mock_doc.score = "0.01"  # distance → similarity = 0.99, above default 0.97
    mock_doc.answer = b"cached answer"
    mock_doc.citations = json.dumps(citations).encode()

    mock_client = MagicMock()
    mock_client.ft.return_value.info.return_value = {}
    mock_client.ft.return_value.search.return_value = MagicMock(docs=[mock_doc])

    with patch("rag.cache._get_client", return_value=mock_client), \
         patch("rag.cache._embed", return_value=[0.0] * 768), \
         patch.dict("os.environ", {"SEMANTIC_CACHE_THRESHOLD": "0.97"}):
        result = cache.lookup("what is attention?", "doc-1")

    assert result is not None
    assert result["answer"] == "cached answer"
    assert result["citations"] == citations


def test_cache_lookup_miss_below_threshold():
    from rag import cache

    mock_doc = MagicMock()
    mock_doc.score = "0.15"  # distance → similarity = 0.85, below 0.97

    mock_client = MagicMock()
    mock_client.ft.return_value.info.return_value = {}
    mock_client.ft.return_value.search.return_value = MagicMock(docs=[mock_doc])

    with patch("rag.cache._get_client", return_value=mock_client), \
         patch("rag.cache._embed", return_value=[0.0] * 768), \
         patch.dict("os.environ", {"SEMANTIC_CACHE_THRESHOLD": "0.97"}):
        assert cache.lookup("something different", "doc-1") is None


def test_cache_lookup_is_scoped_by_doc_id():
    from rag import cache

    # Redis returns no docs when the doc_id tag filter matches nothing
    mock_client = MagicMock()
    mock_client.ft.return_value.info.return_value = {}
    mock_client.ft.return_value.search.return_value = MagicMock(docs=[])

    with patch("rag.cache._get_client", return_value=mock_client), \
         patch("rag.cache._embed", return_value=[0.0] * 768):
        result = cache.lookup("same question as doc-a", "doc-b")

    # Verify the query string includes the doc_id tag filter
    call_args = mock_client.ft.return_value.search.call_args
    query_obj = call_args[0][0]
    assert "doc\\-b" in query_obj.query_string()  # UUID dashes are escaped in tag filter
    assert result is None


# retrieve_with_hyde

def test_retrieve_with_hyde_skips_hyde_when_confident():
    from rag.chains.retrieval import retrieve_with_hyde

    docs = [_doc()]

    # rerank_with_score is imported inside retrieve_with_hyde, so patch the source module
    with patch("rag.chains.retrieval.hybrid_search", return_value=docs), \
         patch("rag.chains.rerank.rerank_with_score", return_value=(docs, 0.8)), \
         patch("rag.chains.retrieval._hyde_dense_search") as mock_hyde, \
         patch.dict("os.environ", {"HYDE_THRESHOLD": "0.3"}):
        result, hyde_triggered = retrieve_with_hyde("test_doc", "what is attention?")

    mock_hyde.assert_not_called()
    assert result == docs
    assert hyde_triggered is False


def test_retrieve_with_hyde_triggers_when_low_confidence():
    from rag.chains.retrieval import retrieve_with_hyde

    original = [_doc("original", "orig")]
    hyde_results = [_doc("hypothetical", "hyde")]
    reranked = [_doc("merged", "merged")]

    rerank_calls = {"n": 0}

    def fake_rerank(query, docs, top_k=5):
        rerank_calls["n"] += 1
        if rerank_calls["n"] == 1:
            return original, 0.1  # low score → HyDE fires
        return reranked, 0.7

    with patch("rag.chains.retrieval.hybrid_search", return_value=original), \
         patch("rag.chains.rerank.rerank_with_score", side_effect=fake_rerank), \
         patch("rag.chains.retrieval._hyde_dense_search", return_value=hyde_results), \
         patch("rag.chains.retrieval._rrf_merge", return_value=reranked), \
         patch.dict("os.environ", {"HYDE_THRESHOLD": "0.3"}):
        result, hyde_triggered = retrieve_with_hyde("test_doc", "obscure query")

    assert result == reranked
    assert hyde_triggered is True
    assert rerank_calls["n"] == 2  # called once before HyDE, once after


def test_retrieve_with_hyde_returns_empty_when_no_candidates():
    from rag.chains.retrieval import retrieve_with_hyde

    with patch("rag.chains.retrieval.hybrid_search", return_value=[]):
        docs, hyde_triggered = retrieve_with_hyde("test_doc", "query")
    assert docs == []
    assert hyde_triggered is False


# /query from_cache field

def test_query_response_includes_from_cache_false(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir(parents=True)
    doc_id = "somedoc"
    (pdf_dir / f"{doc_id}.pdf").write_bytes(b"placeholder")

    from fastapi.testclient import TestClient
    from app.main import app

    with patch("app.main.semantic_cache.lookup", return_value=None), \
         patch("app.main.run_agent", return_value={
             "generation": "an answer", "documents": [], "retry_count": 0, "hyde_triggered": False
         }):
        client = TestClient(app)
        r = client.post("/query", json={"doc_id": doc_id, "question": "What is this?"})

    assert r.status_code == 200
    data = r.json()
    assert data["from_cache"] is False
    assert data["hyde_triggered"] is False


def test_query_returns_from_cache_true_on_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir(parents=True)
    doc_id = "somedoc"
    (pdf_dir / f"{doc_id}.pdf").write_bytes(b"placeholder")

    cached_payload = {
        "answer": "cached answer text",
        "citations": [{"ref": "r1", "page": 1, "chunk_id": 0, "source": "f.pdf"}],
    }

    from fastapi.testclient import TestClient
    from app.main import app

    with patch("app.main.semantic_cache.lookup", return_value=cached_payload):
        client = TestClient(app)
        r = client.post("/query", json={"doc_id": doc_id, "question": "What is this document about?"})

    assert r.status_code == 200
    data = r.json()
    assert data["from_cache"] is True
    assert data["answer"] == "cached answer text"
    assert data["retrieved"] == 1
