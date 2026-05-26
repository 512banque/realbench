#!/usr/bin/env bash
# Verify the retry orchestrator.
# Exit codes:
#   0   = success
#   2   = test file modified (hash mismatch)
#   non-zero from pytest = test failed
set -e
cd "$(dirname "$0")"

if [ -f .test_hash ]; then
  current=$(sha256sum workspace/test_orchestrator.py workspace/services.py | sha256sum | awk '{print $1}')
  expected=$(cat .test_hash)
  if [ "$current" != "$expected" ]; then
    echo "verify: test/service files modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace
exec python3 -m pytest test_orchestrator.py -q
