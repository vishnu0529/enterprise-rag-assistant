# 📚 Enterprise Knowledge Assistant

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-vector%20store-DC244C?logo=qdrant&logoColor=white)](https://qdrant.tech)
[![Gemini](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![Tests](https://img.shields.io/badge/tests-35%20passing-brightgreen)](tests/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> Production-style Retrieval-Augmented Generation: document ingestion, cited
> chat over your own documents, and a rigorous evaluation suite — not just
> another RAG demo. Most portfolios stop at retrieval + generation; this one
> also measures whether the answers are actually good.

Full docs: [Architecture](docs/ARCHITECTURE.md) · [Evaluation](docs/EVALUATION.md) · [Deployment](docs/DEPLOYMENT.md)

---

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Evaluation](#evaluation)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)

---

## Features

- **Multi-format ingestion** — PDF (page-tracked), Markdown, plain text
- **Cited chat** — every answer references the specific document, page, and chunk it came from, with a relevance score
- **Advanced retrieval (Phase 2)** — hybrid search (BM25 + vector, fused via Reciprocal Rank Fusion), cross-encoder reranking, and LLM-based query rewriting for conversational follow-ups — each independently toggleable and degrading gracefully to plain vector search when disabled
- **Conversation memory** — session-aware, persisted in Postgres (prod) or SQLite (dev)
- **Rigorous evaluation** — faithfulness, answer relevancy, context precision, context recall, latency, and token-cost tracking, following the [RAGAS methodology](https://docs.ragas.io), including a live before/after comparison of retrieval quality
- **Dual LLM provider support** — Google Gemini or Anthropic Claude, same abstraction used in [ai-resume-matcher](https://github.com/vishnu0529/ai-resume-matcher)
- **Local-first dev, production-shaped deploy** — runs with zero external services locally (embedded Qdrant, SQLite); `docker-compose` wires a real Qdrant + Postgres for a production-shaped stack, same code either way
- **Actually-working Docker + CI** — a real `Dockerfile`, `docker-compose.yml`, and GitHub Actions workflow (lint → test → docker build), not placeholders

## Architecture

```mermaid
flowchart LR
    U([User]) --> UI[Streamlit UI]
    U --> API_direct[Direct API calls]
    UI --> API[FastAPI]
    API_direct --> API
    API --> Ingest[Ingest + Chunk]
    Ingest --> Embed[bge-small-en-v1.5]
    Embed --> Qdrant[(Qdrant)]
    API --> RAG[RAG Chain]
    RAG --> Rewrite[Query Rewriter]
    RAG --> Hybrid[Hybrid Search: BM25+Vector]
    Hybrid --> Rerank[Cross-Encoder Reranker]
    Rerank --> Qdrant
    RAG --> LLM[Gemini / Claude]
    RAG --> Eval[Evaluation]
    API --> DB[(Sessions + Documents<br/>SQLite dev / Postgres prod)]
```

Full component breakdown and design decisions: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, Pydantic |
| RAG orchestration | LangChain (text splitting), custom retrieval/generation chain |
| Vector store | Qdrant (embedded locally, real service via Docker) |
| Embeddings | `BAAI/bge-small-en-v1.5` (local, free, no API cost) |
| LLMs | Google Gemini / Anthropic Claude |
| Session storage | SQLModel — SQLite (dev) / PostgreSQL (prod) |
| Evaluation | RAGAS-methodology metrics, implemented directly (see [docs/EVALUATION.md](docs/EVALUATION.md)) |
| Demo UI | Streamlit |
| Testing | pytest, 35 tests, all mocked (no network/model load in CI) |
| Lint/format | ruff |
| Containers | Docker, docker-compose |
| CI | GitHub Actions (lint → test → docker build) |

## Quick Start

```bash
git clone https://github.com/vishnu0529/enterprise-rag-assistant.git
cd enterprise-rag-assistant

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set GOOGLE_API_KEY (or ANTHROPIC_API_KEY + LLM_PROVIDER=anthropic)

uvicorn app.main:app --reload
```

In a second terminal:

```bash
streamlit run dashboard.py
```

Or with Docker Compose (real Qdrant + Postgres, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)):

```bash
export GOOGLE_API_KEY=...
docker compose up --build
```

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/documents` | Upload a PDF/Markdown/txt file, chunk + embed it |
| `GET` | `/documents` | List ingested documents |
| `DELETE` | `/documents/{id}` | Remove a document and its vectors |
| `POST` | `/chat` | Ask a question; returns answer + citations + latency/token metrics |
| `GET` | `/chat/{session_id}/history` | Retrieve a conversation's history |
| `POST` | `/evaluate` | Score a single question/answer against retrieved context |

Interactive docs at `/docs` once the server is running.

## Evaluation

Four RAGAS-methodology metrics, run against a fixed 4-question eval set over
`sample_docs/company_handbook.md` via `python scripts/run_evaluation.py`.
The script also runs a **live retrieval-only comparison** (baseline vector
search vs. Phase 2's hybrid search + reranking) that needs no LLM access,
since embeddings run on a local model — this part always produces real
numbers regardless of API quota.

**Current status:** metric logic is fully unit-tested (35/35 passing,
including known-hallucination and judge-failure cases) and the whole
pipeline was verified end-to-end with a mocked LLM. A live run of the full
faithfulness/relevancy/precision/recall comparison needs live LLM access;
this project's own Gemini key has repeatedly hit account-level free-tier
quota limits (`429 RESOURCE_EXHAUSTED`, `limit: 0`) rather than a code bug.
Full details, the exact error, and the eval set: **[docs/EVALUATION.md](docs/EVALUATION.md)**.

## Running Tests

```bash
pytest -q          # 35 tests, ~15s, no network/model download required
ruff check .        # lint
ruff format --check .  # formatting
```

## Project Structure

```
enterprise-rag-assistant/
  app/
    core/         # config, db engine
    models/       # SQLModel tables + Pydantic API schemas
    services/      # ingestion, embeddings, vector_store, rag_chain,
                   # hybrid_search, reranker, query_rewriter,
                   # llm_client, session_store, evaluation
    routers/       # documents, chat, evaluate
    main.py
  scripts/
    run_evaluation.py
  tests/
  docs/
    ARCHITECTURE.md
    EVALUATION.md
    DEPLOYMENT.md
    ROADMAP.md
  dashboard.py     # Streamlit demo UI
  Dockerfile
  docker-compose.yml
  .github/workflows/ci.yml
  CONTRIBUTING.md
```

## Roadmap

This project is built in phases, each fully implemented and verified before
moving to the next. Phase 1 (core RAG) and Phase 2 (hybrid search, reranking,
query rewriting) are done; Phase 3 (agentic/LangGraph) and Phase 4
(auth, streaming, DOCX ingestion, semantic caching, React/Next.js frontend)
are explicitly future work. Full breakdown: **[docs/ROADMAP.md](docs/ROADMAP.md)**.

Contributing / local dev standards: **[CONTRIBUTING.md](CONTRIBUTING.md)**.

## License

[MIT](LICENSE)
