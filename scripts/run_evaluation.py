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
# Deliberately spans five of the seven corpus documents, so this fixed set
# also exercises multi-document retrieval, not just single-file recall.
EVAL_SET = [
    {
        "question": "What is Aldermere Advisory's professional indemnity insurance cover per claim?",  # noqa: E501
        "ground_truth": "Professional indemnity insurance of £5 million per claim.",
    },
    {
        "question": "By how many working days did the finance function redesign engagement reduce month-end close, and from what starting point?",  # noqa: E501
        "ground_truth": "Month-end close was reduced from 12 working days to 5 working days.",  # noqa: E501
    },
    {
        "question": "What is the day rate for a Senior Consultant?",
        "ground_truth": "£1,050 per day, excluding VAT.",
    },
    {
        "question": "What are Aldermere's standard payment terms?",
        "ground_truth": "Net 30 days from invoice date, invoiced monthly in arrears unless the proposal specifies fixed-price milestone billing.",  # noqa: E501
    },
    {
        "question": "Who led the AI-augmented document review pilot for the regional law firm, and what is their relevant qualification?",  # noqa: E501
        "ground_truth": "Dr Ines Falk led the pilot; she holds a PhD in Computer Science (natural language processing) from the University of Edinburgh.",  # noqa: E501
    },
    {
        "question": "What is the liability cap in Aldermere's standard commercial terms?",
        "ground_truth": "Liability is capped at 100% of fees paid in the preceding 12 months, except for gross negligence, wilful misconduct, or breach of confidentiality, which are uncapped.",  # noqa: E501
    },
]

# Illustrative only, NOT official pricing — update with current provider rates
# before relying on this for real cost tracking.
COST_PER_1K_PROMPT_TOKENS_USD = 0.000075
COST_PER_1K_COMPLETION_TOKENS_USD = 0.0003


def main() -> None:
    init_db()

    corpus_dir = Path(__file__).resolve().parent.parent / "sample_docs" / "proposal_corpus"
    for i, doc_path in enumerate(sorted(corpus_dir.glob("*.md"))):
        pages = load_text(doc_path)
        chunks = chunk_document(f"eval-doc-{i}", doc_path.name, pages)
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
            f"`sample_docs/proposal_corpus/` (7 documents), using `{settings.LLM_MODEL}` "
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
