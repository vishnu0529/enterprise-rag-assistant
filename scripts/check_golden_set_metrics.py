"""CI gate: fail unless eval/golden_set_metrics.json still shows a full pass.

Deliberately does not call a live LLM. See the eval-gate job's comment in
.github/workflows/ci.yml for why: re-running the golden set on every push
burns real API credits and broke CI when the configured key ran out.
"""

import json
import sys

METRICS_PATH = "eval/golden_set_metrics.json"


def main() -> int:
    with open(METRICS_PATH) as f:
        metrics = json.load(f)

    print(f"golden set: {metrics['message']}")
    if metrics["color"] != "brightgreen":
        print(
            f"golden-set gate: committed result in {METRICS_PATH} is not a "
            f"full pass ({metrics['message']}). Re-run "
            "scripts/run_golden_set.py with a working LLM key and commit "
            "the refreshed eval/ files.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
