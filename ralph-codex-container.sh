#!/usr/bin/env bash
set -euo pipefail

if [[ -f /.dockerenv ]] || [[ "${IN_CONTAINER:-}" == "1" ]]; then
  # Running inside the dev container.
  export CODEX_HOME="${CODEX_HOME:-/app/.codex}"

  if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <iterations>"
    exit 1
  fi

  timestamp=$(date +"%Y%m%d_%H%M%S")

  mkdir -p .codex/logs

  for ((i=1; i<=$1; i++)); do
    echo "=== Iteration $i ==="

    log=".codex/logs/codex_iteration_${i}_${timestamp}.txt"

    # Run Codex with live streaming output (stdout+stderr), while saving a copy.
    # NOTE: no command substitution - that keeps live progress intact.
    cat ralph_prompt.md | codex exec --dangerously-bypass-approvals-and-sandbox 2>&1 | tee "$log"

    if grep -q "<promise>COMPLETE</promise>" "$log"; then
      echo "PRD complete, exiting."
      exit 0
    fi
  done

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
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm codex ./ralph-codex-container.sh "$@"

if command -v tmsg >/dev/null 2>&1; then
  tmsg "Ralph Codex container run completed."
fi
