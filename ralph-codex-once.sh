set -e

: "${GIT_AUTHOR_NAME:=Ralph Codex}"
: "${GIT_COMMITTER_NAME:=$GIT_AUTHOR_NAME}"
: "${GIT_AUTHOR_EMAIL:=ralph-codex@local}"
: "${GIT_COMMITTER_EMAIL:=$GIT_AUTHOR_EMAIL}"

cat ralph_prompt.md | codex exec --full-auto

echo "PRD complete, exiting."
tmsg "Ralph Once completed PRD."
exit 0
