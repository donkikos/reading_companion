#!/usr/bin/env bash
set -euo pipefail

if [[ -f /.dockerenv ]] || [[ "${IN_CONTAINER:-}" == "1" ]]; then
  # Running inside the dev container.
  export CODEX_HOME="${CODEX_HOME:-/app/.codex}"
  : "${GIT_AUTHOR_NAME:=Ralph Codex}"
  : "${GIT_COMMITTER_NAME:=$GIT_AUTHOR_NAME}"
  : "${GIT_AUTHOR_EMAIL:=ralph-codex@local}"
  : "${GIT_COMMITTER_EMAIL:=$GIT_AUTHOR_EMAIL}"
  cat ralph_prompt.md | codex exec --dangerously-bypass-approvals-and-sandbox
  exit 0
fi

# Running on host: execute inside the dev container.
if ! docker image inspect epub_ai_reader_ralph_app >/dev/null 2>&1; then
  docker compose -f docker-compose.yml -f docker-compose.dev.yml build app
fi
if ! docker image inspect epub_ai_reader_ralph_codex >/dev/null 2>&1; then
  docker compose -f docker-compose.yml -f docker-compose.dev.yml build codex
fi
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm codex ./ralph-codex-once-container.sh

if command -v tmsg >/dev/null 2>&1; then
  tmsg "Ralph Once completed PRD."
fi
