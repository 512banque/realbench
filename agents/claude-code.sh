#!/usr/bin/env bash
# Wrapper for Claude Code CLI.
# Usage: claude-code.sh <prompt_file> <raw_dir>
# cwd is set by the runner to the task workspace.
set -u

prompt_file="$1"
raw_dir="$2"
mkdir -p "$raw_dir"

prompt="$(cat "$prompt_file")"

# -p              : non-interactive print mode
# --output-format json : structured result on stdout (tokens, model, num_turns)
# --permission-mode bypassPermissions : auto-approve everything (sandboxed by runner anyway)
# --no-session-persistence : do not persist session to disk
claude \
  -p \
  --output-format json \
  --permission-mode bypassPermissions \
  --no-session-persistence \
  "$prompt" \
  >"$raw_dir/stdout.txt" \
  2>"$raw_dir/stderr.txt"
rc=$?

# stdout is the native JSON — duplicate it under native.json for parser convenience.
if [ -s "$raw_dir/stdout.txt" ]; then
  cp "$raw_dir/stdout.txt" "$raw_dir/native.json"
fi

exit "$rc"
