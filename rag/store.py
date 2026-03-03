from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

DEFAULT_COLLECTION = "pdf_chunks"


def get_chroma_dir() -> str:
    return os.getenv("CHROMA_DIR", "chroma_db")


def get_client() -> chromadb.ClientAPI:
    chroma_dir = get_chroma_dir()
    Path(chroma_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=chroma_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_collection(name: str = DEFAULT_COLLECTION):
    client = get_client()
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})