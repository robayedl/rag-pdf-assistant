from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig

from rag.agents.state import GraphState
from rag.chains.generation import get_rag_chain

logger = logging.getLogger(__name__)


def generate(state: GraphState, config: RunnableConfig = {}) -> GraphState:
    """Generate an answer from graded documents using the RAG chain."""
    try:
        session_id = state.get("session_id", "")
        chat_history = []

        if session_id:
            from rag.agents.memory import get_memory
            chat_history = get_memory(session_id).messages[-6:]  # last 3 exchanges

        chain = get_rag_chain()
        invoke_kwargs = {"input": state["question"], "context": state["documents"], "chat_history": chat_history}
        answer = chain.invoke(invoke_kwargs, config=config)

        # Save question + answer to memory for follow-up questions
        if session_id and answer:
            from rag.agents.memory import get_memory
            mem = get_memory(session_id)
            mem.add_user_message(state["question"])
            mem.add_ai_message(answer)

        return {"generation": answer}

    except Exception as e:
        logger.error(f"Generator failed, falling back to raw chunks: {e}")
        raw = "\n\n".join(
            (doc.metadata.get("original_content") or doc.page_content)[:300]
            for doc in state.get("documents", [])
        )
        fallback = (
            f"Answer generation failed due to an API error. "
            f"Here are the relevant excerpts from the document:\n\n{raw}"
            if raw else "Answer generation failed and no relevant content was found."
        )
        # Mark as grounded to avoid retry loop
        return {"generation": fallback, "grounded": True}
