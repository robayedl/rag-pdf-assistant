# RAG PDF Assistant (FastAPI)

A minimal Retrieval-Augmented Generation (RAG) service for asking questions over PDFs with page-level citations.

This project demonstrates:
- PDF ingestion
- Vector search
- Citation-based answering
- Evaluation (Recall@k, faithfulness, latency)
- Dockerized local deployment
- CI using GitHub Actions

---

## Quickstart (Local Development)

### 1. Create virtual environment
```bash
python -m venv .venv
source .venv/bin/activate