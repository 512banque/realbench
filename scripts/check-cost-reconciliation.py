#!/usr/bin/env python3
"""Cross-check chart costs against native harness-reported costs when present."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path


BENCH = Path(__file__).resolve().parent.parent
RUNS = Path(os.environ.get("REALBENCH_RUNS", BENCH / "results" / "runs-en-135.jsonl"))

# Only Pi-family agents currently expose a run-level cost field that is directly
# comparable to the chart calculation.
PI_AGENTS = {"pi-ds4pro", "pi-flash", "pi-gemini", "pi-glm"}


def main() -> int:
    totals = defaultdict(float)
    rows = defaultdict(int)
    missing = defaultdict(int)
    for line in RUNS.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        agent = record.get("agent")
        if agent not in PI_AGENTS:
            continue
        rows[agent] += 1
        value = (record.get("native_metrics") or {}).get("pi_reported_cost_usd")
        if isinstance(value, (int, float)):
            totals[agent] += float(value)
        else:
            missing[agent] += 1

    print("| Agent | Rows | Rows with Pi cost | Pi-reported cost sum | Missing run-cost rows |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for agent in sorted(PI_AGENTS):
        present = rows[agent] - missing[agent]
        print(
            f"| `{agent}` | {rows[agent]} | {present} | "
            f"${totals[agent]:.6f} | {missing[agent]} |"
        )
    print()
    print("Provider invoices are not expected to match this table unless the invoice")
    print("is filtered to exactly the same project, time window, model, and runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
