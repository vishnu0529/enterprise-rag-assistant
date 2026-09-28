"""Regenerates the golden-set trend chart embedded in docs/EVALUATION.md from
eval/metrics_history.jsonl (one JSON record per scripts/run_golden_set.py
run). Uses a Mermaid xychart-beta block, which GitHub renders natively in
Markdown, with no image generation, no extra dependencies.

Run this after scripts/run_golden_set.py, once metrics_history.jsonl has at
least one record. CI runs both, in order, on every push to main, which is
what makes the chart move over time instead of being a one-off snapshot.

Usage:
    ./venv/bin/python scripts/update_eval_chart.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "eval" / "metrics_history.jsonl"
EVALUATION_MD = ROOT / "docs" / "EVALUATION.md"
START_MARKER = "<!-- EVAL_TREND_START -->"
END_MARKER = "<!-- EVAL_TREND_END -->"
MAX_POINTS = 12


def _load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    lines = HISTORY_PATH.read_text().strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _render_chart(records: list[dict]) -> str:
    if not records:
        return (
            "_No CI runs recorded yet. This section fills in once "
            "`scripts/run_golden_set.py` has run at least once with a live "
            "API key (see above) and committed to `eval/metrics_history.jsonl`._"
        )

    recent = records[-MAX_POINTS:]
    shas = [r["commit"] for r in recent]
    pass_rates = [r["pass_rate_pct"] for r in recent]
    p95s = [r["p95_latency_ms"] for r in recent]
    max_p95 = max(p95s) if p95s else 1
    y_max = max(100, int(max_p95 * 1.2))

    lines = [
        "```mermaid",
        "xychart-beta",
        '    title "Golden set: pass rate (%) and p95 latency (ms) by CI run"',
        f"    x-axis [{', '.join(shas)}]",
        f'    y-axis "value" 0 --> {y_max}',
        f'    bar "pass rate %" [{", ".join(str(v) for v in pass_rates)}]',
        f'    line "p95 latency ms" [{", ".join(str(v) for v in p95s)}]',
        "```",
        "",
    ]
    latest = recent[-1]
    cost_per_task = latest.get("cost_per_task_usd")
    cost_note = f", ${cost_per_task:.6f}/task" if cost_per_task is not None else ""
    summary = (
        f"Last run: {latest['n_pass']}/{latest['n_items']} passed "
        f"({latest['n_trap_pass']}/{latest['n_traps']} traps refused correctly), "
        f"p95 latency {latest['p95_latency_ms']:.0f} ms, "
        f"cost ${latest['total_cost_usd']:.5f}{cost_note}, commit `{latest['commit']}`."
    )
    lines.append(summary)
    return "\n".join(lines)


def main() -> None:
    records = _load_history()
    chart = _render_chart(records)

    content = EVALUATION_MD.read_text()
    if START_MARKER not in content or END_MARKER not in content:
        raise SystemExit(
            f"{EVALUATION_MD} is missing {START_MARKER}/{END_MARKER} markers. "
            "add them once, manually, around the section this script should own."
        )

    before, rest = content.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    new_content = f"{before}{START_MARKER}\n{chart}\n{END_MARKER}{after}"
    EVALUATION_MD.write_text(new_content)
    print(f"Updated chart in {EVALUATION_MD} from {len(records)} recorded run(s).")


if __name__ == "__main__":
    main()
