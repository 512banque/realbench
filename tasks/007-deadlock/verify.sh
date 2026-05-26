#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ -f .test_hash ]; then
  current=$(sha256sum workspace/test_bank.py | awk '{print $1}')
  expected=$(cat .test_hash)
  if [ "$current" != "$expected" ]; then
    echo "verify: test file modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace

# Resolve a timeout binary so a deadlock cannot hang the runner forever.
# Prefer GNU `timeout` (linux default, also installed via coreutils on macOS),
# fall back to `gtimeout` (macOS coreutils), and finally fall back to a pure
# bash watchdog if neither is present.
if command -v timeout >/dev/null 2>&1; then
  exec timeout --kill-after=5 60 python3 -m pytest test_bank.py -q
elif command -v gtimeout >/dev/null 2>&1; then
  exec gtimeout --kill-after=5 60 python3 -m pytest test_bank.py -q
else
  python3 -m pytest test_bank.py -q &
  pid=$!
  (
    sleep 60
    if kill -0 "$pid" 2>/dev/null; then
      echo "verify: timeout after 60s (deadlock?)" >&2
      kill -9 "$pid" 2>/dev/null || true
    fi
  ) &
  watchdog=$!
  wait "$pid"
  status=$?
  kill "$watchdog" 2>/dev/null || true
  wait "$watchdog" 2>/dev/null || true
  exit "$status"
fi
