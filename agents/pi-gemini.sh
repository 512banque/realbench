#!/usr/bin/env bash
# Variant of agents/pi-ds4pro.sh that targets Google Gemini 3.5 Flash.
#
# AUTH: GEMINI_API_KEY sourced from ~/deepseek/.gemini (a single-line
# file with the AIzaSy... API key). The path is arbitrary — Pi just
# needs the env var.
#
# Usage: pi-gemini.sh <prompt_file> <raw_dir>
set -u

prompt_file="$1"
raw_dir="$2"
mkdir -p "$raw_dir"

key_file="$HOME/deepseek/.gemini"
if [ ! -r "$key_file" ]; then
  printf 'pi-gemini: cannot read %s (expected Google AI Studio API key)\n' \
    "$key_file" >"$raw_dir/stderr.txt"
  exit 127
fi

GEMINI_API_KEY="$(tr -d '[:space:]' < "$key_file")"
export GEMINI_API_KEY

prompt="$(cat "$prompt_file")"

pi \
  -p \
  --provider google \
  --model gemini-3.5-flash \
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
