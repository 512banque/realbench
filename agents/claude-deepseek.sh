#!/usr/bin/env bash
# Wrapper: Claude Code CLI driven by a DeepSeek backend.
#
# This is `claude -p` with ANTHROPIC_BASE_URL/AUTH_TOKEN redirected to an
# Anthropic-API-compatible DeepSeek proxy (loaded from ~/deepseek/.deepseek-env).
# We measure: Claude Code agentic harness + DeepSeek model.
#
# Usage: claude-deepseek.sh <prompt_file> <raw_dir>
set -u

prompt_file="$1"
raw_dir="$2"
mkdir -p "$raw_dir"

env_file="$HOME/deepseek/.deepseek-env"
if [ ! -r "$env_file" ]; then
  printf 'claude-deepseek: cannot read %s\n' "$env_file" >"$raw_dir/stderr.txt"
  exit 127
fi
# shellcheck disable=SC1090
source "$env_file"

prompt="$(cat "$prompt_file")"

claude \
  -p \
  --output-format json \
  --permission-mode bypassPermissions \
  --no-session-persistence \
  "$prompt" \
  >"$raw_dir/stdout.txt" \
  2>"$raw_dir/stderr.txt"
rc=$?

if [ -s "$raw_dir/stdout.txt" ]; then
  cp "$raw_dir/stdout.txt" "$raw_dir/native.json"
fi

exit "$rc"
