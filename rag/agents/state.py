from __future__ import annotations

from typing import List
from typing_extensions import TypedDict

from langchain_core.documents import Document


class GraphState(TypedDict):
    question: str              # the user's question (may be rewritten)
    generation: str            # the LLM's generated answer
    documents: List[Document]  # retrieved (and graded) documents
    doc_id: str                # which PDF to query
    retry_count: int           # prevents infinite loops (max 3)
    route: str                 # "retrieve" or "direct"
    grounded: bool             # whether the generation is supported by documents
    error: str                 # set when a node fails or doc is not indexed
    session_id: str            # for conversation memory (empty string = no memory)
    hyde_triggered: bool       # whether HyDE fired during retrieval
    top_k: int                 # number of chunks to retrieve after reranking
