from __future__ import annotations

import logging
import os
import warnings

os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("unstructured").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*max_size.*", category=FutureWarning)

import json
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from langchain_core.documents import Document

from rag.agents.graph import run_agent
from rag import cache as semantic_cache
from rag.ingest import index_document
from rag.llm import get_embeddings, get_llm
import shutil
from pathlib import Path
from app.storage import delete_document, list_docs, mark_doc_indexed, new_doc_id, pdf_path, save_document_record
from rag.store import clear_document, get_chroma_dir

APP_ENV = os.getenv("ENVIRONMENT", "local")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_embeddings()
    try:
        get_llm()
    except RuntimeError:
        pass  # GOOGLE_API_KEY not set; LLM will fail at query time
    yield


app = FastAPI(title="DocuMind", lifespan=lifespan)

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str = APP_ENV


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    stored_path: str


class IndexResponse(BaseModel):
    doc_id: str
    chunks_indexed: int
    collection: str


class QueryRequest(BaseModel):
    doc_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=2)
    top_k: int = Field(5, ge=1, le=20)
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation memory")


class Citation(BaseModel):
    ref: str
    page: int
    chunk_id: int
    source: str


class QueryResponse(BaseModel):
    doc_id: str
    question: str
    answer: str
    citations: List[Citation]
    retrieved: int
    retries: int
    latency_ms: float
    from_cache: bool = False
    hyde_triggered: bool = False


class DocRecord(BaseModel):
    doc_id: str
    filename: str
    uploaded_at: str
    indexed: bool
    index_time_s: Optional[float] = None


@app.get("/documents", response_model=List[DocRecord])
def list_documents() -> List[DocRecord]:
    return [DocRecord(**d) for d in list_docs()]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/documents", response_model=UploadResponse)
def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    doc_id = new_doc_id()
    out_path = pdf_path(doc_id)

    content = file.file.read()
    out_path.write_bytes(content)
    save_document_record(doc_id, file.filename)

    return UploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        stored_path=str(out_path),
    )


@app.post("/documents/{doc_id}/index", response_model=IndexResponse)
def index(doc_id: str) -> IndexResponse:
    path = pdf_path(doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")

    t0 = time.perf_counter()
    chunks_indexed, collection_name = index_document(doc_id)
    index_time_s = time.perf_counter() - t0
    mark_doc_indexed(doc_id, index_time_s=index_time_s)

    return IndexResponse(
        doc_id=doc_id,
        chunks_indexed=chunks_indexed,
        collection=collection_name,
    )


@app.delete("/documents/{doc_id}", status_code=204)
def delete_doc(doc_id: str) -> None:
    path = pdf_path(doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")
    delete_document(doc_id)
    clear_document(doc_id)
    bm25_path = Path(get_chroma_dir()) / f"bm25_{doc_id}.pkl"
    if bm25_path.exists():
        bm25_path.unlink()
    figures_dir = Path("data") / "figures" / doc_id
    if figures_dir.exists():
        shutil.rmtree(figures_dir)


@app.post("/documents/{doc_id}/index/stream")
async def index_stream(doc_id: str) -> StreamingResponse:
    path = pdf_path(doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")

    async def event_stream() -> AsyncIterator[str]:
        import asyncio

        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def on_progress(msg: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ("status", msg))

        t0 = time.perf_counter()
        future = loop.run_in_executor(None, lambda: index_document(doc_id, on_progress))
        yield _sse("status", "Starting…")

        while not future.done():
            try:
                event, data = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield _sse(event, data)
            except asyncio.TimeoutError:
                pass

        while not queue.empty():
            event, data = queue.get_nowait()
            yield _sse(event, data)

        try:
            chunks_indexed, _ = await future
        except Exception as e:
            yield _sse("error", str(e))
            return

        index_time_s = time.perf_counter() - t0
        mark_doc_indexed(doc_id, index_time_s=index_time_s)
        yield _sse("done", json.dumps({"chunks": chunks_indexed, "index_time_s": round(index_time_s, 1)}))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/documents/{doc_id}/file")
def get_document_file(doc_id: str) -> FileResponse:
    path = pdf_path(doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    t0 = time.perf_counter()

    path = pdf_path(req.doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")

    cached = semantic_cache.lookup(req.question, req.doc_id)
    if cached:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        raw_citations = cached.get("citations", [])
        citations = [
            Citation(
                ref=c.get("ref", ""),
                page=c.get("page", -1),
                chunk_id=c.get("chunk_id", -1),
                source=c.get("source", ""),
            )
            for c in raw_citations
        ]
        return QueryResponse(
            doc_id=req.doc_id,
            question=req.question,
            answer=cached["answer"],
            citations=citations,
            retrieved=len(citations),
            retries=0,
            latency_ms=round(latency_ms, 2),
            from_cache=True,
        )

    state = run_agent(
        question=req.question,
        doc_id=req.doc_id,
        session_id=req.session_id or "",
    )

    answer = state.get("generation", "")
    docs: List[Document] = state.get("documents", [])

    if not answer and not docs:
        raise HTTPException(status_code=404, detail="Document not indexed.")

    citations = (
        []
        if _is_no_answer(answer)
        else [
            Citation(
                ref=doc.metadata.get("ref", ""),
                page=doc.metadata.get("page", -1),
                chunk_id=doc.metadata.get("chunk_id", -1),
                source=doc.metadata.get("source", ""),
            )
            for doc in docs
        ]
    )

    latency_ms = (time.perf_counter() - t0) * 1000.0

    if answer and not _is_no_answer(answer):
        semantic_cache.store(
            req.question,
            req.doc_id,
            answer,
            [c.model_dump() for c in citations],
        )

    return QueryResponse(
        doc_id=req.doc_id,
        question=req.question,
        answer=answer,
        citations=citations,
        retrieved=len(docs),
        retries=state.get("retry_count", 0),
        latency_ms=round(latency_ms, 2),
        hyde_triggered=state.get("hyde_triggered", False),
    )


class StreamQueryRequest(BaseModel):
    doc_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=2)
    session_id: Optional[str] = Field(None)


@app.post("/query/stream")
async def query_stream(req: StreamQueryRequest) -> StreamingResponse:
    path = pdf_path(req.doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")

    async def event_stream() -> AsyncIterator[str]:
        try:
            import asyncio

            cached = semantic_cache.lookup(req.question, req.doc_id)
            if cached:
                yield _sse("status", "Cache hit — returning cached answer…")
                answer: str = cached["answer"]
                words = answer.split(" ")
                for i, word in enumerate(words):
                    token = word if i == 0 else " " + word
                    yield _sse("token", token)
                    await asyncio.sleep(0.005)
                yield _sse("citations", json.dumps(cached.get("citations", [])))
                yield _sse("done", "")
                return

            loop = asyncio.get_event_loop()
            queue: asyncio.Queue[str] = asyncio.Queue()

            def on_step(label: str) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, label)

            future = loop.run_in_executor(
                None,
                lambda: run_agent(
                    question=req.question,
                    doc_id=req.doc_id,
                    session_id=req.session_id or "",
                    on_step=on_step,
                ),
            )

            # Drain real step labels from the queue while the agent runs
            while not future.done():
                try:
                    label = await asyncio.wait_for(queue.get(), timeout=0.3)
                    yield _sse("status", label)
                except asyncio.TimeoutError:
                    pass
            # Drain any remaining steps that arrived after future completed
            while not queue.empty():
                yield _sse("status", queue.get_nowait())

            state = await future

            answer = state.get("generation", "")
            docs: List[Document] = state.get("documents", [])

            if not answer and not docs:
                yield _sse("error", "Document not indexed.")
                return

            if not answer:
                yield _sse("error", "Could not generate an answer. Try rephrasing your question.")
                return

            # Stream the answer word by word
            words = answer.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else " " + word
                yield _sse("token", token)
                await asyncio.sleep(0.005)

            citations_data = (
                []
                if _is_no_answer(answer)
                else [
                    {
                        "ref": d.metadata.get("ref", ""),
                        "page": d.metadata.get("page", -1),
                        "chunk_id": d.metadata.get("chunk_id", -1),
                        "source": d.metadata.get("source", ""),
                        "text": d.page_content[:200],
                    }
                    for d in docs
                ]
            )
            yield _sse("citations", json.dumps(citations_data))
            yield _sse("meta", json.dumps({"hyde_triggered": state.get("hyde_triggered", False)}))
            yield _sse("done", "")

            if answer and not _is_no_answer(answer):
                semantic_cache.store(req.question, req.doc_id, answer, citations_data)

        except Exception as e:
            yield _sse("error", str(e))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


_NO_ANSWER_PREFIXES = (
    "i do not know",
    "i don't know",
    "i cannot find",
    "i can't find",
    "no information",
    "not mentioned",
    "not found",
    "not provided",
    "not available in",
    "based on the provided document, i",
    "based on the provided context, i",
)


def _is_no_answer(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(p) for p in _NO_ANSWER_PREFIXES)


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"
