---
name: governance-bootstrap
description: Use when a project is INSTALLED_NOT_BOOTSTRAPPED, PARTIALLY_GOVERNED, or deliberately adopting ACGM for the first time. 在项目为 INSTALLED_NOT_BOOTSTRAPPED、PARTIALLY_GOVERNED，或首次采用 ACGM 时使用。Human-driven workflow for auditing existing rules, initializing a non-overwriting scaffold, and completing Constitution, root rules, ADRs, snapshots, tracks, and scope.
---

# ACGM Governance Bootstrap

Invoke this workflow with its complete name:

```text
/agent-coding-governance-methodology:governance-bootstrap
```

Bootstrap is human-driven. The Agent audits and proposes; the human decides the
Constitution, scope, role boundaries, and irreversible changes. Do not turn this skill
into an autonomous migration.

## Establish the minimum scaffold

First inspect current state without changing project files:

```bash
acgm doctor --no-update
```

With human approval, initialize the selected path:

```bash
acgm init [PATH]
```

`acgm init` is idempotent and never overwrites existing `CONSTITUTION.md`,
`CLAUDE.md`, or `AGENTS.md`. Existing files require a reviewed manual merge. Init is
not full governance and may correctly leave the project `PARTIALLY_GOVERNED`.

## Complete the eight human checkpoints

0. **Read-only audit.** Read existing rules, history, handoffs, current code, and Git
   state. Produce three lists: still valid; outdated; contradictory and requiring a
   human ruling. Do not delete or rewrite anything in this step.
1. **Constitution.** Propose stable redlines, role boundaries, scope criterion, and
   four-drift defenses. The human owns and edits the Constitution.
2. **Root rules.** Remove duplicated technical facts. Keep meta-rules, pointers to
   current truth, and behavior constraints. Merge rather than overwrite an existing
   `CLAUDE.md` or `AGENTS.md`.
3. **Decision log.** Create a non-empty index or ADR under one machine-discoverable
   path: `decisions/`, `docs/decisions/`, or `.governance/decisions/`. Mark
   reconstructed decisions as reconstructed; distinguish `Superseded` from
   `Withdrawn`.
4. **Snapshots and checks.** Generate a non-empty current-state snapshot under
   `.governance/snapshots/`, `docs/snapshots/`, or `snapshots/`; stamp its source
   commit and add project-specific drift checks alongside it.
5. **Session grounding.** Adopt the complete namespaced workflow:

   ```text
   /agent-coding-governance-methodology:session-grounding
   ```

6. **Tracks and scope.** Define tracks for this project's actual cognitive contexts.
   Write `.governance/scope.yml` or `.governance/scope.yaml` with both `in:` and
   `out:` sections. Do not copy another project's track map.
7. **Audit cadence.** Rebuild snapshots at version boundaries, review root rules
   periodically, and inspect the local Activity Report.

Then run:

```bash
acgm doctor --strict
acgm report --project current
```

Doctor reports missing or drifted components; it does not auto-rewrite them. If a
previously `GOVERNED` project loses required components, treat `DRIFTED` as a review
request, not permission for an automatic migration.

A project may deliberately use another layout, but doctor will keep it
`PARTIALLY_GOVERNED`; the RC does not auto-discover arbitrary conventions. The human
may either adopt one supported path or accept that machine-state limitation.

## High-risk changes during bootstrap

For destructive cleanup, branch/history changes, or other state-changing operations,
invoke:

```text
/agent-coding-governance-methodology:truth-first
```

Run a read-only source check and provide the exact gate fields before the tool call:

```text
ACGM-EVIDENCE: <current-session source and observed identifier>
ACGM-CURRENT-STATE: <state read now>
ACGM-VERIFY-AFTER: <concrete post-action check>
ACGM-ROLLBACK: <recovery plan>
```

The fields do not authorize the action. Wait for the hook's human permission stage.

---

# ACGM 治理 Bootstrap

使用完整调用名：

```text
/agent-coding-governance-methodology:governance-bootstrap
```

Bootstrap 必须由人驱动。Agent 审计并提出方案；Constitution、范围、角色边界与不可逆
变更由人决定。不得把本 skill 变成自动迁移器。

## 建立最小骨架

先只读检查当前状态，不改项目文件：

```bash
acgm doctor --no-update
```

人批准后，初始化选定路径：

```bash
acgm init [PATH]
```

`acgm init` 幂等，永不覆盖已有的 `CONSTITUTION.md`、`CLAUDE.md` 或 `AGENTS.md`。
已有文件必须人工审查后手动合并。Init 不等于完整治理，项目停在
`PARTIALLY_GOVERNED` 可能完全正确。

## 完成八个人工检查点

0. **只读审计。** 阅读现有规则、历史、交接、当前代码和 Git 状态。输出三份清单：仍
   有效；已过时；相互矛盾且需要人裁定。本步骤不删除、不重写。
1. **Constitution。** 提出稳定红线、角色边界、范围判据和四类漂移防线；Constitution
   由人所有并亲自编辑。
2. **根规则。** 删除重复的技术事实，只保留元规则、当前真值指针和行为约束。已有
   `CLAUDE.md` 或 `AGENTS.md` 只能合并，不能覆盖。
3. **决策日志。** 在机器可发现的 `decisions/`、`docs/decisions/` 或
   `.governance/decisions/` 中建立非空索引或 ADR。事后重建的决策明确标注
   reconstructed，并区分 `Superseded` 与 `Withdrawn`。
4. **快照与检查。** 在 `.governance/snapshots/`、`docs/snapshots/` 或 `snapshots/`
   中从代码生成非空当前状态快照，标明来源 commit，同时建立项目专属漂移检查。
5. **Session grounding。** 采用完整 namespaced 工作流：

   ```text
   /agent-coding-governance-methodology:session-grounding
   ```

6. **轨道与范围。** 按本项目真实认知上下文定义轨道；在 `.governance/scope.yml` 或
   `.governance/scope.yaml` 中同时写出 `in:` 与 `out:`。不得复制其他项目的轨道图。
7. **审计节奏。** 版本边界重建快照，周期审查根规则，并查看本地 Activity Report。

随后运行：

```bash
acgm doctor --strict
acgm report --project current
```

Doctor 只报告缺失或漂移组件，不会自动改写。原本 `GOVERNED` 的项目丢失必要组件后，
`DRIFTED` 是人工复审请求，不是自动迁移许可。

项目可以主动使用其他布局，但 doctor 会保持报告 `PARTIALLY_GOVERNED`；本 RC 不自动
发现任意约定。人可以采用支持路径，也可以接受这一机器状态限制。

## Bootstrap 中的高风险变更

破坏性清理、分支/历史修改或其他状态变更操作前，调用：

```text
/agent-coding-governance-methodology:truth-first
```

先做只读取证，再在工具调用前写出四个精确字段：

```text
ACGM-EVIDENCE: <本 Session 当下来源与观察到的标识符>
ACGM-CURRENT-STATE: <刚刚读取的状态>
ACGM-VERIFY-AFTER: <具体后验检查>
ACGM-ROLLBACK: <恢复方案>
```

字段本身不授权操作；必须等待 hook 进入人工权限阶段。
