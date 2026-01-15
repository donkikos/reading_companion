#!/usr/bin/env bash
set -euo pipefail

if [[ -f /.dockerenv ]] || [[ "${IN_CONTAINER:-}" == "1" ]]; then
  # Running inside the dev container.
  export CODEX_HOME="${CODEX_HOME:-/app/.codex}"
  cat ralph_prompt.md | codex exec --full-auto
  exit 0
fi

# Running on host: execute inside the dev container.
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm codex ./ralph-codex-once-container.sh

if command -v tmsg >/dev/null 2>&1; then
  tmsg "Ralph Once completed PRD."
fi
