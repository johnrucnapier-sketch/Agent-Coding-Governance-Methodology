---
name: truth-first
description: Use before writing technical conclusions or governance documentation, and before irreversible, destructive, or state-changing operations. 写技术结论、治理文档，或做不可逆、破坏性、状态变更操作前使用。Requires current-source evidence and the exact ACGM-EVIDENCE, ACGM-CURRENT-STATE, ACGM-VERIFY-AFTER, and ACGM-ROLLBACK gate fields for high-risk operations.
---

# ACGM Truth-First

Invoke this selective workflow with its complete name:

```text
/agent-coding-governance-methodology:truth-first
```

Truth-first prevents conversation residue, handoffs, and compacted summaries from
silently becoming current technical truth. The hooks mechanically cover a targeted
subset; this skill supplies the judgment the mechanism cannot infer.

## Technical claims

Every technical conclusion must:

- come from current code, configuration, schema, runtime state, or another primary
  source read in this session;
- cite a concrete `file:line` when the truth source is a file;
- distinguish current fact, historical decision, inference, and unresolved unknown;
- avoid “I think,” “usually,” “should be,” “I recall,” and equivalent wording as a
  substitute for evidence.

Do not copy a technical claim from history, superseded documents, old handoffs,
transcripts, memory retrieval, or version snapshots. Those sources may establish what
was once said or decided, not what the system is now.

If a current source cannot be read, say exactly what was not verified and stop before
turning the unknown into a conclusion.

The PostToolUse hook may advise on a risky governance-file claim, but it does not edit
the file for you. Re-read the source and correct or cite the claim yourself.

## High-risk operation gate

Before an irreversible, destructive, or state-changing operation:

1. Resolve every identifier from a current-session, read-only source check in its own
   tool call.
2. Read the target's current state now.
3. Define the exact, standalone, category- and target-matching post-action verification.
4. Define a workable rollback or recovery plan.
5. Put the following exact fields in the reply immediately before the tool call:

```text
ACGM-EVIDENCE: <tool output or primary source establishing each target identifier>
ACGM-CURRENT-STATE: <current state observed now>
ACGM-VERIFY-AFTER: <specific command/check and intended success signal>
ACGM-ROLLBACK: <recovery steps if the target or result is wrong>
```

Do not put placeholders or inherited claims in these fields. The PreToolUse hook may
deny a missing or unsourced gate. When the gate is complete, it still asks the human
for explicit approval; the fields never grant permission by themselves.

Keep source inspection, the high-risk state change, and post-action verification in
three separate tool calls. Do not combine them with `;`, `&&`, pipes, redirection, or
subshells: ordering and partial failure would no longer be auditable.

After an approved operation, run `ACGM-VERIFY-AFTER` and inspect the result. Exit code
zero is not sufficient unless it proves the intended state. `Stop` may keep the turn
open while verification is pending; `SessionEnd` records an unresolved obligation if
the session closes without it.

Constitution changes are human-owned. Propose the amendment and evidence; do not use
an Agent write path to edit `CONSTITUTION.md`, including Edit/Write or Bash that may
mutate it. A clearly read-only Bash command may inspect the file; ambiguous or compound
shell access is denied because the hook cannot prove it is read-only.

For session-level orientation, use:

```text
/agent-coding-governance-methodology:session-grounding
```

---

# ACGM 真值优先

使用完整调用名：

```text
/agent-coding-governance-methodology:truth-first
```

Truth-first 防止对话残留、交接和 compact 摘要静默变成当前技术真值。Hooks 只机械覆盖
精准收窄的子集；本 skill 负责机制无法推断的判断。

## 技术结论

每条技术结论必须：

- 来自本 Session 当下读取的代码、配置、schema、运行状态或其他一手来源；
- 真值源是文件时，附具体 `file:line`；
- 区分当前事实、历史决策、推断和仍未解决的未知；
- 不用“我觉得”“通常”“应该是”“我记得”等措辞代替证据。

不得从历史、已被取代的文档、旧交接、transcript、记忆检索或版本快照复制技术结论。这些
来源可以证明过去说过什么、决定过什么，不能证明系统现在是什么。

当前真值源读不到时，明确说出哪一项未验证，并停在这里，不得把未知写成结论。

PostToolUse hook 可能提醒治理文档里的风险结论，但不会替你修改文件。你必须自己重读源头，
修正结论或补上证据。

## 高风险操作证据门

不可逆、破坏性或状态变更操作之前：

1. 用独立工具调用完成本 Session 当下只读取证，解析每一个目标标识符。
2. 刚刚读取目标当前状态。
3. 定义准确、独立、与类别和目标匹配的操作后核验。
4. 定义可执行的回滚或恢复方案。
5. 在紧邻工具调用之前的回复中写出以下精确字段：

```text
ACGM-EVIDENCE: <建立每个目标标识符的一手来源或工具输出>
ACGM-CURRENT-STATE: <刚刚观察到的当前状态>
ACGM-VERIFY-AFTER: <具体核验命令/检查与成功信号>
ACGM-ROLLBACK: <目标或结果错误时的恢复步骤>
```

字段内不得放占位符或从摘要继承的结论。字段缺失或没有当下证据时，PreToolUse hook 可以
拒绝操作。四项完整后仍会要求人明确批准；这些字段本身永远不授予权限。

取证、高风险状态变更、后验核验必须拆成三个独立工具调用。不得用 `;`、`&&`、pipe、
重定向或 subshell 把它们拼在一起，否则顺序和部分失败不可审计。

获批执行后，运行 `ACGM-VERIFY-AFTER` 并检查结果。除非 exit code 0 能证明预期状态，
否则它本身不算验证。验证未完成时，`Stop` 可能保持本轮开启；Session 未验证就结束时，
`SessionEnd` 会记录 unresolved 义务。

Constitution 归人所有。可以提出修订建议和证据，但不得通过任何 Agent 写入路径修改
`CONSTITUTION.md`，包括 Edit/Write 或可能写入的 Bash。明确只读的 Bash 可以检查文件；
含糊或复合 shell 访问因无法证明只读而会被拒绝。

Session 级定位使用：

```text
/agent-coding-governance-methodology:session-grounding
```
