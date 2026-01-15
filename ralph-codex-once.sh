set -e

cat ralph_prompt.md | codex exec --full-auto

echo "PRD complete, exiting."
tmsg "Ralph Once completed PRD."
exit 0
