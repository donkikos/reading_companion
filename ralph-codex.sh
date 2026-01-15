#!/usr/bin/env bash
set -euo pipefail

timestamp=$(date +"%Y%m%d_%H%M%S")

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <iterations>"
  exit 1
fi

mkdir -p .codex/logs

for ((i=1; i<=$1; i++)); do
  echo "=== Iteration $i ==="

  log=".codex/logs/codex_iteration_${i}_${timestamp}.txt"

  # Run Codex with live streaming output (stdout+stderr), while saving a copy.
  # NOTE: no command substitution - that keeps live progress intact.
  cat ralph_prompt.md | codex exec --full-auto 2>&1 | tee "$log"

  if grep -q "<promise>COMPLETE</promise>" "$log"; then
    echo "PRD complete, exiting."
    tmsg "PRD complete after $i iterations"
    exit 0
  fi
done
