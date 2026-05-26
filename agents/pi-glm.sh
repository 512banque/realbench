#!/usr/bin/env bash
# Variant of agents/pi-ds4pro.sh that targets Z.ai GLM 5.1 through OpenRouter.
#
# AUTH: OPENROUTER_API_KEY is sourced from ~/openrouter/.openrouter-env.
# No key is read from the repo.
#
# Usage: pi-glm.sh <prompt_file> <raw_dir>
set -u

prompt_file="$1"
raw_dir="$2"
mkdir -p "$raw_dir"

env_file="$HOME/openrouter/.openrouter-env"
if [ ! -r "$env_file" ]; then
  printf 'pi-glm: cannot read %s (expected OPENROUTER_API_KEY)\n' "$env_file" \
    >"$raw_dir/stderr.txt"
  exit 127
fi
# shellcheck disable=SC1090
source "$env_file"

prompt="$(cat "$prompt_file")"

pi \
  -p \
  --provider openrouter \
  --model z-ai/glm-5.1 \
  --mode json \
  --no-session \
  --thinking high \
  "$prompt" \
  </dev/null \
  >"$raw_dir/stdout.txt" \
  2>"$raw_dir/stderr.txt"
rc=$?

if [ -s "$raw_dir/stdout.txt" ]; then
  cp "$raw_dir/stdout.txt" "$raw_dir/native.jsonl"
fi

exit "$rc"
