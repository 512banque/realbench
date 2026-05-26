# FAQ

Common criticisms of realbench, answered. If your question isn't here,
open an issue.

Cross-references: `METHODOLOGY.md` for the running protocol and
`BENCH_SPEC.md` for the original brief.

---

## "N is uneven per cell — you're cherry-picking."

The public snapshot is not uneven. Both `results/runs.jsonl` and
`results/runs-en-135.jsonl` contain the same comparable slice:
9 public agents × 27 tasks × 5 English-prompt runs = 1215 records.

What's done about it:

- `scripts/curate-en-135.py` builds the public slice deterministically.
- The headline charts read that slice via `REALBENCH_RUNS=results/runs-en-135.jsonl`.
- `results/runs.jsonl` is kept as the default-path copy for local tooling.

What this bench will not do:

- Claim statistical significance from 27 tasks.
- Hide failures inside the published slice. Strict failures are kept.

## "If the tasks were hard enough, more agents would fail. You're hiding the difficulty."

We have failures, they're concentrated on a few hard tasks, and they're in
`results/runs-en-135.jsonl`:

| Agent | Strict runs | Notes |
| --- | ---: | --- |
| claude-code | 133/135 | one `009` timeout after a passing workspace; one `026` JSON omission |
| codex | 134/135 | one `018` anti-tamper hash failure |
| qwen-code | 134/135 | one `026` JSON omission |
| opencode-DS4pro | 132/135 | one `006` instability; two `026` JSON omissions |
| pi-ds4pro | 131/135 | `006`, `025`, and `026` strict misses |
| pi-flash | 134/135 | one `004` Laravel migration miss |
| pi-gemini | 134/135 | one `006` timeout after a passing workspace |
| pi-glm | 129/135 | one `004` timeout and five `026` JSON omissions |
| claude-deepseek | 128/135 | one `004` timeout, four `006` misses, two `026` omissions |

The matrix is **not** "all pass". Read:

```bash
grep '"success": false' results/runs-en-135.jsonl
```

## "Why strict pass counts? Isn't a timeout with passing tests basically a pass?"

No. The verifier result is useful for diagnosis, but the operational contract is
"the harness completes the task and exits cleanly." A run that leaves a correct
workspace but times out still burns wall time and would leave a user staring at
a hung CLI. We keep those as strict failures and describe them separately from
logic/verifier failures.

## "Why is codex billed at the Priority tier? That's cherry-picking the most expensive config."

`agents/codex.sh` pins three options inline:

- `model=gpt-5.5`
- `model_reasoning_effort=xhigh`
- `service_tier=fast` (= OpenAI's Priority tier)

This is the high-effort, low-latency codex configuration chosen for
this snapshot. Measuring codex at lower tiers would answer a different
question: cheaper codex, with a different quality/latency trade-off.

The trade-off is explicit: Priority is 2.5× standard list price,
and `xhigh` emits 5–10× more reasoning tokens than `medium`. So
the codex bar in the chart is roughly 5× what it would be at
`service_tier=auto` + `model_reasoning_effort=medium`. Both
numbers exist; both are defensible. We picked the high-effort config
because this snapshot compares quality-oriented interactive loops, not
cheapest possible settings. Fork the wrapper if you want the lower tier
— the change is one line, but the full 135-run re-run is still a real run.

Documented in METHODOLOGY.md §2 and §5.

## "Why doesn't the Gemini total match my Google invoice?"

The chart is not a provider-invoice reconciliation. It reads the curated
135-run snapshot, sums native token telemetry, and applies the documented
rates. A Google invoice can include exploratory calls, failed integrations,
retries outside the curated slice, other projects, and provider-side billing
details that are not exposed per run.

For the current snapshot, `pi-gemini` has Pi-reported run costs for 134/135
rows. One strict timeout row has no native run-cost telemetry. You can inspect
the reproducible cross-check with:

```bash
python3 scripts/check-cost-reconciliation.py
```

## "Why not publish every exploratory run?"

Because this repo is a publishable snapshot, not a private lab notebook. The
public chart is generated from `results/runs-en-135.jsonl`, so every shown
agent is on the same 135-record denominator. Exploratory provider checks,
failed integrations, and pre-English-prompt runs are not part of the public
comparison.

## "Your tariffs are arbitrary."

They're not. Every line of the `PRICING` dict in
`scripts/make-cost-chart.py` carries the upstream URL it was last
verified against. The full sourced table, including per-model verification
dates, is in `METHODOLOGY.md` §5. Re-verify before each re-publish.

Known caveats already documented in the script:

- DeepSeek's 75%-off promo on V4 Pro became the permanent list price
  on 2026-05-22. If the promo expires the reversion rate is encoded
  as a comment in the file.
- GPT-5.5 Priority cache read rate is extrapolated from the standard
  tier (10% of input), pending an explicit OpenAI publication. The
  assumption is flagged in `METHODOLOGY.md` §5.
  Sensitivity on the current 135-run codex slice: if cached-priority input
  were free, the codex bar would be about $84.60 instead of $133.39. The
  headline spread would shrink, but the cost-ordering would not flip.
- Qwen Code reports `cache_read_input_tokens`; the chart treats those
  tokens as Qwen Cloud implicit-cache input and applies the public
  implicit-cache tariff.
- Gemini cache-read pricing is modeled at 10% of input because the run logs
  expose cached-token telemetry, while Google billing is not available per
  realbench run. Treat the Gemini row as run-scoped telemetry cost, not invoice
  reconciliation.

If a tariff is wrong, the fix is a one-line PR.

## "You're comparing a heavy harness to a light one. Of course the heavy one is slower / pricier."

Yes. That's the bench.

realbench measures **the harness as shipped**, not the model in
isolation. The interesting comparison is exactly this: same backend
target, different harness — for example `opencode-DS4pro` and
`pi-ds4pro` both target DeepSeek V4 Pro directly, while
`claude-deepseek` targets DeepSeek V4 Pro through a Claude-compatible
proxy and reports some DeepSeek V4 Flash sub-agent calls in native
metrics. The differences in wall time, turn count, and prompt cache
behaviour are therefore harness/proxy-loop effects, not a raw model
leaderboard.

If you want to compare GPT-5.5 vs Opus 4.7 vs DeepSeek V4 Pro as bare
models, the benchmark you want is SWE-bench, HumanEval, or LiveCodeBench.
They exist and they're good at that. realbench is the other axis: how
much does the harness cost you when you `brew install codex`?

realbench deliberately refuses to flatten the agents behind a uniform
proxy because the shipped harness loop is the object being measured.

## "Your tasks are synthetic. Real bugs aren't like this."

Partially true. Fabricated mini-projects are reproducible,
hash-protected, deterministic, and shippable in a public repo without
rights issues. Real codebases drag in tens of MB of unrelated context,
change upstream, and break verifiers.

What we do about it:

- The fabricated tasks are tight: each task ships the smallest
  workspace that reproduces the bug. Tasks 005/006/007 (race
  conditions) and 017/018 (Rust tokio/Arc<Mutex>) are bugs we have
  actually seen in production code.
- Task `024-caddy-intercept-header` calibrates the fabricated battery
  against a real upstream PR — caddyserver/caddy#6429, pinned at the
  parent SHA. The agent must fetch the real codebase, reproduce the
  failure, and ship the same one-line fix the project's maintainers
  shipped. If an agent fails this one, it would likely fail on a real
  user-reported bug too.
- All tasks have non-trivial deterministic verifiers. No LLM judge.

## "Your configuration is unfavourable to agent X."

The exact flags passed to each CLI are documented verbatim in
`METHODOLOGY.md` §2 and visible in `agents/*.sh`. There is no hidden
config.

Choices that could be re-litigated:

- `qwen` runs without `--bare`. We tested `--bare` and it strips
  `write_file` from the tool catalog, breaking file-creation tasks
  like `001-fizzbuzz`. Documented in `agents/qwen-code.sh`.
- `codex` is pinned explicitly to `gpt-5.5`,
  `model_reasoning_effort=xhigh`, and `service_tier=fast` in
  `agents/codex.sh`. Lower effort or standard tier would be cheaper,
  but it would be a different codex configuration.
- `claude-code` does not use Fast Mode (which would multiply Opus
  4.7 cost by 6x). It runs at the standard tier.

If you think a different flag set is fairer, fork, change the wrapper,
re-run, and PR the result with the diff. We can compare it.

## "It's macOS-only. Doesn't run on Linux."

True today. Every snapshot in `runs.jsonl` came off the same Apple
M2 Max under macOS 26.2. The bench has no Mac-specific code (just
bash, python, the agent CLIs, and standard toolchains), so we expect
it to work on Linux x86 and WSL with at most cosmetic changes — but
nobody has validated.

Cross-platform validation is open work. The cost of bringing it up
is low; we just haven't done it. PRs welcome.

## "Coup de chance / cherry-pick / you ran until you got the result you wanted."

`runs.jsonl` is a tracked snapshot artifact, not an immutable event log.
The current public repository is the intentionally squashed initial public
snapshot. Future public snapshots should be committed as ordinary diffs so
additions and removals are reviewable from that point forward.

Concretely:

- Every run included in the current published snapshot is in the file,
  including failures. `grep '"success": false' results/runs-en-135.jsonl`
  returns the current snapshot's real failure count.
- The two visualisations in the README are regenerated by
  deterministic scripts (`scripts/make-comparison.py`,
  `scripts/make-cost-chart.py`) from `results/runs-en-135.jsonl`, which is
  itself generated by `scripts/curate-en-135.py`.
- The curator has closed rules: keep the nine public agents and 27 public
  tasks, exclude pre-English rows for tasks 001-023, drop runner-infra records
  with no agent/verify exit code, and keep the first five valid records per
  `(agent, task)`.
- The published snapshot is dated. The next snapshot will be too. Drift
  and curation should be visible in future git diffs.
- The bench is forkable. If you doubt the run, run it yourself.

Private exploratory logs may be uneven; the public snapshot is the clean
`--runs 5` resnapshot.

---

## "Why no LLM judge?"

Verification is `verify.sh` exiting 0. An LLM judge would add cost,
non-determinism, and a third party we'd then have to defend the prompts
of. Tests are cheaper, faster, deterministic, and the ground truth they
encode is the same ground truth the human authoring the task already had
to encode (otherwise we wouldn't know what "passing" means).

## "Why hash the test file?"

It caught at least one agent that ran `rustfmt` on the test file.
Reformatting tests can mask test deletion or silent skips. Cheap
insurance.

## "Why a quality dimension via ruff/tsc/staticcheck/clippy and not <other tool>?"

We picked the tool each language ecosystem already considers canonical.
Opinionated tools (e.g. `eslint-plugin-...`) would inject our taste into
the measurement. The current choice is "violate-nothing under the
standard tool's default ruleset".

The quality dimension is intentionally coarse. It distinguishes
clean code from sloppy code; it does not adjudicate design taste.
That's by design. The "ambiguous-spec" tasks repeatedly collapsed to a
canonical implementation pattern across frontier models.

## "Why not include <my favourite harness>?"

PR welcome. The contract is one bash file in `agents/`:

- Takes `<prompt_file> <raw_dir>` as args.
- Runs the harness in headless mode.
- Writes the harness's native JSON output to `$raw_dir/native.json`
  (or `.jsonl`).
- Exits the harness's own return code.

Then add a parser to `runner.py` that maps the native JSON to the
shared `native_metrics` shape. If the harness is genuinely headless,
the wrapper is usually under 30 lines.

## "Will you keep this updated?"

See `METHODOLOGY.md` §9. Yes, but on a stated cadence: pricing
re-verified before every chart regeneration, full matrix re-run at
least monthly while the bench is actively published, and a public
snapshot with a date stamp each time. Drift is logged in git.
