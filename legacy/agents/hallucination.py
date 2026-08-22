"""Superseded by the critic agent in rag/agents/. Kept for reference."""
from __future__ import annotations

import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig, RunnableLambda

from pydantic import BaseModel, Field
from typing import Literal

from rag.agents.state import GraphState
from rag.llm import get_llm

logger = logging.getLogger(__name__)


class GroundednessScore(BaseModel):
    """Kept for backward compatibility with tests."""
    grounded: Literal["yes", "no"] = Field(default="yes")

_HALLUCINATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a factual grounding checker. Given source documents and a generated answer, "
            "decide if the substantive factual claims in the answer are supported by the documents.\n"
            "Focus on names, numbers, descriptions, and conclusions, not on metadata like figure "
            "numbers or table labels that the user mentioned in their question.\n"
            "Answer 'yes' if the answer's factual content is grounded in the documents, or if "
            "the answer is a refusal ('I do not know').\n"
            "Answer 'no' only if the answer asserts specific facts that contradict or are absent "
            "from the documents.\n"
            "Reply with a single word: yes or no.",
        ),
        (
            "human",
            "Source documents:\n{context}\n\nGenerated answer:\n{generation}",
        ),
    ]
)


def check_hallucination(state: GraphState, config: RunnableConfig = {}) -> GraphState:
    """Verify the generated answer is supported by the retrieved documents."""
    try:
        from rag.usage import capture_from_message
        llm = get_llm()
        chain = _HALLUCINATION_PROMPT | llm | RunnableLambda(capture_from_message) | StrOutputParser()

        context = "\n\n".join(
            doc.metadata.get("original_content") or doc.page_content
            for doc in state["documents"]
        )
        invoke_input = {"context": context, "generation": state["generation"]}
        raw: str = chain.invoke(invoke_input, config=config)

        grounded = "no" not in raw.strip().lower()[:10]
        if grounded:
            return {"grounded": True}

        return {
            "grounded": False,
            "generation": "",
            "retry_count": state["retry_count"] + 1,
        }

    except Exception as e:
        logger.error(f"Hallucination check failed, assuming grounded: {e}")
        return {"grounded": True}
