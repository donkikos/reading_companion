#!/usr/bin/env bash
set -euo pipefail

timestamp=$(date +"%Y%m%d_%H%M%S")

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <iterations>"
  exit 1
fi

: "${GIT_AUTHOR_NAME:=Ralph Claude}"
: "${GIT_COMMITTER_NAME:=$GIT_AUTHOR_NAME}"
: "${GIT_AUTHOR_EMAIL:=ralph-claude@local}"
: "${GIT_COMMITTER_EMAIL:=$GIT_AUTHOR_EMAIL}"

mkdir -p .claude/logs

for ((i=1; i<=$1; i++)); do
  echo "=== Iteration $i ==="

  log=".claude/logs/claude_iteration_${i}_${timestamp}.txt"

  # Run Claude with live streaming output (stdout+stderr), while saving a copy.
  # NOTE: no command substitution - that’s what killed live progress.
  claude --permission-mode acceptEdits -p "@plans/prd.json @plans/progress.txt \
1. Find the highest-priority feature to work on and work only on that feature. \
This should be the one YOU decide has the highest priority - not necessarily the first in the list. \
2. Run ruff format on changed Python files, then ruff check ., then pytest, and ensure they pass. \
3. Update the PRD with the work that was done. \
4. Append your progress to the plans/progress.txt file. \
Use this to leave a note for the next person working in the codebase. \
5. Make a git commit of that feature. \
ONLY WORK ON A SINGLE FEATURE. \
If, while implementing the feature, you notice the PRD is complete, output <promise>COMPLETE</promise>. \
" 2>&1 | tee "$log"

  if grep -q "<promise>COMPLETE</promise>" "$log"; then
    echo "PRD complete, exiting."
    tt notify "AI Hero CLI PRD complete after $i iterations"
    exit 0
  fi
done
