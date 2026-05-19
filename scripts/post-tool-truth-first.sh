#!/bin/sh
# post-tool-truth-first.sh — Claude Code PostToolUse hook (Edit|Write|MultiEdit).
#
# When a write lands in a project's ACTIVE governance doc (CONSTITUTION.md /
# AGENTS.md / CLAUDE.md / decisions/** / .governance/**) and the written text
# contains an unsourced technical claim or asserted uncertainty phrasing, append
# ONE fixed-format marker comment at the end of that doc and exit 0 (non-blocking).
#
# Deliberately NOT scoped to pedagogical docs (METHODOLOGY*/README/CASES/
# CONTRIBUTING) — they quote the forbidden vocabulary while teaching it; flagging
# them would be the very ② drift this guards against. Same design as drift-check.sh.
#
# Non-blocking, idempotent-ish (re-appends only on a new risky write), no external
# state. jq used if present; if jq is missing, exit 0 silently (never block work).

set -eu

command -v jq >/dev/null 2>&1 || exit 0
IN=$(cat 2>/dev/null || true)
[ -n "$IN" ] || exit 0

fp=$(printf '%s' "$IN" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
[ -n "$fp" ] || exit 0

base=$(basename "$fp")
case "$base" in
  CONSTITUTION.md|AGENTS.md|CLAUDE.md) is_gov=1 ;;
  *) is_gov=0 ;;
esac
case "$fp" in
  */decisions/*|decisions/*|*/.governance/*|.governance/*) is_gov=1 ;;
esac
[ "$is_gov" = 1 ] || exit 0

txt=$(printf '%s' "$IN" | jq -r '
  (.tool_input.new_string // empty),
  (.tool_input.content // empty),
  ((.tool_input.edits // []) | map(.new_string // empty) | join("\n"))
' 2>/dev/null || true)
[ -n "$txt" ] || exit 0

# strip quoted / backticked / emphasized spans (quoted = discussed, not asserted)
clean=$(printf '%s\n' "$txt" | sed \
  -e 's/`[^`]*`/ /g' -e 's/"[^"]*"/ /g' -e "s/'[^']*'/ /g" \
  -e 's/“[^”]*”/ /g' -e 's/\*\*[^*]*\*\*/ /g')

UNCERT='我记得|应该是|大概|可能是|似乎|据说|I recall|should be|probably|supposedly|seems'
TECH='使用|依赖|调用|导入|配置为|uses|imports|depends on|calls'

risk=0
printf '%s' "$clean" | grep -Eq "$UNCERT" && risk=1
if printf '%s' "$clean" | grep -Eq "$TECH"; then
  printf '%s' "$txt" | grep -Eq '[A-Za-z0-9_./-]+\.[A-Za-z0-9]+:[0-9]+' || risk=1
fi

[ "$risk" = 1 ] || exit 0

[ -f "$fp" ] || exit 0
ts=$(date '+%Y-%m-%d %H:%M')
printf '\n<!-- [governance self-check %s] this write contains an unsourced technical claim or asserted uncertainty phrasing; human review requested -->\n' "$ts" >> "$fp" 2>/dev/null || true
exit 0
