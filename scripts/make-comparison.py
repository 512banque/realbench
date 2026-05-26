#!/usr/bin/env python3
"""Generate the wall-time comparison chart for the README.

Reads a runs JSONL file (results/runs.jsonl by default, or REALBENCH_RUNS)
and renders a LONG VERTICAL chart with every (task, agent) cell laid out as
a horizontal bar. Output: docs/realbench-comparison.png.

The chart is intentionally tall (one bar per cell instead of the
previous grouped-bar layout limited to 5 showcase tasks) so the reader
can scroll through the full battery without losing any cells.

Publication charts normally read results/runs-en-135.jsonl via REALBENCH_RUNS:
five EN-prompt runs per public agent and task. Strict pass means success=true;
timeouts and anti-tamper trips remain visible as failures.
"""

from __future__ import annotations

import json
import os
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

BENCH = Path(__file__).resolve().parent.parent
RUNS = Path(os.environ.get("REALBENCH_RUNS", BENCH / "results" / "runs.jsonl"))
OUT = Path(os.environ.get("REALBENCH_COMPARISON_OUT", BENCH / "docs" / "realbench-comparison.png"))

# All tasks of the battery, in canonical order.
TASKS = [
    "001-fizzbuzz",
    "002-fix-bug",
    "003-implement-spec",
    "004-laravel-migrate",
    "005-race-condition",
    "006-lru-race",
    "007-deadlock",
    "008-debounce-leak",
    "009-refactor-god-controller",
    "010-goroutine-leak",
    "011-channel-deadlock",
    "012-context-propagation",
    "013-extract-package",
    "014-promise-race-leak",
    "015-react-effect-cleanup",
    "016-event-emitter-memory",
    "017-tokio-select-cancel",
    "018-arc-mutex-deadlock",
    "019-chained-bugs",
    "020-ambiguous-cache",
    "021-retry-orchestrator",
    "022-state-machine",
    "023-config-merger",
    "024-caddy-intercept-header",
    "025-policy-override",
    "026-effective-date",
    "027-no-rule-canary",
]

# Agent display order (top to bottom within each task block).
AGENTS = [
    "claude-code",
    "codex",
    "qwen-code",
    "opencode",
    "pi-ds4pro",
    "pi-flash",
    "pi-gemini",
    "pi-glm",
    "claude-deepseek",
]

COLORS = {
    "claude-code":     "#D97757",
    "codex":           "#10A37F",
    "claude-deepseek": "#7C3AED",
    "qwen-code":       "#EF4444",
    "opencode":        "#84CC16",
    "pi-ds4pro":       "#EC4899",
    "pi-flash":        "#F472B6",
    "pi-gemini":       "#FBBF24",
    "pi-glm":          "#8B5CF6",
}

DISPLAY_LABELS = {
    "opencode": "opencode-DS4pro",
    "pi-ds4pro": "pi-ds4pro",
    "pi-flash": "pi-flash",
    "pi-glm": "pi-glm",
}

def load_medians() -> tuple[dict[tuple[str, str], float], set[tuple[str, str]]]:
    """Return (medians, failed_cells).

    Strict pass is `success == True`; timeouts and anti-tamper trips remain
    visible as failed observed cells.
    """
    succ: dict[tuple[str, str], list[float]] = {}
    tried: set[tuple[str, str]] = set()
    succeeded: set[tuple[str, str]] = set()
    for line in RUNS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        k = (r["agent"], r["task"])
        if k[0] not in AGENTS or k[1] not in TASKS:
            continue
        tried.add(k)
        if r.get("success"):
            succ.setdefault(k, []).append(r["wall_time_sec"])
            succeeded.add(k)
    failed = tried - succeeded
    return {k: statistics.median(v) for k, v in succ.items()}, failed


def make_chart(medians: dict[tuple[str, str], float],
               failed: set[tuple[str, str]]) -> None:
    n_tasks = len(TASKS)
    n_agents = len(AGENTS)
    rows_per_task = n_agents  # one row per agent in each task block

    # Layout — vertical with one row per (task, agent) cell, grouped
    # visually by task. Row 0 sits at the TOP for natural top-down read
    # order (task 001 at top, task 024 at bottom).
    row_h = 0.42  # height of each bar in axis units
    gap_within_task = 0.05
    gap_between_tasks = 1.4

    # Compute y position for each (task, agent)
    positions: dict[tuple[str, str], float] = {}
    task_label_positions: dict[str, float] = {}
    y_cursor = 0.0
    for task in TASKS:
        task_top = y_cursor
        for agent in AGENTS:
            y_cursor += row_h + gap_within_task
            positions[(task, agent)] = y_cursor
        task_label_positions[task] = (task_top + y_cursor) / 2 + row_h / 2
        y_cursor += gap_between_tasks
    y_max_axis = y_cursor

    # Figure size: ~14 inches wide, height scaled to row count
    fig_h = y_max_axis * 0.13 + 2.5  # heuristic
    fig, ax = plt.subplots(figsize=(14, fig_h), dpi=110)
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")

    # Compute global ymax over wall_time values for x-axis scaling
    all_wall = [v for v in medians.values()]
    x_max = max(all_wall) * 1.05 if all_wall else 1.0
    fail_marker_w = x_max * 0.025

    for task in TASKS:
        for agent in AGENTS:
            y = positions[(task, agent)]
            m = medians.get((agent, task))
            if m is not None:
                ax.barh(y, m, height=row_h, color=COLORS[agent],
                        edgecolor="white", linewidth=0.4)
                # Numeric label at the end of the bar
                ax.text(m + x_max * 0.005, y, f"{m:.0f}s",
                        va="center", ha="left", fontsize=7, color="#333")
            elif (agent, task) in failed:
                # Tried but failed — pale agent-coloured bar with hatched
                # overlay and an "F" letter.
                ax.barh(y, fail_marker_w, height=row_h, color=COLORS[agent],
                        edgecolor=COLORS[agent], linewidth=0.5,
                        alpha=0.25, hatch="///")
                ax.text(fail_marker_w + x_max * 0.005, y, "F",
                        va="center", ha="left", fontsize=8,
                        color=COLORS[agent], weight="bold")
            # else: never run — nothing drawn (blank row)

            # Agent label on the LEFT of each row (small, grey)
            ax.text(-x_max * 0.005, y, DISPLAY_LABELS.get(agent, agent), va="center", ha="right",
                    fontsize=7, color="#555")

    # Task headers — left of the block, large
    for task, y_label in task_label_positions.items():
        ax.text(-x_max * 0.18, y_label, task, va="center", ha="left",
                fontsize=10, weight="bold", color="#111")

    # Invert y so task 001 is at the top
    ax.invert_yaxis()
    ax.set_xlim(-x_max * 0.20, x_max)
    ax.set_ylim(y_max_axis, -0.5)

    # X axis cosmetic
    ax.set_xlabel("Wall time (seconds, median across runs)",
                  fontsize=10, color="#333")
    ax.tick_params(axis="x", colors="#444")
    ax.tick_params(axis="y", length=0, labelleft=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#CCC")
    ax.grid(axis="x", linestyle="--", color="#E5E5E5", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    # Title and subtitle as fig.text
    fig.suptitle(
        "realbench — wall time per (task, agent), median across runs",
        fontsize=14, x=0.02, y=0.995, ha="left", weight="bold",
    )
    fig.text(0.02, 0.985,
             f"{len(TASKS)} tasks × {len(AGENTS)} agents = {len(TASKS) * len(AGENTS)} cells.  "
             "Coloured bar: strict pass.  Pale 'F': timeout, verify failure, or anti-tamper failure.  Blank: not run.",
             fontsize=8.5, color="#666", ha="left", va="top")

    plt.subplots_adjust(left=0.16, right=0.97, top=0.97, bottom=0.02)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"wrote {OUT}  (size ≈ {fig_h:.1f}in tall × 14in wide)")


if __name__ == "__main__":
    medians, failed = load_medians()
    make_chart(medians, failed)
