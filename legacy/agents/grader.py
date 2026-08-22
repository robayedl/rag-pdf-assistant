"""Superseded by the researcher/critic agents in rag/agents/. Kept for reference."""
from __future__ import annotations

import json
import logging
from typing import List

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig, RunnableLambda

from rag.agents.state import GraphState
from rag.llm import get_llm

logger = logging.getLogger(__name__)

_GRADER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a relevance grader. Given a user question and a numbered list of document chunks, "
            "return a JSON array of 'yes' or 'no' for each chunk.\n"
            "Mark 'yes' if the chunk:\n"
            "- Directly answers the question, OR\n"
            "- Contains evidence, definitions, or values the question refers to, OR\n"
            "- Provides context that helps reason toward the answer.\n"
            "Only mark 'no' if the chunk is entirely unrelated to the question's topic.\n"
            "When in doubt, mark 'yes', it is better to keep a loosely relevant chunk than to discard it.\n"
            "Example output for 3 chunks: [\"yes\", \"no\", \"yes\"]\n"
            "Return only the JSON array, nothing else.",
        ),
        (
            "human",
            "Question: {question}\n\nDocuments:\n{documents}",
        ),
    ]
)


def grade_documents(state: GraphState, config: RunnableConfig = {}) -> GraphState:
    """Filter retrieved documents to only those relevant to the question (single LLM call)."""
    documents: List[Document] = state.get("documents", [])
    if not documents:
        return {"documents": []}

    try:
        from rag.usage import capture_from_message
        llm = get_llm()
        chain = _GRADER_PROMPT | llm | RunnableLambda(capture_from_message) | StrOutputParser()

        numbered = "\n\n".join(
            f"[{i+1}] {doc.page_content}" for i, doc in enumerate(documents)
        )
        invoke_input = {"question": state["question"], "documents": numbered}
        raw = chain.invoke(invoke_input, config=config)

        try:
            scores: List[str] = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            scores = ["yes"] * len(documents)

        relevant_docs = [
            doc for doc, score in zip(documents, scores)
            if str(score).strip().lower() == "yes"
        ]
        return {"documents": relevant_docs}

    except Exception as e:
        logger.error(f"Grader failed, keeping all documents: {e}")
        return {"documents": documents}
