---
name: session-grounding
description: Use at the START of every new, resumed, cleared, or compacted session, or when taking over half-done work in an ACGM-governed project. 在 ACGM 项目的新开、续接、clear、compact 后 Session 或接手半截工作时使用。Read current project truth, identify track and scope, report the five grounding items, and wait for human confirmation before edits.
---

# ACGM Session Grounding

This is the selective workflow invoked as:

```text
/agent-coding-governance-methodology:session-grounding
```

The `SessionStart` hook runs automatically when healthy and reports the project state.
This skill does not auto-fire and does not replace that mechanism. It performs the
human-visible grounding judgment after the hook has oriented the session.

## Before acting

1. Run `acgm doctor` if SessionStart reports `BROKEN`, `PARTIALLY_GOVERNED`, or
   `DRIFTED`. Do not claim ACGM is healthy when doctor says otherwise.
2. Read the Constitution and root rules in full. Follow their pointers to the current
   truth sources; do not treat the root rules themselves as a technical-fact cache.
3. Identify the worktree, branch, track, and scope for this task. One session works in
   one track; split cross-track work into explicit consecutive stages.
4. Re-read current code, configuration, and Git state. A handoff, transcript, memory,
   compacted summary, or prior report is historical evidence, never current code truth.
5. Report these five items, then **wait for human confirmation before editing**:
   - track and scope;
   - current `git log` and `git status` state;
   - relevant structure observed by reading current sources;
   - exact files proposed for change;
   - execution and verification steps.

After changes, run the declared checks. Give a closing report and commit draft; wait
for human approval before committing.

## High-risk handoff to Truth-First

Before a recognized high-risk operation, invoke:

```text
/agent-coding-governance-methodology:truth-first
```

Run the read-only source check first, then put these exact fields in the reply
immediately before the tool call:

```text
ACGM-EVIDENCE: <current-session source and observed identifier>
ACGM-CURRENT-STATE: <state read now>
ACGM-VERIFY-AFTER: <concrete post-action check>
ACGM-ROLLBACK: <recovery plan>
```

The four fields are evidence, not authorization. The PreToolUse hook still asks the
human before the operation and keeps post-action verification open.

---

# ACGM Session 启动 Grounding

完整调用名：

```text
/agent-coding-governance-methodology:session-grounding
```

插件健康时，`SessionStart` hook 会自动运行并报告项目状态；本 skill 不会自动点火，也不
替代 hook。它负责在 hook 定位之后，完成人可见的 grounding 判断。

## 动手之前

1. 如果 SessionStart 报告 `BROKEN`、`PARTIALLY_GOVERNED` 或 `DRIFTED`，先运行
   `acgm doctor`。doctor 未确认健康时，不得声称 ACGM 正常。
2. 完整阅读 Constitution 和根规则，并沿指针找到当前真值源；不得把根规则本身当成技术
   事实缓存。
3. 识别本任务所在 worktree、分支、轨道和范围。一个 Session 只在一个轨道；跨轨道工作
   拆成明确的连续阶段。
4. 当下重读代码、配置与 Git 状态。交接、transcript、记忆、compact 摘要或旧报告只是
   历史证据，永远不是当前代码真值。
5. 报告以下五项，然后**等人确认再编辑**：
   - 轨道和范围；
   - 当前 `git log` 与 `git status`；
   - 实际阅读当前真值源后看到的相关结构；
   - 拟修改的准确文件清单；
   - 执行和验证步骤。

改完运行已声明的检查。收尾时提供报告和 commit 草稿，等人批准后再提交。

## 高风险操作转交 Truth-First

执行已识别的高风险操作前，调用：

```text
/agent-coding-governance-methodology:truth-first
```

先做只读取证，再在紧邻工具调用之前的回复中写出四个精确字段：

```text
ACGM-EVIDENCE: <本 Session 当下来源与观察到的标识符>
ACGM-CURRENT-STATE: <刚刚读取的状态>
ACGM-VERIFY-AFTER: <具体后验检查>
ACGM-ROLLBACK: <恢复方案>
```

四个字段只是证据，不是授权。PreToolUse hook 仍会要求人批准，并保持后验验证义务。
