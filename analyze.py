#!/usr/bin/env python3
"""Summarize results/runs.jsonl as a markdown table to stdout."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
RUNS_FILE = BENCH_DIR / "results" / "runs.jsonl"


def load_runs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def median_or_none(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def fmt_num(x, kind="float"):
    if x is None:
        return "—"
    if kind == "int":
        return f"{int(round(x))}"
    return f"{x:.1f}"


_QUALITY_LANGS = ("python", "go", "typescript", "rust", "php")


def _quality_violations(record: dict):
    """Best-effort total violations across linters for a run.

    Returns None if no quality_metrics, or if every detected language linter
    was unavailable. Sums violations_total across detected languages otherwise.
    """
    q = record.get("quality_metrics")
    if not isinstance(q, dict):
        return None
    langs = q.get("languages_detected") or []
    if not langs:
        return None
    total = 0
    saw_any = False
    for lang in langs:
        sect = q.get(lang)
        if not isinstance(sect, dict):
            continue
        if sect.get("available") is False:
            continue
        v = sect.get("violations_total")
        if v is None:
            continue
        total += int(v)
        saw_any = True
    return total if saw_any else None


def summarize(runs: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in runs:
        groups[(r.get("agent", "?"), r.get("task", "?"))].append(r)

    rows = []
    for (agent, task), rs in sorted(groups.items()):
        n = len(rs)
        wins = sum(1 for r in rs if r.get("success"))
        timeouts = sum(1 for r in rs if r.get("agent_timeout"))
        nonzero = sum(
            1 for r in rs
            if (r.get("agent_exit_code") not in (None, 0))
        )
        walls = [r.get("wall_time_sec") for r in rs]

        in_toks, out_toks = [], []
        qualities: list[int] = []
        for r in rs:
            nm = r.get("native_metrics") or {}
            it = nm.get("input_tokens")
            ot = nm.get("output_tokens")
            if it is not None:
                in_toks.append(it)
            if ot is not None:
                out_toks.append(ot)
            q = _quality_violations(r)
            if q is not None:
                qualities.append(q)

        rows.append({
            "agent": agent,
            "task": task,
            "n": n,
            "successes": wins,
            "median_wall": median_or_none(walls),
            "median_input_tokens": median_or_none(in_toks),
            "median_output_tokens": median_or_none(out_toks),
            "nonzero_exits": nonzero,
            "timeouts": timeouts,
            "median_quality_violations": median_or_none(qualities),
        })
    return rows


def render_markdown(rows: list[dict]) -> str:
    headers = [
        "agent", "task", "success",
        "median wall (s)", "median input tok", "median output tok",
        "non-zero exits", "timeouts", "median quality",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for r in rows:
        lines.append(
            "| " + " | ".join([
                r["agent"],
                r["task"],
                f"{r['successes']}/{r['n']}",
                fmt_num(r["median_wall"]),
                fmt_num(r["median_input_tokens"], "int"),
                fmt_num(r["median_output_tokens"], "int"),
                str(r["nonzero_exits"]),
                str(r["timeouts"]),
                fmt_num(r.get("median_quality_violations"), "int"),
            ]) + " |"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs-file", default=str(RUNS_FILE))
    args = ap.parse_args()

    runs = load_runs(Path(args.runs_file))
    if not runs:
        print(f"(no runs found in {args.runs_file})")
        return 0

    rows = summarize(runs)
    print(f"# Bench results ({len(runs)} runs)\n")
    print(render_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
