from __future__ import annotations

import logging
from functools import lru_cache
from typing import Callable, Literal

from langgraph.graph import END, StateGraph

from rag.agents.generator import generate
from rag.agents.grader import grade_documents
from rag.agents.hallucination import check_hallucination
from rag.agents.rewriter import rewrite_query
from rag.agents.state import GraphState
from rag.chains.retrieval import retrieve_with_hyde
from rag.usage import TokenUsageCallback

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


# Node functions

def retrieve(state: GraphState) -> GraphState:
    """Hybrid search + reranking with HyDE fallback on low-confidence results."""
    try:
        top_k = state.get("top_k", 6)
        docs, hyde_triggered = retrieve_with_hyde(doc_id=state["doc_id"], query=state["question"], top_k=top_k)
        if not docs and state["retry_count"] == 0:
            return {
                "documents": [],
                "hyde_triggered": False,
                "error": (
                    "No documents have been indexed for this document. "
                    "Please index the document first."
                ),
            }
        return {"documents": docs, "hyde_triggered": hyde_triggered}
    except Exception as e:
        logger.error(f"Retrieve failed: {e}")
        return {"documents": [], "hyde_triggered": False, "error": str(e)}


def fallback(state: GraphState) -> GraphState:
    """Return a fallback message; use error details if available."""
    error = state.get("error", "")
    if error:
        return {"generation": error}
    return {"generation": "I do not know based on the provided document."}


# Conditional edge functions

def decide_after_grading(
    state: GraphState,
) -> Literal["generate", "rewrite_query", "fallback"]:
    if state.get("error"):
        return "fallback"
    if state["documents"]:
        return "generate"
    if state["retry_count"] < MAX_RETRIES:
        return "rewrite_query"
    return "fallback"


def decide_after_hallucination(
    state: GraphState,
) -> Literal["__end__", "generate", "fallback"]:
    if state["grounded"]:
        return END
    if state["retry_count"] < MAX_RETRIES:
        return "generate"
    return "fallback"


# Graph builder

@lru_cache(maxsize=1)
def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_documents", grade_documents)
    graph.add_node("generate", generate)
    graph.add_node("check_hallucination", check_hallucination)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("fallback", fallback)

    graph.set_entry_point("retrieve")

    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges(
        "grade_documents",
        decide_after_grading,
        {"generate": "generate", "rewrite_query": "rewrite_query", "fallback": "fallback"},
    )
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("generate", "check_hallucination")
    graph.add_conditional_edges(
        "check_hallucination",
        decide_after_hallucination,
        {END: END, "generate": "generate", "fallback": "fallback"},
    )
    graph.add_edge("fallback", END)

    return graph.compile()


# Public entry point

_NODE_LABELS: dict[str, str] = {
    "retrieve":            "Searching the document…",
    "grade_documents":     "Reading relevant sections…",
    "rewrite_query":       "Refining search query…",
    "generate":            "Generating answer…",
    "check_hallucination": "Verifying accuracy…",
    "fallback":            "Preparing response…",
}


def run_agent(
    question: str,
    doc_id: str,
    session_id: str = "",
    on_step: Callable[[str], None] | None = None,
    top_k: int = 6,
) -> tuple[GraphState, TokenUsageCallback]:
    """Run the agentic RAG graph, calling on_step(label) as each node completes.

    Returns (state, usage) where usage.tokens_in / tokens_out are totals across all LLM calls.
    """
    graph = build_graph()
    usage = TokenUsageCallback()
    usage.activate()
    try:
        init: GraphState = {
            "question": question,
            "generation": "",
            "documents": [],
            "doc_id": doc_id,
            "retry_count": 0,
            "grounded": False,
            "error": "",
            "session_id": session_id,
            "hyde_triggered": False,
            "top_k": top_k,
        }

        if on_step is None:
            result = graph.invoke(init)
            return result, usage

        final: GraphState = init
        for chunk in graph.stream(init, stream_mode="updates"):
            for node_name in chunk:
                label = _NODE_LABELS.get(node_name, f"{node_name}…")
                on_step(label)
                final = {**final, **chunk[node_name]}
        return final, usage
    finally:
        usage.deactivate()
