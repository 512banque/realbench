#!/usr/bin/env bash
# Wrapper for pi-ds4pro: Pi CLI (earendil-works/pi-coding-agent)
# running DeepSeek V4 Pro. We bench it to see how a
# universal harness performs vs native harnesses (claude-deepseek
# uses the Claude Code loop on the same backend).
#
# AUTH: the wrapper reuses the same DeepSeek key the operator already
# has for claude-deepseek. The key lives in ~/deepseek/.deepseek-env
# (file uses Anthropic-compat naming -- ANTHROPIC_AUTH_TOKEN -- because
# claude-deepseek goes through a proxy, but the underlying value is a
# native DeepSeek API key). We extract it and re-export as
# DEEPSEEK_API_KEY, the env var Pi expects per its docs.
#
# Usage: pi-ds4pro.sh <prompt_file> <raw_dir>
set -u

prompt_file="$1"
raw_dir="$2"
mkdir -p "$raw_dir"

env_file="$HOME/deepseek/.deepseek-env"
if [ ! -r "$env_file" ]; then
  printf 'pi-ds4pro: cannot read %s (expected DeepSeek API key)\n' "$env_file" \
    >"$raw_dir/stderr.txt"
  exit 127
fi

# Extract the DeepSeek key from the shared env file (claude-deepseek uses
# Anthropic-compat naming, but the value is the raw DeepSeek key).
DEEPSEEK_API_KEY="$(grep '^export ANTHROPIC_AUTH_TOKEN=' "$env_file" \
  | sed 's/^export ANTHROPIC_AUTH_TOKEN=//' | tr -d '"')"
export DEEPSEEK_API_KEY

prompt="$(cat "$prompt_file")"

# -p / --print          : non-interactive
# --provider deepseek   : pin the provider (Pi's default is google)
# --model deepseek-v4-pro : pin the model
# --mode json           : JSONL event stream
# --no-session          : don't persist session to ~/.pi/agent/sessions/
# --thinking high       : DeepSeek V4 Pro has thinking mode; high matches
#                         what other harnesses run (claude-code Opus, codex xhigh)
pi \
  -p \
  --provider deepseek \
  --model deepseek-v4-pro \
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
