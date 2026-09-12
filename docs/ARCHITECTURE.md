# Architecture

## Overview

```mermaid
flowchart TD
    User([User]) --> UI[Streamlit UI<br/>dashboard.py]
    User --> API_direct[Direct API calls]
    UI --> API[FastAPI app<br/>app/main.py]
    API_direct --> API

    subgraph Ingestion
        API --> Ingest[services/ingestion.py<br/>PDF / Markdown / txt loader]
        Ingest --> Chunk[RecursiveCharacterTextSplitter]
        Chunk --> Embed1[services/embeddings.py<br/>BAAI/bge-small-en-v1.5]
        Embed1 --> Qdrant[(Qdrant<br/>vector store)]
        Ingest --> DocDB[(Document registry<br/>SQLModel)]
    end

    subgraph "Chat — two-agent graph (services/rag_graph.py)"
        API --> RecallMem[recall_memory node]
        RecallMem --> UserMem[(Qdrant: user_memory<br/>services/memory_store.py)]
        RecallMem --> Strategize["strategize node<br/>(Retrieval Strategist agent)<br/>decides sub_queries + top_k"]
        Strategize --> Retrieve["retrieve node<br/>fans out over sub_queries,<br/>merges + dedupes chunks"]
        Retrieve --> Embed2[services/embeddings.py]
        Embed2 --> Qdrant
        Qdrant --> Retrieve
        Retrieve -->|no chunks| NoDocs[no_documents node<br/>short-circuit]
        Retrieve -->|has chunks| Draft["draft node<br/>(Drafting Agent)<br/>reuses rag_chain.build_context"]
        Draft --> LLM[services/llm_client.py<br/>Gemini / Claude]
        LLM --> Draft
        Draft --> Critique[critique node<br/>evaluation.score_faithfulness]
        Critique -->|faithfulness < 0.7<br/>and retries left| Strategize
        Critique -->|faithfulness OK<br/>or retries exhausted| Remember[remember node]
        Remember --> UserMem
        Draft --> Citations[Citations +<br/>latency/token metrics]
        API --> SessionDB[(ChatSession / ChatMessage<br/>SQLModel)]
    end

    subgraph Evaluation
        API --> Eval[services/evaluation.py]
        Eval -.->|invokes the same graph| RecallMem
        Eval --> Judge[LLM-as-judge calls<br/>via llm_client.call_llm_json]
        Eval --> EvalReport[docs/EVALUATION.md]
    end

    DocDB -.dev: SQLite / prod: Postgres.- SessionDB
```

## Component responsibilities

| Component | File(s) | Responsibility |
|---|---|---|
| Ingestion | `app/services/ingestion.py` | Load PDF (page-tracked)/Markdown/txt, chunk with overlap |
| Embeddings | `app/services/embeddings.py` | Local `BAAI/bge-small-en-v1.5` via `sentence-transformers` — no per-call API cost |
| Vector store | `app/services/vector_store.py` | Qdrant: embedded local mode (dev) or a real Qdrant service via `QDRANT_URL` (prod) |
| RAG chain (primitives) | `app/services/rag_chain.py` | `build_context`/`SYSTEM_PROMPT` reused by the Drafting Agent; `answer_question` (single-pass) kept for its own tests, no longer the `/chat` path |
| Two-agent graph | `app/services/rag_graph.py`, `app/services/agent_state.py` | LangGraph, two distinct agent roles: **Retrieval Strategist** (`strategize_node`) decides sub-queries/top_k, **Drafting Agent** (`draft_node`) writes the answer from whatever was retrieved. Neither sees the other's prompt — they only share `RagAgentState`. Flow: recall memory → strategize → retrieve (fan out + dedupe) → draft → critique → (send Strategist back to re-plan, capped) → remember. This is the actual `/chat` and `/evaluate` path |
| Cross-session memory | `app/services/memory_store.py` | Second Qdrant collection (`user_memory`), keyed by caller-supplied `user_id`, embeds and recalls past Q&A pairs across unrelated sessions |
| LLM client | `app/services/llm_client.py` | Dual-provider (Gemini/Claude) abstraction, ported from `ai-resume-matcher` |
| Session memory | `app/services/session_store.py`, `app/models/schemas.py` | Conversation history persisted per session (SQLModel: SQLite dev / Postgres prod) |
| Evaluation | `app/services/evaluation.py` | Faithfulness, answer relevancy, context precision/recall — implemented directly (see that file's docstring for why, not via the `ragas` package); scores the graph's actual output, reusing its faithfulness score rather than recomputing it |

## Design decisions worth calling out

- **Two agent roles, not one function doing both jobs.** `strategize_node` (Retrieval Strategist) and `draft_node` (Drafting Agent) are separate LLM calls with separate system prompts and separate responsibilities: the Strategist never writes prose or sees retrieved text, the Drafter never decides search strategy. They communicate only through `RagAgentState` fields (`sub_queries`, `chunks`, `critique_feedback`) — this is what makes it a genuine multi-agent split rather than a renamed single-pass chain.
- **The critique loop retries by re-planning, not just rewording.** A low faithfulness score routes back to `strategize`, not to a narrow query-rewrite step — so a retry can mean a broader query, a completely different angle, or decomposing into multiple sub-queries, not just different phrasing of the same search. Capped at `DEFAULT_MAX_RETRIES` (2) so it can't loop forever.
- **Multi-hop retrieval is a side effect of the Strategist having real agency.** For comparison-style questions, the Strategist can emit 2-3 sub-queries instead of one; `retrieve_node` fans out over all of them and `_merge_and_dedupe` collapses overlapping chunks (same `document_id`/`chunk_index`) down to their highest score, so multi-hop questions don't get double-counted context.
- **Cross-session memory is a separate mechanism from LangGraph's own checkpointing.** The graph is compiled with an in-memory `MemorySaver` purely so one request's strategize/retrieve/draft/critique loop can be invoked consistently; it does not persist between separate `/chat` calls. Actual cross-session recall (a later, unrelated session semantically recalling an earlier one) is handled explicitly by `memory_store.py` against a second Qdrant collection, keyed by `user_id` — a deliberate choice, since LangGraph's thread-scoped checkpointing isn't designed for semantic recall across unrelated threads.
- **Evaluation stays honest about what it's measuring.** `evaluate_question()` calls the same `answer_question_agentic` the `/chat` router calls — not a separate, simpler path — so the eval metrics reflect real production behaviour, including any Strategist re-planning. (`evaluation.py` imports `rag_graph` lazily, inside the function, to avoid a circular import — `rag_graph`'s critique node imports `score_faithfulness` from `evaluation` at module level.)
- **Environment-parity via config, not hardcoding.** Dev mode needs zero external services: Qdrant runs embedded (`qdrant-client`'s local mode) and sessions persist to a SQLite file. Setting `QDRANT_URL` and `DATABASE_URL` (as `docker-compose.yml` does) switches to a real Qdrant service and Postgres — same code path, no branching.
- **Citations are structural, not an afterthought.** Every retrieved chunk carries `document_id`, `filename`, `page`, `chunk_index`, and `score` all the way through to the API response, so an answer can always be traced back to its source.
