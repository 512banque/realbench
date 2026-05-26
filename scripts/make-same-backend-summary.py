#!/usr/bin/env python3
"""Print the DeepSeek V4 Pro same-backend cost summary used in README.md."""

from __future__ import annotations

import json
import os
import statistics
from collections import defaultdict
from pathlib import Path


BENCH = Path(__file__).resolve().parent.parent
RUNS = Path(os.environ.get("REALBENCH_RUNS", BENCH / "results" / "runs-en-135.jsonl"))

AGENTS = ["claude-deepseek", "opencode", "pi-ds4pro"]
BASELINE = "pi-ds4pro"
DISPLAY = {"opencode": "opencode-DS4pro"}

# DeepSeek V4 Pro list price, USD per 1M tokens.
PRICE = {"input": 0.435, "cache_read": 0.003625, "output": 0.87}


def token_cost(metrics: dict) -> float:
    input_tokens = metrics.get("input_tokens") or 0
    cache_read = metrics.get("cache_read_input_tokens") or metrics.get("cached_input_tokens") or 0
    output_tokens = metrics.get("output_tokens") or 0
    return (
        input_tokens * PRICE["input"]
        + cache_read * PRICE["cache_read"]
        + output_tokens * PRICE["output"]
    ) / 1_000_000


def main() -> int:
    per_task: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    with RUNS.open() as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            agent = record.get("agent")
            if agent not in AGENTS:
                continue
            per_task[agent][record["task"]] += token_cost(record.get("native_metrics") or {})

    baseline = per_task[BASELINE]
    print("| Harness | Total cost, 135 runs | Median per-task spend (sum of 5 runs), across the 27 tasks | Std-dev of per-task spend across the 27 tasks | Paired note |")
    print("| --- | ---: | ---: | ---: | --- |")
    for agent in AGENTS:
        values = list(per_task[agent].values())
        if len(values) != 27:
            raise SystemExit(f"{agent}: expected 27 task bundles, got {len(values)}")
        total = sum(values)
        median = statistics.median(values)
        stdev = statistics.pstdev(values)
        if agent == BASELINE:
            note = "Cheapest total on the shared DeepSeek V4 Pro target"
        else:
            more_expensive = sum(
                1 for task, cost in per_task[agent].items() if cost > baseline[task]
            )
            note = f"More expensive than `{BASELINE}` on {more_expensive}/27 tasks"
        label = DISPLAY.get(agent, agent)
        print(f"| `{label}` | ${total:.2f} | ${median:.3f} | ${stdev:.3f} | {note} |")
    print()
    print("Directional, not a formal significance test: N=5 runs per task.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
