from __future__ import annotations

import logging
import os
import warnings

os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
logging.getLogger("unstructured").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", message=".*max_size.*", category=FutureWarning)

import json
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.documents import Document

from sqlalchemy import text

import redis as _redis_mod

from app.auth import ClerkUser, current_user
from app.db import engine, get_db
from app.models import Base, Document as DocModel, User
from app.storage import delete_pdf, get_storage_root, new_doc_id, pdf_path, save_pdf
from rag import cache as semantic_cache
from rag.agents.graph import run_agent
from rag.ingest import index_document
from rag.llm import get_embeddings, get_llm
from rag.store import clear_document

APP_ENV = os.getenv("ENVIRONMENT", "local")

_redis_client = _redis_mod.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
)


def _get_progress(doc_id: str) -> int:
    val = _redis_client.get(f"doc:{doc_id}:progress")
    return int(val) if val else 0


def _get_step(doc_id: str) -> str | None:
    return _redis_client.get(f"doc:{doc_id}:step")


async def _init_db() -> None:
    """Create all tables and extensions on first run (idempotent)."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chunks (
                id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                doc_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                ref      TEXT NOT NULL,
                content  TEXT NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}',
                embedding vector(768),
                tsv      tsvector
            )
        """))
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS chunks_ref_idx ON chunks (ref)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS chunks_doc_id_idx ON chunks (doc_id)"
        ))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
                ON chunks USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS chunks_tsv_gin_idx ON chunks USING GIN (tsv)"
        ))
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION chunks_tsv_update() RETURNS trigger
                LANGUAGE plpgsql AS $$
            BEGIN
                NEW.tsv := to_tsvector('english', COALESCE(NEW.content, ''));
                RETURN NEW;
            END;
            $$
        """))
        await conn.execute(text(
            "DROP TRIGGER IF EXISTS chunks_tsv_trigger ON chunks"
        ))
        await conn.execute(text("""
            CREATE TRIGGER chunks_tsv_trigger
                BEFORE INSERT OR UPDATE OF content ON chunks
                FOR EACH ROW EXECUTE FUNCTION chunks_tsv_update()
        """))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_db()
    get_embeddings()
    try:
        get_llm()
    except RuntimeError:
        pass
    yield


app = FastAPI(title="DocuMind", lifespan=lifespan)

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _ensure_user(db: AsyncSession, user: ClerkUser) -> None:
    """Upsert the Clerk user into the users table on every authenticated request."""
    stmt = (
        pg_insert(User)
        .values(clerk_id=user.user_id, email=user.email)
        .on_conflict_do_nothing(index_elements=["clerk_id"])
    )
    await db.execute(stmt)
    await db.commit()


async def _get_doc_or_404(
    db: AsyncSession, doc_id: str, user_id: str
) -> DocModel:
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found.")
    result = await db.execute(
        select(DocModel).where(
            DocModel.id == doc_uuid,
            DocModel.user_id == user_id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None or not pdf_path(doc_id).exists():
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str = APP_ENV


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    status: str = "pending"


class IndexResponse(BaseModel):
    doc_id: str
    chunks_indexed: int
    collection: str


class QueryRequest(BaseModel):
    doc_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=2)
    top_k: int = Field(5, ge=1, le=20)
    session_id: Optional[str] = Field(None)


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
    status: str
    indexed: bool
    index_time_s: Optional[float] = None
    page_count: Optional[int] = None
    progress_percent: int = 0
    step: Optional[str] = None


class DocStatusResponse(BaseModel):
    status: str
    progress_percent: int
    page_count: Optional[int] = None
    step: Optional[str] = None


class StreamQueryRequest(BaseModel):
    doc_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=2)
    session_id: Optional[str] = Field(None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/documents", response_model=List[DocRecord])
async def list_documents(
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DocRecord]:
    await _ensure_user(db, user)
    result = await db.execute(
        select(DocModel)
        .where(DocModel.user_id == user.user_id)
        .order_by(DocModel.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        DocRecord(
            doc_id=str(doc.id),
            filename=doc.filename,
            uploaded_at=doc.created_at.isoformat(),
            status=doc.status,
            indexed=doc.status == "indexed",
            index_time_s=doc.index_time_s,
            page_count=doc.page_count,
            progress_percent=(
                _get_progress(str(doc.id)) if doc.status == "processing"
                else (100 if doc.status == "indexed" else 0)
            ),
            step=(
                _get_step(str(doc.id)) if doc.status == "processing" else None
            ),
        )
        for doc in docs
    ]


@app.post("/documents", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    await _ensure_user(db, user)

    doc_id = new_doc_id()
    out_path = pdf_path(doc_id)
    content = await file.read()
    save_pdf(out_path, content)

    doc = DocModel(
        id=uuid.UUID(doc_id),
        user_id=user.user_id,
        filename=file.filename,
        status="pending",
    )
    db.add(doc)
    await db.commit()

    from worker.tasks import ingest_document as _enqueue_ingest
    task = _enqueue_ingest.delay(doc_id)
    doc.celery_task_id = task.id
    await db.commit()

    return UploadResponse(doc_id=doc_id, filename=file.filename, status="pending")


@app.post("/documents/{doc_id}/index", response_model=IndexResponse)
async def index(
    doc_id: str,
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> IndexResponse:
    await _ensure_user(db, user)
    doc = await _get_doc_or_404(db, doc_id, user.user_id)

    t0 = time.perf_counter()
    chunks_indexed, collection_name, page_count = index_document(doc_id)
    index_time_s = time.perf_counter() - t0

    doc.status = "indexed"
    doc.index_time_s = round(index_time_s, 1)
    doc.page_count = page_count
    await db.commit()

    return IndexResponse(
        doc_id=doc_id,
        chunks_indexed=chunks_indexed,
        collection=collection_name,
    )


@app.post("/documents/{doc_id}/index/stream")
async def index_stream(
    doc_id: str,
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await _ensure_user(db, user)
    doc = await _get_doc_or_404(db, doc_id, user.user_id)

    async def event_stream() -> AsyncIterator[str]:
        import asyncio
        from app.db import async_session_factory

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
            chunks_indexed, _, page_count = await future
        except Exception as e:
            yield _sse("error", str(e))
            return

        index_time_s = time.perf_counter() - t0

        # Update status in DB using a fresh session (we can't reuse the request session across threads)
        async with async_session_factory() as sess:
            result = await sess.execute(select(DocModel).where(DocModel.id == doc.id))
            d = result.scalar_one_or_none()
            if d:
                d.status = "indexed"
                d.index_time_s = round(index_time_s, 1)
                d.page_count = page_count
                await sess.commit()

        yield _sse("done", json.dumps({"chunks": chunks_indexed, "index_time_s": round(index_time_s, 1)}))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/documents/{doc_id}/status", response_model=DocStatusResponse)
async def get_document_status(
    doc_id: str,
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> DocStatusResponse:
    await _ensure_user(db, user)
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found.")
    result = await db.execute(
        select(DocModel).where(DocModel.id == doc_uuid, DocModel.user_id == user.user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.status == "processing":
        progress = _get_progress(doc_id)
        step = _get_step(doc_id)
    elif doc.status == "indexed":
        progress = 100
        step = None
    else:
        progress = 0
        step = None

    return DocStatusResponse(
        status=doc.status,
        progress_percent=progress,
        page_count=doc.page_count,
        step=step,
    )


@app.post("/documents/{doc_id}/stop", status_code=200)
async def stop_document(
    doc_id: str,
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _ensure_user(db, user)
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found.")
    result = await db.execute(
        select(DocModel).where(DocModel.id == doc_uuid, DocModel.user_id == user.user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.status not in ("pending", "processing"):
        raise HTTPException(status_code=400, detail="Document is not active.")

    if doc.celery_task_id:
        from worker.celery_app import celery_app as _celery
        try:
            _celery.control.revoke(doc.celery_task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass

    doc.status = "stopped"
    await db.commit()
    return {"status": "stopped"}


@app.post("/documents/{doc_id}/reindex", status_code=200)
async def reindex_document(
    doc_id: str,
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _ensure_user(db, user)
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found.")
    result = await db.execute(
        select(DocModel).where(DocModel.id == doc_uuid, DocModel.user_id == user.user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not pdf_path(doc_id).exists():
        raise HTTPException(status_code=404, detail="Document file not found.")

    doc.status = "pending"
    doc.error_message = None
    await db.commit()

    from worker.tasks import ingest_document as _enqueue_ingest
    task = _enqueue_ingest.delay(doc_id)
    doc.celery_task_id = task.id
    await db.commit()

    return {"status": "pending", "doc_id": doc_id}


@app.delete("/documents/{doc_id}", status_code=204)
async def delete_doc(
    doc_id: str,
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _ensure_user(db, user)
    doc = await _get_doc_or_404(db, doc_id, user.user_id)

    # Remove PDF from disk
    delete_pdf(doc_id)
    # Remove chunks from pgvector
    clear_document(doc_id)
    # Remove extracted figures
    figures_dir = get_storage_root() / "figures" / doc_id
    if figures_dir.exists():
        shutil.rmtree(figures_dir)
    # Remove DB record (cascades to chunks via FK)
    await db.execute(delete(DocModel).where(DocModel.id == doc.id))
    await db.commit()


@app.get("/documents/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    await _ensure_user(db, user)
    await _get_doc_or_404(db, doc_id, user.user_id)
    path = pdf_path(doc_id)
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    await _ensure_user(db, user)
    await _get_doc_or_404(db, req.doc_id, user.user_id)

    t0 = time.perf_counter()
    cached = semantic_cache.lookup(req.question, req.doc_id)
    if cached:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        raw = cached.get("citations", [])
        citations = [
            Citation(ref=c.get("ref", ""), page=c.get("page", -1),
                     chunk_id=c.get("chunk_id", -1), source=c.get("source", ""))
            for c in raw
        ]
        return QueryResponse(
            doc_id=req.doc_id, question=req.question, answer=cached["answer"],
            citations=citations, retrieved=len(citations), retries=0,
            latency_ms=round(latency_ms, 2), from_cache=True,
        )

    state = run_agent(question=req.question, doc_id=req.doc_id, session_id=req.session_id or "")
    answer = state.get("generation", "")
    docs: List[Document] = state.get("documents", [])

    if not answer and not docs:
        raise HTTPException(status_code=404, detail="Document not indexed.")

    citations = (
        []
        if _is_no_answer(answer)
        else [
            Citation(ref=d.metadata.get("ref", ""), page=d.metadata.get("page", -1),
                     chunk_id=d.metadata.get("chunk_id", -1), source=d.metadata.get("source", ""))
            for d in docs
        ]
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0

    if answer and not _is_no_answer(answer):
        semantic_cache.store(req.question, req.doc_id, answer, [c.model_dump() for c in citations])

    return QueryResponse(
        doc_id=req.doc_id, question=req.question, answer=answer,
        citations=citations, retrieved=len(docs), retries=state.get("retry_count", 0),
        latency_ms=round(latency_ms, 2), hyde_triggered=state.get("hyde_triggered", False),
    )


@app.post("/query/stream")
async def query_stream(
    req: StreamQueryRequest,
    user: ClerkUser = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await _ensure_user(db, user)
    await _get_doc_or_404(db, req.doc_id, user.user_id)

    async def event_stream() -> AsyncIterator[str]:
        try:
            import asyncio

            cached = semantic_cache.lookup(req.question, req.doc_id)
            if cached:
                yield _sse("status", "Cache hit — returning cached answer…")
                answer: str = cached["answer"]
                for i, word in enumerate(answer.split(" ")):
                    yield _sse("token", word if i == 0 else " " + word)
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

            while not future.done():
                try:
                    label = await asyncio.wait_for(queue.get(), timeout=0.3)
                    yield _sse("status", label)
                except asyncio.TimeoutError:
                    pass
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

            for i, word in enumerate(answer.split(" ")):
                yield _sse("token", word if i == 0 else " " + word)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NO_ANSWER_PREFIXES = (
    "i do not know", "i don't know", "i cannot find", "i can't find",
    "no information", "not mentioned", "not found", "not provided",
    "not available in", "based on the provided document, i",
    "based on the provided context, i",
)


def _is_no_answer(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(p) for p in _NO_ANSWER_PREFIXES)


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"
