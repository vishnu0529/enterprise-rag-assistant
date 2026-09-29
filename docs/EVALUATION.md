# Evaluation

Metrics follow the [RAGAS methodology](https://docs.ragas.io): faithfulness,
answer relevancy, context precision, context recall, implemented directly in
`app/services/evaluation.py` rather than via the `ragas` package (which has a
broken import against this project's langchain-community version; see that
file's docstring). Each metric uses an LLM-as-judge call or embedding
similarity, following the same published formulas RAGAS uses.

## What's verified vs. what's pending

**Verified: metric logic is correct.** All four metrics have unit tests
(`tests/test_evaluation.py`) exercising known-correct and known-incorrect
inputs (e.g. a fully-hallucinated claim scores faithfulness `0.0`, and a
judge-call failure degrades to `0.0` rather than crashing). The full RAG
pipeline plus evaluation was also verified end-to-end against real ingested
documents with a mocked LLM standing in for the model (see the commit
history for `app/services/evaluation.py` and `app/services/rag_chain.py`).
81/81 tests pass; `pytest -q` reproduces this. `evaluate_question()` now
scores the two-agent graph (`app/services/rag_graph.py`) rather than the
single-pass chain directly. Same principle as before, evaluation measures
whatever `/chat` actually runs, including any Strategist re-planning the
graph did, not a separate simplified path (`tests/test_rag_graph.py` covers
the graph's own retry/cap/memory/multi-hop-merge behaviour).

**Pending: a live run against this project's own API key.**
`scripts/run_evaluation.py` runs the fixed 6-question eval set below through
the *real* Gemini API and writes real scores here. Running it today produces:

```
google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED.
Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 0, model: gemini-2.0-flash
```

This is an account-level free-tier quota limit (`limit: 0`, i.e. no free
daily allowance configured for this Google Cloud project/model), not a bug
in the evaluation code. The same key hits the same error from
`ai-resume-matcher`'s existing usage. Once billing/quota is configured for
this key (or a different `GOOGLE_API_KEY`/`ANTHROPIC_API_KEY` is set in
`.env`), running `python scripts/run_evaluation.py` will populate the table
below with real faithfulness/relevancy/precision/recall/latency/cost numbers
against `sample_docs/proposal_corpus/`.

## Fixed evaluation set

Deliberately spans five of the seven corpus documents, so this fixed set also
exercises multi-document retrieval, not just single-file recall.

| # | Question | Ground truth |
|---|---|---|
| 1 | What is Aldermere Advisory's professional indemnity insurance cover per claim? | £5 million per claim |
| 2 | By how many working days did the finance function redesign engagement reduce month-end close, and from what starting point? | From 12 working days to 5 working days |
| 3 | What is the day rate for a Senior Consultant? | £1,050 per day, excluding VAT |
| 4 | What are Aldermere's standard payment terms? | Net 30 days from invoice date, invoiced monthly in arrears unless the proposal specifies fixed-price milestone billing |
| 5 | Who led the AI-augmented document review pilot for the regional law firm, and what is their relevant qualification? | Dr Ines Falk; PhD in Computer Science (NLP), University of Edinburgh |
| 6 | What is the liability cap in Aldermere's standard commercial terms? | 100% of fees paid in the preceding 12 months, except gross negligence, wilful misconduct, or breach of confidentiality, which are uncapped |

## How to fill this in with real numbers

```bash
export GOOGLE_API_KEY=<a key with available quota>
python scripts/run_evaluation.py
```

This overwrites this file with a results table (per-question scores +
averages) and an approximate token-cost estimate, generated directly from a
live run, not hand-written.

## Golden set: 50 items, including 12 deliberate traps

The fixed 6-question set above checks recall on questions the corpus *can*
answer. `eval/golden_set.json` goes further: 38 answerable questions plus 12
traps: questions phrased exactly like real RFP questions, but asking for
facts genuinely absent from the corpus (a named individual who doesn't
exist, a rate that's explicitly "quoted separately," an SLA figure that was
never stated). The correct behaviour on a trap is an explicit refusal, not a
fluent guess. This is the check that actually matters for a bid team, since
a hallucinated commercial term in a real proposal is far more costly than a
missed factual lookup.

The golden set's structure is validated in CI with no API key required
(`tests/test_golden_set.py`: 50 items, ≥10 traps, every source doc actually
exists, every trap explains why it's unanswerable). Scoring it against the
live model is a separate step, same quota constraint as above:

```bash
export GOOGLE_API_KEY=<a key with available quota>
python scripts/run_golden_set.py
```

This ingests the full corpus, runs every item through the real
corrective-RAG graph, and writes `eval/golden_set_results.md`, pass/fail
per item, with faithfulness/context-recall for answerable items and a
refusal check for traps, plus p50/p95 latency and an illustrative cost-per-task estimate.
It also appends a record to `eval/metrics_history.jsonl` and rewrites
`eval/golden_set_metrics.json` (a shields.io endpoint-badge payload). The
script exits non-zero if any trap is answered instead of refused.

## CI merge gate

`.github/workflows/ci.yml` has an `eval-gate` job, after `test`, that runs
`scripts/run_golden_set.py` on every push and pull request, but only when a
`GOOGLE_API_KEY` or `ANTHROPIC_API_KEY` repository secret is configured; if
neither secret is set, the job skips with a clear message instead of failing
the build for contributors who don't have one. **To make this a real,
active merge gate:**

1. Add `GOOGLE_API_KEY` (or `ANTHROPIC_API_KEY`) as a repository secret
   (Settings → Secrets and variables → Actions).
2. Mark `eval-gate` as a required status check under branch protection for
   `main` (Settings → Branches). This repo does not enable that
   automatically, since it changes what can block a merge and is a call for
   whoever owns the repo to make deliberately, not something to switch on
   silently.

Once the secret is set, a separate `publish-eval-metrics` job, running only
on pushes to `main`, after `eval-gate` passes, runs
`scripts/update_eval_chart.py` and commits the refreshed
`eval/golden_set_metrics.json`, `eval/metrics_history.jsonl`, and this file's
trend chart back to `main`. That's what makes the badge and chart below move
on their own after every merge, rather than being a hand-updated snapshot.

### Trend

<!-- EVAL_TREND_START -->
_No CI runs recorded yet. This section fills in once `scripts/run_golden_set.py` has run at least once with a live API key (see above) and committed to `eval/metrics_history.jsonl`._
<!-- EVAL_TREND_END -->
