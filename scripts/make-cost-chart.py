#!/usr/bin/env python3
"""Estimated cost-to-run chart.

Reads a runs JSONL file (results/runs.jsonl by default, or REALBENCH_RUNS),
sums tokens per (agent, segment), multiplies by the public or explicitly
modeled per-million-tokens rate of the model the agent rides, and renders a
stacked bar chart of estimated run-scoped spend per agent — sorted descending.

Tariffs are public pricing pages with per-model verification dates documented
in METHODOLOGY.md. They drift; re-verify the URLs whenever you re-render.
The number printed on each bar is a run-scoped API-equivalent estimate from
native token telemetry. It is not a provider-invoice reconciliation: invoices
can include exploratory runs, failed integrations, retries outside the curated
snapshot, and provider-side billing details not exposed per run. For agents
that ride a flat-fee subscription (codex), the bar is hypothetical: what you
would pay via the underlying API at the chosen tier.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

BENCH = Path(__file__).resolve().parent.parent
RUNS = Path(os.environ.get("REALBENCH_RUNS", BENCH / "results" / "runs.jsonl"))
OUT = Path(os.environ.get("REALBENCH_COST_OUT", BENCH / "docs" / "realbench-cost.png"))
SCOPE_LABEL = os.environ.get("REALBENCH_COST_SCOPE_LABEL", "every run in runs.jsonl")
ONLY_AGENTS_WITH_RUNS = os.environ.get("REALBENCH_COST_ONLY_AGENTS_WITH_RUNS") == "1"

# Pricing per 1M tokens, USD. Public list-price.
# Each entry is preceded by the upstream URL it was last verified against.
# "cache_read" is the prompt-cache hit rate, "cache_write" is the
# cache-creation tier (when the provider distinguishes one — Anthropic does,
# DashScope and DeepSeek don't surface it separately so we leave it 0).
PRICING = {
    # Claude Opus 4.7 — used by claude-code.
    # Source: https://platform.claude.com/docs/en/docs/about-claude/pricing
    # Confirmed 2026-05-24: 1M context window is at STANDARD pricing
    # (no premium tier), so $5/$0.50/$25 is correct. cache_write at
    # $6.25 is the 5-minute cache tier (1.25x base input). The Claude
    # harness uses 5-min caching by default for session prompts.
    # Fast mode (6x standard, $30/$150) is NOT used by claude-code.sh.
    "claude-opus-4-7": {"input": 5.00, "cache_read": 0.50, "cache_write": 6.25, "output": 25.00},

    # GPT-5.5 Priority tier ("xhigh fast") — used by codex.
    # Source: https://openai.com/api/pricing (Priority tier listed)
    # Verified via apidog.com/blog/gpt-5-5-pricing/ and theregister.com.
    # codex CLI's current default (0.133.0, `codex doctor`) is gpt-5.5.
    # Priority is 2.5x standard ($5/$30); cache hits assumed at the
    # same 10% input ratio as standard ($1.25 = 0.10 × $12.50). The
    # standard tier costs $5/$0.50/$30 — use that if you don't run
    # codex in Priority mode. OpenAI doesn't expose a separate
    # cache_creation tier, so we leave it at 0.
    "gpt-5-5-priority": {"input": 12.50, "cache_read": 1.25, "cache_write": 0.0, "output": 75.00},

    # DeepSeek V4 Pro — used by claude-deepseek.
    # Source: https://api-docs.deepseek.com/quick_start/pricing
    # The 75%-off promo on V4-Pro became the permanent list price
    # on 2026-05-22 (announced on the DeepSeek pricing page). The
    # cache-hit rate was also cut to 1/10 of launch price on 2026-04-26.
    # If the promo expires the listed reversion is $1.74/$0.0145/$3.48.
    "deepseek-v4-pro": {"input": 0.435, "cache_read": 0.003625, "cache_write": 0.0, "output": 0.87},

    # Qwen3.7 Max — used by qwen-code via DashScope International.
    # Source: https://www.qwencloud.com/models/qwen3.7-max
    # Current public page shows 50%-off rates: input $1.25/M,
    # implicit-cache input $0.25/M, output $3.75/M.
    "qwen3-7-max": {"input": 1.25, "cache_read": 0.25, "cache_write": 0.0, "output": 3.75},

    # DeepSeek V4 Flash — used by pi-flash. Smaller / cheaper sibling
    # of V4 Pro. Source: https://api-docs.deepseek.com/quick_start/pricing
    # Current pricing $0.14 input / $0.0028 cache_read / $0.28 output
    # per M tokens (98% cache discount, like V4 Pro).
    "deepseek-v4-flash": {"input": 0.14, "cache_read": 0.0028, "cache_write": 0.0, "output": 0.28},

    # Gemini 3.5 Flash — used by pi-gemini.
    # Source: https://ai.google.dev/gemini-api/docs/pricing
    # cache_read is modeled at 10% of input, matching the discount shape
    # Google publishes for current Flash context-caching tiers. Update if a
    # model-specific Gemini 3.5 Flash cache-read rate is published.
    "gemini-3-5-flash": {"input": 1.50, "cache_read": 0.15, "cache_write": 0.0, "output": 9.00},

    # Z.ai GLM 5.1 via OpenRouter — used by pi-glm.
    # Source: https://openrouter.ai/z-ai/glm-5.1/pricing and
    # https://openrouter.ai/api/v1/models (model id z-ai/glm-5.1).
    # Verified 2026-05-26: prompt $0.98/M, cache_read $0.182/M,
    # completion $3.08/M; context_length 202,752.
    "glm-5-1-openrouter": {"input": 0.98, "cache_read": 0.182, "cache_write": 0.0, "output": 3.08},

}

# Map agent name → which pricing entry to apply
AGENT_TO_MODEL = {
    "claude-code": "claude-opus-4-7",
    "codex": "gpt-5-5-priority",
    "claude-deepseek": "deepseek-v4-pro",
    "qwen-code": "qwen3-7-max",
    "pi-ds4pro": "deepseek-v4-pro",
    "pi-flash": "deepseek-v4-flash",
    "pi-gemini": "gemini-3-5-flash",
    "pi-glm": "glm-5-1-openrouter",
    "opencode": "deepseek-v4-pro",
}

DISPLAY_LABELS = {
    "claude-code": ("claude-code", "Opus 4.7"),
    "codex": ("codex", "GPT-5.5 xhigh+fast"),
    "claude-deepseek": ("claude-deepseek", "DeepSeek V4 Pro"),
    "qwen-code": ("qwen-code", "Qwen3.7 Max"),
    "pi-ds4pro": ("pi-ds4pro", "DeepSeek V4 Pro"),
    "pi-flash": ("pi-flash", "DeepSeek V4 Flash"),
    "pi-gemini": ("pi-gemini", "Gemini 3.5 Flash"),
    "pi-glm": ("pi-glm", "OpenRouter GLM 5.1"),
    "opencode": ("opencode-DS4pro", "DeepSeek V4 Pro"),
}

# Which model/provider brand logo to show under each agent (not the harness
# vendor). For brokered routes, keep the pricing label explicit but show the
# model owner's brand. Logos live in docs/assets/logos/<provider>.png at 128px
# height.
AGENT_TO_PROVIDER_LOGO = {
    "claude-code":     "anthropic",
    "codex":           "openai",
    "claude-deepseek": "deepseek",
    "qwen-code":       "qwen",
    "pi-ds4pro":       "deepseek",
    "pi-flash":        "deepseek",
    "pi-gemini":       "google",
    "pi-glm":          "zai",
    "opencode":        "deepseek",
}

# Canonical score denominator for the badge above each bar. Keep in sync with
# runner.DEFAULT_TASKS and scripts/make-comparison.py.
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

# Stack colors — input (lighter) / cache_read / cache_write / output (full)
SEG_COLOR = {
    "input": "#FFD9C2",        # very light orange
    "cache_read": "#FFAA80",   # medium orange
    "cache_write": "#F08A5D",  # darker orange between cache_read and output
    "output": "#D97757",       # solid orange
}

def collect_tokens() -> dict[str, dict[str, int]]:
    """Sum tokens per (agent, segment) across EVERY run in runs.jsonl —
    including duplicates and failures. The chart's headline number is
    a run-scoped API-equivalent estimate, not an invoice total. Re-runs and
    failed runs both consume tokens; flattening them out would understate the
    estimated spend. For publication, point REALBENCH_RUNS at
    results/runs-en-135.jsonl so each agent is compared over the same 27 × 5
    EN run snapshot.

    Token-shape per harness:
      - Claude harnesses (claude-code/deepseek): input_tokens is
        ALREADY uncached, cache_read and cache_creation are separate.
      - codex: input_tokens is the TOTAL prompt (includes cached); the
        OpenAI Responses API returns it this way.
      - qwen-code (DashScope OpenAI-compat): input_tokens is the TOTAL
        prompt and cache_read_input_tokens is the cached subset, matching
        Qwen Cloud's implicit-cache billing tier.

    For TOTAL-shape harnesses with validated cache billing we subtract
    cache_read to get the uncached portion.
    """
    TOTAL_SHAPE = {"codex", "qwen-code"}
    acc: dict[str, dict[str, int]] = defaultdict(lambda: {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0})
    for line in RUNS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        agent = r.get("agent")
        if agent not in AGENT_TO_MODEL:
            continue
        nm = r.get("native_metrics") or {}
        ipt = nm.get("input_tokens") or 0
        crt = nm.get("cache_read_input_tokens") or nm.get("cached_input_tokens") or 0
        cwt = nm.get("cache_creation_input_tokens") or 0
        out = nm.get("output_tokens") or 0
        if agent in TOTAL_SHAPE and crt and ipt >= crt:
            uncached = ipt - crt
        else:
            uncached = ipt
        acc[agent]["input"] += uncached
        acc[agent]["cache_read"] += crt
        acc[agent]["cache_write"] += cwt
        acc[agent]["output"] += out
    return dict(acc)


def collect_run_counts() -> dict[str, int]:
    """How many runs we have per agent, for display alongside each bar."""
    from collections import Counter
    counts: Counter = Counter()
    for line in RUNS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        agent = r.get("agent")
        if agent in AGENT_TO_MODEL:
            counts[agent] += 1
    return dict(counts)


def collect_turn_counts() -> dict[str, tuple[int, int]]:
    """Reported agent turns per agent, plus missing-turn row count.

    Some timeout records do not contain native turn metrics. We keep the count
    honest by returning `(reported_turns, missing_rows)` and rendering a `+`
    suffix in the chart when at least one run was missing turn telemetry.
    """
    turns: dict[str, int] = defaultdict(int)
    missing: dict[str, int] = defaultdict(int)
    for line in RUNS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        agent = r.get("agent")
        if agent not in AGENT_TO_MODEL:
            continue
        num_turns = (r.get("native_metrics") or {}).get("num_turns")
        if isinstance(num_turns, (int, float)):
            turns[agent] += int(num_turns)
        else:
            missing[agent] += 1
    return {agent: (turns[agent], missing[agent]) for agent in AGENT_TO_MODEL}


AUDITED_SEMANTIC_PASS_RUN_IDS = {
    # Codex 018 modified only test formatting, tripping .test_hash. Restoring
    # the original test file and re-running verify.sh passes. Keep the
    # anti-tamper event documented, but do not show it as a semantic miss on
    # the cost chart.
    "37a83126",
}


def is_semantic_pass(record: dict) -> bool:
    """Whether the produced solution is semantically correct for chart badges.

    This deliberately differs from runner `success`, which is stricter:
    runner success also fails on agent timeout even when verify.sh passes, and
    it fails anti-tamper advisories before tests can run.
    """
    if record.get("success"):
        return True
    if record.get("verify_exit_code") == 0:
        return True
    if record.get("run_id") in AUDITED_SEMANTIC_PASS_RUN_IDS:
        return True
    return False


def collect_semantic_pass_counts() -> dict[str, tuple[int, int]]:
    """Semantic pass count per agent across the records used by this chart."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for line in RUNS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        agent = r.get("agent")
        task = r.get("task")
        if agent not in AGENT_TO_MODEL or task not in TASKS:
            continue
        counts[agent][1] += 1
        if is_semantic_pass(r):
            counts[agent][0] += 1
    return {
        agent: (counts[agent][0], counts[agent][1])
        for agent in AGENT_TO_MODEL
    }


def cost(tokens: dict[str, int], model_key: str) -> dict[str, float]:
    p = PRICING[model_key]
    return {
        "input":       tokens.get("input", 0)       * p["input"]       / 1_000_000,
        "cache_read":  tokens.get("cache_read", 0)  * p["cache_read"]  / 1_000_000,
        "cache_write": tokens.get("cache_write", 0) * p.get("cache_write", 0.0) / 1_000_000,
        "output":      tokens.get("output", 0)      * p["output"]      / 1_000_000,
    }


def make_chart() -> None:
    tokens_by_agent = collect_tokens()
    run_counts = collect_run_counts()
    turn_counts = collect_turn_counts()
    pass_counts = collect_semantic_pass_counts()
    agents = list(AGENT_TO_MODEL)
    if ONLY_AGENTS_WITH_RUNS:
        agents = [agent for agent in agents if run_counts.get(agent, 0) > 0]
    costs = {
        agent: cost(tokens_by_agent.get(agent, {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0}),
                    AGENT_TO_MODEL[agent])
        for agent in agents
    }
    totals = {a: sum(c.values()) for a, c in costs.items()}

    # Sort descending by total
    order = sorted(totals.keys(), key=lambda a: -totals[a])

    # 16:9 figure, sized for Twitter / X (target ~1600×900 at 120 dpi).
    # Wide canvas so the agent bars spread out without crowding.
    fig, ax = plt.subplots(figsize=(22, 9), dpi=120)
    # Bottom padding budget: 3-line xticklabel + provider logo row
    # under the axis. Left/right margins tight to use the full width.
    fig.subplots_adjust(top=0.82, bottom=0.22, left=0.04, right=0.99)
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")

    bar_w = 0.65
    x = list(range(len(order)))

    # Agents whose harness doesn't expose tokens — we don't have data to price
    no_tokens = {a for a in order if sum(tokens_by_agent.get(a, {}).values()) == 0}

    for i, agent in enumerate(order):
        if agent in no_tokens:
            # Render a placeholder hatched bar so the agent isn't silently absent
            ax.bar(i, 0.5, bar_w, color="#EEE", edgecolor="#BBB",
                   linewidth=0.5, hatch="///")
            ax.text(i, 0.55, "n/a*", ha="center", va="bottom",
                    fontsize=12, weight="bold", color="#888")
            continue
        c = costs[agent]
        bottom = 0.0
        # Decide whether to label individual segments: only on bars tall
        # enough that two-three labels can fit without colliding. Threshold
        # in absolute USD because the y-axis is shared.
        label_segments = totals[agent] >= 3.0
        for seg in ("input", "cache_read", "cache_write", "output"):
            v = c[seg]
            if v <= 0:
                continue
            ax.bar(i, v, bar_w, bottom=bottom, color=SEG_COLOR[seg],
                   edgecolor="white", linewidth=0.5)
            if label_segments and v / totals[agent] > 0.10:
                ax.text(i, bottom + v / 2, f"${v:.2f}", ha="center", va="center",
                        fontsize=10, color="#222", weight="bold")
            bottom += v
        # Above the bar: cost (bold) on top, total tokens discreet underneath.
        # The token line uses a compact M/k suffix so the figure isn't crowded.
        total_tokens = sum(tokens_by_agent.get(agent, {}).values())
        if total_tokens >= 1_000_000:
            tok_str = f"{total_tokens/1_000_000:.2f}M tokens"
        elif total_tokens >= 1_000:
            tok_str = f"{total_tokens/1_000:.0f}k tokens"
        else:
            tok_str = f"{total_tokens} tokens"
        # Cost label — top line, prominent. Switch to 5 decimals for the
        # sub-cent rows (small DeepSeek Flash snapshots can land below
        # $0.01, which rounded to $0.00 hides the actual number —
        # readers see "zero" and assume an error).
        if totals[agent] < 0.01:
            cost_str = f"${totals[agent]:.5f}"
        else:
            cost_str = f"${totals[agent]:.2f}"
        ymax_estimate = max(totals.values()) if totals else 1
        # Two-line label stacked above the bar: tokens (small, grey) on
        # top, cost (large, bold) below. Use textcoords offset-points so
        # the gap is in pixels (consistent regardless of bar height)
        # rather than data units (which made the small bars' labels
        # overlap into the big bars' labels).
        ax.annotate(cost_str, xy=(i, totals[agent]),
                    xytext=(0, 6), textcoords="offset points",
                    ha="center", va="bottom", fontsize=14,
                    weight="bold", color="#111")
        ax.annotate(tok_str, xy=(i, totals[agent]),
                    xytext=(0, 26), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, color="#777")
        passed, total = pass_counts.get(agent, (0, 0))
        pass_color = "#4B5563"
        pass_bg = "#F3F4F6"
        ax.annotate(f"{passed}/{total}", xy=(i, totals[agent]),
                    xytext=(0, 46), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10,
                    weight="bold", color=pass_color,
                    bbox={
                        "boxstyle": "round,pad=0.22,rounding_size=0.12",
                        "facecolor": pass_bg,
                        "edgecolor": pass_color,
                        "linewidth": 0.8,
                    })

    ax.set_xticks(x)
    # Three-line x-label so each piece of metadata sits on its own row:
    #   line 1: agent name
    #   line 2: model
    #   line 3: total reported agent turns across the snapshot
    xlabels = []
    for a in order:
        reported_turns, missing_turn_rows = turn_counts.get(a, (0, 0))
        turns_suffix = "+" if missing_turn_rows else ""
        xlabels.append(
            f"{DISPLAY_LABELS[a][0]}\n{DISPLAY_LABELS[a][1]}\n"
            f"{reported_turns:,}{turns_suffix} turns"
        )
    ax.set_xticklabels(xlabels, fontsize=11, color="#333")

    # Provider logo BELOW the 3-line xticklabel — anchored at the
    # bottom of the figure (figure coords y=0) so a fixed pixel
    # offset puts it well clear of the xtick text. Loaded once per
    # file, cached.
    logos_dir = BENCH / "docs" / "assets" / "logos"
    logo_cache: dict[str, "OffsetImage"] = {}
    for i, agent in enumerate(order):
        provider = AGENT_TO_PROVIDER_LOGO.get(agent)
        if not provider:
            continue
        logo_path = logos_dir / f"{provider}.png"
        if not logo_path.exists():
            continue
        if provider not in logo_cache:
            img = mpimg.imread(str(logo_path))
            logo_cache[provider] = img
        # Logo placed right under the x-axis baseline (axes y=0) with a
        # small fixed pixel offset below. The xticklabel is pushed
        # further down via tick_params pad=46 so it sits BELOW the logo.
        ab = AnnotationBbox(
            OffsetImage(logo_cache[provider], zoom=0.18),
            xy=(i, 0),
            xybox=(0, -22),                # ~22 px below the axis baseline
            xycoords=("data", "axes fraction"),
            boxcoords="offset points",
            frameon=False,
            box_alignment=(0.5, 0.5),
            pad=0,
            annotation_clip=False,
        )
        ax.add_artist(ab)
    # No tick marks. Pad pushes the 3-line xticklabel ~46 px below the
    # axis, opening a strip right under the baseline where the provider
    # logo sits.
    ax.tick_params(axis="x", length=0, pad=46)

    ax.set_ylabel(f"Cumulative spend across {SCOPE_LABEL}  (USD)",
                  fontsize=11, color="#333")

    fig.suptitle(
        "realbench — estimated API-equivalent spend by coding-agent harness",
        fontsize=18, x=0.07, y=0.94, ha="left", weight="bold",
    )
    fig.text(0.04, 0.895,
             f"Run-scoped token telemetry across the {SCOPE_LABEL}; not a provider-invoice reconciliation.  "
             "Tariff dates are per model in METHODOLOGY.  "
             "Same battery, different harness.  "
             f"Badges show semantic pass count across {SCOPE_LABEL}; strict operational failures are tracked separately.",
             fontsize=10, color="#555", ha="left")
    fig.text(0.04, 0.872,
             "codex = GPT-5.5 + xhigh reasoning + fast (Priority) tier.  "
             "Gemini cache-read is modeled; Pi-reported costs are cross-checked separately.",
             fontsize=10, color="#555", ha="left")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCC")
    ax.spines["bottom"].set_color("#CCC")
    ax.tick_params(colors="#444")
    ax.grid(axis="y", linestyle="--", color="#E5E5E5", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    # Legend — positioned inside the chart, top-right, in the white space
    # to the right of the tallest bar (which is on the left).
    handles = [plt.Rectangle((0, 0), 1, 1, color=SEG_COLOR[s]) for s in ("input", "cache_read", "cache_write", "output")]
    ax.legend(handles, ["Input (uncached)", "Cache read", "Cache write", "Output"],
              loc="upper right", frameon=False, fontsize=11,
              bbox_to_anchor=(0.98, 0.95))

    # Extra headroom on y for the 3-line top labels (pass + tokens + cost).
    # The labels are offset in pixels, so this multiplier mostly protects
    # the tallest bar from clipping against the subtitle.
    ymax = max(totals.values()) * 1.22 if totals else 1
    ax.set_ylim(0, ymax)
    # Tighten x so the bar row uses the full canvas (default xlim leaves
    # ~0.5 unit of dead space on each side; visible as a "white gap" at
    # the right of the figure when there are 12 bars).
    ax.set_xlim(-0.55, len(order) - 0.45)

    # Keep the manual margins above. tight_layout() pulls the axes back into
    # the two-line subtitle and can overlap the tallest pass badge.
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"wrote {OUT}")
    print()
    print("Token totals per agent:")
    for a in order:
        t = tokens_by_agent.get(a, {})
        print(f"  {a:18}  in={t.get('input',0):>10}  cache_r={t.get('cache_read',0):>10}  cache_w={t.get('cache_write',0):>10}  out={t.get('output',0):>10}  ->  ${totals[a]:.2f}")


if __name__ == "__main__":
    make_chart()
