#!/usr/bin/env bash
set -euo pipefail

if [[ -f /.dockerenv ]] || [[ "${IN_CONTAINER:-}" == "1" ]]; then
  # Running inside the dev container.
  export CODEX_HOME="${CODEX_HOME:-/app/.codex}"
  : "${GIT_AUTHOR_NAME:=Ralph Codex}"
  : "${GIT_COMMITTER_NAME:=$GIT_AUTHOR_NAME}"
  : "${GIT_AUTHOR_EMAIL:=ralph-codex@local}"
  : "${GIT_COMMITTER_EMAIL:=$GIT_AUTHOR_EMAIL}"

  if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <iteration> [timestamp]"
    exit 1
  fi

  iteration="$1"
  timestamp="${2:-$(date +"%Y%m%d_%H%M%S")}"

  mkdir -p .codex/logs

  echo "=== Iteration $iteration ==="

  log=".codex/logs/codex_iteration_${iteration}_${timestamp}.txt"

  # Run Codex with live streaming output (stdout+stderr), while saving a copy.
  # NOTE: no command substitution - that keeps live progress intact.
  cat ralph_prompt.md | codex exec --dangerously-bypass-approvals-and-sandbox 2>&1 | tee "$log"

  success_line=$(grep -m1 -E '^<promise>US_SUCCESS: US-[0-9]+</promise>$' "$log" || true)
  if [[ -z "$success_line" ]]; then
    echo "User story not fully completed; missing success marker."
    exit 1
  fi

  if grep -q "^<promise>COMPLETE</promise>$" "$log"; then
    echo "PRD complete, exiting."
    exit 0
  fi

  exit 0
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <iterations>"
  exit 1
fi

# Running on host: execute inside the dev container.
if ! docker image inspect epub_ai_reader_ralph_app >/dev/null 2>&1; then
  docker compose -f docker-compose.yml -f docker-compose.dev.yml build app
fi
if ! docker image inspect epub_ai_reader_ralph_codex >/dev/null 2>&1; then
  docker compose -f docker-compose.yml -f docker-compose.dev.yml build codex
fi

iterations="$1"
timestamp=$(date +"%Y%m%d_%H%M%S")

for ((i=1; i<=iterations; i++)); do
  docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm codex ./ralph-codex-container.sh "$i" "$timestamp"

  log=".codex/logs/codex_iteration_${i}_${timestamp}.txt"

  success_line=""
  if [[ -f "$log" ]]; then
    success_line=$(grep -m1 -E '^<promise>US_SUCCESS: US-[0-9]+</promise>$' "$log" || true)
  fi
  if [[ ! -f "$log" ]] || [[ -z "$success_line" ]]; then
    if command -v tmsg >/dev/null 2>&1; then
      tmsg "Ralph Codex iteration $i failed."
    fi
    exit 1
  fi

  success_id="${success_line#<promise>US_SUCCESS: }"
  success_id="${success_id%</promise>}"

  if command -v tmsg >/dev/null 2>&1; then
    tmsg "Ralph Codex iteration $i completed (${success_id})."
  fi

  if grep -q "^<promise>COMPLETE</promise>$" "$log"; then
    if command -v tmsg >/dev/null 2>&1; then
      tmsg "PRD complete, exiting."
    fi
    exit 0
  fi
done

if command -v tmsg >/dev/null 2>&1; then
  tmsg "Ralph Codex container run completed."
fi
