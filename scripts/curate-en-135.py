#!/usr/bin/env python3
"""Build the comparable EN 5-run snapshot used by publication charts.

The public repo ships a clean 1215-row results/runs.jsonl. This script is kept
as the deterministic definition of the comparable slice: exactly five valid EN
records per public (agent, task). It is idempotent on the public snapshot.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path


BENCH = Path(__file__).resolve().parent.parent
RAW_RUNS = BENCH / "results" / "runs.jsonl"
OUT = BENCH / "results" / "runs-en-135.jsonl"

# Tasks 001-023 were originally run with French prompts, then translated to
# English before the publication rerun batch. Historical rows do not carry a
# prompt_lang field, so the public slice uses the first post-translation rerun
# boundary captured in raw timestamps. Tasks 024-027 were authored in English.
PROMPT_EN_CUTOFF_UTC = dt.datetime.fromisoformat("2026-05-24T20:22:57+00:00")
TRANSLATED_PROMPT_TASK_PREFIXES = {f"{i:03d}" for i in range(1, 24)}

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

def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def is_en_prompt_record(record: dict) -> bool:
    task = str(record.get("task") or "")
    if task[:3] not in TRANSLATED_PROMPT_TASK_PREFIXES:
        return True
    timestamp = record.get("timestamp")
    if not timestamp:
        return False
    try:
        ts = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    return ts >= PROMPT_EN_CUTOFF_UTC


def is_runner_infra_record(record: dict) -> bool:
    """Drop records where the runner itself failed before a real attempt.

    Agent timeouts are kept. They are real harness outcomes and count as
    strict failures even when the workspace happens to verify.
    """
    if record.get("runner_error"):
        return True
    return (
        not record.get("success")
        and record.get("agent_exit_code") is None
        and record.get("verify_exit_code") is None
    )


def sort_key(record: dict) -> tuple[str, int, str]:
    return (
        str(record.get("timestamp") or ""),
        int(record.get("run_index") or 0),
        str(record.get("run_id") or ""),
    )


def main() -> int:
    rows = load_jsonl(RAW_RUNS)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in rows:
        agent = record.get("agent")
        task = record.get("task")
        if agent not in AGENTS or task not in TASKS:
            continue
        if not is_en_prompt_record(record) or is_runner_infra_record(record):
            continue
        record = dict(record)
        record["agent"] = agent
        groups[(agent, task)].append(record)

    selected: list[dict] = []
    trimmed: list[tuple[str, str, int, list[tuple[int | None, bool, str | None]]]] = []
    missing: list[tuple[str, str, int]] = []
    for agent in AGENTS:
        for task in TASKS:
            records = sorted(groups[(agent, task)], key=sort_key)
            if len(records) < 5:
                missing.append((agent, task, len(records)))
                continue
            selected.extend(records[:5])
            if len(records) > 5:
                trimmed.append(
                    (
                        agent,
                        task,
                        len(records),
                        [
                            (
                                record.get("run_index"),
                                bool(record.get("success")),
                                record.get("run_id"),
                            )
                            for record in records[5:]
                        ],
                    )
                )

    if missing:
        print("missing comparable records:")
        for agent, task, count in missing:
            print(f"  {agent:16s} {task:26s} count={count}")
        return 1

    selected.sort(
        key=lambda record: (
            AGENTS.index(record["agent"]),
            TASKS.index(record["task"]),
            *sort_key(record),
        )
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(record, sort_keys=True) for record in selected) + "\n")

    print(f"wrote {OUT} rows={len(selected)}")
    for agent in AGENTS:
        records = [record for record in selected if record.get("agent") == agent]
        passed = sum(bool(record.get("success")) for record in records)
        print(f"{agent:16s} rows={len(records):3d} pass={passed:3d} fail={len(records) - passed:2d}")

    if trimmed:
        print("trimmed extras:")
        for agent, task, count, extras in trimmed:
            print(f"  {agent:16s} {task:26s} count={count} extras={extras}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
