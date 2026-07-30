"""Runs a fixed Q&A evaluation set against the RAG pipeline and writes a
results report to docs/EVALUATION.md.

Usage:
    ./venv/bin/python scripts/run_evaluation.py
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.db import init_db
from app.services.evaluation import evaluate_question
from app.services.ingestion import chunk_document, load_text
from app.services.vector_store import upsert_chunks

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


def main() -> None:
    init_db()

    sample_doc = Path(__file__).resolve().parent.parent / "sample_docs" / "company_handbook.md"
    pages = load_text(sample_doc)
    chunks = chunk_document("eval-doc", sample_doc.name, pages)
    upsert_chunks(chunks)

    results = []
    for item in EVAL_SET:
        r = evaluate_question(item["question"], ground_truth=item["ground_truth"])
        results.append(r)
        print(
            f"Q: {item['question']}\n"
            f"  faithfulness={r.faithfulness:.2f} relevancy={r.answer_relevancy:.2f} "
            f"precision={r.context_precision:.2f} recall={r.context_recall:.2f} "
            f"latency={r.latency_ms:.0f}ms"
        )

    def avg(field: str) -> float:
        return statistics.mean(getattr(r, field) for r in results)

    total_prompt_tokens = sum(r.prompt_tokens for r in results)
    total_completion_tokens = sum(r.completion_tokens for r in results)
    est_cost = (
        total_prompt_tokens / 1000 * COST_PER_1K_PROMPT_TOKENS_USD
        + total_completion_tokens / 1000 * COST_PER_1K_COMPLETION_TOKENS_USD
    )

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
        "**Averages**",
        "",
        f"- Faithfulness: {avg('faithfulness'):.2f}",
        f"- Answer Relevancy: {avg('answer_relevancy'):.2f}",
        f"- Context Precision: {avg('context_precision'):.2f}",
        f"- Context Recall: {avg('context_recall'):.2f}",
        f"- Mean Latency: {avg('latency_ms'):.0f} ms",
        f"- Total tokens: {total_prompt_tokens} prompt + {total_completion_tokens} completion",
        f"- Estimated cost (illustrative pricing, not official rates): ${est_cost:.5f}",
    ]

    out_path = Path(__file__).resolve().parent.parent / "docs" / "EVALUATION.md"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nWrote results to {out_path}")


if __name__ == "__main__":
    main()
