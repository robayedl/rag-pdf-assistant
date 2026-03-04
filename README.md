# RAG PDF Assistant

A FastAPI-based Retrieval-Augmented Generation (RAG) backend that allows users to upload PDF documents, index them using embeddings, and query their content using semantic search.

The system extracts text from uploaded PDFs, splits the text into chunks, generates vector embeddings, stores them in a Chroma vector database, and retrieves the most relevant chunks for a given query.

---

## Features

- Upload and store PDF documents
- Automatic text extraction and chunking
- Vector embeddings for semantic search
- ChromaDB vector database
- FastAPI REST API
- Docker and Docker Compose support
- Automated tests with Pytest
- CI workflow using GitHub Actions

---

## Architecture

```
PDF Upload
     │
     ▼
Text Extraction (pypdf)
     │
     ▼
Text Chunking
     │
     ▼
Embedding Generation
     │
     ▼
Chroma Vector Database
     │
     ▼
Semantic Retrieval
     │
     ▼
Answer Construction
```

---

## Project Structure

```
rag-pdf-assistant
│
├── .github/workflows        # CI pipeline
├── app                      # FastAPI application
│   ├── main.py
│   └── storage.py
│
├── rag                      # RAG pipeline
│   ├── ingest.py            # PDF chunking and indexing
│   ├── retrieve.py          # semantic retrieval
│   ├── embed.py             # embedding generation
│   └── store.py             # vector database interface
│
├── eval                     # evaluation scripts
├── tests                    # automated tests
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── README.md
├── .env.example
├── .dockerignore
└── .gitignore
```

---

## Installation (Local Development)

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/rag-pdf-assistant.git
cd rag-pdf-assistant
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the API

```bash
uvicorn app.main:app --reload
```

API will run at:

```
http://127.0.0.1:8000
```

---

## Running with Docker

### Build and start the service

```bash
docker compose up --build
```

The API will be available at:

```
http://localhost:8000
```

The following directories are mounted as volumes:

- `storage/` – stores uploaded PDFs
- `chroma_db/` – stores vector embeddings

This ensures that data persists across container restarts.

---

## Environment Variables

Create a `.env` file using the provided example.

```bash
cp .env.example .env
```

Example configuration:

```
ENVIRONMENT=local
STORAGE_DIR=storage
CHROMA_DIR=chroma_db
```

---

## API Endpoints

### Health Check

```
GET /health
```

Example response:

```json
{
  "status": "ok",
  "environment": "local"
}
```

---

### Upload a PDF

```
POST /documents
```

Example request:

```bash
curl -F "file=@resume.pdf" http://127.0.0.1:8000/documents
```

Example response:

```json
{
  "doc_id": "abc123",
  "filename": "resume.pdf",
  "stored_path": "storage/pdfs/abc123.pdf"
}
```

---

### Index a Document

```
POST /documents/{doc_id}/index
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/documents/<doc_id>/index
```

Example response:

```json
{
  "doc_id": "abc123",
  "chunks_indexed": 24,
  "collection": "pdf_chunks"
}
```

---

### Query the Document

```
POST /query
```

Example request:

```bash
curl -X POST http://127.0.0.1:8000/query \
-H "Content-Type: application/json" \
-d '{
  "doc_id": "abc123",
  "question": "What skills are listed in the document?",
  "top_k": 5
}'
```

Example response:

```json
{
  "doc_id": "abc123",
  "question": "What skills are listed in the document?",
  "answer": "Machine Learning, Computer Vision, PyTorch, OpenCV, TensorFlow",
  "citations": [],
  "retrieved": 5,
  "latency_ms": 23.1
}
```

---

## Running Tests

```bash
pytest -q
```

Tests validate:

- Query validation rules
- Missing document handling
- API response schema

---

## Continuous Integration

GitHub Actions runs automatically on push and pull requests.

Pipeline includes:

- dependency installation
- automated tests

Workflow configuration is located in:

```
.github/workflows/
```

---

## Future Improvements

Possible future improvements:

- LLM-based answer generation
- Streaming responses
- Hybrid search (BM25 + embeddings)
- Advanced chunking strategies
- Query evaluation benchmarks

---

## License

This project is provided for educational and research purposes.