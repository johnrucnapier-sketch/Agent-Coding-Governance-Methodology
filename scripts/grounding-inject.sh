#!/bin/sh
# SessionStart grounding injector — part of agent-coding-governance-methodology.
# Only hooks auto-fire in Claude Code; this injects a thin directive that points
# at the skills rather than duplicating their content.
set -eu

DIR="$(pwd)"
HAS_GOV="no"
for f in CLAUDE.md docs/CONSTITUTION.md CONSTITUTION.md AGENTS.md; do
  if [ -f "$DIR/$f" ]; then HAS_GOV="yes"; break; fi
done

if [ "$HAS_GOV" = "yes" ]; then
  MSG="This project uses agent-coding-governance. Before acting: invoke the \`session-grounding\` skill and follow its 5-step ritual (read constitution + root rules, identify track, report 5 items and WAIT for human confirmation, verify after changes, get approval before commit). Before writing any technical conclusion, editing docs, or any irreversible/destructive action: invoke \`truth-first\` (cite file:line for every claim; never \"I think/usually/I recall\"; list + rollback + quote authorization before destructive ops). 本项目启用治理:动手前先走 session-grounding;写结论/改文档/不可逆操作前先过 truth-first。"
else
  MSG="agent-coding-governance is installed but no governance docs were found in this project. To bootstrap governance from zero, invoke the \`governance-bootstrap\` skill (a human-driven 8-step checklist). 未发现治理文档;从零建治理请调用 governance-bootstrap。"
fi

# Emit valid JSON via python3 (portable, correct escaping).
python3 - "$MSG" <<'PY'
import json, sys
print(json.dumps({
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": sys.argv[1]
  }
}))
PY
