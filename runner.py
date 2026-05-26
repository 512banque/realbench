#!/usr/bin/env python3
"""Bench runner. Compare coding-agent CLIs on identical tasks.

Reads tasks/ and agents/, executes the matrix, writes results/runs.jsonl.
Per-run artifacts live in results/raw/<run_id>/ and results/workspaces/<run_id>/.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # graceful fallback if tqdm not installed
    def tqdm(iterable, **kwargs):
        return iterable


BENCH_DIR = Path(__file__).resolve().parent
AGENTS_DIR = BENCH_DIR / "agents"
TASKS_DIR = BENCH_DIR / "tasks"
RESULTS_DIR = BENCH_DIR / "results"
RUNS_FILE = RESULTS_DIR / "runs.jsonl"

DEFAULT_AGENTS = ["claude-code", "codex", "qwen-code", "opencode", "pi-ds4pro", "pi-flash", "pi-gemini", "pi-glm", "claude-deepseek"]
ALL_AGENTS = DEFAULT_AGENTS.copy()
# qwen-code: requires ~/qwen/.qwen-env (DashScope key).
# pi-ds4pro: Pi CLI + DeepSeek V4 Pro. Reads DEEPSEEK_API_KEY from ~/deepseek/.deepseek-env.
# pi-glm: Pi CLI + Z.ai GLM 5.1 through OpenRouter. Reads OPENROUTER_API_KEY from a user-local env file.
# opencode: anomalyco/opencode + DeepSeek V4 Pro. Same DeepSeek key source.
DEFAULT_TASKS = [
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


# ---------------------------------------------------------------------------
# Discovery helpers


def list_agents() -> list[str]:
    return [p.stem for p in AGENTS_DIR.glob("*.sh")]


def list_tasks() -> list[str]:
    return sorted(p.name for p in TASKS_DIR.iterdir() if p.is_dir())


def resolve_agents(spec: str | None) -> list[str]:
    if spec is None:
        return DEFAULT_AGENTS
    parts = [a.strip() for a in spec.split(",") if a.strip()]
    return parts


def resolve_tasks(spec: str | None) -> list[str]:
    """Accepts either '001' or '001-fizzbuzz'. Resolves to full task dir name."""
    available = list_tasks()
    if spec is None:
        return [t for t in DEFAULT_TASKS if t in available]
    parts = [s.strip() for s in spec.split(",") if s.strip()]
    resolved = []
    for p in parts:
        match = next(
            (t for t in available if t == p or t.startswith(p + "-")),
            None,
        )
        if match is None:
            raise SystemExit(f"unknown task: {p!r} (available: {available})")
        resolved.append(match)
    return resolved


# ---------------------------------------------------------------------------
# Validation


def validate(agents: list[str], tasks: list[str]) -> list[str]:
    """Return list of error strings. Empty means everything is OK."""
    errors: list[str] = []

    for a in agents:
        wrapper = AGENTS_DIR / f"{a}.sh"
        if not wrapper.exists():
            errors.append(f"agent {a!r}: wrapper missing at {wrapper}")
            continue
        if not os.access(wrapper, os.X_OK):
            errors.append(f"agent {a!r}: wrapper not executable: {wrapper}")

    for t in tasks:
        tdir = TASKS_DIR / t
        if not tdir.exists():
            errors.append(f"task {t!r}: directory missing")
            continue
        if not (tdir / "prompt.md").exists():
            errors.append(f"task {t!r}: missing prompt.md")
        if not (tdir / "verify.sh").exists():
            errors.append(f"task {t!r}: missing verify.sh")
        elif not os.access(tdir / "verify.sh", os.X_OK):
            errors.append(f"task {t!r}: verify.sh not executable")
        if not (tdir / "workspace").is_dir():
            errors.append(f"task {t!r}: missing workspace/")
        if not (tdir / "_reference").is_dir():
            errors.append(f"task {t!r}: missing _reference/")

    return errors


# ---------------------------------------------------------------------------
# Native metrics parsers


def parse_claude_code(raw_dir: Path) -> dict:
    """Claude `-p --output-format json` emits a single JSON object on stdout."""
    f = raw_dir / "native.json"
    if not f.exists():
        return {"raw_format": "claude-json", "parsing_error": True,
                "error": "native.json missing"}
    try:
        obj = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        return {"raw_format": "claude-json", "parsing_error": True,
                "error": f"json decode: {e}"}

    usage = obj.get("usage") or {}
    model_usage = obj.get("modelUsage") or {}
    models = sorted(model_usage.keys()) or None

    # Claude Code reports total_cost_usd computed from Anthropic Opus rates.
    # When the harness is piloting a non-Anthropic backend through a proxy
    # (currently claude-deepseek), the figure is misleading. Detect
    # the case from the model name and emit null rather than propagate a
    # wrong number. The real cost has to come from the provider's dashboard.
    raw_cost = obj.get("total_cost_usd")
    is_proxied = bool(models) and not any(m.startswith("claude-") for m in models)
    total_cost_usd = None if is_proxied else raw_cost

    return {
        "raw_format": "claude-json",
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "num_turns": obj.get("num_turns"),
        "duration_ms": obj.get("duration_ms"),
        "total_cost_usd": total_cost_usd,
        "total_cost_usd_reported_raw": raw_cost if is_proxied else None,
        "is_proxied_backend": is_proxied,
        "models": models,
        "stop_reason": obj.get("stop_reason"),
        "is_error": obj.get("is_error"),
    }


def parse_codex(raw_dir: Path) -> dict:
    """Codex `exec --json` emits one JSON event per line.

    Last `turn.completed` carries token usage. We also count item types
    (command_execution, file_change, agent_message) for a coarse activity view.
    """
    f = raw_dir / "native.jsonl"
    if not f.exists():
        return {"raw_format": "codex-jsonl", "parsing_error": True,
                "error": "native.jsonl missing"}

    usage = None
    item_counts: dict[str, int] = {}
    turns = 0
    thread_id = None
    parse_errors = 0
    try:
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            etype = ev.get("type")
            if etype == "thread.started":
                thread_id = ev.get("thread_id")
            elif etype == "turn.completed":
                turns += 1
                usage = ev.get("usage") or usage
            elif etype == "item.completed":
                item = ev.get("item") or {}
                kind = item.get("type")
                if kind:
                    item_counts[kind] = item_counts.get(kind, 0) + 1
    except OSError as e:
        return {"raw_format": "codex-jsonl", "parsing_error": True,
                "error": f"read: {e}"}

    out = {
        "raw_format": "codex-jsonl",
        "num_turns": turns or None,
        "thread_id": thread_id,
        "item_counts": item_counts or None,
        "jsonl_parse_errors": parse_errors or None,
    }
    if usage:
        out.update({
            "input_tokens": usage.get("input_tokens"),
            "cached_input_tokens": usage.get("cached_input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "reasoning_output_tokens": usage.get("reasoning_output_tokens"),
        })
    return out


def parse_qwen_code(raw_dir: Path) -> dict:
    """Qwen Code `--output-format json` emits a single JSON array on stdout.

    Events: `system:init`, then a mix of `assistant`, `user`, `tool_use`,
    `tool_result`, ending with `result:success` (or `result:error_during_execution`).
    The final `result` event carries usage, num_turns, duration, and a `stats`
    sub-tree with per-model tokens and per-tool call counts.
    """
    f = raw_dir / "native.json"
    if not f.exists():
        return {"raw_format": "qwen-json", "parsing_error": True,
                "error": "native.json missing"}
    try:
        events = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        return {"raw_format": "qwen-json", "parsing_error": True,
                "error": f"json decode: {e}"}
    if not isinstance(events, list) or not events:
        return {"raw_format": "qwen-json", "parsing_error": True,
                "error": "expected non-empty JSON array"}

    init = next((e for e in events if e.get("type") == "system"
                 and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events)
                   if e.get("type") == "result"), {})

    usage = result.get("usage") or {}
    stats = result.get("stats") or {}
    models_stats = (stats.get("models") or {})
    tools_stats = (stats.get("tools") or {})
    files_stats = (stats.get("files") or {})

    return {
        "raw_format": "qwen-json",
        "qwen_code_version": init.get("qwen_code_version"),
        "session_id": init.get("session_id"),
        "models": sorted(models_stats.keys()) or None,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "num_turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
        "duration_api_ms": result.get("duration_api_ms"),
        "is_error": result.get("is_error"),
        "result_subtype": result.get("subtype"),
        "tool_calls": tools_stats.get("totalCalls"),
        "tool_fail": tools_stats.get("totalFail"),
        "lines_added": files_stats.get("totalLinesAdded"),
        "lines_removed": files_stats.get("totalLinesRemoved"),
    }


def parse_pi(raw_dir: Path) -> dict:
    """Pi (earendil-works/pi-coding-agent) `-p --mode json` emits a JSONL
    event stream. Per-message cumulative usage lives in `message_end`
    events under `message.usage` (input / output / cacheRead / cacheWrite /
    totalTokens / cost). The last `turn_end` carries the final totals.

    Pi reports its own per-run cost in USD which we keep as
    `pi_reported_cost_usd` for cross-validation against our PRICING calc.
    """
    f = raw_dir / "native.jsonl"
    if not f.exists():
        return {"raw_format": "pi-jsonl", "parsing_error": True,
                "error": "native.jsonl missing"}
    usage_totals = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
    total_cost_usd = 0.0
    saw_usage = False
    turn_count = 0
    tool_calls = 0
    parse_errors = 0
    model = None
    provider = None
    try:
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            t = ev.get("type")
            if t == "turn_start":
                turn_count += 1
            elif t == "turn_end":
                msg = ev.get("message") or {}
                u = msg.get("usage")
                if u:
                    saw_usage = True
                    usage_totals["input"] += u.get("input") or 0
                    usage_totals["output"] += u.get("output") or 0
                    usage_totals["cacheRead"] += u.get("cacheRead") or 0
                    usage_totals["cacheWrite"] += u.get("cacheWrite") or 0
                    total_cost_usd += ((u.get("cost") or {}).get("total") or 0.0)
                    model = model or msg.get("model")
                    provider = provider or msg.get("provider")
            elif t == "message_end":
                msg = ev.get("message") or {}
                model = model or msg.get("model")
                provider = provider or msg.get("provider")
                # Count tool_use parts in assistant message content
                if msg.get("role") == "assistant":
                    for part in msg.get("content") or []:
                        if isinstance(part, dict) and part.get("type") == "tool_use":
                            tool_calls += 1
    except OSError as e:
        return {"raw_format": "pi-jsonl", "parsing_error": True,
                "error": f"read: {e}"}

    out = {
        "raw_format": "pi-jsonl",
        "model": model,
        "provider": provider,
        "num_turns": turn_count or None,
        "tool_calls": tool_calls or None,
        "jsonl_parse_errors": parse_errors or None,
    }
    if saw_usage:
        out.update({
            "input_tokens": usage_totals["input"],
            "output_tokens": usage_totals["output"],
            "cache_read_input_tokens": usage_totals["cacheRead"],
            "cache_creation_input_tokens": usage_totals["cacheWrite"],
            "pi_reported_cost_usd": total_cost_usd,
        })
    return out


def parse_opencode(raw_dir: Path) -> dict:
    """OpenCode (anomalyco/opencode) `run --format json` only streams
    `step_start` events on stdout. The detailed per-run usage and cost
    are stored in the local opencode session DB; the wrapper invokes
    `opencode export <sessionID>` after the run to dump the full
    session JSON into raw_dir/session.json, which we parse here.

    session.json shape:
      info.cost                  -> total USD reported by opencode
      info.tokens.{input, output, reasoning, cache.{read, write}}
      messages[]                 -> message history (used for turn count)
    """
    f = raw_dir / "session.json"
    if not f.exists():
        return {"raw_format": "opencode-export", "parsing_error": True,
                "error": "session.json missing (wrapper failed to capture sessionID)"}
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        return {"raw_format": "opencode-export", "parsing_error": True,
                "error": f"session.json parse: {e}"}

    info = data.get("info") or {}
    tokens = info.get("tokens") or {}
    cache = tokens.get("cache") or {}
    messages = data.get("messages") or []

    assistant_turns = sum(
        1 for m in messages
        if (m.get("info") or {}).get("role") == "assistant"
    )
    # Count tool-use parts across assistant messages
    tool_calls = 0
    for m in messages:
        if (m.get("info") or {}).get("role") != "assistant":
            continue
        for p in m.get("parts") or []:
            if isinstance(p, dict) and p.get("type", "").startswith("tool"):
                tool_calls += 1

    model_info = info.get("model") or {}

    return {
        "raw_format": "opencode-export",
        "session_id": info.get("id"),
        "model": model_info.get("id"),
        "provider": model_info.get("providerID"),
        "input_tokens": tokens.get("input"),
        "output_tokens": tokens.get("output"),
        "reasoning_output_tokens": tokens.get("reasoning"),
        "cache_read_input_tokens": cache.get("read"),
        "cache_creation_input_tokens": cache.get("write"),
        "num_turns": assistant_turns or None,
        "tool_calls": tool_calls or None,
        "opencode_reported_cost_usd": info.get("cost"),
    }


PARSERS = {
    "claude-code": parse_claude_code,
    "claude-deepseek": parse_claude_code,  # same JSON shape (claude harness, DeepSeek backend)
    "codex": parse_codex,
    "opencode": parse_opencode,            # universal harness, DeepSeek backend (session.json from `opencode export`)
    "pi-ds4pro": parse_pi,                 # universal harness, DeepSeek V4 Pro
    "pi-flash": parse_pi,                  # same harness, DeepSeek V4 Flash (3x cheaper, smaller model)
    "pi-gemini": parse_pi,                 # same harness, Gemini 3.5 Flash (Google frontier as of 2026-05)
    "pi-glm": parse_pi,                    # same harness, GLM 5.1 via OpenRouter
    "qwen-code": parse_qwen_code,
}


# ---------------------------------------------------------------------------
# Quality checks (linters)
#
# Run after verify.sh on the post-run workspace. Purely informative — never
# fails the run. Detects languages by file presence, invokes a standard
# linter per language, captures structured counts under quality_metrics.
#
# Design notes:
# - Each linter is wrapped in its own try/except so one busted toolchain
#   doesn't taint the rest.
# - Short per-linter timeout (~30s). The post-verify workspace is already
#   built (node_modules / target / vendor) so we ride on the cache.
# - When a linter binary is missing locally, we mark `available: false`
#   rather than fail.


_QUALITY_TIMEOUT_SEC = 30
# Honor PATH but also reach into ~/go/bin and ~/.cargo/bin which are common
# for tools installed via `go install` / `cargo install` and not always on
# the inherited PATH (cron, IDE shells, etc.).
_EXTRA_QUALITY_PATHS = [
    str(Path.home() / "go" / "bin"),
    str(Path.home() / ".cargo" / "bin"),
]


def _which(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for d in _EXTRA_QUALITY_PATHS:
        candidate = Path(d) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _run_quality_cmd(
    cmd: list[str], cwd: Path, timeout: int = _QUALITY_TIMEOUT_SEC,
) -> tuple[int, str, str, bool]:
    """Run a linter, capture stdout/stderr as text. Returns (rc, stdout, stderr, timed_out)."""
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as e:
        return -1, (e.stdout or "") if isinstance(e.stdout, str) else "", \
               (e.stderr or "") if isinstance(e.stderr, str) else "", True
    except FileNotFoundError:
        return 127, "", "binary not found", False


def _detect_languages(workspace_dir: Path) -> list[str]:
    """Cheap language detection from top-level + recursive file presence."""
    langs: list[str] = []
    if (workspace_dir / "go.mod").exists():
        langs.append("go")
    if (workspace_dir / "package.json").exists():
        langs.append("typescript")
    if (workspace_dir / "Cargo.toml").exists():
        langs.append("rust")
    if (workspace_dir / "composer.json").exists():
        langs.append("php")
    # Python: presence of any .py file (skip site-packages-ish trees).
    has_python = False
    try:
        for p in workspace_dir.rglob("*.py"):
            # Skip virtualenv-y directories and vendored stuff.
            parts = set(p.relative_to(workspace_dir).parts)
            if parts & {".venv", "venv", "__pycache__", "node_modules", "vendor", "target"}:
                continue
            has_python = True
            break
    except OSError:
        pass
    if has_python:
        langs.append("python")
    return langs


def _quality_python(workspace_dir: Path) -> dict:
    binary = _which("ruff")
    if not binary:
        return {"linter": "ruff", "available": False}
    version_rc, version_out, _, _ = _run_quality_cmd([binary, "--version"], workspace_dir, timeout=5)
    version = (version_out.strip().split() or [""])[-1] if version_rc == 0 else None
    rc, stdout, stderr, timed_out = _run_quality_cmd(
        [binary, "check", "--output-format=json", "--no-cache", "."], workspace_dir,
    )
    if timed_out:
        return {"linter": "ruff", "linter_version": version, "available": True,
                "timed_out": True}
    violations_total = 0
    by_category: dict[str, int] = {}
    try:
        items = json.loads(stdout or "[]")
        if isinstance(items, list):
            violations_total = len(items)
            for it in items:
                code = (it or {}).get("code") or "UNKNOWN"
                by_category[code] = by_category.get(code, 0) + 1
    except json.JSONDecodeError:
        return {"linter": "ruff", "linter_version": version, "available": True,
                "exit_code": rc, "parse_error": True,
                "stderr_tail": (stderr or "")[-300:]}
    return {
        "linter": "ruff",
        "linter_version": version,
        "available": True,
        "violations_total": violations_total,
        "violations_by_category": by_category,
        "exit_code": rc,
    }


def _quality_go(workspace_dir: Path) -> dict:
    go = _which("go")
    if not go:
        return {"linter": "go vet", "available": False}
    go_version_rc, go_version_out, _, _ = _run_quality_cmd([go, "version"], workspace_dir, timeout=5)
    go_version = go_version_out.strip() if go_version_rc == 0 else None

    rc, stdout, stderr, timed_out = _run_quality_cmd([go, "vet", "./..."], workspace_dir)
    # go vet writes to stderr by convention; one warning ~= one non-empty line.
    vet_warnings = len([
        ln for ln in (stderr or "").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]) if not timed_out else None

    out: dict = {
        "linter": "go vet",
        "linter_version": go_version,
        "available": True,
        "vet_warnings": vet_warnings,
        "vet_exit_code": rc,
        "vet_timed_out": timed_out,
    }

    staticcheck = _which("staticcheck")
    if staticcheck:
        sc_version_rc, sc_version_out, _, _ = _run_quality_cmd(
            [staticcheck, "-version"], workspace_dir, timeout=5,
        )
        sc_version = sc_version_out.strip() if sc_version_rc == 0 else None
        sc_rc, sc_stdout, sc_stderr, sc_timed_out = _run_quality_cmd(
            [staticcheck, "./..."], workspace_dir,
        )
        # staticcheck output: one issue per line (path:line:col: message (CODE)).
        sc_warnings = len([
            ln for ln in (sc_stdout or "").splitlines() if ln.strip()
        ]) if not sc_timed_out else None
        out["staticcheck_available"] = True
        out["staticcheck_version"] = sc_version
        out["staticcheck_warnings"] = sc_warnings
        out["staticcheck_exit_code"] = sc_rc
        out["staticcheck_timed_out"] = sc_timed_out
    else:
        out["staticcheck_available"] = False

    # Aggregate violations_total: vet + staticcheck if available.
    total = 0
    have_any = False
    if vet_warnings is not None:
        total += vet_warnings
        have_any = True
    if out.get("staticcheck_available") and out.get("staticcheck_warnings") is not None:
        total += out["staticcheck_warnings"]
        have_any = True
    if have_any:
        out["violations_total"] = total
    return out


def _quality_typescript(workspace_dir: Path) -> dict:
    """Run local tsc --noEmit (from node_modules) and optionally eslint."""
    out: dict = {"linter": "tsc", "available": False}
    local_tsc = workspace_dir / "node_modules" / ".bin" / "tsc"
    if not local_tsc.exists():
        # Without local node_modules, falling back to `npx tsc` would download
        # typescript on demand — too slow and side-effecting. Skip cleanly.
        out["reason"] = "no node_modules/.bin/tsc (skipped to avoid npm install)"
        return out

    tsconfig = workspace_dir / "tsconfig.json"
    cmd = [str(local_tsc), "--noEmit"]
    if tsconfig.exists():
        cmd += ["--project", str(tsconfig)]
    version_rc, version_out, _, _ = _run_quality_cmd(
        [str(local_tsc), "--version"], workspace_dir, timeout=5,
    )
    tsc_version = version_out.strip() if version_rc == 0 else None
    rc, stdout, stderr, timed_out = _run_quality_cmd(cmd, workspace_dir)
    # tsc prints diagnostics like "src/foo.ts(12,3): error TS2322: ..."
    text = (stdout or "") + (stderr or "")
    type_errors = 0
    for ln in text.splitlines():
        if "error TS" in ln:
            type_errors += 1

    out.update({
        "linter": "tsc",
        "linter_version": tsc_version,
        "available": True,
        "tsc_type_errors": type_errors,
        "tsc_exit_code": rc,
        "tsc_timed_out": timed_out,
    })

    # Optional eslint pass: only if a config exists in the workspace and a
    # local eslint binary is installed (we won't trigger npx-driven installs).
    eslint_configs = [
        ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json",
        ".eslintrc.yaml", ".eslintrc.yml", "eslint.config.js",
        "eslint.config.cjs", "eslint.config.mjs", "eslint.config.ts",
    ]
    has_eslint_config = any((workspace_dir / c).exists() for c in eslint_configs)
    local_eslint = workspace_dir / "node_modules" / ".bin" / "eslint"
    if has_eslint_config and local_eslint.exists():
        e_version_rc, e_version_out, _, _ = _run_quality_cmd(
            [str(local_eslint), "--version"], workspace_dir, timeout=5,
        )
        eslint_version = e_version_out.strip() if e_version_rc == 0 else None
        e_rc, e_stdout, e_stderr, e_timed_out = _run_quality_cmd(
            [str(local_eslint), "--format", "json", "."], workspace_dir,
        )
        eslint_errors = 0
        eslint_warnings = 0
        parsed_ok = False
        try:
            data = json.loads(e_stdout or "[]")
            if isinstance(data, list):
                for f in data:
                    eslint_errors += int((f or {}).get("errorCount") or 0)
                    eslint_warnings += int((f or {}).get("warningCount") or 0)
                parsed_ok = True
        except json.JSONDecodeError:
            pass
        out["eslint_available"] = True
        out["eslint_version"] = eslint_version
        out["eslint_errors"] = eslint_errors if parsed_ok else None
        out["eslint_warnings"] = eslint_warnings if parsed_ok else None
        out["eslint_exit_code"] = e_rc
        out["eslint_timed_out"] = e_timed_out
        if not parsed_ok:
            out["eslint_parse_error"] = True
    else:
        out["eslint_available"] = False
        if not has_eslint_config:
            out["eslint_skip_reason"] = "no eslint config"
        elif not local_eslint.exists():
            out["eslint_skip_reason"] = "no local eslint binary"

    # Aggregate violations_total: type errors + eslint errors+warnings.
    total = type_errors
    if out.get("eslint_errors") is not None:
        total += out["eslint_errors"]
    if out.get("eslint_warnings") is not None:
        total += out["eslint_warnings"]
    out["violations_total"] = total
    return out


def _quality_rust(workspace_dir: Path) -> dict:
    cargo = _which("cargo")
    if not cargo:
        return {"linter": "cargo clippy", "available": False}
    target_dir = workspace_dir / "target"
    if not target_dir.exists():
        return {"linter": "cargo clippy", "available": False,
                "reason": "no target/ — skipping to avoid full rebuild"}

    version_rc, version_out, _, _ = _run_quality_cmd(
        [cargo, "clippy", "--version"], workspace_dir, timeout=5,
    )
    clippy_version = version_out.strip() if version_rc == 0 else None

    # Use --release to reuse artefacts produced by the verify (verify runs
    # `cargo test --release` on rust tasks).
    rc, stdout, stderr, timed_out = _run_quality_cmd(
        [cargo, "clippy", "--release", "--message-format=json",
         "--quiet", "--no-deps"],
        workspace_dir, timeout=60,
    )
    if timed_out:
        return {"linter": "cargo clippy", "linter_version": clippy_version,
                "available": True, "timed_out": True}

    by_level: dict[str, int] = {}
    violations_total = 0
    parse_errors = 0
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if obj.get("reason") != "compiler-message":
            continue
        msg = obj.get("message") or {}
        # Filter out messages that don't belong to the workspace crate.
        # Clippy emits diagnostics with `spans` pointing to local files.
        spans = msg.get("spans") or []
        if spans and not any(
            (s or {}).get("is_primary") and not (s or {}).get("file_name", "").startswith("/")
            for s in spans
        ):
            # All primary spans are absolute paths — could be deps. Best-effort
            # filter: skip if every primary span file is outside the workspace.
            in_workspace = False
            ws_str = str(workspace_dir)
            for s in spans:
                if not (s or {}).get("is_primary"):
                    continue
                fname = (s or {}).get("file_name", "")
                if not fname.startswith("/") or fname.startswith(ws_str):
                    in_workspace = True
                    break
            if not in_workspace:
                continue
        level = msg.get("level") or "unknown"
        # Ignore "help"/"note" sub-diagnostics; they aren't standalone issues.
        if level in {"help", "note"}:
            continue
        by_level[level] = by_level.get(level, 0) + 1
        violations_total += 1

    return {
        "linter": "cargo clippy",
        "linter_version": clippy_version,
        "available": True,
        "violations_total": violations_total,
        "violations_by_level": by_level,
        "exit_code": rc,
        "json_parse_errors": parse_errors or None,
    }


def _quality_php(workspace_dir: Path) -> dict:
    """PHPStan support disabled — would require per-task minimal config.

    We detect composer.json but explicitly flag this as not implemented
    rather than silently skip.
    """
    return {
        "linter": "phpstan",
        "available": False,
        "reason": "no minimal phpstan config",
    }


_QUALITY_DISPATCH = {
    "python": _quality_python,
    "go": _quality_go,
    "typescript": _quality_typescript,
    "rust": _quality_rust,
    "php": _quality_php,
}


def run_quality_checks(workspace_dir: Path) -> dict:
    """Detect languages and run available linters. Never raises."""
    result: dict = {
        "languages_detected": [],
        "python": None,
        "go": None,
        "typescript": None,
        "rust": None,
        "php": None,
    }
    try:
        if not workspace_dir.exists():
            result["error"] = f"workspace missing: {workspace_dir}"
            return result
        # Resolve to absolute so subprocess invocations with cwd= the workspace
        # don't break when callers pass relative paths.
        workspace_dir = workspace_dir.resolve()
        langs = _detect_languages(workspace_dir)
        result["languages_detected"] = langs
        for lang in langs:
            fn = _QUALITY_DISPATCH.get(lang)
            if not fn:
                continue
            try:
                result[lang] = fn(workspace_dir)
            except Exception as e:
                result[lang] = {"error": f"linter crashed: {e!r}"}
    except Exception as e:
        result["error"] = f"detection crashed: {e!r}"
    return result


# ---------------------------------------------------------------------------
# Run execution


def short_uuid() -> str:
    return uuid.uuid4().hex[:8]


def run_with_timeout(
    cmd: list[str], cwd: Path, timeout: int, log_path: Path | None = None,
) -> tuple[int, float, bool]:
    """Run cmd, capture stdout+stderr to log_path if provided. Returns (exit, wall_s, timed_out)."""
    start = time.monotonic()
    timed_out = False
    log_fh = open(log_path, "w") if log_path else subprocess.DEVNULL
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd),
            stdout=log_fh if log_path else subprocess.DEVNULL,
            stderr=subprocess.STDOUT if log_path else subprocess.DEVNULL,
        )
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            try:
                rc = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                rc = -9
    finally:
        if log_path:
            log_fh.close()
    return rc, time.monotonic() - start, timed_out


def do_one_run(agent: str, task: str, run_index: int, timeout: int) -> dict:
    run_id = short_uuid()
    raw_dir = RESULTS_DIR / "raw" / run_id
    work_dir = RESULTS_DIR / "workspaces" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    task_dir = TASKS_DIR / task
    # Layout for verify.sh's `cd $(dirname $0)`:
    #   work_dir/verify.sh
    #   work_dir/.test_hash
    #   work_dir/workspace/...
    shutil.copytree(task_dir / "workspace", work_dir / "workspace")
    shutil.copy(task_dir / "verify.sh", work_dir / "verify.sh")
    if (task_dir / ".test_hash").exists():
        shutil.copy(task_dir / ".test_hash", work_dir / ".test_hash")

    prompt_path = task_dir / "prompt.md"
    wrapper = AGENTS_DIR / f"{agent}.sh"

    # Run agent inside workspace/ — that's where the code lives.
    agent_rc, agent_wall, agent_timeout = run_with_timeout(
        [str(wrapper), str(prompt_path), str(raw_dir)],
        cwd=work_dir / "workspace",
        timeout=timeout,
        log_path=raw_dir / "wrapper.log",
    )

    # Verify (separate, modest timeout — pytest shouldn't hang)
    verify_log = raw_dir / "verify.log"
    verify_rc, verify_wall, verify_timeout = run_with_timeout(
        [str(work_dir / "verify.sh")],
        cwd=work_dir,
        timeout=120,
        log_path=verify_log,
    )

    parser = PARSERS.get(agent, lambda _r: {"raw_format": "unknown"})
    try:
        native_metrics = parser(raw_dir)
    except Exception as e:  # never crash the runner on parsing
        native_metrics = {"raw_format": agent, "parsing_error": True,
                          "error": f"parser crashed: {e!r}"}

    # Quality checks — purely informative, must never break the run.
    try:
        quality_metrics = run_quality_checks(work_dir / "workspace")
    except Exception as e:
        quality_metrics = {"error": f"quality crashed: {e!r}"}

    record = {
        "run_id": run_id,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                     .replace("+00:00", "Z"),
        "agent": agent,
        "task": task,
        "run_index": run_index,
        "success": verify_rc == 0 and not agent_timeout,
        "wall_time_sec": round(agent_wall, 3),
        "agent_exit_code": agent_rc,
        "agent_timeout": agent_timeout,
        "verify_exit_code": verify_rc,
        "verify_wall_time_sec": round(verify_wall, 3),
        "verify_timeout": verify_timeout,
        "native_metrics": native_metrics,
        "quality_metrics": quality_metrics,
        "raw_dir": str(raw_dir.relative_to(BENCH_DIR)),
        "workspace_dir": str(work_dir.relative_to(BENCH_DIR)),
    }
    return record


def append_jsonl(record: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RUNS_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# CLI


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--agents", help=f"comma-separated, default: {','.join(DEFAULT_AGENTS)}")
    ap.add_argument("--tasks", help="comma-separated, default: all tasks")
    ap.add_argument("--runs", type=int, default=1, help="runs per (agent, task)")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per run")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate agents/tasks without running anything")
    args = ap.parse_args()

    agents = resolve_agents(args.agents)
    tasks = resolve_tasks(args.tasks)

    errors = validate(agents, tasks)
    if errors:
        print("validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 2

    print(f"agents: {agents}")
    print(f"tasks:  {tasks}")
    print(f"runs:   {args.runs}  timeout: {args.timeout}s")
    total = len(agents) * len(tasks) * args.runs
    print(f"total runs: {total}")

    if args.dry_run:
        print("dry-run OK — wrappers and tasks look valid.")
        return 0

    triplets = [(a, t, i) for a in agents for t in tasks for i in range(1, args.runs + 1)]
    bar = tqdm(triplets, ncols=100)
    for agent, task, idx in bar:
        label = f"{agent} / {task} / run {idx}/{args.runs}"
        with contextlib.suppress(AttributeError):
            bar.set_description(label)
        try:
            record = do_one_run(agent, task, idx, args.timeout)
        except Exception as e:
            record = {
                "run_id": short_uuid(),
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                             .replace("+00:00", "Z"),
                "agent": agent, "task": task, "run_index": idx,
                "success": False, "runner_error": repr(e),
            }
        append_jsonl(record)
        status = "✓" if record.get("success") else "✗"
        with contextlib.suppress(AttributeError):
            bar.write(f"  {status} {label}  wall={record.get('wall_time_sec','?')}s "
                      f"agent_rc={record.get('agent_exit_code','?')} "
                      f"verify_rc={record.get('verify_exit_code','?')}")

    print(f"\ndone. results in {RUNS_FILE.relative_to(BENCH_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
