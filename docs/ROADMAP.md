# Roadmap

This is a personal portfolio project built in phases, each one fully
implemented and verified (tests passing, lint clean, run against real data)
before moving to the next — rather than many features half-built at once.

## Phase 1 — Production RAG core (done)

- Multi-format ingestion: PDF (page-tracked), Markdown, plain text
- Chunking, embeddings (`BAAI/bge-small-en-v1.5`, local), Qdrant vector store
- FastAPI backend with cited chat (`/documents`, `/chat`, `/evaluate`)
- Conversation memory (SQLite dev / Postgres prod via SQLModel)
- Dual LLM provider support: Google Gemini or Anthropic Claude
- RAGAS-methodology evaluation: faithfulness, answer relevancy, context
  precision, context recall, latency, token cost — implemented directly
  (see [EVALUATION.md](EVALUATION.md) for why, not via the `ragas` package)
- Docker + docker-compose (real Qdrant + Postgres) and GitHub Actions CI
  (lint → test → docker build)

## Phase 2 — Advanced RAG (done, this round)

- **Hybrid search**: BM25 (lexical) + vector (semantic) search, fused via
  Reciprocal Rank Fusion — `app/services/hybrid_search.py`
- **Reranking**: cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`)
  rescoring over a wider candidate pool, two-stage retrieve-then-rerank —
  `app/services/reranker.py`
- **Query rewriting**: resolves pronouns/follow-ups from conversation
  history into a standalone search query before retrieval —
  `app/services/query_rewriter.py`
- Each stage is independently toggleable
  (`ENABLE_HYBRID_SEARCH` / `ENABLE_RERANKING` / `ENABLE_QUERY_REWRITING`
  in `app/core/config.py`), degrading gracefully to Phase 1's plain vector
  search when disabled — nothing breaks if a stage is turned off
- Dedicated tests for all three modules (RRF fusion logic, mocked
  cross-encoder, mocked query-rewrite LLM calls + fallback behavior)
- Before/after comparison in `scripts/run_evaluation.py` — see
  [EVALUATION.md](EVALUATION.md). Note: the retrieval-only half of that
  comparison runs live regardless of API quota, since embeddings are local;
  the full faithfulness/relevancy/precision/recall comparison needs live
  LLM access and is reported honestly when that's unavailable rather than
  faked.

## Phase 3 — Agentic RAG (future, not started)

- Multi-agent workflow via LangGraph: separate planning, retrieval, and
  synthesis agents instead of a single linear chain
- Tool calling (e.g. a calculator or structured-lookup tool alongside
  retrieval)
- Citation verification as its own agentic step, distinct from generation

## Phase 4 — Production infra & UX (future, not started)

- JWT authentication
- Streaming chat responses (currently request/response)
- DOCX and web-page ingestion (currently PDF/Markdown/txt)
- Redis-backed semantic caching for repeated/similar queries
- Parent-child retrieval (retrieve small chunks, return larger surrounding
  context) and metadata filtering (by date, department, document type, etc.)
- React/Next.js frontend (currently a Streamlit demo UI)
- Live cloud deployment (Railway/Render) and a portfolio domain

None of the Phase 3/4 items are implemented yet — they're listed here so
scope is explicit rather than implied, not because any of them are close to
done.
