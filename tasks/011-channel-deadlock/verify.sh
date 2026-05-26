#!/usr/bin/env bash
# Toolchain: Go 1.23+ (tested with 1.26.0)
# Exit codes:
#   0   = success
#   2   = test files were tampered with
#   127 = Go toolchain not found
#   non-zero (other) = `go test` failure (deadlock detected via per-test timeout)
set -u
cd "$(dirname "$0")"

if ! command -v go >/dev/null; then
  echo "verify: Go toolchain not found on PATH" >&2
  exit 127
fi

if [ -f .test_hash ]; then
  current=$(sha256sum workspace/pipeline_test.go | awk '{print $1}')
  expected=$(cat .test_hash)
  if [ "$current" != "$expected" ]; then
    echo "verify: test file modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace
exec go test ./... -count=1 -timeout=60s
