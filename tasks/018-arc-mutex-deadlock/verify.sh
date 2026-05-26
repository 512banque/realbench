#!/usr/bin/env bash
# Toolchain: Rust 1.80+ stable (tested with 1.94.0)
set -u
cd "$(dirname "$0")"

if ! command -v cargo >/dev/null 2>&1; then
  echo "verify: cargo not found on PATH" >&2
  exit 127
fi

if [ -f .test_hash ]; then
  if command -v sha256sum >/dev/null 2>&1; then
    current=$(sha256sum workspace/tests/integration.rs | awk '{print $1}')
  else
    current=$(shasum -a 256 workspace/tests/integration.rs | awk '{print $1}')
  fi
  expected=$(cat .test_hash)
  if [ "$current" != "$expected" ]; then
    echo "verify: test file modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace

# `--release` for speed; the test logic does not depend on optimization.
# Tests carry their own 5s deadlock deadline and force-exit the process on
# deadlock, so cargo will not hang on the buggy version.
TEST_CMD=(cargo test --release --test integration)

# Outer shell timeout as a belt-and-braces guard in case the in-test
# deadlock detector ever fails to fire.
if command -v timeout >/dev/null 2>&1; then
  exec timeout --kill-after=5 60 "${TEST_CMD[@]}"
elif command -v gtimeout >/dev/null 2>&1; then
  exec gtimeout --kill-after=5 60 "${TEST_CMD[@]}"
else
  "${TEST_CMD[@]}" &
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
