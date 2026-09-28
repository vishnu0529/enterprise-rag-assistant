"""Scores eval/golden_set.json (38 answerable questions + 12 deliberate traps)
against the real corrective-RAG graph and writes a results report to
eval/golden_set_results.md.

Answerable items are scored with the same RAGAS-methodology metrics as
scripts/run_evaluation.py. Trap items have no ground truth; a trap "passes"
when the answer contains an explicit refusal (per the SYSTEM_PROMPT in
app/services/rag_chain.py), and "fails" if the model fabricates a specific
answer instead. This is the honesty check the plain accuracy metrics can't
catch on their own: a model that just makes things up fluently can still
score well on faithfulness against context it retrieved for the wrong
reasons, but it cannot fake a correct refusal on a question the corpus
genuinely doesn't answer.

Also logs cost-per-run and p95 latency, appends a record to
eval/metrics_history.jsonl, and writes eval/golden_set_metrics.json in
shields.io's endpoint-badge format. CI updates both on every run to main,
which is what makes the README badge and trend chart move over time instead
of being a one-off snapshot.

Usage:
    ./venv/bin/python scripts/run_golden_set.py
"""

import json
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.cost import estimate_cost_usd
from app.core.db import init_db
from app.services.evaluation import evaluate_question
from app.services.ingestion import chunk_document, load_text
from app.services.rag_chain import is_refusal
from app.services.rag_graph import answer_question_agentic
from app.services.vector_store import upsert_chunks

MIN_FAITHFULNESS = 0.7
MIN_CONTEXT_RECALL = 0.5


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def _ingest_corpus() -> None:
    corpus_dir = Path(__file__).resolve().parent.parent / "sample_docs" / "proposal_corpus"
    for i, doc_path in enumerate(sorted(corpus_dir.glob("*.md"))):
        pages = load_text(doc_path)
        chunks = chunk_document(f"golden-doc-{i}", doc_path.name, pages)
        upsert_chunks(chunks)


def _score_answerable(item: dict) -> dict:
    result = evaluate_question(item["question"], ground_truth=item["expected_answer"])
    passed = result.faithfulness >= MIN_FAITHFULNESS and result.context_recall >= MIN_CONTEXT_RECALL
    return {
        "id": item["id"],
        "category": item["category"],
        "passed": passed,
        "faithfulness": result.faithfulness,
        "context_recall": result.context_recall,
        "answer_relevancy": result.answer_relevancy,
        "latency_ms": result.latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "answer": result.answer,
    }


def _score_trap(item: dict) -> dict:
    result = answer_question_agentic(item["question"])
    passed = is_refusal(result["answer"])
    return {
        "id": item["id"],
        "category": "trap",
        "passed": passed,
        "latency_ms": result["latency_ms"],
        "prompt_tokens": result.get("prompt_tokens", 0),
        "completion_tokens": result.get("completion_tokens", 0),
        "answer": result["answer"],
    }


def main() -> None:
    init_db()
    _ingest_corpus()

    golden_set = json.loads(
        (Path(__file__).resolve().parent.parent / "eval" / "golden_set.json").read_text()
    )
    items = golden_set["items"]

    results = []
    for item in items:
        scorer = _score_trap if item["category"] == "trap" else _score_answerable
        r = scorer(item)
        results.append(r)
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['id']} ({r['category']})")

    answerable_results = [r for r in results if r["category"] != "trap"]
    trap_results = [r for r in results if r["category"] == "trap"]

    n_pass = sum(1 for r in results if r["passed"])
    n_trap_pass = sum(1 for r in trap_results if r["passed"])

    overview = (
        f"Run against all {len(items)} items in `eval/golden_set.json` "
        f"({len(answerable_results)} answerable, {len(trap_results)} traps) "
        "through the real corrective-RAG graph."
    )
    overall = (
        f"**Overall: {n_pass}/{len(items)} passed "
        f"({n_trap_pass}/{len(trap_results)} traps correctly refused).**"
    )
    trap_note = (
        'A trap "pass" means the model refused rather than fabricating an '
        "answer. This is the metric that actually matters for a bid team, "
        "since a hallucinated commercial term in a real proposal is far more "
        "costly than a missed factual lookup."
    )
    lines = [
        "# Golden Set Results",
        "",
        overview,
        "",
        overall,
        "",
        trap_note,
        "",
        "| ID | Category | Result | Faithfulness | Context Recall | Latency (ms) |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        faith = f"{r['faithfulness']:.2f}" if "faithfulness" in r else "n/a"
        recall = f"{r['context_recall']:.2f}" if "context_recall" in r else "n/a"
        row = (
            f"| {r['id']} | {r['category']} | {status} | {faith} | "
            f"{recall} | {r['latency_ms']:.0f} |"
        )
        lines.append(row)

    if answerable_results:
        avg_faith = statistics.mean(r["faithfulness"] for r in answerable_results)
        avg_recall = statistics.mean(r["context_recall"] for r in answerable_results)
        avg_relevancy = statistics.mean(r["answer_relevancy"] for r in answerable_results)
        lines += [
            "",
            "**Answerable-item averages**",
            "",
            f"- Faithfulness: {avg_faith:.2f}",
            f"- Context recall: {avg_recall:.2f}",
            f"- Answer relevancy: {avg_relevancy:.2f}",
        ]

    latencies = [r["latency_ms"] for r in results]
    p50_latency = _percentile(latencies, 50)
    p95_latency = _percentile(latencies, 95)
    mean_latency = statistics.mean(latencies)
    total_prompt_tokens = sum(r.get("prompt_tokens", 0) for r in results)
    total_completion_tokens = sum(r.get("completion_tokens", 0) for r in results)
    total_cost = estimate_cost_usd(total_prompt_tokens, total_completion_tokens)
    cost_per_task = total_cost / len(results) if results else 0.0

    latency_line = (
        f"- p50 latency: {p50_latency:.0f} ms &middot; "
        f"p95 latency: {p95_latency:.0f} ms (mean: {mean_latency:.0f} ms)"
    )
    cost_line = (
        f"- Estimated cost (illustrative pricing, not official rates): "
        f"${total_cost:.5f} total, ${cost_per_task:.6f}/task"
    )
    lines += [
        "",
        "**Cost and latency**",
        "",
        latency_line,
        f"- Total tokens: {total_prompt_tokens} prompt + {total_completion_tokens} completion",
        cost_line,
    ]

    failed = [r for r in results if not r["passed"]]
    if failed:
        lines += ["", "## Failed items (for debugging)", ""]
        for r in failed:
            lines.append(f"- **{r['id']}**: {r['answer'][:200]}")

    eval_dir = Path(__file__).resolve().parent.parent / "eval"
    out_path = eval_dir / "golden_set_results.md"
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\n{n_pass}/{len(items)} passed. Wrote results to {out_path}")

    pct = round(100 * n_pass / len(items))
    if pct == 100:
        color = "brightgreen"
    elif pct >= 90:
        color = "green"
    elif pct >= 75:
        color = "yellow"
    else:
        color = "red"
    badge = {
        "schemaVersion": 1,
        "label": "golden set",
        "message": f"{n_pass}/{len(items)} ({pct}%)",
        "color": color,
    }
    (eval_dir / "golden_set_metrics.json").write_text(json.dumps(badge, indent=2) + "\n")

    history_record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "commit": _git_sha(),
        "n_items": len(items),
        "n_pass": n_pass,
        "n_traps": len(trap_results),
        "n_trap_pass": n_trap_pass,
        "pass_rate_pct": pct,
        "p50_latency_ms": round(p50_latency, 1),
        "p95_latency_ms": round(p95_latency, 1),
        "mean_latency_ms": round(mean_latency, 1),
        "total_cost_usd": round(total_cost, 5),
        "cost_per_task_usd": round(cost_per_task, 6),
    }
    with (eval_dir / "metrics_history.jsonl").open("a") as f:
        f.write(json.dumps(history_record) + "\n")

    if n_trap_pass < len(trap_results):
        sys.exit(1)


if __name__ == "__main__":
    main()
