# 📋 Proposal Response Assistant

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-vector%20store-DC244C?logo=qdrant&logoColor=white)](https://qdrant.tech)
[![Gemini](https://img.shields.io/badge/Gemini-3.6%20Flash-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![Tests](https://img.shields.io/badge/tests-86%20passing-brightgreen)](tests/)
[![Golden Set](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/vishnu0529/enterprise-rag-assistant/main/eval/golden_set_metrics.json)](docs/EVALUATION.md#golden-set-50-items-including-12-deliberate-traps)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> Production-style Retrieval-Augmented Generation for a professional-services
> bid team: drafts answers to RFP and proposal questions from a firm's own
> capability statement, past proposals, team credentials, rate card, and
> standard terms, every claim cited back to a source, and a rigorous
> evaluation suite, not just another RAG demo. Most portfolios stop at
> retrieval + generation; this one also measures whether the answers are
> actually good, and refuses to answer what the corpus doesn't support.

**Live demo:** [Streamlit dashboard](https://enterprise-rag-assistant-iyq9apbv2jeyby3xxqx3ce.streamlit.app/) · backend on Render (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for how both are wired together, including a shared API-key gate. The demo only holds the synthetic `sample_docs/proposal_corpus/` documents, never a real client's).

Full docs: [Architecture](docs/ARCHITECTURE.md) · [Evaluation](docs/EVALUATION.md) · [Deployment](docs/DEPLOYMENT.md) · [Failure Modes](docs/FAILURE_MODES.md) · [Agent Production Readiness Scorecard](https://claude.ai/code/artifact/5c6af602-27b4-4bc1-af7b-c2cb501da89c) (this repo scored against all 15 items)

<p align="center"><img src="docs/graph.png" alt="The real compiled corrective-RAG graph" width="360"></p>

<p align="center"><sub>Rendered directly from the live <code>StateGraph</code> object via <code>scripts/render_graph.py</code>, not hand-drawn, so it can't silently drift out of sync with the actual node/edge structure. Rerun the script after any change to <code>build_graph()</code>.</sub></p>

---

## Case Study: From Demo to Production-Shaped

This started as a generic single-document Q&A demo (`sample_docs/company_handbook.md`,
an employee handbook, no domain, no hardening). The table below is what actually
changed converting it into a bid-team proposal-response tool. Every number is
either a live command you can rerun (`pytest -q`, `git diff --stat`) or a
`git show` against the exact pre-hardening commit (`d2e0092`), not an estimate.

| | Before (`d2e0092`) | After the first pass |
|---|---|---|
| Corpus | 1 generic document, 2 chunks | 7 domain documents (capability statement, 2 past proposals, case studies, CVs, rate card, terms), 33 chunks |
| Tests | 31 passing | 50 passing (+19) |
| CI jobs | 3 (`lint`, `test`, `docker-build`) | 5 (+ `eval-gate`, `publish-eval-metrics`) |
| Hallucination testing | None | 50-item golden set: 38 answerable + 12 deliberate refusal traps |
| Citation enforcement | None. An uncited answer was indistinguishable from a cited one | `critique_node` retries, then escalates, any answer missing a `[Source N]` marker |
| Escalation on low confidence | None. A low-faithfulness answer after retries was returned exactly like a good one | Visible "needs bid-director review" banner + `escalated: true` on the response |
| Data-boundary control | None. [A real tuition-payment letter with bank details reached the public demo](docs/DEPLOYMENT.md) and had to be manually deleted | Ingestion scans for UK sort codes/account numbers/NI numbers and rejects by default (`DATA_BOUNDARY_MODE=block`) |
| Recovery from a bad state | Manual reconstruction | `scripts/rollback.py [git-ref]`, one command, verified against both the working tree and a specific past commit |

That covered evals, hardening, and honesty. A second pass then went further:
from a RAG pipeline that answers questions to a multi-agent system that can
survive a process being killed mid-conversation and won't release a
commercial figure without a human saying so:

| | Before this pass | Now (`HEAD`) |
|---|---|---|
| Checkpointing | In-memory only. A killed process loses the conversation | `PostgresSaver` in prod; verified with a real two-process, real-`SIGKILL` demonstration (`scripts/demo_kill_and_resume.py`), not just claimed |
| Human oversight | A written warning banner on a bad answer | A genuine LangGraph `interrupt()` halt on any answer quoting a £ figure, opt-in, resumed via `POST /chat/{session_id}/approve` |
| Tracing | None | OpenTelemetry span per graph node + one parent span per request, verified against OTel's own in-memory exporter |
| Failure modes | Handled in code, not written down anywhere | `docs/FAILURE_MODES.md`: every mode, organised by category, each with a code/test reference |
| Config/prompt version | Not traceable to a specific past answer | Every answer carries the exact git commit that produced it (`code_version`) |
| LLM resilience | No timeout. A hung connection could hang a request indefinitely | Explicit timeout + native SDK backoff (Google `HttpRetryOptions`, Anthropic `timeout`/`max_retries`) |
| Graph diagram | Hand-drawn Mermaid, could drift from the real code | `docs/graph.png`, rendered directly from the compiled `StateGraph` object |
| Tests | 50 passing | 86 passing (+36) |

Scale across both passes: 22 commits, 58 files touched, +3,290/-250 lines
since `d2e0092` (`git diff --stat d2e0092 HEAD`).

**What's not in this table yet, on purpose:** live faithfulness/relevancy/context-recall
scores, golden-set pass rate, p50/p95 latency, and per-task cost all require a real
LLM API call, and this project's own key is currently quota-limited (see
[docs/EVALUATION.md](docs/EVALUATION.md)). The badge and chart there read
"pending live run" rather than a made-up number. Standing rule for this repo:
if it isn't measured, it doesn't go in the README.

---

## Table of Contents
- [Case Study](#case-study-from-demo-to-production-shaped)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Evaluation](#evaluation)
- [Running Tests](#running-tests)
- [Production Hardening](#production-hardening)
- [Project Structure](#project-structure)
- [Future Improvements](#future-improvements)

---

## Features

- **Multi-format ingestion**: PDF (page-tracked), Markdown, plain text
- **Cited chat**: every answer references the specific document, page, and chunk it came from, with a relevance score
- **Two-agent corrective RAG**: a Retrieval Strategist agent decides *how* to search (including real multi-hop decomposition into several sub-queries for comparison-style questions), a separate Drafting Agent writes the answer from whatever evidence it's given, and they never see each other's prompts, only shared graph state. A critique node scores faithfulness *and* checks that the answer actually cites a source, and if either check fails, sends the Strategist back to re-plan (capped), instead of just returning a possibly-hallucinated or uncited answer
- **Escalation instead of silent degradation**: if retries run out and the answer is still ungrounded or uncited, it's flagged with a visible "needs bid-director review" banner and `escalated: true` in the API response, so a low-confidence answer never looks the same as a good one. A genuine refusal ("the corpus doesn't cover this") is correctly exempted from the citation check
- **Durable checkpointing**: the graph's own state (not just chat history) is checkpointed to Postgres in production, so a killed and restarted process resumes an in-flight run instead of losing it, verified with a real two-process, real-`SIGKILL` demo (`scripts/demo_kill_and_resume.py`), not just claimed. Falls back to in-memory for local SQLite dev
- **Human-in-the-loop approval on commercially-sensitive answers**: opt in with `require_approval: true` and an answer quoting a specific £ figure genuinely pauses the graph via LangGraph's `interrupt()`. Not a warning banner, an actual halt. It stays paused until `POST /chat/{session_id}/approve` releases or rejects it. Off by default, so every existing caller (eval, golden set) is unaffected
- **LLM calls have an explicit timeout and retry with backoff**: neither provider client had a timeout configured before, so a hung connection could hang a `/chat` request indefinitely. Both `LLM_TIMEOUT_SECONDS` and `LLM_MAX_RETRIES` are wired through each SDK's own native retry transport (exponential backoff with jitter), not a hand-rolled loop, and verified via `tests/test_llm_client.py` that the config actually reaches the client, not just that it's declared in settings
- **Every graph node is traced with OpenTelemetry**: a real span per node (`recall_memory`, `strategize`, `retrieve`, `draft`, `critique`, `escalate`, `approval_gate`, `remember`) nested under one parent span per request, with cost/latency/retry attributes attached, not just the final answer. Console output with zero setup in dev; set `OTEL_EXPORTER_OTLP_ENDPOINT` to export to any real backend (Jaeger, Grafana Tempo, Honeycomb, ...) in production. Verified with `tests/test_tracing.py` using OpenTelemetry's own in-memory exporter: real spans, a real trace hierarchy, not asserted by inspection
- **Every answer carries the exact commit that produced it**: `code_version` on every `/chat` response and `/health`, resolved from git (or `GIT_COMMIT_SHA` at deploy time). Since prompts and config live as code here, the commit *is* the prompt/config version, answering "which version produced this past answer" exactly
- **Cross-session memory**: optional `user_id` lets the agent semantically recall relevant exchanges from a *different*, earlier session, not just the current conversation's history. Deliberately a separate mechanism from graph checkpointing: one is short-term/thread-scoped, the other long-term/cross-session (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md))
- **Conversation memory**: session-aware, persisted in Postgres (prod) or SQLite (dev)
- **Rigorous evaluation**: faithfulness, answer relevancy, context precision, context recall, latency, and token-cost tracking, following the [RAGAS methodology](https://docs.ragas.io), scored against the same corrective-RAG graph `/chat` uses, not a separate simplified path
- **Dual LLM provider support**: Google Gemini or Anthropic Claude, same abstraction used in [ai-resume-matcher](https://github.com/vishnu0529/ai-resume-matcher)
- **Local-first dev, production-shaped deploy**: runs with zero external services locally (embedded Qdrant, SQLite); `docker-compose` wires a real Qdrant + Postgres for a production-shaped stack, same code either way
- **Actually-working Docker + CI**: a real `Dockerfile`, `docker-compose.yml`, and GitHub Actions workflow (lint → test → docker build), not placeholders

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
    API --> Strategist[Retrieval Strategist<br/>decides sub-queries]
    Strategist --> Qdrant
    Qdrant --> Drafter[Drafting Agent<br/>writes from evidence]
    Drafter --> LLM[Gemini / Claude]
    Drafter -.critique fails: re-plan.-> Strategist
    Drafter --> Escalate{{"escalate: still bad<br/>after retries?"}}
    Escalate --> Approval{{"approval_gate:<br/>interrupt() if priced"}}
    Approval -.human decides.-> API
    Strategist --> Memory[(User Memory<br/>Qdrant, per user_id)]
    API --> DB[(Sessions + Documents<br/>SQLite dev / Postgres prod)]
    Strategist -.checkpoint per node.-> Checkpoint[(Graph Checkpoint<br/>Postgres prod / in-memory dev)]
```

The chat path is `app/services/rag_graph.py`: recall memory → **strategize** (Retrieval
Strategist decides sub-queries + top_k) → retrieve → **draft** (Drafting Agent writes the
answer) → critique (faithfulness + citation check) → (send the Strategist back to re-plan if
ungrounded or uncited, capped at 2 retries) → **escalate** (flags the answer for human review if
still bad) → **approval_gate** (pauses via `interrupt()` if the answer quotes a commercial
figure and the caller opted in) → remember. Full component breakdown and design decisions:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, Pydantic |
| Agent orchestration | LangGraph, with two agent roles (Retrieval Strategist, Drafting Agent) plus a faithfulness-gated critique node that routes retries back to the Strategist |
| RAG primitives | LangChain (text splitting), custom retrieval/generation chain reused by the graph |
| Vector store | Qdrant (embedded locally, real service via Docker), with separate collections for document chunks and cross-session user memory |
| Embeddings | `BAAI/bge-small-en-v1.5` via `fastembed`/ONNX Runtime (local, free, no API cost, no torch) |
| LLMs | Google Gemini / Anthropic Claude |
| Session storage | SQLModel: SQLite (dev) / PostgreSQL (prod) |
| Graph checkpointing | `langgraph-checkpoint-postgres` (`PostgresSaver`) in prod, in-memory `MemorySaver` in dev, the same split as session storage above |
| Tracing | OpenTelemetry, one span per graph node, console exporter in dev / OTLP to any real backend in prod (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)) |
| Evaluation | RAGAS-methodology metrics, implemented directly, scored against the real two-agent graph (see [docs/EVALUATION.md](docs/EVALUATION.md)) |
| Demo UI | Streamlit |
| Testing | pytest, 86 tests, all mocked (no network/model load in CI) |
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
| `POST` | `/chat` | Ask a question (optionally with `user_id` for cross-session memory, `require_approval` for the HITL gate); returns answer + citations + latency/token/cost metrics + faithfulness score + retry count + `escalated` flag + `code_version` + the Strategist's sub-queries/reasoning. If `require_approval` is set and the answer is commercially sensitive, `answer` is `null` and `pending_approval: true` |
| `POST` | `/chat/{session_id}/approve` | Resumes a paused run with `{"approved": bool, "reason": str?}`, the human-in-the-loop decision on a `pending_approval` response. 409 if nothing is actually paused on that session |
| `GET` | `/chat/{session_id}/history` | Retrieve a conversation's history |
| `POST` | `/evaluate` | Score a single question/answer against retrieved context |

Interactive docs at `/docs` once the server is running.

## Evaluation

Four RAGAS-methodology metrics, run against a fixed 6-question eval set over
`sample_docs/proposal_corpus/` via `python scripts/run_evaluation.py`. A
larger 50-item golden set (`eval/golden_set.json`) goes further: 38
answerable questions plus 12 deliberate traps. These are questions phrased like real
RFP questions but asking for facts the corpus doesn't contain, where a
correct refusal counts as a pass and a fabricated answer counts as a
failure. See [docs/EVALUATION.md](docs/EVALUATION.md#golden-set-50-items-including-12-deliberate-traps)
for how to run it.

**Current status:** metric logic is fully unit-tested (86/86 passing,
including known-hallucination and judge-failure cases, the retry/cap/memory
loop, and multi-hop sub-query merging/deduplication) and the whole pipeline
was verified end-to-end with a mocked LLM. A live run against this project's
own Gemini key currently hits a `429` free-tier quota limit (`limit: 0`
requests/day, an account configuration issue, not a code bug). Full details,
the exact error, and the eval set: **[docs/EVALUATION.md](docs/EVALUATION.md)**.

## Running Tests

```bash
pytest -q          # 86 tests, ~5s (after first model download), no network required
ruff check .        # lint
ruff format --check .  # formatting
```

## Production Hardening

The four things pilots typically skip, demonstrated in code and tests, not
just described here:

| Scorecard item | What it is | Where |
|---|---|---|
| **Escalation on low confidence** | If the critique loop exhausts its retries and the answer is still ungrounded or uncited, a visible "needs bid-director review" banner is prepended and `escalated: true` is set on the response, so a low-confidence answer is never indistinguishable from a good one. | `escalate_node` in `app/services/rag_graph.py`; `tests/test_rag_graph.py::test_escalation_banner_added_*` |
| **Citation enforcement** | The critique node checks every drafted answer for a `[Source N]` marker, not just faithfulness. An answer with no citation is treated as ungrounded and retried, same as a low faithfulness score. A genuine refusal is correctly exempted (it has nothing to cite). | `critique_node`/`_CITATION_MARKER` in `app/services/rag_graph.py`; `tests/test_rag_graph.py::test_missing_citation_triggers_a_retry*`, `test_refusal_answers_are_not_flagged*` |
| **Data-boundary config** | Document ingestion is scanned for patterns that look like real personal/financial data (UK sort codes, account numbers, National Insurance numbers) and rejected by default. This is the control that would have caught [the real incident already on record](docs/DEPLOYMENT.md) where a tuition-payment letter with bank details reached the public demo. Configurable via `DATA_BOUNDARY_MODE` (`block` / `warn` / `off`). | `app/services/data_boundary.py`; `tests/test_data_boundary.py` |
| **One-command rollback** | `scripts/rollback.py [git-ref]` wipes the vector store and documents table, then re-ingests the corpus from the current working tree or a specific past commit, restoring a known-good state in a single command instead of hand-reconstructing what was ingested. | `scripts/rollback.py`, `vector_store.reset_collection()` |

## Project Structure

```
enterprise-rag-assistant/
  app/
    core/         # config, db engine
    models/       # SQLModel tables + Pydantic API schemas
    services/      # ingestion, embeddings, vector_store, rag_chain, rag_graph,
                   # agent_state, memory_store, llm_client, session_store, evaluation
    routers/       # documents, chat, evaluate
    main.py
  scripts/
    run_evaluation.py
  tests/
  docs/
    ARCHITECTURE.md
    EVALUATION.md
    DEPLOYMENT.md
  dashboard.py     # Streamlit demo UI
  Dockerfile
  docker-compose.yml
  .github/workflows/ci.yml
```

## Future Improvements

Deliberately deferred to keep this round's scope real and fully verified
rather than partially built everywhere:

- **Next.js/TypeScript frontend** (currently a Streamlit demo UI)
- **Word document and web-page ingestion** (currently PDF/Markdown/txt)
- **Streaming chat responses**
- **Hybrid search** (BM25 + vector) and **reranking**
- **Parent-document retrieval**
- **MCP tool support**
- **A portfolio domain** for the live demo (currently on Render/Streamlit Cloud's default subdomains)

## License

[MIT](LICENSE)
