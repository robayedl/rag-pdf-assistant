from __future__ import annotations

import os
import time
import uuid

import redis as _redis
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from worker.celery_app import celery_app

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = _redis.from_url(_REDIS_URL, decode_responses=True)

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://documind:documind@localhost:5432/documind"
).replace("postgresql+asyncpg://", "postgresql://")

_engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
_Session = sessionmaker(bind=_engine)

_TTL = 86400  # 24 h


def _set_progress(doc_id: str, pct: int) -> None:
    _redis_client.setex(f"doc:{doc_id}:progress", _TTL, str(pct))


def _set_step(doc_id: str, step: str) -> None:
    _redis_client.setex(f"doc:{doc_id}:step", _TTL, step)


def _clear_progress(doc_id: str) -> None:
    _redis_client.delete(f"doc:{doc_id}:progress")


def _clear_step(doc_id: str) -> None:
    _redis_client.delete(f"doc:{doc_id}:step")


@celery_app.task(bind=True, name="worker.tasks.ingest_document")
def ingest_document(self, doc_id: str) -> dict:
    from app.models import Document
    from rag.ingest import index_document

    _set_progress(doc_id, 0)
    _set_step(doc_id, "Starting")

    with _Session() as db:
        doc = db.get(Document, uuid.UUID(doc_id))
        if doc is None:
            return {"error": "document not found"}
        if doc.status == "stopped":
            return {"error": "task was stopped"}
        doc.status = "processing"
        db.commit()

    _set_progress(doc_id, 5)
    _set_step(doc_id, "Parsing PDF")

    try:
        def on_progress(msg: str) -> None:
            lower = msg.lower()
            if "parsing" in lower:
                _set_progress(doc_id, 15)
                _set_step(doc_id, "Parsing PDF")
            elif "elements" in lower:
                _set_progress(doc_id, 45)
                _set_step(doc_id, "Extracting")
            elif "chunks" in lower or "generating" in lower or "embedding" in lower:
                _set_progress(doc_id, 75)
                _set_step(doc_id, "Embedding")

        t0 = time.perf_counter()
        chunks_indexed, _, page_count = index_document(doc_id, on_progress)
        index_time_s = time.perf_counter() - t0

        _set_progress(doc_id, 95)
        _set_step(doc_id, "Finalizing")

        with _Session() as db:
            doc = db.get(Document, uuid.UUID(doc_id))
            if doc and doc.status != "stopped":
                doc.status = "indexed"
                doc.index_time_s = round(index_time_s, 1)
                doc.page_count = page_count
                db.commit()

        _set_progress(doc_id, 100)
        _clear_step(doc_id)
        _clear_progress(doc_id)
        return {"chunks": chunks_indexed, "index_time_s": round(index_time_s, 1)}

    except Exception as exc:
        with _Session() as db:
            doc = db.get(Document, uuid.UUID(doc_id))
            if doc and doc.status != "stopped":
                doc.status = "failed"
                doc.error_message = str(exc)[:500]
                db.commit()
        _clear_step(doc_id)
        _clear_progress(doc_id)
        raise
