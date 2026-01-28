set -e

: "${GIT_AUTHOR_NAME:=Ralph Claude}"
: "${GIT_COMMITTER_NAME:=$GIT_AUTHOR_NAME}"
: "${GIT_AUTHOR_EMAIL:=ralph-claude@local}"
: "${GIT_COMMITTER_EMAIL:=$GIT_AUTHOR_EMAIL}"

claude --permission-mode acceptEdits "@plans/prd.json @plans/progress.txt \
1. Find the highest-priority feature to work on and work only on that feature. \
This should be the one YOU decide has the highest priority - not necessarily the first in the list. \
2. Run ruff format on changed Python files, then ruff check ., then pytest, and ensure they pass. \
3. Update the PRD with the work that was done. \
4. Append your progress to the plans/progress.txt file. \
Use this to leave a note for the next person working in the codebase. \
5. Make a git commit of that feature. \
ONLY WORK ON A SINGLE FEATURE. \
If, while implementing the feature, you notice the PRD is complete, output <promise>COMPLETE</promise>. \
"
