# Methodology

How realbench measures coding-agent harnesses. Every number in this public
snapshot's `results/runs.jsonl` and every figure in `docs/*.png` is
reproducible from this document.

If something here doesn't match what the code does, **the code is
right and this file is stale**. Open an issue.

---

## 1. What we measure

Per `(agent, task)` cell:

| Dimension | Source | Notes |
| --- | --- | --- |
| `success` | `verify.sh` exit code is 0 and the wrapper did not time out | Verifier is hash-protected (see §3). A timeout after a correct workspace is still a strict harness failure. |
| `wall_ms` | Runner-side `monotonic()` around the wrapper subprocess | Includes wrapper overhead. |
| `input_tokens` | Native JSON of each harness | Cache writes lumped with input. |
| `cache_read_input_tokens` | Native JSON of each harness | Where supported. |
| `output_tokens` | Native JSON of each harness | |
| `num_turns` | Native JSON of each harness | **Not comparable across CLIs.** See §6. |
| `total_cost_usd` | Native JSON when the harness is talking to Anthropic; `null` otherwise (set defensively for non-Anthropic backends) | Recomputed from tokens for proxied/non-Anthropic rows in the cost chart. |
| `quality` | Linters re-run on the produced workspace post-verify | ruff (Python), staticcheck/go vet (Go), tsc (TS), clippy (Rust). |

`runner.py` writes one JSON line per run to `results/runs.jsonl`, then
`analyze.py` aggregates to a markdown table with medians.

## 2. Agent invocations

We do **not** retrofit a uniform "agent API". Each harness is invoked
in its own documented headless mode, with the flags closest to "go do
the task, no interactive prompts". Wrappers live in `agents/*.sh`.

Verbatim flags as of 2026-05-24:

| Agent | Command line (flags only, prompt elided) | Source file |
| --- | --- | --- |
| `claude-code` | `claude -p --output-format json --permission-mode bypassPermissions --no-session-persistence` | `agents/claude-code.sh` |
| `codex` | `codex exec --json --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -c model=gpt-5.5 -c model_reasoning_effort=xhigh -c service_tier=fast` | `agents/codex.sh` |
| `claude-deepseek` | Same as `claude-code`, with `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` redirected to a DeepSeek Anthropic-compatible proxy via `~/deepseek/.deepseek-env` | `agents/claude-deepseek.sh` |
| `qwen-code` | `qwen --yolo --output-format json --auth-type openai --chat-recording false` with `OPENAI_*` env from `~/qwen/.qwen-env` pointing at `dashscope-intl.aliyuncs.com` | `agents/qwen-code.sh` |
| `opencode` | `opencode run --model deepseek/deepseek-v4-pro --format json` with DeepSeek key from `~/deepseek/.deepseek-env` | `agents/opencode.sh` |
| `pi-ds4pro` | `pi -p --provider deepseek --model deepseek-v4-pro --mode json --no-session --thinking high` | `agents/pi-ds4pro.sh` |
| `pi-flash` | Same Pi CLI invocation, with `--model deepseek-v4-flash` | `agents/pi-flash.sh` |
| `pi-gemini` | `pi -p --provider google --model gemini-3.5-flash --mode json --no-session --thinking high` with key from `~/deepseek/.gemini` | `agents/pi-gemini.sh` |
| `pi-glm` | `pi -p --provider openrouter --model z-ai/glm-5.1 --mode json --no-session --thinking high` with key from a user-local OpenRouter env file | `agents/pi-glm.sh` |

Notes on the flag choices:

- We pass the most permissive sandbox/approval flag each harness
  offers (`--yolo`, `--dangerously-bypass-approvals-and-sandbox`,
  `--permission-mode bypassPermissions`). Isolation is workspace-level,
  not a security sandbox: the runner gives the agent a fresh
  `workspace/` copy and a separate process tree, and does not copy
  `_reference/` into that working directory. A malicious local process
  could still browse outside cwd; realbench assumes cooperative CLIs.
- We do **not** pass `--bare` to `qwen` (it strips `write_file`
  from the tool catalog, which breaks file-creation tasks). Documented
  in `agents/qwen-code.sh`.
- `codex` is **pinned** to gpt-5.5 + reasoning_effort=xhigh +
  service_tier=fast (OpenAI's Priority tier, 2.5× standard list
  price). Passed inline via `-c` so the bench reproduces the same
  setup regardless of the operator's `~/.codex/config.toml`. We
  picked Priority/xhigh as the quality-oriented interactive setup for
  this snapshot — measuring lower tiers would answer a different
  question with a different quality/latency trade-off. See §4 for the
  pricing implications.

## 3. Anti-tamper

Each task ships with a `.test_hash` file containing the SHA-256 of
the verifier files. `runner.py` recomputes the hash post-run; a
mismatch fails the run even if `verify.sh` exits 0. This caught one
real case where a Rust agent reformatted the test file via `rustfmt`.

This is also why realbench does not use an LLM judge: the scored
contract is deterministic local verification.

## 4. Backend models

The agent's model is determined by environment, not by realbench:

| Agent | Model (as observed in `runs.jsonl native_metrics.models`) | How configured |
| --- | --- | --- |
| `claude-code` | `claude-opus-4-7[1m]` (plus `claude-haiku-4-5-20251001` for sub-agents) | Claude Code CLI default |
| `codex` | `gpt-5.5` (pinned in wrapper, reasoning_effort=xhigh, service_tier=fast/Priority) | Hardcoded via `-c` flags in `agents/codex.sh` |
| `claude-deepseek` | `deepseek-v4-pro[1m]` (plus `deepseek-v4-flash` for sub-agents) | Via DeepSeek Anthropic-compatible proxy URL |
| `qwen-code` | `qwen3.7-max` (Alibaba flagship since 2026-05-21) | `OPENAI_MODEL=qwen3.7-max` pinned in `agents/qwen-code.sh`. |
| `opencode` | `deepseek-v4-pro` | `--model deepseek/deepseek-v4-pro` flag |
| `pi-ds4pro` | `deepseek-v4-pro` | `--model deepseek-v4-pro` flag |
| `pi-flash` | `deepseek-v4-flash` | `--model deepseek-v4-flash` flag |
| `pi-gemini` | `gemini-3.5-flash` | `--model gemini-3.5-flash` flag (Google AI Studio API key) |
| `pi-glm` | `z-ai/glm-5.1` | `--provider openrouter --model z-ai/glm-5.1` |

Important caveat for `codex`: the model field is not in the
`runs.jsonl` records (codex doesn't surface it in its event stream).
The wrapper pins it via `-c model=gpt-5.5` so re-runs are stable,
but you have to trust the wrapper. If you switch the pin to a
different model, bump the `codex` row of the pricing table in §5.

## 5. Pricing

Tariffs used by `scripts/make-cost-chart.py` are list price per 1M
tokens, USD, sourced from each provider's official pricing page or explicitly
marked as modeled when the provider does not expose a run-scoped rate.
Each row has its own `Verified` date because providers were checked at
different times during the publication run.

| Model | Input | Cache read | Output | Source URL | Verified |
| --- | --- | --- | --- | --- | --- |
| Claude Opus 4.7 | $5.00 | $0.50 | $25.00 | https://docs.anthropic.com/en/docs/about-claude/pricing | 2026-05-24 |
| GPT-5.5 Priority | $12.50 | $1.25* | $75.00 | https://openai.com/api/pricing | 2026-05-24 |
| DeepSeek V4 Pro | $0.435 | $0.003625 | $0.87 | https://api-docs.deepseek.com/quick_start/pricing | 2026-05-24 |
| DeepSeek V4 Flash | $0.14 | $0.0028 | $0.28 | https://api-docs.deepseek.com/quick_start/pricing | 2026-05-24 |
| Qwen3.7 Max | $1.25 | $0.25 | $3.75 | https://www.qwencloud.com/models/qwen3.7-max | 2026-05-27 |
| Gemini 3.5 Flash | $1.50 | $0.15** | $9.00 | https://ai.google.dev/gemini-api/docs/pricing | 2026-05-24 |
| GLM 5.1 via OpenRouter | $0.98 | $0.182 | $3.08 | https://openrouter.ai/z-ai/glm-5.1/pricing | 2026-05-26 |

\* GPT-5.5 Priority cache read rate is estimated at the same 10%-of-input
ratio as the standard tier ($0.50 / $5.00 = 10%, so $1.25 / $12.50 = 10%).
OpenAI does not publish a separate cached-priority figure as of the
snapshot date. If you read this and the published rate differs, that's
what counts — update the table and the script.

\** Gemini cache-read pricing is modeled at 10% of input for this snapshot,
matching the discount shape Google publishes for current Flash context-caching
tiers. If Google publishes a different Gemini 3.5 Flash cache-read rate, that
published rate should replace this modeled value.

These charted costs are run-scoped telemetry estimates, not provider-invoice
reconciliations. Provider invoices can include exploratory runs, failed
integrations, retries outside `results/runs-en-135.jsonl`, and billing details
that are not exposed per run.

Caveats already encoded in `make-cost-chart.py`:

- DeepSeek's "75% off" promo on V4 Pro became the standing price on
  2026-05-22 (announced on DeepSeek's pricing page). If the promo
  expires the listed reversion is $1.74 / $0.0145 / $3.48 per 1M.
- Qwen3.7 Max exposes cache-read telemetry in Qwen Code's native JSON.
  The chart treats `input_tokens` as total prompt tokens and
  `cache_read_input_tokens` as the cached subset, billed at Qwen Cloud's
  public implicit-cache rate.
- Anthropic's Opus 4.7 uses a new tokenizer that may consume up to 35%
  more tokens for the same text — this is already reflected in the
  per-call token counts the API returns, so the dollar total is right.

Codex is a subscription product in practice; its bar is the
hypothetical pay-as-you-go cost at the **Priority** tier of GPT-5.5.
We pin `service_tier=fast` (= Priority) and `model_reasoning_effort=xhigh`
in `agents/codex.sh` (§2), which together push codex's estimate to
the top of the chart for two compounding reasons:

1. Priority list price is 2.5× standard tier ($12.50 vs $5 per 1M
   input, $75 vs $30 per 1M output). If you flip the wrapper to
   `service_tier=auto` (standard), the codex bar shrinks ~60%.
2. `xhigh` reasoning effort emits 5–10× more `reasoning_output_tokens`
   than `medium`. Output tokens dominate codex's per-call cost, so
   pushing effort to xhigh roughly doubles the spend independently
   of the tier choice.

That setup is the quality-oriented interactive codex configuration in
this snapshot. Testing a lower tier would be cheaper and also defensible,
but it would answer a different question. Fork the wrapper and re-run
if you want the lower-tier number.

### What the cost chart actually sums

The published cost chart reads `results/runs-en-135.jsonl`. In the public
repo, `results/runs.jsonl` is the same curated snapshot kept at the default
path used by local tools. The slice contains exactly five English-prompt
records per public `(agent, task)` cell: 9 agents × 27 tasks × 5 runs =
1215 records.

Each bar is `Σ (tokens × per-million rate)` over those 135 records for that
agent, including strict failures and timeouts. We do not extrapolate from a
single run, and we do not drop failed attempts: failed attempts still cost
money.

For Pi-family harnesses, `scripts/check-cost-reconciliation.py` prints the
sum of Pi's own `pi_reported_cost_usd` field. In the current snapshot,
`pi-gemini` has 134 rows with Pi-reported run costs and one strict timeout row
without native run-cost telemetry. A Google invoice for the same account is
therefore not expected to match the chart unless it is filtered to exactly the
same project, time window, model, and runs.

Pi CLI JSONL reports usage at the end of each turn, so the parser sums all
turn-level usage events for Pi-family agents.

## 6. Wall time and `num_turns`

- **`wall_ms` is comparable cross-harness.** Same machine, same
  monotonic clock around the same subprocess.
- **`num_turns` is NOT comparable cross-harness.** Codex aggregates
  to 1, Claude Code reports 7–18 on the same task. Do not rank
  agents on it.

Wall time includes wrapper overhead (CLI startup, tool catalog
loading, model context preparation). On small tasks like
`001-fizzbuzz` this overhead dominates — that's a real signal about
the harness, not a measurement artifact.

## 7. Reproducibility — machine

All runs in the snapshotted `runs.jsonl` were produced on:

- Hardware: Apple M2 Max, 12 cores, 32 GB RAM
- OS: macOS 26.2 (build 25C56)
- Filesystem: APFS, local SSD

Toolchain versions (verifier-side):

- Python 3.14.3 (Homebrew), pytest 9.0.3, ruff 0.15.14
- PHP 8.5.1 (NTS), Composer 2.8.9
- Node 25.2.1, npm 11.x
- Go 1.26.0 (darwin/arm64), staticcheck 2026.1 / v0.7.0, goleak 1.3.0
- Rust 1.94.0 stable, cargo 1.94.0, clippy 0.1.94

Older toolchains may produce different verifier or linter behavior. The
versions above are the tested snapshot environment, not a minimum-support
matrix.

Agent CLI versions:

- `claude` 2.1.141 (Claude Code)
- `codex-cli` 0.133.0
- `qwen` 0.16.1
- `opencode` and Pi CLI versions are captured in their native output when the
  CLIs expose them.

The bench has not been validated on Linux x86 or Windows WSL. Expected
to work, contributions welcome.

## 8. Reproducibility — running the bench

```bash
git clone https://github.com/512banque/realbench
cd realbench
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Configure secrets (none committed). Each agent reads from a
# user-local file under $HOME, never from the repo:
#   ~/deepseek/.deepseek-env   ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN
#   ~/qwen/.qwen-env           OPENAI_API_KEY, OPENAI_BASE_URL
#   ~/deepseek/.gemini         Gemini API key for pi-gemini
#   ~/openrouter/.openrouter-env OPENROUTER_API_KEY for pi-glm
# claude-code and codex use the CLI's own login (claude auth, codex login).

# Full matrix, single-run-per-cell (smoke test):
python3 runner.py --runs 1 --timeout 900

# Statistical run for publication. Wall ≈ 5–8h sequential, cost ≈
# $200–$300 at the list-price totals reported by scripts/make-cost-chart.py
# (dominated by codex at GPT-5.5 Priority and claude-code at Opus 4.7).
python3 runner.py --runs 5 --timeout 900

# One specific cell, useful while debugging:
python3 runner.py --agents claude-code --tasks 001-fizzbuzz --runs 1

# Aggregate the table:
python3 analyze.py

# Build the comparable EN 135-run slice and regenerate the two headline charts:
.venv/bin/python scripts/curate-en-135.py
.venv/bin/python scripts/make-same-backend-summary.py
.venv/bin/python scripts/check-cost-reconciliation.py
REALBENCH_RUNS=results/runs-en-135.jsonl .venv/bin/python scripts/make-comparison.py
REALBENCH_RUNS=results/runs-en-135.jsonl REALBENCH_COST_SCOPE_LABEL='curated EN 135-run snapshot' REALBENCH_COST_ONLY_AGENTS_WITH_RUNS=1 .venv/bin/python scripts/make-cost-chart.py
```

## 9. Re-run cadence

Pricing pages drift, CLIs auto-update, default models change. To stay
honest, the curated public snapshot should be refreshed on a predictable
cadence:

- **Pricing pages**: re-verify before every chart regeneration. The
  per-model `Verified` column in §5 is the contract.
- **CLI versions and model defaults**: re-check whenever a major
  release ships for any of the nine public harnesses.
- **Full matrix re-run**: at least monthly while the bench is being
  actively published, or whenever any of the above changes.

A re-run that produces materially different numbers should be committed
alongside a note in the README, a new `results/runs.jsonl`, and a
regenerated `results/runs-en-135.jsonl`. `runs.jsonl` is a tracked snapshot
artifact, not an append-only event log.

The public slice is generated only by the closed rules in
`scripts/curate-en-135.py`: keep the nine public agents and 27 public tasks,
exclude pre-English-prompt rows for tasks 001-023, drop runner-infra records
that never produced an agent or verify exit code, sort deterministically, and
keep the first five valid records per `(agent, task)`.

## 10. What this bench does NOT measure

To set expectations and avoid attacks:

- **It's not a model benchmark.** It measures harness behaviour on
  agentic tasks. The same model under a different harness will land
  different numbers. That's the point.
- **It's not a raw model leaderboard.** The public badge is strict
  `success=true` over 135 records per harness. Timeouts and anti-tamper
  trips stay failures even if nearby reruns pass.
- **It's not a SWE-bench replacement.** SWE-bench measures model
  capability in a researcher harness on real GitHub bugs. realbench
  measures shipped harness behaviour on a mix of fabricated and
  (one) real task.
- **It does not currently exercise**: SQL/database work, data-science
  notebooks, DevOps / IaC, frontend visual, mobile, sysadmin. Known
  bias section in the README enumerates this. Pull requests welcome.
- **Private exploratory runs are not published.** The public snapshot is the
  comparable 9 agents × 27 tasks × 5 runs slice. It is enough to reproduce the
  published charts, not a complete lab notebook.

See `FAQ.md` for responses to specific criticisms.
