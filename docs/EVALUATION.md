# Evaluation

Metrics follow the [RAGAS methodology](https://docs.ragas.io) — faithfulness,
answer relevancy, context precision, context recall — implemented directly in
`app/services/evaluation.py` rather than via the `ragas` package (which has a
broken import against this project's langchain-community version; see that
file's docstring). Each metric uses an LLM-as-judge call or embedding
similarity, following the same published formulas RAGAS uses.

## What's verified vs. what's pending

**Verified — metric logic is correct.** All four metrics have unit tests
(`tests/test_evaluation.py`) exercising known-correct and known-incorrect
inputs (e.g. a fully-hallucinated claim scores faithfulness `0.0`, and a
judge-call failure degrades to `0.0` rather than crashing). The full RAG
pipeline plus evaluation was also verified end-to-end against real ingested
documents with a mocked LLM standing in for the model (see the commit
history for `app/services/evaluation.py` and `app/services/rag_chain.py`).
28/28 tests pass; `pytest -q` reproduces this. `evaluate_question()` now
scores the corrective-RAG graph (`app/services/rag_graph.py`) rather than the
single-pass chain directly — same principle as before, evaluation measures
whatever `/chat` actually runs, including any reformulate-and-retry the graph
did, not a separate simplified path (`tests/test_rag_graph.py` covers the
graph's own retry/cap/memory behaviour).

**Pending — a live run against this project's own API key.**
`scripts/run_evaluation.py` runs the fixed 4-question eval set below through
the *real* Gemini API and writes real scores here. Running it today produces:

```
google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED.
Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 0, model: gemini-2.0-flash
```

This is an account-level free-tier quota limit (`limit: 0` — i.e. no free
daily allowance configured for this Google Cloud project/model), not a bug
in the evaluation code — the same key hits the same error from
`ai-resume-matcher`'s existing usage. Once billing/quota is configured for
this key (or a different `GOOGLE_API_KEY`/`ANTHROPIC_API_KEY` is set in
`.env`), running `python scripts/run_evaluation.py` will populate the table
below with real faithfulness/relevancy/precision/recall/latency/cost numbers
against `sample_docs/company_handbook.md`.

## Fixed evaluation set

| # | Question | Ground truth |
|---|---|---|
| 1 | How many days of annual leave do full-time employees get, and does it increase over time? | 25 days/year, rising to 30 after 5 years of continuous service |
| 2 | How many days per week can employees work remotely without special approval? | Up to 3 days/week; full-time remote needs director approval |
| 3 | What is the expense reimbursement threshold that requires manager approval? | Above £500 requires written line-manager sign-off |
| 4 | How much paid parental leave do secondary caregivers get? | 4 weeks fully paid |

## How to fill this in with real numbers

```bash
export GOOGLE_API_KEY=<a key with available quota>
python scripts/run_evaluation.py
```

This overwrites this file with a results table (per-question scores +
averages) and an approximate token-cost estimate, generated directly from a
live run — not hand-written.
