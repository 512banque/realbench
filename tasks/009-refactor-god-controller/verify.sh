#!/usr/bin/env bash
# Verify the refactor: feature tests must keep passing AND architectural tests
# must now succeed.
# Exit codes:
#   0   = success
#   2   = test files were tampered with
#   3   = composer.json doesn't declare laravel/framework ^12
#   4   = composer install failed
#   5   = phpunit failed
set -u
cd "$(dirname "$0")"

if [ -f .test_hash ]; then
  current=$(sha256sum workspace/tests/Architecture/StructureTest.php workspace/tests/Feature/OrderApiTest.php | sha256sum | awk '{print $1}')
  expected=$(cat .test_hash)
  if [ "$current" != "$expected" ]; then
    echo "verify: test files modified (hash mismatch)" >&2
    exit 2
  fi
fi

cd workspace

# (1) composer.json must declare laravel/framework ^12
if ! grep -Eq '"laravel/framework"[[:space:]]*:[[:space:]]*"\^12\.[0-9]+(\.[0-9]+)?"' composer.json; then
  echo "verify: composer.json must declare \"laravel/framework\": \"^12.x\"" >&2
  exit 3
fi

# (2) composer install must succeed (cache is shared via ~/.composer)
if ! composer install --no-interaction --prefer-dist --no-progress --quiet 2>composer.err; then
  echo "verify: composer install failed" >&2
  cat composer.err >&2 || true
  exit 4
fi

# (3) phpunit must pass on both Feature and Architecture suites
if [ ! -x vendor/bin/phpunit ]; then
  echo "verify: vendor/bin/phpunit missing after composer install" >&2
  exit 4
fi

if ! vendor/bin/phpunit --no-coverage --display-warnings 2>&1; then
  echo "verify: phpunit failed" >&2
  exit 5
fi

echo "verify: OK"
exit 0
