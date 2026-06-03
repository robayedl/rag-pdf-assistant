from __future__ import annotations

from functools import lru_cache
from typing import List

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda

from rag.llm import get_llm

_SYSTEM_PROMPT = (
    "You are a precise, helpful assistant that answers questions strictly based on "
    "the provided context extracted from a PDF document.\n\n"
    "Rules:\n"
    "- Answer ONLY using information present in the context below.\n"
    "- Cite the relevant parts of the context by quoting or referencing them directly.\n"
    "- When the context contains labels, names, or terms that directly address the "
    "substance of the question, use them to answer. Do not refuse just because a "
    "secondary detail (e.g. exact figure number, table position) is not explicitly "
    "confirmed; answer from what IS in the context.\n"
    "- If the context genuinely contains no information relevant to the question, "
    "respond with: 'I do not know based on the provided document.'\n"
    "- Do not speculate or add information beyond what is in the context.\n"
    "- Respond in plain text only. Do not use markdown, bullet points, bold, or any special formatting.\n\n"
    "Context:\n{context}"
)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
    ]
)


def _doc_text(doc: Document) -> str:
    return doc.metadata.get("original_content") or doc.page_content


def _format_inputs(inputs: dict) -> dict:
    """Convert Document list to a plain string and pass through chat history."""
    docs: List[Document] = inputs["context"]
    formatted = "\n\n".join(_doc_text(doc) for doc in docs)
    return {
        "context": formatted,
        "input": inputs["input"],
        "chat_history": inputs.get("chat_history", []),
    }


@lru_cache(maxsize=1)
def get_rag_chain():
    from rag.usage import capture_from_message
    llm = get_llm()
    return RunnableLambda(_format_inputs) | _PROMPT | llm | RunnableLambda(capture_from_message) | StrOutputParser()
