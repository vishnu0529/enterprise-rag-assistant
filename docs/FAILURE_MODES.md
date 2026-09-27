# Failure-Mode Inventory

Scorecard item 8. Every row below is a failure mode this codebase already
handles, with a pointer to exactly where — this is a record of what's
actually built, not a wishlist. If a row doesn't have a code reference, it
isn't in this inventory.

Escalation path in one sentence: quality problems (ungrounded/uncited
answers) retry then get a visible review banner; commercial-sensitivity
problems pause for a named human decision; infrastructure problems (a
killed process, a bad corpus) recover via durable state and one-command
rollback rather than manual reconstruction. Nothing fails silently.

## Ingestion

| Failure mode | Trigger | Detection | Behaviour |
|---|---|---|---|
| Unsupported file type | Upload isn't `.pdf`/`.md`/`.txt` | Extension check before any parsing | `400` with the supported list — `app/routers/documents.py` |
| File has no extractable text | A scanned/blank PDF, an empty file | `load_text()` returns no pages | `400`, nothing ingested — `app/routers/documents.py` |
| Document contains real personal/financial data | Text matches a UK sort code, account number, or NI number pattern | `data_boundary.enforce()`, called before chunking | `422`, raw upload deleted from disk immediately — never reaches the vector store. This is the control that would have caught [the real incident on record](DEPLOYMENT.md) — `app/services/data_boundary.py` |
| Document produces zero usable chunks | Text exists but is all whitespace/boilerplate after splitting | Chunk count check post-split | `400`, nothing ingested — `app/routers/documents.py` |
| Document not found on delete | Client references a stale/wrong `document_id` | DB lookup miss | `404` — `app/routers/documents.py` |

## Retrieval and drafting

| Failure mode | Trigger | Detection | Behaviour |
|---|---|---|---|
| No documents ingested yet | Empty corpus, any question | Cheap DB check in the router, and independently in `retrieve_node` | Short-circuits to a clear "upload a document first" message — never reaches the LLM at all. `test_no_documents_short_circuits_without_calling_the_llm` |
| LLM call fails during drafting (quota/network/5xx) | Provider outage, bad key, rate limit | `try/except` around `call_llm` in `draft_node` | Clean degraded message exposing only the exception type (never the raw message, in case it contains anything sensitive); `llm_error=True` short-circuits critique/retry/escalation/remember rather than retrying a failure retrying can't fix. `test_llm_failure_in_draft_returns_clean_message_without_retry_or_memory_write` |
| LLM call fails during strategizing | Same as above, during search planning | `try/except` in `strategize_node` | Falls back to the raw question as a single sub-query and a default `top_k` — degrades the search plan, doesn't fail the request |
| LLM call fails during cross-session memory recall | Same, during `recall_memory_node` | `try/except` | Falls back to no remembered context — this turn just doesn't get memory, it isn't blocked by it |
| LLM call hangs, or the provider is rate-limiting | Slow/unresponsive connection | Explicit `LLM_TIMEOUT_SECONDS` + `LLM_MAX_RETRIES`, via each SDK's own exponential-backoff transport | Bounded wait, then a clean failure via the drafting path above — never hangs a request indefinitely. `tests/test_llm_client.py` |
| LLM returns invalid JSON from a structured call | Model doesn't follow the "respond only with JSON" instruction | `call_llm_json` tries `json.loads`, raises a clear `ValueError` on failure | Caught by whichever node called it (strategize, the eval judges), degrading per that node's own fallback above |
| Unknown/misconfigured `LLM_PROVIDER` | A typo or unsupported value in config | Explicit `else: raise ValueError` in `llm_client.py` | Fails loudly at call time — never silently calls the wrong provider |

## Quality gates

| Failure mode | Trigger | Detection | Behaviour |
|---|---|---|---|
| Answer not well-grounded (low faithfulness) | Retrieved context doesn't actually support the drafted answer | `critique_node` scores faithfulness against the retrieved chunks | Retries via `strategize` with feedback, capped at `DEFAULT_MAX_RETRIES`; if still bad, `escalate_node` prepends a visible review banner. `test_retries_send_strategist_back_to_replan_until_it_passes`, `test_escalation_banner_added_when_retries_exhausted_still_ungrounded` |
| Answer cites no source | Draft doesn't include a `[Source N]` marker despite having context | `critique_node`'s `_CITATION_MARKER` check, exempting genuine refusals via `is_refusal()` | Same retry-then-escalate path as low faithfulness. `test_missing_citation_triggers_a_retry_even_when_faithful`, `test_refusal_answers_are_not_flagged_for_missing_citation` |
| A golden-set regression is introduced | A code change causes a previously-correct answer to hallucinate or a trap to stop being refused | `scripts/run_golden_set.py` in the `eval-gate` CI job | Fails the CI job (exits non-zero on any trap answered instead of refused). **Not yet a merge-blocking required check** — needs a repo secret and a branch-protection setting, both left as deliberate repo-owner decisions, documented in `EVALUATION.md` |

## Human oversight

| Failure mode | Trigger | Detection | Behaviour |
|---|---|---|---|
| Answer quotes a commercially sensitive figure | A £ amount appears in the drafted answer, and the caller opted in with `require_approval=True` | `approval_gate_node`'s `_COMMERCIAL_FIGURE` regex | Graph genuinely pauses via LangGraph `interrupt()` until `POST /chat/{session_id}/approve` supplies a human decision — not released either way without one. `tests/test_rag_graph.py::test_approval_required_pauses_on_a_priced_answer` |
| Approval requested for a session with nothing actually paused | Client calls `/approve` on a thread that never paused, or whose pause already resolved | `resume_approval()` checks `graph.get_state(config).interrupts` before attempting to resume | `409`, not a silent no-op and not a stale replay of an old answer. `test_resume_approval_raises_when_nothing_is_actually_paused`, `test_resume_approval_raises_for_a_session_that_never_existed` |
| Missing or invalid API key on a gated endpoint | No `X-API-Key`, or the wrong one | `app/core/auth.py`'s dependency | `401` — a no-op when `API_KEY` is unset (local dev only) |

## Infrastructure and recovery

| Failure mode | Trigger | Detection | Behaviour |
|---|---|---|---|
| Process is killed or crashes mid-run | Container restart, OOM kill, deploy | Durable Postgres checkpoint (`app/services/checkpointer.py`) | A fresh process resumes the same `thread_id` from the last completed node instead of losing the run. Verified with a real two-process, real-`SIGKILL` demonstration, not just claimed — `scripts/demo_kill_and_resume.py` |
| Corpus or config regresses to a bad state | A bad ingestion, a bad deploy | Manual trigger | `scripts/rollback.py [git-ref]` wipes and re-ingests from the working tree or a specific past commit in one command — verified against both paths |
| Best-effort memory write fails | `remember_exchange` throws during `remember_node` | `try/except`, swallowed | The user's answer is already returned; a failed memory write degrades future recall, not this turn |

## What this inventory does not cover

Failure modes with no code reference above genuinely aren't handled yet —
this file is honest about gaps, not just wins. As of this writing that
includes: no per-user access control (a single shared API key gates
everything, not per-tenant permissions — scorecard item 11), no config/prompt
version stamped onto individual past answers (scorecard item 12), and no
request-level tracing backend (scorecard item 4, in progress — see
`docs/ARCHITECTURE.md`).
