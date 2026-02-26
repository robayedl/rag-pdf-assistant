from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pypdf import PdfReader


@dataclass(frozen=True)
class Chunk:
    text: str
    page: int
    chunk_id: int


def extract_pages(pdf_path: str) -> list[str]:
    reader = PdfReader(pdf_path)
    pages: list[str] = []
    for p in reader.pages:
        txt = p.extract_text() or ""
        pages.append(txt)
    return pages


def chunk_text(
    pages: list[str],
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> list[Chunk]:
    """
    Simple character-based chunking:
    - chunk_size: number of characters per chunk
    - overlap: number of overlapping characters
    """
    chunks: list[Chunk] = []
    for page_idx, page_text in enumerate(pages, start=1):
        text = (page_text or "").strip()
        if not text:
            continue

        start = 0
        chunk_id = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            piece = text[start:end].strip()
            if piece:
                chunks.append(Chunk(text=piece, page=page_idx, chunk_id=chunk_id))
                chunk_id += 1
            start = end - chunk_overlap
            if start < 0:
                start = 0
            if start >= len(text):
                break
    return chunks