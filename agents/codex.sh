#!/usr/bin/env bash
# Wrapper for Codex CLI.
# Usage: codex.sh <prompt_file> <raw_dir>
# cwd is set by the runner to the task workspace.
set -u

prompt_file="$1"
raw_dir="$2"
mkdir -p "$raw_dir"

prompt="$(cat "$prompt_file")"

# exec                                       : non-interactive mode
# --json                                     : JSONL event stream on stdout
# --dangerously-bypass-approvals-and-sandbox : auto-approve every tool call (no sandbox)
# --skip-git-repo-check                      : workspace is not a git repo
# -c model=gpt-5.5                           : pin the model; ignore local
#                                              ~/.codex/config.toml so the bench
#                                              is reproducible across machines
# -c model_reasoning_effort=xhigh            : highest reasoning tier (more
#                                              reasoning_output_tokens, longer
#                                              traces, more accurate fixes)
# -c service_tier=fast                       : OpenAI's "priority" tier (2.5x
#                                              standard list price; the bench
#                                              measures fast/priority because
#                                              that's the codex experience we
#                                              want to characterise — interactive
#                                              latency, not batch). See METHODOLOGY.
codex exec \
  --json \
  --dangerously-bypass-approvals-and-sandbox \
  --skip-git-repo-check \
  -c model=gpt-5.5 \
  -c model_reasoning_effort=xhigh \
  -c service_tier=fast \
  "$prompt" \
  </dev/null \
  >"$raw_dir/stdout.txt" \
  2>"$raw_dir/stderr.txt"
rc=$?

# stdout is the native JSONL event stream.
if [ -s "$raw_dir/stdout.txt" ]; then
  cp "$raw_dir/stdout.txt" "$raw_dir/native.jsonl"
fi

exit "$rc"
