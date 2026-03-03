from __future__ import annotations

from dataclasses import dataclass
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
        pages.append(p.extract_text() or "")
    return pages


def chunk_text(
    pages: list[str],
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> list[Chunk]:
    """
    Safe character-based chunking that always makes progress.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []
    step = chunk_size - chunk_overlap

    for page_idx, page_text in enumerate(pages, start=1):
        text = (page_text or "").strip()
        if not text:
            continue

        chunk_id = 0
        for start in range(0, len(text), step):
            end = min(start + chunk_size, len(text))
            piece = text[start:end].strip()
            if piece:
                chunks.append(Chunk(text=piece, page=page_idx, chunk_id=chunk_id))
                chunk_id += 1

            if end >= len(text):
                break

    return chunks