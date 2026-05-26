#!/usr/bin/env bash
# Wrapper for Qwen Code CLI (@qwen-code/qwen-code).
#
# Qwen Code has a documented non-interactive mode (positional prompt +
# `--output-format json`). We pair it with `--yolo` (auto-approve every
# tool call) and explicitly set `--auth-type openai` so the run does not
# fall back to the discontinued qwen-oauth flow.
#
# AUTH: Qwen Code itself ships no `QWEN_API_KEY`. The recommended path is
# the OpenAI-compatible endpoint exposed by Alibaba Cloud Model Studio
# (DashScope). The user is expected to source these env vars from a
# user-local file at $HOME/qwen/.qwen-env, matching the pattern used by
# agents/claude-deepseek.sh. The file must export at least:
#   OPENAI_API_KEY=<dashscope key, e.g. sk-...>
#   OPENAI_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
# No key is ever read from the repo.
#
# Usage: qwen-code.sh <prompt_file> <raw_dir>
# cwd is set by the runner to the task workspace.
set -u

prompt_file="$1"
raw_dir="$2"
mkdir -p "$raw_dir"

env_file="$HOME/qwen/.qwen-env"
if [ ! -r "$env_file" ]; then
  printf 'qwen-code: cannot read %s (expected to export OPENAI_API_KEY and OPENAI_BASE_URL for the DashScope-compatible endpoint)\n' \
    "$env_file" >"$raw_dir/stderr.txt"
  exit 127
fi
# shellcheck disable=SC1090
source "$env_file"
# Pin the model in the wrapper (not the env file) so the bench is
# reproducible across machines. qwen3.7-max is Alibaba's flagship since
# the 2026-05-21 Cloud Summit.
export OPENAI_MODEL=qwen3.7-max

prompt="$(cat "$prompt_file")"

# --yolo                : auto-approve every tool call
# --output-format json  : single JSON array on stdout with full session events
# --auth-type openai    : force OpenAI-compatible provider (qwen-oauth is EOL)
# --chat-recording false: do not persist session to ~/.qwen
# (we deliberately do NOT pass --bare: --bare strips the tool catalog down
#  to read_file / run_shell_command / edit / notebook_edit and removes
#  write_file, which makes file-creation tasks like 001-fizzbuzz harder.)
qwen \
  --yolo \
  --output-format json \
  --auth-type openai \
  --chat-recording false \
  "$prompt" \
  </dev/null \
  >"$raw_dir/stdout.txt" \
  2>"$raw_dir/stderr.txt"
rc=$?

# stdout is the native JSON event array — duplicate it under native.json
# for parser convenience.
if [ -s "$raw_dir/stdout.txt" ]; then
  cp "$raw_dir/stdout.txt" "$raw_dir/native.json"
fi

exit "$rc"
