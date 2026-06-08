# DocuMind: Agentic Document Intelligence

> Chat with any PDF or DOCX file using a production-grade agentic pipeline powered by LangGraph, Gemini 2.5 Flash, hybrid search, real-time streaming, Clerk auth, and Postgres + pgvector storage.

[![CI](https://github.com/robayedl/documind/actions/workflows/ci.yml/badge.svg)](https://github.com/robayedl/documind/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Next.js](https://img.shields.io/badge/Next.js-16-orange)
![LangGraph](https://img.shields.io/badge/LangGraph-agentic-purple)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Demo

https://github.com/user-attachments/assets/aa924408-7f80-4968-b5b2-7e2bac769806

---

## Features

| Feature | Description |
|---|---|
| **Agentic RAG** | LangGraph pipeline with document grading, query rewriting, hallucination checking, and HyDE fallback on low-confidence retrieval |
| **Hybrid Search + Reranking** | Dense pgvector (HNSW cosine) + sparse `ts_rank` full-text, fused with RRF and cross-encoder reranking (`ms-marco-MiniLM-L-6-v2`) |
| **HyDE Fallback** | On low reranker confidence, generates a hypothetical passage and re-retrieves for better recall |
| **Gemini 2.5 Flash** | Google's fastest frontier LLM for low-latency generation; also used for figure captioning and contextual retrieval |
| **Semantic Cache** | Redis vector cache; near-identical queries return instantly without hitting the LLM |
| **Multi-Source Ingestion** | PDF and DOCX. DOCX files are converted to PDF via LibreOffice on ingest and then processed through the same hi_res OCR pipeline |
| **Contextual Retrieval** | Gemini prepends a context sentence to every chunk before embedding (Anthropic-style); dramatically improves retrieval precision for long documents |
| **Rich Document Parsing** | Tables extracted as Markdown; PDF figures captioned by Gemini multimodal |
| **PDF Viewer** | Inline PDF pane with citation-click-to-page-jump and snippet highlighting |
| **Background Ingestion** | Celery worker processes documents asynchronously. DOCX adds a Converting step before the shared Parsing -> Extracting -> Embedding -> Finalizing pipeline. UI polls with live progress |
| **Postgres + pgvector** | All metadata, embeddings, and conversation history in one Postgres instance (HNSW cosine + GIN full-text) |
| **Streaming + Recovery** | SSE token-by-token output; answer and cost persist to Postgres even on client disconnect; auto-recovered on next page load |
| **Cost Tracking** | Per-query token + cost on every message; `/usage` dashboard with hourly, daily, weekly, monthly, all-time views |
| **Rate Limiting** | Redis token-bucket: 30 req/hr, 200 req/day per user; HTTP 429 + `Retry-After`; frontend toast with countdown |
| **PII Redaction** | Presidio: EMAIL, PHONE, SSN, CREDIT_CARD scrubbed from the user query before the agent sees it; restored in the final answer |
| **Auth & Isolation** | Clerk (Google + email); per-user document isolation; JWT/RS256 validation |
| **RAGAS Evaluation** | Faithfulness, answer relevancy, context precision & recall on a 30-question golden dataset |

---

## Architecture

**Query Pipeline**

```mermaid
flowchart TD
    Q([User Question]) --> SC{Semantic Cache?}

    SC -->|hit| CR([Return Cached Response])
    SC -->|miss| RET[Hybrid Retrieval\npgvector + ts_rank + RRF]

    RET --> RR[Cross-Encoder Rerank]
    RR --> HY{Score < HyDE\nThreshold?}

    HY -->|yes| HD[HyDE: Generate\nHypothetical Passage]
    HD --> RE2[Re-retrieve + RRF\nmerge + Re-rank]
    RE2 --> GD

    HY -->|no| GD[Grade Documents]

    GD -->|relevant| GEN[Generate Answer\nGemini 2.5 Flash]
    GD -->|none · retry < 3| RW[Rewrite Query]
    GD -->|none · max retries| FB[Fallback]
    RW --> RET

    GEN --> HC[Hallucination Check]
    HC -->|grounded| STORE[Store in Cache]
    STORE --> RESP([Response + Citations])
    HC -->|not grounded · retry < 3| GEN
    HC -->|max retries| FB
    FB --> E2([END])
```

**Ingestion Pipeline**

```mermaid
flowchart LR
    FILE([Upload File]) --> Q
    Q[Celery Queue\nRedis broker] --> DISP{source_type?}

    DISP -->|docx| LO[LibreOffice\nconvert to PDF]
    LO --> UP
    DISP -->|pdf| UP[unstructured\nhi_res + Tesseract]

    UP --> T[Tables → Markdown\nchunk]
    UP --> F[Figures → Gemini\nVision caption]
    UP --> TX[Text → 800-token\nchunks]

    T & F & TX --> CR{Contextual\nRetrieval?}
    CR -->|yes| CTX[Gemini prepends\ncontext sentence]
    CR -->|no| EMB
    CTX --> EMB[Embed\nall-mpnet-base-v2]
    EMB --> VEC[(pgvector\nHNSW index)]
    EMB --> TS[(PostgreSQL\nts_rank / GIN)]
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI, Uvicorn, Server-Sent Events |
| **Agent** | LangGraph, LangChain |
| **LLM** | Google Gemini 2.5 Flash |
| **Embeddings & Reranking** | HuggingFace `all-mpnet-base-v2`, `ms-marco-MiniLM-L-6-v2` |
| **Vector Store** | PostgreSQL + pgvector (HNSW cosine) + `ts_rank` full-text (hybrid) |
| **Database** | PostgreSQL (Supabase or self-hosted via Docker) |
| **Auth** | Clerk (Google + email, JWT/RS256) |
| **Cache** | Redis Stack (vector similarity + Celery broker/backend) |
| **Background Workers** | Celery: async ingestion queue with LibreOffice DOCX conversion |
| **Document Parsing** | unstructured hi_res, Tesseract OCR, Gemini 2.5 Flash multimodal |
| **Frontend** | Next.js 16 (App Router), shadcn/ui, Tailwind CSS |
| **Evaluation** | RAGAS |
| **CI/CD** | GitHub Actions, Docker |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- A [Clerk](https://clerk.com) account (free tier works)
- A Google AI Studio API key
- A Postgres instance; the `docker-compose.yml` spins one up automatically with pgvector

### Docker

```bash
git clone https://github.com/robayedl/documind.git
cd documind
cp .env.example .env
```

Edit `.env` and fill in `GOOGLE_API_KEY`, `CLERK_JWT_KEY`, and `DATABASE_URL`.

```bash
cp web/.env.local.example web/.env.local
```

Edit `web/.env.local` and fill in `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, and `NEXT_PUBLIC_API_URL`.

```bash
docker compose up --build
```

> The first build downloads ML models (~2 GB) and may take several minutes. Tables and indexes are created automatically on first startup.

| Service | URL / Notes |
|---|---|
| UI | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Worker | Background Celery process (no HTTP port, connects to Redis + Postgres) |

---

## Auth Setup (Clerk)

1. Create an app at [clerk.com](https://clerk.com) and enable **Google** and **Email** sign-in.
2. Go to **API Keys**: copy **Publishable Key** → `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` in both `.env` and `web/.env.local`
3. Copy **Secret Key** → `CLERK_SECRET_KEY` in both `.env` (used by Docker web container) and `web/.env.local` (used in local dev)
4. Go to **JWT Templates → Default** → copy the **PEM public key** → `CLERK_JWT_KEY` in `.env` (wrap in double quotes)
5. Development keys (`pk_test_*`) automatically whitelist `localhost`; no domain configuration needed.

> In local dev without `CLERK_JWT_KEY`, the backend auto-creates a `dev_user` identity so you can test without signing in.

---

## API

All endpoints (except `GET /health`) require `Authorization: Bearer <clerk-jwt>`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check (no auth) |
| `GET` | `/documents` | List current user's documents (includes `status`, `progress_percent`, `page_count`, `source_type`) |
| `POST` | `/documents` | Upload a PDF or DOCX; enqueues background ingestion, returns `{doc_id, status: "pending"}` immediately |
| `GET` | `/documents/{doc_id}/status` | Poll ingestion status: `{status, progress_percent, step, page_count}` |
| `POST` | `/documents/{doc_id}/stop` | Cancel a pending or processing ingestion job |
| `POST` | `/documents/{doc_id}/reindex` | Re-enqueue a stopped or failed document |
| `DELETE` | `/documents/{doc_id}` | Delete a document, its chunks, and its file |
| `POST` | `/documents/{doc_id}/index/stream` | Manual re-index with SSE progress (for debugging) |
| `GET` | `/documents/{doc_id}/file` | Download the original PDF or DOCX file |
| `POST` | `/query/stream` | Ask a question; SSE streaming tokens + citations; answer + cost persisted to DB regardless of client disconnect |
| `GET` | `/conversations/{session_id}` | Fetch persisted messages for a session (used for client-side recovery after navigation) |
| `GET` | `/usage/me?period=` | Token and AUD cost summary for a given period (`1h`, `24h`, `7d`, `30d`, `all`); defaults to `all` |
| `GET` | `/usage/me/history?period=` | Time-series data points (bucket, tokens, requests, cost) for charting; granularity varies by period |

---

## Environment Variables

**Backend / Docker** (`.env`):

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | - | **Required.** Google AI Studio API key |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | - | **Required.** Clerk publishable key (baked into web build) |
| `CLERK_SECRET_KEY` | - | **Required.** Clerk secret key (passed to web container at runtime) |
| `CLERK_JWT_KEY` | - | **Required in prod.** RSA public key for JWT validation (PEM, quoted) |
| `DATABASE_URL` | `postgresql://documind:documind@localhost:5432/documind` | Postgres connection string |
| `STORAGE_DIR` | `./storage` | Directory for uploaded PDFs and figures |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `REDIS_URL` | `redis://localhost:6379` | Redis Stack connection URL |
| `SEMANTIC_CACHE_THRESHOLD` | `0.92` | Cosine similarity threshold for cache hit |
| `CACHE_TTL_SECONDS` | `86400` | Cache TTL (seconds) |
| `HYDE_THRESHOLD` | `0.3` | Reranker score below which HyDE is triggered |
| `EXTRACT_FIGURES` | `true` | Caption figures with Gemini multimodal (max 30/doc) |
| `CONTEXTUAL_RETRIEVAL` | `true` | Prepend per-chunk context before embedding |
| `CONTEXTUALIZE_WORKERS` | `8` | Parallel LLM workers for contextual retrieval during indexing |
| `TESSERACT_CMD` | _(PATH)_ | Full path to `tesseract` binary |
| `RATE_LIMIT_PER_HOUR` | `30` | Max chat queries per user per hour |
| `RATE_LIMIT_PER_DAY` | `200` | Max chat queries per user per day |
| `PII_REDACTION` | `true` | Enable Presidio PII redaction on user queries (`true`/`false`) |

**Frontend** (`web/.env.local`):

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | - | **Required.** Clerk frontend publishable key |
| `CLERK_SECRET_KEY` | - | **Required.** Clerk secret key (server-side auth) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API base URL for the frontend |

---

## Project Structure

```
documind/
├── app/
│   ├── auth.py           # Clerk JWT validation (FastAPI dependency)
│   ├── db.py             # SQLAlchemy async engine + session factory
│   ├── models.py         # ORM models: User, Document, Conversation, Message
│   ├── pricing.py        # Model cost table + compute_cost()
│   ├── ratelimit.py      # Redis token-bucket rate limiter
│   ├── redact.py         # Presidio PII redaction / restore
│   ├── storage.py        # File-system helpers (PDF read/write)
│   └── main.py           # FastAPI routes
├── worker/
│   ├── celery_app.py     # Celery app config (broker = Redis)
│   └── tasks.py          # ingest_document task: pending → processing → indexed / failed / stopped
├── rag/
│   ├── agents/           # LangGraph nodes: grader, generator, rewriter, hallucination check
│   ├── chains/           # Retrieval (pgvector + ts_rank + HyDE), reranking, generation
│   ├── store.py          # pgvector CRUD (add, search, clear)
│   ├── cache.py          # Redis semantic cache
│   └── ingest.py         # Unified PDF pipeline: hi_res + Tesseract OCR; LibreOffice DOCX conversion
├── migrations/           # SQL migrations: 001_init, 002_pgvector, 003_cost, 004_source_type
├── legacy/
│   ├── scripts/          # One-off tooling (Chroma → pgvector migration)
│   └── streamlit/        # Previous Streamlit UI (kept for reference)
├── web/                  # Next.js 16 frontend (App Router, shadcn/ui, Clerk)
│   ├── app/              # Pages: /, /chat, /docs, /usage, /login, /about, /how-to-use
│   ├── components/       # Nav, PdfPane, DocWatcher (global bg poller), shadcn primitives
│   ├── lib/              # Typed API client with auth headers (api.ts)
│   └── proxy.ts          # Clerk route protection for /chat, /docs, and /usage
├── eval/                 # RAGAS runner and golden dataset
└── tests/                # Python backend tests
```

---

## Evaluation

Results on a 30-question golden dataset built from **"Attention Is All You Need"** (Vaswani et al., 2017), scored by Gemini 2.5 Flash via [RAGAS](https://docs.ragas.io).

<!-- EVAL-RESULTS-START -->
| Metric | Score | |
|---|---|---|
| `faithfulness` | 0.984 | ███████████████████ |
| `answer_relevancy` | 0.887 | █████████████████ |
| `context_precision` | 0.882 | █████████████████ |
| `context_recall` | 0.933 | ██████████████████ |

_Evaluated on 30 questions · 2026-05-23 · full results in [`eval/results/latest.json`](eval/results/latest.json)_
<!-- EVAL-RESULTS-END -->

```bash
DOC_ID=<your_doc_id> make eval   # full run (~10 min)
make update-readme                # refresh scores without re-running
```

---

## Tests

```bash
make test        # backend
make test-ui     # frontend
make lint
```

---

## License

MIT: free to use, modify, and distribute.
