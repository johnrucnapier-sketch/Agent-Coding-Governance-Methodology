#!/bin/sh
# pretool-destructive-bash.sh — PreToolUse hook for destructive Bash only.
#
# Implements the mechanism layer of:
#   - Principle Three · corollary: operational truth
#   - Principle Three · corollary: async / post-action self-monitoring (promise-on-record)
#   - Principle Four · corollary: grounding before destructive operations
#   - Meta-observation 1: performative compliance (detection criterion)
#
# What it does:
#   1. Matches ONLY destructive Bash patterns (curated whitelist). Non-destructive
#      Bash and all other tools are passed through silently.
#   2. When matched, reads the agent's most recent text reply via transcript_path
#      and checks whether the four ACGM gate parts (a)(b)(c)(d) are all present.
#   3. If any part is missing → returns permissionDecision: "ask" with a structured
#      prompt enumerating what (a)-(d) require. The agent must answer them before
#      the destructive Bash will run.
#   4. If all four are present → soft-verifies that at least one plausible
#      verification tool_use exists in the transcript (systemctl list-units / ls
#      / cat / grep / nvidia-smi etc.). If none → emits a non-blocking advisory
#      (Meta-observation 1 risk: form-complete but no sourcing tool_use found).
#   5. Otherwise → passes through silently.
#
# Honest limits (audit layer closes the rest):
#   - The (a) source check is HEURISTIC, not strict. A determined agent could
#     fabricate citations to existing tool_uses. The mechanism raises the cost
#     of fabrication and leaves a trail; substance verification is audit-layer.
#   - "Promise on record" for (c) is captured in transcript but the hook cannot
#     fire hours later to verify follow-through; audit-layer closes it.
#
# Architectural notes:
#   - Pure POSIX sh + jq + python3 (all standard on macOS/Linux).
#   - Triggers only on the curated destructive Bash whitelist (Meta-observation 2:
#     whitelist hooks preferred over blanket hooks; injection saturation prevention).
#   - SessionStart already says the same baseline (don't fake grep, summaries not
#     truth); this hook does NOT repeat that — it adds the (a)-(d) gate for the
#     destructive-Bash moment only (no duplicate injection across hooks).

set -eu

# Read stdin
input=$(cat 2>/dev/null || true)
[ -n "$input" ] || { echo '{}'; exit 0; }

# Required tools — graceful no-op if missing (never block work due to env)
command -v jq >/dev/null 2>&1 || { echo '{}'; exit 0; }

# Tool filter — only act on Bash
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null || true)
[ "$tool_name" = "Bash" ] || { echo '{}'; exit 0; }

# Extract the command
command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
[ -n "$command" ] || { echo '{}'; exit 0; }

# ---- Destructive Bash whitelist ----
# Per Meta-observation 2: precise targeting, not blanket coverage.
# Whitelist extension policy: every new CASES.md case that involves a destructive
# operation not currently listed here MUST add a pattern. Tied to case growth.
is_destructive=0
case "$command" in
  *"systemctl stop"*|*"systemctl start"*|*"systemctl disable"*|*"systemctl enable"*|*"systemctl mask"*|*"systemctl restart"*|*"systemctl reload"*) is_destructive=1 ;;
  *"rm -rf "*|*"rm -fr "*|*" rm -r "*|*"rm --recursive"*) is_destructive=1 ;;
  *"git push --force"*|*"git push -f"*|*"git reset --hard"*|*"git clean -f"*|*"git checkout -- "*|*"git checkout ."*) is_destructive=1 ;;
  *"drop table"*|*"DROP TABLE"*|*"truncate "*|*"TRUNCATE "*|*"delete from"*|*"DELETE FROM"*) is_destructive=1 ;;
  *"dd if="*|*"mkfs"*|*"kill -9"*|*"kill -KILL"*|*"shutdown "*|*"reboot "*) is_destructive=1 ;;
esac

[ "$is_destructive" = 1 ] || { echo '{}'; exit 0; }

# ---- Transcript reading ----
transcript_path=$(printf '%s' "$input" | jq -r '.transcript_path // .transcriptPath // empty' 2>/dev/null || true)

# Read last assistant text message (the message immediately before this tool call)
last_text=""
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
  last_text=$(TPATH="$transcript_path" python3 - <<'PY' 2>/dev/null || true
import json, os
path = os.environ.get("TPATH","")
last = ""
try:
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("type") != "assistant":
                continue
            msg = d.get("message", {})
            if not isinstance(msg, dict):
                continue
            c = msg.get("content", "")
            if isinstance(c, list):
                buf = ""
                for block in c:
                    if isinstance(block, dict) and block.get("type") == "text":
                        buf += block.get("text", "") + "\n"
                if buf.strip():
                    last = buf
except Exception:
    pass
print(last[-4000:])
PY
)
fi

# ---- Check (a)(b)(c)(d) presence in the agent's last reply ----
has_a=0; has_b=0; has_c=0; has_d=0
printf '%s' "$last_text" | grep -qE '\(a\)|（a）|^[[:space:]]*a\)' && has_a=1 || true
printf '%s' "$last_text" | grep -qE '\(b\)|（b）|^[[:space:]]*b\)' && has_b=1 || true
printf '%s' "$last_text" | grep -qE '\(c\)|（c）|^[[:space:]]*c\)' && has_c=1 || true
printf '%s' "$last_text" | grep -qE '\(d\)|（d）|^[[:space:]]*d\)' && has_d=1 || true

missing=""
[ "$has_a" = 0 ] && missing="$missing (a)"
[ "$has_b" = 0 ] && missing="$missing (b)"
[ "$has_c" = 0 ] && missing="$missing (c)"
[ "$has_d" = 0 ] && missing="$missing (d)"

if [ -n "$missing" ]; then
  REASON="ACGM gate: this destructive Bash is gated by the Principle 3 corollary 'operational truth' + Principle 4 corollary 'grounding before destructive ops'.

Your prior reply is missing the required parts:$missing

In your NEXT reply, before retrying this Bash, answer each explicitly:

(a) For EACH identifier in this command (unit / path / service / PID / container / host): cite a specific tool_use in this session that established the name — point to the line in its output. If no such tool_use exists in this session, run the verification command FIRST (e.g., 'systemctl list-units', 'ls', 'cat config') then come back to answer (a).

(b) Current REAL state of the target (is-active / resource usage / process / mtime). Read it NOW — not from memory or from the inherited summary.

(c) Post-execution verification — what specific check will you run AFTER this command to confirm it achieved its intent (not just exit code 0)?

(d) Rollback — if this command hits the wrong target, what's the recovery plan?

Skipping any of (a)-(d) and proceeding anyway = performative compliance (ACGM Meta-observation 1). This decision will remain in transcript record."
  jq -n --arg reason "$REASON" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "ask",
      "permissionDecisionReason": $reason
    }
  }'
  exit 0
fi

# ---- Soft (a) check: was ANY plausible verification tool_use run in this session? ----
# This is a HEURISTIC, not strict citation-matching. Strict matching would parse the
# (a) section to extract claims and look up exact tool_use outputs; for v1 we just
# check whether at least one verification-shaped Bash tool_use exists in transcript.
# If none exists, that's a strong signal of pure form-compliance — but allowed with
# a non-blocking advisory (audit-layer closes the rest).
has_verify_tool=0
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
  if grep -qE '"command":[[:space:]]*"[^"]*(systemctl[[:space:]]list-units|systemctl[[:space:]]status|systemctl[[:space:]]is-active|ls[[:space:]]|cat[[:space:]]|grep[[:space:]]|find[[:space:]]|nvidia-smi|ps[[:space:]]|stat[[:space:]])' "$transcript_path" 2>/dev/null; then
    has_verify_tool=1
  fi
fi

if [ "$has_verify_tool" = 0 ]; then
  ADVISORY="ACGM advisory (Meta-observation 1 / performative-compliance risk): the (a)-(d) gate appears to be filled, but I could not find any plausible verification tool_use (systemctl list-units/status/is-active, ls, cat, grep, find, nvidia-smi, ps, stat) anywhere earlier in this session. If your (a) citation is fabricated or transferred from a prior session's compaction, this command will likely hit the wrong target. Audit-layer recommendation: re-verify before proceeding. (Non-blocking; proceeding allowed.)"
  jq -n --arg advisory "$ADVISORY" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "additionalContext": $advisory
    }
  }'
  exit 0
fi

# All checks passed silently — emit empty JSON, let the Bash proceed
echo '{}'
