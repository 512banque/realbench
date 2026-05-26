#!/usr/bin/env bash
# Wrapper for OpenCode (anomalyco/opencode) — universal AI coding agent
# CLI. We bench it on DeepSeek V4 Pro for the same harness-vs-native
# comparison as agents/pi-ds4pro.sh.
#
# AUTH: same DeepSeek key as pi-ds4pro.sh, sourced from ~/deepseek/.deepseek-env.
# OpenCode reads DEEPSEEK_API_KEY directly.
#
# IMPORTANT: `opencode run --format json` only streams `step_start`
# events on stdout. The detailed per-run usage / cost is in the session
# DB; we recover it via `opencode export <sessionID>` after the run.
# The wrapper captures the sessionID from the stdout stream's
# `step_start.sessionID` field and re-invokes opencode to dump the
# session JSON into raw_dir/session.json — that's what parse_opencode
# reads.
#
# Usage: opencode.sh <prompt_file> <raw_dir>
set -u

prompt_file="$1"
raw_dir="$2"
mkdir -p "$raw_dir"

env_file="$HOME/deepseek/.deepseek-env"
if [ ! -r "$env_file" ]; then
  printf 'opencode: cannot read %s (expected DeepSeek API key)\n' \
    "$env_file" >"$raw_dir/stderr.txt"
  exit 127
fi
DEEPSEEK_API_KEY="$(grep '^export ANTHROPIC_AUTH_TOKEN=' "$env_file" \
  | sed 's/^export ANTHROPIC_AUTH_TOKEN=//' | tr -d '"')"
export DEEPSEEK_API_KEY

prompt="$(cat "$prompt_file")"

opencode run \
  --model deepseek/deepseek-v4-pro \
  --format json \
  "$prompt" \
  </dev/null \
  >"$raw_dir/stdout.txt" \
  2>"$raw_dir/stderr.txt"
rc=$?

if [ -s "$raw_dir/stdout.txt" ]; then
  cp "$raw_dir/stdout.txt" "$raw_dir/native.jsonl"
fi

# Recover detailed usage via `opencode export`. The session id is in the
# first `step_start` event's `sessionID` field (`ses_...`).
session_id="$(head -1 "$raw_dir/stdout.txt" 2>/dev/null \
  | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(d.get('sessionID') or (d.get('part') or {}).get('sessionID') or '')
except Exception:
    print('')
" 2>/dev/null)"

if [ -n "$session_id" ]; then
  # When stdout is not a TTY, `opencode export` writes pure JSON
  # straight to stdout (the "Exporting session: ..." banner is
  # TTY-only). So we redirect as-is.
  opencode export "$session_id" </dev/null \
    >"$raw_dir/session.json" 2>>"$raw_dir/stderr.txt"
  if [ ! -s "$raw_dir/session.json" ]; then
    printf 'opencode: export of %s returned empty\n' "$session_id" \
      >>"$raw_dir/stderr.txt"
  fi
else
  printf 'opencode: could not extract sessionID from stdout\n' \
    >>"$raw_dir/stderr.txt"
fi

exit "$rc"
