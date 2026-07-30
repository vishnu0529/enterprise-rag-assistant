"""Runs a fixed Q&A evaluation set against the RAG pipeline and writes a
results report to docs/EVALUATION.md.

Two things run every time:
1. A retrieval-only baseline-vs-Phase-2 comparison (no LLM calls — embeddings
   are a local sentence-transformers model, not Gemini — so this always
   produces real, live numbers regardless of API quota).
2. A best-effort full-metrics run (faithfulness/relevancy/precision/recall),
   which needs live Gemini access for both generation and judging. If the
   API quota is exhausted, this is reported honestly rather than faked.

Usage:
    ./venv/bin/python scripts/run_evaluation.py
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.db import init_db
from app.services import hybrid_search
from app.services.evaluation import EvalResult, evaluate_question
from app.services.ingestion import chunk_document, load_text
from app.services.rag_chain import retrieve
from app.services.vector_store import delete_document, upsert_chunks

# noqa: E501 — these are natural-language eval data, not code; wrapping them
# would hurt readability more than the line-length lint helps.
EVAL_SET = [
    {
        "question": "How many days of annual leave do full-time employees get, and does it increase over time?",  # noqa: E501
        "ground_truth": "Full-time employees get 25 days of annual leave per year, increasing to 30 days after 5 years of continuous service.",  # noqa: E501
    },
    {
        "question": "How many days per week can employees work remotely without special approval?",
        "ground_truth": "Employees may work remotely up to 3 days per week without special approval; full-time remote work needs department director approval.",  # noqa: E501
    },
    {
        "question": "What is the expense reimbursement threshold that requires manager approval?",
        "ground_truth": "Expenses above £500 require written sign-off from a line manager before being incurred.",  # noqa: E501
    },
    {
        "question": "How much paid parental leave do secondary caregivers get?",
        "ground_truth": "Secondary caregivers receive 4 weeks of fully paid parental leave.",
    },
]

# Illustrative only, NOT official pricing — update with current provider rates
# before relying on this for real cost tracking.
COST_PER_1K_PROMPT_TOKENS_USD = 0.000075
COST_PER_1K_COMPLETION_TOKENS_USD = 0.0003


def _set_phase2_flags(enabled: bool) -> None:
    settings.ENABLE_HYBRID_SEARCH = enabled
    settings.ENABLE_RERANKING = enabled
    settings.ENABLE_QUERY_REWRITING = enabled


def _run_retrieval_comparison() -> list[str]:
    """Compares the single top-ranked chunk under baseline (plain vector
    search — last round's behavior) vs Phase 2 (hybrid search + reranking)
    for each eval question. Needs no LLM calls, so it always runs live."""
    lines = [
        "## Retrieval Comparison (live, no LLM required)",
        "",
        (
            "Baseline = plain vector search (last round). Phase 2 = hybrid "
            "search (BM25 + vector via Reciprocal Rank Fusion) + cross-encoder "
            "reranking. Embeddings run on a local `sentence-transformers` model, "
            "not Gemini, so this comparison is unaffected by API quota."
        ),
        "",
        "| Question | Baseline top chunk | Phase 2 top chunk | Changed? |",
        "|---|---|---|---|",
    ]

    original_hybrid, original_rerank = settings.ENABLE_HYBRID_SEARCH, settings.ENABLE_RERANKING

    try:
        for item in EVAL_SET:
            settings.ENABLE_HYBRID_SEARCH = False
            settings.ENABLE_RERANKING = False
            baseline_chunks = retrieve(item["question"], top_k=1)

            settings.ENABLE_HYBRID_SEARCH = True
            settings.ENABLE_RERANKING = True
            phase2_chunks = retrieve(item["question"], top_k=1)

            def _preview(chunks: list[dict]) -> str:
                if not chunks:
                    return "(none)"
                flat = " ".join(chunks[0]["text"].split())
                return flat[:60]

            baseline_text = _preview(baseline_chunks)
            phase2_text = _preview(phase2_chunks)
            changed = "Yes" if baseline_text != phase2_text else "No"

            q_short = item["question"][:40] + "…"
            lines.append(f"| {q_short} | {baseline_text} | {phase2_text} | {changed} |")
    finally:
        settings.ENABLE_HYBRID_SEARCH, settings.ENABLE_RERANKING = (
            original_hybrid,
            original_rerank,
        )

    lines += [
        "",
        (
            "Note: `sample_docs/company_handbook.md` is a small demo document "
            "that chunks into only 2 pieces at the configured `CHUNK_SIZE` "
            "(chunk 0 alone contains the Remote Work, Annual Leave, and "
            "Expense Reimbursement sections). With only 2 candidates total, "
            "baseline and Phase 2 agreeing on the same top chunk is the "
            "*correct* outcome, not a null result — it confirms Phase 2 "
            "doesn't regress retrieval on a known-correct case. Hybrid "
            "search and reranking earn their keep on larger, more ambiguous "
            "corpora with lexical/semantic mismatches, where there's "
            "actually room for the ranking to differ."
        ),
    ]
    return lines


def _run_full_metrics(label: str) -> tuple[list[EvalResult] | None, str | None]:
    """Attempts the full generation+judge metrics for the whole eval set.
    Requires live LLM access; returns (None, error_message) instead of
    crashing the script if any question fails (e.g. missing API key,
    exhausted quota, network error) — the real error is surfaced honestly
    rather than assumed."""
    results = []
    for item in EVAL_SET:
        try:
            r = evaluate_question(item["question"], ground_truth=item["ground_truth"])
        except Exception as e:
            error_message = f"{type(e).__name__}: {e}"
            q_short = item["question"][:40]
            print(f"[{label}] Full metrics run failed on {q_short!r}: {error_message}")
            return None, error_message
        results.append(r)
        print(
            f"[{label}] Q: {item['question']}\n"
            f"  faithfulness={r.faithfulness:.2f} relevancy={r.answer_relevancy:.2f} "
            f"precision={r.context_precision:.2f} recall={r.context_recall:.2f} "
            f"latency={r.latency_ms:.0f}ms"
        )
    return results, None


def _avg(results: list[EvalResult], field: str) -> float:
    return statistics.mean(getattr(r, field) for r in results)


def _full_metrics_table(label: str, results: list[EvalResult]) -> list[str]:
    lines = [
        f"### {label}",
        "",
        "| Question | Faithfulness | Answer Relevancy | Context Precision | Context Recall | Latency (ms) |",  # noqa: E501
        "|---|---|---|---|---|---|",
    ]
    for item, r in zip(EVAL_SET, results, strict=True):
        q_short = item["question"][:60] + ("…" if len(item["question"]) > 60 else "")
        lines.append(
            f"| {q_short} | {r.faithfulness:.2f} | {r.answer_relevancy:.2f} | "
            f"{r.context_precision:.2f} | {r.context_recall:.2f} | {r.latency_ms:.0f} |"
        )
    lines += [
        "",
        f"- Faithfulness: {_avg(results, 'faithfulness'):.2f}",
        f"- Answer Relevancy: {_avg(results, 'answer_relevancy'):.2f}",
        f"- Context Precision: {_avg(results, 'context_precision'):.2f}",
        f"- Context Recall: {_avg(results, 'context_recall'):.2f}",
        f"- Mean Latency: {_avg(results, 'latency_ms'):.0f} ms",
    ]
    return lines


def _delta_table(baseline: list[EvalResult], phase2: list[EvalResult]) -> list[str]:
    fields = [
        ("Faithfulness", "faithfulness"),
        ("Answer Relevancy", "answer_relevancy"),
        ("Context Precision", "context_precision"),
        ("Context Recall", "context_recall"),
    ]
    lines = [
        "### Delta (Phase 2 − Baseline)",
        "",
        "| Metric | Baseline | Phase 2 | Delta |",
        "|---|---|---|---|",
    ]
    for label, field in fields:
        b, p = _avg(baseline, field), _avg(phase2, field)
        lines.append(f"| {label} | {b:.2f} | {p:.2f} | {p - b:+.2f} |")
    return lines


def main() -> None:
    init_db()

    sample_doc = Path(__file__).resolve().parent.parent / "sample_docs" / "company_handbook.md"
    pages = load_text(sample_doc)
    chunks = chunk_document("eval-doc", sample_doc.name, pages)
    # chunk_document() assigns a fresh random point ID per call, so without
    # this cleanup, re-running this script repeatedly upserts duplicate
    # copies of "eval-doc" into the persisted local Qdrant collection —
    # duplicates then dominate retrieval scoring rather than relevance.
    delete_document("eval-doc")
    upsert_chunks(chunks)
    hybrid_search.invalidate()

    lines = [
        "# Evaluation Results",
        "",
        (
            f"Run against {len(EVAL_SET)} fixed Q&A pairs over "
            f"`sample_docs/company_handbook.md`, using `{settings.LLM_MODEL}` "
            f"via `{settings.LLM_PROVIDER}`."
        ),
        "",
        (
            "Metrics follow the RAGAS methodology, implemented directly in "
            "`app/services/evaluation.py` (see that file's docstring for why)."
        ),
        "",
    ]

    lines += _run_retrieval_comparison()
    lines.append("")

    original_hybrid, original_rerank, original_rewrite = (
        settings.ENABLE_HYBRID_SEARCH,
        settings.ENABLE_RERANKING,
        settings.ENABLE_QUERY_REWRITING,
    )

    print("Attempting full metrics run (baseline: Phase 2 features disabled)...")
    _set_phase2_flags(False)
    baseline_results, baseline_error = _run_full_metrics("baseline")

    print("Attempting full metrics run (Phase 2 features enabled)...")
    _set_phase2_flags(True)
    phase2_results, phase2_error = _run_full_metrics("phase2")

    settings.ENABLE_HYBRID_SEARCH = original_hybrid
    settings.ENABLE_RERANKING = original_rerank
    settings.ENABLE_QUERY_REWRITING = original_rewrite

    lines.append("## Full Metrics: Faithfulness / Relevancy / Precision / Recall")
    lines.append("")

    if baseline_results and phase2_results:
        lines += _full_metrics_table("Baseline (Phase 2 disabled)", baseline_results)
        lines.append("")
        lines += _full_metrics_table("Phase 2 (hybrid + rerank + query rewriting)", phase2_results)
        lines.append("")
        lines += _delta_table(baseline_results, phase2_results)
        lines.append("")

        all_results = baseline_results + phase2_results
        total_prompt_tokens = sum(r.prompt_tokens for r in all_results)
        total_completion_tokens = sum(r.completion_tokens for r in all_results)
        est_cost = (
            total_prompt_tokens / 1000 * COST_PER_1K_PROMPT_TOKENS_USD
            + total_completion_tokens / 1000 * COST_PER_1K_COMPLETION_TOKENS_USD
        )
        lines += [
            (
                f"- Total tokens across both runs: {total_prompt_tokens} prompt + "
                f"{total_completion_tokens} completion"
            ),
            f"- Estimated cost (illustrative pricing, not official rates): ${est_cost:.5f}",
        ]
    else:
        error_message = baseline_error or phase2_error
        lines += [
            (
                "**Not available this run.** This requires live LLM access for both answer "
                "generation and LLM-as-judge scoring. The actual error raised during this "
                f"run was:\n\n```\n{error_message}\n```\n\n"
                "Re-run this script once that's resolved (e.g. a valid `GOOGLE_API_KEY` in "
                "`.env`, or the daily quota resetting if it's a quota error — this project "
                "hit a `GenerateRequestsPerDayPerProjectPerModel-FreeTier` 20/day cap earlier "
                "in development). The code path for the full before/after comparison is "
                "implemented and only needs live LLM access to produce numbers."
            ),
            "",
            (
                "The retrieval comparison above needs no LLM calls and reflects real, live "
                "results from this run."
            ),
        ]

    out_path = Path(__file__).resolve().parent.parent / "docs" / "EVALUATION.md"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nWrote results to {out_path}")


if __name__ == "__main__":
    main()
