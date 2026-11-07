# Product Requirements Document

## Summary

Proposal Response Assistant is a retrieval-augmented drafting tool for
professional-services bid teams. It answers RFP and proposal questions from
a firm's own capability statement, past proposals, case studies, team CVs,
rate card, and standard terms, with every claim cited back to a source
document, and refuses to answer what the corpus doesn't support rather than
fabricating a plausible-sounding figure.

This repo currently runs against a synthetic firm ("Aldermere Advisory LLP")
as a reference implementation. No real client corpus has been loaded.

## Problem

Drafting a bid response means re-finding the same facts (insurance cover,
day rates, liability caps, past case studies, named experts) scattered
across a firm's own documents, under time pressure, with a real cost to
getting a commercial figure wrong. A hallucinated day rate or liability cap
in a submitted proposal is far more costly than a missed lookup — the
asymmetry a generic RAG demo doesn't account for.

Estimated cost today (no tool): roughly 40 hours of partner/consultant time
per bid at a ~£95/h loaded rate, across an estimated ~60 bids/year for a
firm this size.

## Target users

- **Bid director** — owns proposal/RFP response drafting. Wants a correct
  first draft fast, with sources, and wants to know when the tool itself is
  unsure rather than finding out after submission.
- **Engagement partner** (adjacent workflow, not built yet — see Non-goals)
  — document review and first-draft deliverables from an engagement corpus.

## Goals

1. Answer a bid question from the firm's own corpus with an inline citation
   for every claim.
2. Refuse, visibly, when the corpus doesn't contain the answer — never
   produce a fluent guess on a commercial fact.
3. Flag low-confidence answers for human review instead of returning them
   looking identical to a good answer.
4. Pause for an explicit human decision before releasing any answer that
   quotes a specific commercial figure.
5. Survive a process crash or restart mid-conversation without losing the
   in-flight run.
6. Make every answer traceable to the exact code/prompt version that
   produced it.
7. Measure answer quality continuously (golden set in CI), not just at
   build time.

## Non-goals (this version)

- The engagement-document-review workflow (second workflow from the parent
  90-day plan) — not built, no code in this repo targets it yet.
- Multi-tenant / per-client deployments — this repo ingests one shared
  corpus; every key can see every ingested document, there is no per-firm
  or per-client data isolation (per-user *identity* is built, see below;
  per-user *data scoping* is not).
- A production frontend — the demo UI is Streamlit, not a client-ready
  Next.js/TypeScript app.
- Ingesting Word documents or web pages — only PDF, Markdown, and plain
  text are supported.
- Streaming responses — `/chat` returns a complete answer, not a token
  stream.
- Reranking and parent-document retrieval — hybrid (dense + BM25) retrieval
  is implemented; a separate reranking stage and parent-document expansion
  are not.

## User stories

1. *As a bid director*, I ask "What is our professional indemnity cover per
   claim?" and get back the figure with a citation to the specific document
   and page it came from.
2. *As a bid director*, I ask for a rate or SLA figure the corpus never
   states, and the tool tells me it doesn't have that information instead
   of guessing.
3. *As a bid director*, I ask a comparison-style question spanning two case
   studies, and the tool decomposes it into sub-queries and merges evidence
   from both, rather than only searching once.
4. *As a bid director*, when the drafted answer quotes a commercial figure,
   I'm required to explicitly approve it before it's released, so nothing
   priced goes out without a named human sign-off.
5. *As a bid director*, if the answer is weakly grounded even after the
   tool retries its own search, I see a visible "needs bid-director review"
   flag rather than a confident-looking but shaky answer.
6. *As the repo owner*, if a code change regresses answer quality, the CI
   eval gate catches it on the golden set before merge (once wired up as a
   required check).
7. *As the repo owner*, if the deployed process crashes mid-conversation,
   restarting it resumes the same session from where it left off rather
   than losing the exchange.

## Functional requirements

| # | Requirement | Where it's implemented |
|---|---|---|
| 1 | Ingest PDF/Markdown/txt, reject anything else or anything with no extractable text | `app/services/ingestion.py`, `app/routers/documents.py` |
| 2 | Reject ingestion of documents containing UK sort codes, account numbers, or NI numbers by default | `app/services/data_boundary.py` |
| 3 | Answer a question with inline `[Source N]` citations to document/page/chunk | `app/services/rag_graph.py` (`draft_node`), `app/services/rag_chain.py` |
| 4 | Decompose comparison-style questions into multiple sub-queries and merge/dedupe retrieved evidence | `strategize_node`/`retrieve_node`, `app/services/rag_graph.py` |
| 5 | Retry re-planning (not just rewording) when an answer is ungrounded or uncited, capped at 2 retries | `critique_node`, `app/services/rag_graph.py` |
| 6 | Escalate with a visible review banner when retries are exhausted and the answer is still bad | `escalate_node`, `app/services/rag_graph.py` |
| 7 | Pause for human approval before releasing an answer quoting a £ figure, opt-in per request | `approval_gate_node`, `POST /chat/{session_id}/approve` |
| 8 | Resume a killed/restarted process mid-conversation without losing the run | `app/services/checkpointer.py` |
| 9 | Recall relevant exchanges from a different, earlier session given a `user_id` | `app/services/memory_store.py` |
| 10 | Restore a known-good corpus/vector-store state in one command | `scripts/rollback.py` |
| 11 | Stamp every answer with the exact code commit that produced it | `app/core/version.py` |
| 12 | Trace every graph node's execution with cost/latency attributes | `app/core/tracing.py` |
| 13 | Score answer quality continuously against a fixed golden set in CI | `eval/golden_set.json`, `scripts/run_golden_set.py`, `.github/workflows/ci.yml` |

## Success metrics

Current measured state (`eval/golden_set_results.md`, commit `745c7ed`,
2026-10-05) — the authoritative numbers for this project, not an estimate:

| Metric | Result |
|---|---|
| Golden-set pass rate | 50/50 (38 answerable + 12 traps) |
| Trap refusal rate | 12/12 |
| Faithfulness | 1.00 |
| Context recall | 1.00 |
| Answer relevancy | 0.88 |
| Latency | p50 7,654ms / p95 23,943ms |
| Cost per task | ~$0.000145 |
| Test suite | 87/87 passing |

Note: this pass rate is one sample, not a guarantee. `eval/metrics_history.jsonl`
shows three reruns at an earlier commit scoring 94%/92%/96% before a
retrieval fix landed; traps have never failed. See `docs/EVALUATION.md` for
the full flakiness note.

These are read off `eval/golden_set_results.md`/`eval/golden_set_metrics.json`
directly — if that file has since been regenerated by a newer CI run, the
newer numbers are authoritative, not this snapshot.

## Open questions / risks

- **Access control (scorecard item 11): per-user identity is built, per-tenant
  data isolation is not.** Each `X-API-Key` now resolves to a specific user
  (`app/core/auth.py`, backed by `api_keys.json`), and `/chat` sessions and
  trace spans carry that identity instead of trusting a client-supplied
  `user_id`. What's still missing is per-tenant *data* scoping — every key
  can still see every ingested document, since the corpus itself has no
  owner field. That's a bigger, separate feature (needs a decision before
  any real multi-client use), not a quick follow-on to this.
- **The CI eval gate is not yet a required branch-protection check** — it
  needs a repo secret (`GOOGLE_API_KEY`/`ANTHROPIC_API_KEY`) and a
  branch-protection setting, both left as deliberate repo-owner decisions
  (see [docs/EVALUATION.md](EVALUATION.md)).
- **The engagement-document-review workflow has no code yet** — if that
  becomes the near-term priority over proposal drafting, it needs its own
  requirements pass, not an assumption that this graph generalizes to it
  unchanged.
