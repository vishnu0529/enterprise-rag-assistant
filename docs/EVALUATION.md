# Evaluation Results

Run against 4 fixed Q&A pairs over `sample_docs/company_handbook.md`, using `gemini-2.0-flash` via `google`.

Metrics follow the RAGAS methodology, implemented directly in `app/services/evaluation.py` (see that file's docstring for why).

## Retrieval Comparison (live, no LLM required)

Baseline = plain vector search (last round). Phase 2 = hybrid search (BM25 + vector via Reciprocal Rank Fusion) + cross-encoder reranking. Embeddings run on a local `sentence-transformers` model, not Gemini, so this comparison is unaffected by API quota.

| Question | Baseline top chunk | Phase 2 top chunk | Changed? |
|---|---|---|---|
| How many days of annual leave do full-ti… | # Acme Corp Employee Handbook ## Remote Work Policy Employee | # Acme Corp Employee Handbook ## Remote Work Policy Employee | No |
| How many days per week can employees wor… | # Acme Corp Employee Handbook ## Remote Work Policy Employee | # Acme Corp Employee Handbook ## Remote Work Policy Employee | No |
| What is the expense reimbursement thresh… | # Acme Corp Employee Handbook ## Remote Work Policy Employee | # Acme Corp Employee Handbook ## Remote Work Policy Employee | No |
| How much paid parental leave do secondar… | ## Parental Leave Primary caregivers are entitled to 16 week | ## Parental Leave Primary caregivers are entitled to 16 week | No |

Note: `sample_docs/company_handbook.md` is a small demo document that chunks into only 2 pieces at the configured `CHUNK_SIZE` (chunk 0 alone contains the Remote Work, Annual Leave, and Expense Reimbursement sections). With only 2 candidates total, baseline and Phase 2 agreeing on the same top chunk is the *correct* outcome, not a null result — it confirms Phase 2 doesn't regress retrieval on a known-correct case. Hybrid search and reranking earn their keep on larger, more ambiguous corpora with lexical/semantic mismatches, where there's actually room for the ranking to differ.

## Full Metrics: Faithfulness / Relevancy / Precision / Recall

**Not available this run.** This requires live LLM access for both answer generation and LLM-as-judge scoring. The actual error raised during this run was:

```
ValueError: No API key was provided. Please pass a valid API key. Learn how to create an API key at https://ai.google.dev/gemini-api/docs/api-key.
```

Re-run this script once that's resolved (e.g. a valid `GOOGLE_API_KEY` in `.env`, or the daily quota resetting if it's a quota error — this project hit a `GenerateRequestsPerDayPerProjectPerModel-FreeTier` 20/day cap earlier in development). The code path for the full before/after comparison is implemented and only needs live LLM access to produce numbers.

The retrieval comparison above needs no LLM calls and reflects real, live results from this run.
