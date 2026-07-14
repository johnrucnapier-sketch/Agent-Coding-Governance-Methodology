#!/bin/sh
# Single hook entry point for ACGM V3. Hook inputs remain on stdin.
set -eu

MODE=${1:-}
PLUGIN_DATA=${2:-}
SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INPUT=$(cat 2>/dev/null || true)

if [ -z "${ACGM_DATA_DIR:-}" ] && [ -n "$PLUGIN_DATA" ]; then
  ACGM_DATA_DIR=$PLUGIN_DATA
  export ACGM_DATA_DIR
fi

if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  set +e
  OUTPUT=$(printf '%s' "$INPUT" | python3 "$SELF_DIR/acgm_runtime.py" "hook-$MODE" 2>/dev/null)
  STATUS=$?
  set -e
  if [ "$STATUS" -eq 0 ]; then
    [ -n "$OUTPUT" ] || OUTPUT='{}'
    printf '%s\n' "$OUTPUT"
    exit 0
  fi
fi

# A missing or crashed runtime must never fail silently. Because classification
# is unavailable, Bash fails closed; write hooks conservatively protect the
# human-owned constitution. Other events receive a visible startup warning.
case "$MODE" in
  pretool-bash)
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"ACGM mechanism error: its Python runtime is unavailable or failed, so Bash cannot be classified safely. Restore Python 3 or the plugin package, run acgm doctor, then retry. / ACGM 机制故障：Python 运行时不可用或执行失败，当前无法安全分类 Bash。请恢复 Python 3 或插件包、运行 acgm doctor 后重试。"}}'
    ;;
  pretool-write)
    if printf '%s' "$INPUT" | grep -Eq 'CONSTITUTION\.md'; then
      printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"ACGM mechanism error: the human-owned constitution cannot be evaluated safely while the runtime is broken. Run acgm doctor before retrying. / ACGM 机制故障：运行时损坏时无法安全评估人拥有的宪法写入；请先运行 acgm doctor。"}}'
    else
      printf '%s\n' '{}'
    fi
    ;;
  session-start)
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ACGM is installed but BROKEN: Python 3.10+ is unavailable or the runtime failed. Do not assume governance hooks are healthy; restore the runtime and run `acgm doctor`. / ACGM 已安装但处于 BROKEN：Python 3.10+ 不可用或运行时失败。不要假定治理 hook 正常；请恢复运行时并执行 `acgm doctor`。"}}'
    ;;
  posttool)
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ACGM mechanism error: post-action state could not be persisted. Do not assume no effect; run the declared verification manually and repair ACGM with `acgm doctor`. / ACGM 机制错误：动作后状态无法持久化。不得假定没有副作用；请手动执行已声明核验并用 `acgm doctor` 修复。"}}'
    ;;
  posttool-failure)
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PostToolUseFailure","additionalContext":"ACGM mechanism error: a failed command may still have partial effects and its obligation could not be persisted. Verify current state manually and run `acgm doctor`. / ACGM 机制错误：失败命令仍可能有部分副作用，且义务无法持久化。请手动核验当前状态并运行 `acgm doctor`。"}}'
    ;;
  stop)
    printf '%s\n' '{"decision":"block","reason":"ACGM runtime is broken, so post-action obligations cannot be verified safe to close. Run the declared verification manually and repair ACGM with `acgm doctor`. / ACGM 运行时损坏，无法确认后验义务可安全关闭。请手动核验并用 `acgm doctor` 修复。"}'
    ;;
  *)
    printf '%s\n' '{}'
    ;;
esac
