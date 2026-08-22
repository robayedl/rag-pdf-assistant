from __future__ import annotations

import json
import logging
import os
import struct
import uuid
from typing import Optional

import redis as redis_lib
from redis.commands.search.field import TagField, TextField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

from rag.llm import get_embeddings

logger = logging.getLogger(__name__)

# v2: added doc_id TagField, bump name so existing index is replaced on next start
_INDEX_NAME = "semantic_cache_v2_idx"
_KEY_PREFIX = "cache:"
_VECTOR_DIM = 768


def _get_client() -> redis_lib.Redis:
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return redis_lib.from_url(url, decode_responses=False)


def _ensure_index(client: redis_lib.Redis) -> None:
    try:
        client.ft(_INDEX_NAME).info()
    except Exception:
        schema = (
            TagField("doc_id"),
            VectorField(
                "embedding",
                "FLAT",
                {"TYPE": "FLOAT32", "DIM": _VECTOR_DIM, "DISTANCE_METRIC": "COSINE"},
            ),
            TextField("answer"),
            TextField("citations"),
        )
        client.ft(_INDEX_NAME).create_index(
            schema,
            definition=IndexDefinition(prefix=[_KEY_PREFIX], index_type=IndexType.HASH),
        )


def _embed(query: str) -> list[float]:
    return get_embeddings().embed_query(query)


def _to_bytes(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _escape_tag(value: str) -> str:
    """Escape special chars in Redis Search tag values (UUIDs contain dashes)."""
    return value.replace("-", "\\-")


def lookup(query: str, doc_id: str) -> Optional[dict]:
    threshold = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.97"))
    try:
        client = _get_client()
        _ensure_index(client)
        vec_bytes = _to_bytes(_embed(query))
        tag = _escape_tag(doc_id)
        q = (
            Query(f"(@doc_id:{{{tag}}})=>[KNN 1 @embedding $vec AS score]")
            .sort_by("score")
            .return_fields("answer", "citations", "score")
            .dialect(2)
        )
        results = client.ft(_INDEX_NAME).search(q, query_params={"vec": vec_bytes})
        if not results.docs:
            return None
        top = results.docs[0]
        # RediSearch COSINE returns distance (0 = identical), convert to similarity
        similarity = 1.0 - float(top.score)
        if similarity >= threshold:
            answer = top.answer
            citations_raw = top.citations
            if isinstance(answer, bytes):
                answer = answer.decode()
            if isinstance(citations_raw, bytes):
                citations_raw = citations_raw.decode()
            logger.info("Cache hit (similarity=%.4f) for %r on doc %s", similarity, query, doc_id)
            return {"answer": answer, "citations": json.loads(citations_raw)}
    except Exception as e:
        logger.warning("Cache lookup failed: %s", e)
    return None


def store(query: str, doc_id: str, answer: str, citations: list) -> None:
    ttl = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
    try:
        client = _get_client()
        _ensure_index(client)
        key = f"{_KEY_PREFIX}{uuid.uuid4()}"
        client.hset(
            key,
            mapping={
                "doc_id": doc_id,
                "embedding": _to_bytes(_embed(query)),
                "answer": answer,
                "citations": json.dumps(citations),
            },
        )
        client.expire(key, ttl)
    except Exception as e:
        logger.warning("Cache store failed: %s", e)
