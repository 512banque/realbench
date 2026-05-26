#!/usr/bin/env bash
# Variant of agents/pi-ds4pro.sh that targets DeepSeek V4 Flash instead of
# V4 Pro. Same harness (Pi), same provider (DeepSeek), same auth
# source — only the model differs.
#
# Purpose: isolate the "small fast model vs large model" trade-off
# on a harness whose cache implementation is already proven
# Flash is ~3x cheaper per token at list ($0.14/$0.28 vs $0.435/$0.87),
# so if it passes 24/24 it becomes the new cost floor.
#
# Usage: pi-flash.sh <prompt_file> <raw_dir>
set -u

prompt_file="$1"
raw_dir="$2"
mkdir -p "$raw_dir"

env_file="$HOME/deepseek/.deepseek-env"
if [ ! -r "$env_file" ]; then
  printf 'pi-flash: cannot read %s\n' "$env_file" >"$raw_dir/stderr.txt"
  exit 127
fi

DEEPSEEK_API_KEY="$(grep '^export ANTHROPIC_AUTH_TOKEN=' "$env_file" \
  | sed 's/^export ANTHROPIC_AUTH_TOKEN=//' | tr -d '"')"
export DEEPSEEK_API_KEY

prompt="$(cat "$prompt_file")"

pi \
  -p \
  --provider deepseek \
  --model deepseek-v4-flash \
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
