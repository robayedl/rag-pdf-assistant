from __future__ import annotations

import base64
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Tuple

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from unstructured.documents.elements import Image as UnstructuredImage
from unstructured.documents.elements import Table
from unstructured.partition.pdf import partition_pdf
import unstructured_pytesseract

_tesseract_cmd = os.environ.get("TESSERACT_CMD")
if _tesseract_cmd:
    unstructured_pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd


def _tesseract_available() -> bool:
    import shutil
    cmd = _tesseract_cmd or "tesseract"
    return shutil.which(cmd) is not None

from rag.contextualize import contextualize_chunk
from rag.store import add_documents, clear_document

DEFAULT_COLLECTION = "pgvector"


_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""],
)

_MAX_FIGURES = 30

_FIGURE_PROMPT = (
    "Describe this figure from a document in 2-3 sentences for retrieval purposes. "
    "Include visible numbers, labels, or trends."
)

_IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def get_storage_dir() -> Path:
    return Path(os.getenv("STORAGE_DIR", "storage"))


def get_pdf_path(doc_id: str) -> Path:
    return get_storage_dir() / "pdfs" / f"{doc_id}.pdf"


def _clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_figures_enabled() -> bool:
    return os.getenv("EXTRACT_FIGURES", "").lower() in ("1", "true", "yes")


def _use_contextual_retrieval() -> bool:
    return os.getenv("CONTEXTUAL_RETRIEVAL", "").lower() in ("1", "true", "yes")


def _html_to_markdown(html: str) -> str:
    try:
        import markdownify
        return markdownify.markdownify(html, heading_style="ATX").strip()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html).strip()


def _caption_figure(image_path: str) -> str:
    from rag.llm import get_llm

    path = Path(image_path)
    if not path.exists():
        return ""

    mime_type = _IMAGE_MIME.get(path.suffix.lower(), "image/png")
    with open(path, "rb") as fh:
        image_b64 = base64.b64encode(fh.read()).decode("utf-8")

    message = HumanMessage(
        content=[
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
            },
            {"type": "text", "text": _FIGURE_PROMPT},
        ]
    )
    try:
        return get_llm().invoke([message]).content.strip()
    except Exception:
        return ""


def extract_elements(pdf_path: Path, doc_id: str) -> list:
    if not _tesseract_available():
        cmd = _tesseract_cmd or "tesseract"
        raise RuntimeError(
            f"Tesseract not found at '{cmd}'. "
            "Install it (macOS: brew install tesseract; Ubuntu: apt install tesseract-ocr) "
            "and set TESSERACT_CMD in your .env if it is not on PATH."
        )
    kwargs: dict = {
        "filename": str(pdf_path),
        "infer_table_structure": True,
        "strategy": "hi_res",
    }
    if _extract_figures_enabled():
        figures_dir = get_storage_dir() / "figures" / doc_id
        figures_dir.mkdir(parents=True, exist_ok=True)
        kwargs["extract_images_in_pdf"] = True
        kwargs["extract_image_block_output_dir"] = str(figures_dir)

    return partition_pdf(**kwargs)


_CONTEXTUALIZE_WORKERS = int(os.getenv("CONTEXTUALIZE_WORKERS", "8"))


def _build_docs_from_elements(
    elements: list,
    doc_id: str,
    source_name: str,
    contextual: bool,
    full_doc_text: str,
) -> List[Document]:
    """Convert parsed elements to Documents, parallelising contextualisation calls."""

    # ── Pass 1: collect raw chunks without contextualisation ─────────────────
    raw: List[dict] = []
    chunk_id = 0
    figure_count = 0
    text_buf: List[Tuple[int, str]] = []
    current_page: int = -1

    def _flush_buf() -> None:
        nonlocal chunk_id
        if not text_buf:
            return
        page = text_buf[0][0]
        combined = "\n\n".join(t for _, t in text_buf)
        for c in _SPLITTER.split_text(combined):
            if not c.strip():
                continue
            raw.append({
                "content": c,
                "page": page,
                "chunk_id": chunk_id,
                "element_type": "text",
                "image_path": None,
            })
            chunk_id += 1
        text_buf.clear()

    for el in elements:
        page = el.metadata.page_number or 0

        if isinstance(el, Table):
            _flush_buf()
            current_page = page
            html = getattr(el.metadata, "text_as_html", None) or ""
            md_text = _html_to_markdown(html) if html else _clean_text(el.text or "")
            if md_text.strip():
                raw.append({
                    "content": md_text,
                    "page": page,
                    "chunk_id": chunk_id,
                    "element_type": "table",
                    "image_path": None,
                })
                chunk_id += 1

        elif isinstance(el, UnstructuredImage):
            _flush_buf()
            current_page = page
            if not _extract_figures_enabled() or figure_count >= _MAX_FIGURES:
                continue
            image_path = (
                getattr(el.metadata, "image_path", None)
                or getattr(el.metadata, "filename", None)
            )
            if not image_path:
                continue
            caption = _caption_figure(str(image_path))
            if not caption:
                continue
            raw.append({
                "content": caption,
                "page": page,
                "chunk_id": chunk_id,
                "element_type": "figure",
                "image_path": str(image_path),
            })
            chunk_id += 1
            figure_count += 1

        else:
            text = _clean_text(el.text or "")
            if not text:
                continue
            if page != current_page and text_buf:
                _flush_buf()
            current_page = page
            text_buf.append((page, text))

    _flush_buf()

    if not raw:
        return []

    # ── Pass 2: contextualise in parallel ─────────────────────────────────────
    if contextual:
        contexts: List[str] = [""] * len(raw)

        def _ctx(idx: int) -> Tuple[int, str]:
            return idx, contextualize_chunk(full_doc_text, raw[idx]["content"])

        with ThreadPoolExecutor(max_workers=_CONTEXTUALIZE_WORKERS) as pool:
            futures = {pool.submit(_ctx, i): i for i in range(len(raw))}
            for fut in as_completed(futures):
                idx, ctx = fut.result()
                contexts[idx] = ctx
    else:
        contexts = [""] * len(raw)

    # ── Pass 3: assemble Documents ────────────────────────────────────────────
    all_docs: List[Document] = []
    for item, ctx in zip(raw, contexts):
        c = item["content"]
        embed_text = f"{ctx} {c}" if ctx else c
        ref = (
            f"{doc_id}_p{item['page']}_fig{item['chunk_id']}"
            if item["element_type"] == "figure"
            else f"{doc_id}_p{item['page']}_c{item['chunk_id']}"
        )
        meta: dict = {
            "doc_id": doc_id,
            "ref": ref,
            "page": item["page"],
            "chunk_id": item["chunk_id"],
            "source": source_name,
            "element_type": item["element_type"],
            "original_content": c,
        }
        if item["image_path"]:
            meta["image_path"] = item["image_path"]
        all_docs.append(Document(page_content=embed_text, metadata=meta))

    return all_docs


def index_document(
    doc_id: str,
    progress: Callable[[str], None] | None = None,
    on_pct: Callable[[int], None] | None = None,
) -> Tuple[int, str, int]:
    def emit(msg: str) -> None:
        if progress:
            progress(msg)

    def pct(n: int) -> None:
        if on_pct:
            on_pct(n)

    pdf_path = get_pdf_path(doc_id)
    if not pdf_path.exists():
        raise FileNotFoundError(str(pdf_path))

    clear_document(doc_id)

    source_name = pdf_path.name
    contextual = _use_contextual_retrieval()

    emit("Parsing PDF with hi_res layout analysis…")
    elements = extract_elements(pdf_path, doc_id)
    page_count = max((el.metadata.page_number or 0) for el in elements) if elements else 0

    # OCR done → Extracting starts (threshold 70)
    pct(70)
    emit(f"Parsed {len(elements)} elements. Building document chunks…")

    full_doc_text = (
        "\n\n".join(
            el.text
            for el in elements
            if not isinstance(el, UnstructuredImage) and el.text
        )
        if contextual
        else ""
    )
    all_docs = _build_docs_from_elements(
        elements, doc_id, source_name, contextual, full_doc_text
    )

    if not all_docs:
        return 0, DEFAULT_COLLECTION, page_count

    # Chunk building done → Embedding starts (threshold 80)
    pct(80)
    emit(f"Built {len(all_docs)} chunks. Generating embeddings and storing in pgvector…")

    def _on_embed_batch(done: int, total: int) -> None:
        # Fill 80 → 97 smoothly as batches complete
        pct(80 + int((done / total) * 17))

    add_documents(doc_id, all_docs, on_batch=_on_embed_batch)
    return len(all_docs), DEFAULT_COLLECTION, page_count
