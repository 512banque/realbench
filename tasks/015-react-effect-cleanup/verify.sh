#!/usr/bin/env bash
# Toolchain: Node 20+ (tested with 25.2.1), TypeScript 5.5+
# Exit codes:
#   0   = success
#   2   = test file tampered with (hash mismatch)
#   4   = npm ci failed
#   5   = jest tests failed
#   127 = node/npm not on PATH
set -u
cd "$(dirname "$0")"

if ! command -v node >/dev/null; then
  echo "verify: node not found on PATH" >&2
  exit 127
fi
if ! command -v npm >/dev/null; then
  echo "verify: npm not found on PATH" >&2
  exit 127
fi

if [ -f .test_hash ]; then
  current=$(sha256sum workspace/tests/useDebounce.test.tsx | awk '{print $1}')
  expected=$(cat .test_hash | tr -d '[:space:]')
  if [ "$current" != "$expected" ]; then
    echo "verify: test file modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace

if ! npm ci --no-audit --no-fund --prefer-offline >npm.log 2>&1; then
  echo "verify: npm ci failed" >&2
  cat npm.log >&2 || true
  exit 4
fi

if command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT="gtimeout 120"
elif command -v timeout >/dev/null 2>&1; then
  TIMEOUT="timeout 120"
else
  TIMEOUT="perl -e alarm(120);exec(@ARGV) --"
fi

if ! $TIMEOUT npx jest --no-coverage 2>&1; then
  echo "verify: jest failed" >&2
  exit 5
fi

echo "verify: OK"
exit 0
