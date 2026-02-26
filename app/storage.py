from __future__ import annotations

import os
import uuid
from pathlib import Path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def new_doc_id() -> str:
    return uuid.uuid4().hex


def get_storage_root() -> Path:
    # project_root/storage
    return Path(os.getenv("STORAGE_DIR", "storage")).resolve()


def pdf_path(doc_id: str) -> Path:
    root = get_storage_root()
    ensure_dir(root / "pdfs")
    return root / "pdfs" / f"{doc_id}.pdf"