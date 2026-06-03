from __future__ import annotations

import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig, RunnableLambda

from rag.agents.state import GraphState
from rag.llm import get_llm

logger = logging.getLogger(__name__)

_REWRITER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a query rewriter. The retrieved documents were not relevant to the user's question. "
            "Fix any spelling or typos, then rewrite the question to be more specific and better suited "
            "for document search. Return only the rewritten question, nothing else.",
        ),
        ("human", "Original question: {question}"),
    ]
)


def rewrite_query(state: GraphState, config: RunnableConfig = {}) -> GraphState:
    """Rewrite the question for better retrieval and increment the retry counter."""
    try:
        from rag.usage import capture_from_message
        llm = get_llm()
        chain = _REWRITER_PROMPT | llm | RunnableLambda(capture_from_message) | StrOutputParser()
        invoke_input = {"question": state["question"]}
        rewritten = chain.invoke(invoke_input, config=config)
        return {
            "question": rewritten.strip(),
            "retry_count": state["retry_count"] + 1,
        }
    except Exception as e:
        logger.error(f"Query rewriter failed, keeping original question: {e}")
        return {"retry_count": state["retry_count"] + 1}
