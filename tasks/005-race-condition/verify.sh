#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ -f .test_hash ]; then
  current=$(sha256sum workspace/test_inventory.py | awk '{print $1}')
  expected=$(cat .test_hash)
  if [ "$current" != "$expected" ]; then
    echo "verify: test file modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace
exec python3 -m pytest test_inventory.py -q
