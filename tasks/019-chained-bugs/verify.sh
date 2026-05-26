#!/usr/bin/env bash
# Toolchain: Python >= 3.10, pytest
# Exit codes:
#   0   = success (all tests pass)
#   2   = test file was tampered with (hash mismatch)
#   127 = python3 or pytest not found
#   non-zero (other) = pytest failure
set -u
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "verify: python3 not found on PATH" >&2
  exit 127
fi

if [ -f .test_hash ]; then
  current=$(sha256sum workspace/tests/test_pipeline.py | awk '{print $1}')
  expected=$(cat .test_hash)
  if [ "$current" != "$expected" ]; then
    echo "verify: test file modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace
exec python3 -m pytest tests/test_pipeline.py -q
