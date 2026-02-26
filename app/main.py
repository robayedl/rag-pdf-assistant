from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from app.config import settings
from app.storage import new_doc_id, pdf_path

from rag.ingest import extract_pages, chunk_text
from rag.embed import embed_texts
from rag.store import get_collection

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    head = await file.read(5)
    if head != b"%PDF-":
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    rest = await file.read()
    content = head + rest

    doc_id = new_doc_id()
    path = pdf_path(doc_id)
    path.write_bytes(content)

    return {"doc_id": doc_id, "filename": file.filename, "stored_path": str(path)}


@app.post("/documents/{doc_id}/index")
def index_document(doc_id: str):
    path = pdf_path(doc_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document not found")

    pages = extract_pages(str(path))
    chunks = chunk_text(pages)

    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")

    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)

    ids = [f"{doc_id}_p{c.page}_c{c.chunk_id}" for c in chunks]
    metadatas = [
        {"doc_id": doc_id, "page": c.page, "chunk_id": c.chunk_id, "source": path.name}
        for c in chunks
    ]

    col = get_collection()
    col.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

    return {"doc_id": doc_id, "chunks_indexed": len(chunks), "collection": col.name}