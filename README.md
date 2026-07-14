# ACGM

**Drift control for long-horizon agent coding.**

Agent Coding Governance Methodology (ACGM) is a governance method and a Claude Code
plugin for multi-session, long-running development. It makes recurring agent drift
visible, interceptable, reversible, and locally auditable.

[![Version: 0.3.0-rc.2](https://img.shields.io/badge/version-0.3.0--rc.2-orange.svg)](CHANGELOG.md)
[![Code: MIT](https://img.shields.io/badge/code-MIT-green.svg)](LICENSING.md)
[![Docs: CC--BY--4.0](https://img.shields.io/badge/docs-CC--BY--4.0-blue.svg)](LICENSING.md)

> **Release status:** `0.3.0-rc.2` is an **unreleased testing candidate**, not a
> stable release. Changing the source version does not publish a Git tag or GitHub
> prerelease; the pinned install command below becomes usable only after
> `v0.3.0-rc.2` is actually published. Its local runtime and regression suite can be
> verified without a Claude account, but it must pass the real-Claude-Code checklist in
> [`tests/manual/CLAUDE_CODE_E2E.md`](tests/manual/CLAUDE_CODE_E2E.md) before promotion
> to stable. The controlled Windows profile has not yet completed real-machine E2E;
> do not describe this RC as fully validated on Windows or current Claude Code yet.
>
> English is complete first. 中文完整版在后半部分。

## Why ACGM exists

Long-horizon agent development accumulates structural drift:

- **Implementation drift:** the agent detours around a hard technical problem.
- **Cognitive drift:** a summary, memory, or stale document is treated as current truth.
- **Structural-placement drift:** governance or truth lives on the wrong branch or worktree.
- **Scope drift:** content outside the software boundary enters the repository.

ACGM does not claim to eliminate drift. It provides a normative method, targeted
runtime mechanisms, and an audit trail so drift can be found earlier and handled
explicitly. The full method is in [`METHODOLOGY.en.md`](METHODOLOGY.en.md); real,
desensitized examples are in [`CASES.md`](CASES.md).

[`EVIDENCE.md`](EVIDENCE.md) is the public claim-maturity register. It separates
Observed, Reproduced, Corroborated, Predictive, and Rejected claims so an activity
count or single incident cannot silently become a universal rule or a marketed win.

## What V3 adds

V3 closes the gap between “the plugin is installed” and “governance is actually
operating”:

- versioned package identity (`0.3.0-rc.2`) and release checks;
- project states: `INSTALLED_NOT_BOOTSTRAPPED`, `PARTIALLY_GOVERNED`, `GOVERNED`,
  `DRIFTED`, and `BROKEN`;
- deterministic hook coverage for session health, high-risk operations, governance
  writes, post-action verification, turn stop, and session end;
- a local, source-minimized Event Ledger and Activity Report;
- `acgm init`, `doctor`, `report`, `export-case`, `resolve`, and `version` commands;
- explicit upgrade, reload, uninstall, and verification procedures.

The plugin ID and repository slug remain unchanged:

```text
agent-coding-governance-methodology@agent-coding-governance-methodology
johnrucnapier-sketch/Agent-Coding-Governance-Methodology
```

## Requirements

- a current, working Claude Code installation; record the actual version and establish
  compatibility with the read-only preflight plus real-machine E2E. This RC does not
  claim an evidence-backed exact minimum Claude Code version;
- Python `3.10` or newer (the runtime uses modern Python syntax; hooks, doctor,
  reports, and Event Ledger require it);
- Git for repository and worktree grounding.

The RC2 automated-regression target includes macOS, Linux, and one controlled Windows
testing profile: **Windows 10/11 + Git for Windows/Git Bash + Python 3.10+ +
`CLAUDE_CODE_USE_POWERSHELL_TOOL=0`**. That Windows profile is still a testing
candidate until the manual real-machine E2E checklist passes. Native PowerShell hook
execution is not supported by this RC, and WSL is outside its verified matrix. Do not
infer broader Windows support from portable methodology prose or a green unit test.

If Python is unavailable or the Python runtime crashes, ACGM reports itself as
`BROKEN` and the wrapper fails closed for **all Bash**, because it cannot safely prove
which commands are harmless. Other events surface a health warning instead of
pretending governance is healthy.

The installed plugin exposes `acgm` to Bash launched inside plugin-enabled Claude
Code. An ordinary login shell is not guaranteed to inherit that PATH entry. From a
repository clone, use `./bin/acgm` when `acgm` is not available. The ACGM command
examples below assume plugin-enabled Claude Code Bash unless stated otherwise.

## Install and initialize

First clone or download the exact candidate source and run the read-only preflight
from its repository root. Use the launcher available on the machine:

```bash
python3 scripts/preflight.py --json
```

On the controlled Windows Git Bash profile, `python` or the Windows launcher may be
used instead:

```bash
py -3 scripts/preflight.py --json
```

Preflight checks the install prerequisites and reports `READY_FOR_RC_TEST` or
`BLOCKED`. It does not edit Claude settings, install the plugin, initialize a project,
or infer which account/model is behind the runtime route. On Windows, it requires the
effective `CLAUDE_CODE_USE_POWERSHELL_TOOL` setting to be exactly `0` and a detectable
Git for Windows/Git Bash installation. A ready result is not proof that live E2E has
passed.

After the `v0.3.0-rc.2` tag is actually published, register that immutable source and
install the unchanged plugin ID:

```bash
claude plugin marketplace add https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology.git#v0.3.0-rc.2
claude plugin install agent-coding-governance-methodology@agent-coding-governance-methodology
```

Before the tag exists, that pinned GitHub command cannot work; a local-source test
must record its exact commit and must not be reported as a successful GitHub install.
Downloading alone is not installation. An Agent may continue through the read-only
preflight and CLI install commands, but reload and the project health/bootstrap review
remain explicit, observable steps.

In an active Claude Code session, reload installed plugins:

```text
/reload-plugins
```

Verify the running package, initialize the current project with the non-overwriting
scaffold, then inspect it again:

```bash
acgm version
acgm doctor
acgm init .
acgm doctor --strict
```

`acgm init [PATH]` is idempotent and does not overwrite existing `CONSTITUTION.md`,
`CLAUDE.md`, or `AGENTS.md`. It establishes the minimum scaffold; it does not invent
your constitution, scope, tracks, ADRs, or snapshots. Complete those human decisions
through:

```text
/agent-coding-governance-methodology:governance-bootstrap
```

Run `acgm doctor --strict` again after bootstrap. A partial or drifted project is
reported, not silently rewritten. ACGM has no automatic “project upgrade” that edits
user governance files.

For a machine-verifiable `GOVERNED` state, doctor requires a non-placeholder
Constitution and root rules plus all of the following discoverable assets:

- a non-empty decision index or ADR under `decisions/`, `docs/decisions/`, or
  `.governance/decisions/`;
- a non-empty snapshot under `.governance/snapshots/`, `docs/snapshots/`, or
  `snapshots/`;
- `.governance/scope.yml` or `.governance/scope.yaml` containing both `in:` and
  `out:` sections.

Projects may use another layout as a methodology choice, but this RC will report that
layout as `PARTIALLY_GOVERNED`; doctor does not pretend to auto-discover arbitrary
project conventions.

`acgm init` implements its scaffold in Python and is the Windows installation path;
it does not depend on the POSIX scaffold script. For a plugin-free static scaffold on
macOS or Linux only, clone the repository and run:

```bash
sh Agent-Coding-Governance-Methodology/scripts/governance-init.sh /path/to/project
```

`scripts/governance-init.sh` is a POSIX fallback only. It writes static files; it does
not install hooks or the Event Ledger and is not the Windows initialization path.

## What runs automatically

Hooks and skills have different guarantees.

When the plugin is healthy and Claude Code emits a matching event, the hook command
runs automatically. Detection inside a hook is still deliberately bounded and
heuristic; “automatic” does not mean “omniscient.” Skills are model-selected or
explicitly invoked guidance and are not enforcement by themselves.

| Event | Deterministic mechanism |
|---|---|
| `SessionStart` | Checks package/project health on startup, resume, clear, and compact; shows the resolved actual project root for wrong-cwd detection and injects state plus grounding. |
| `PreToolUse` | Gates recognized high-risk Bash operations and denies Agent write paths to the human-owned Constitution, including potentially mutating or ambiguous Bash; clearly read-only Bash inspection remains available. |
| `PostToolUse` | Opens or resolves post-action verification obligations and advises on risky governance-file claims without modifying the file. |
| `PostToolUseFailure` | Treats a failed/partial high-risk call as an unknown execution result and keeps post-action verification open. |
| `Stop` | Prevents a quiet turn ending while a post-action verification remains open, with a bounded loop cap. |
| `SessionEnd` | Records unresolved obligations and execution states that were never observed, without assuming a denied or missing PostTool event means “not executed.” |

The three selective skills are:

```text
/agent-coding-governance-methodology:session-grounding
/agent-coding-governance-methodology:truth-first
/agent-coding-governance-methodology:governance-bootstrap
```

## The high-risk evidence gate

Before retrying a recognized high-risk operation, the agent must first run a current,
read-only source check and put these exact fields in its immediately preceding reply:

```text
ACGM-EVIDENCE: <current-session source and observed identifier>
ACGM-CURRENT-STATE: <state read now, not inherited from a summary>
ACGM-VERIFY-AFTER: <concrete check to run after the operation>
ACGM-ROLLBACK: <recovery plan if the operation hits the wrong target>
```

The source check, high-risk state change, and post-action verification must be separate
standalone tool calls. The evidence and current-state fields must name the actual
target; `ACGM-VERIFY-AFTER` must be a standalone, category-matching check. This avoids
false verification from command order, unrelated output, or partial compound failure.

Missing fields or missing current-session evidence are denied before the human
permission stage. A complete gate does not authorize the operation: ACGM then asks for
explicit human approval and keeps the declared post-action verification open until it
is checked or recorded as unresolved.

## Doctor, Activity Report, and case export

Check package identity, hook presence, project state, local storage, Python, and
continuity warnings:

```bash
acgm version
acgm doctor
acgm doctor --strict
acgm doctor --json
```

Read the local Event Ledger:

```bash
acgm report --project current --limit 20
acgm report --project current --json
```

Generate a locally sanitized case preview from an event ID, then review every line
yourself before sharing:

```bash
acgm export-case evt_EXAMPLE -o acgm-case-preview.md
```

Classify an event after human review:

```bash
acgm resolve evt_EXAMPLE --status resolved
```

Allowed resolution states are `resolved`, `verified`, `human_override`,
`false_positive`, and `unresolved`.

## Event Ledger privacy model

The Event Ledger is local-only and source-minimized. It **never automatically uploads
data** and
does not first collect raw material and sanitize it later. Raw hook input is processed
in memory and discarded. Persistent events use opaque local IDs and enumerated fields.
The local Event Ledger does not automatically upload anything.

The ledger does not store project paths, file names, commands, prompts, transcript
content, model/provider names, remote URLs, infrastructure identifiers, credentials,
or reconstructable technical fingerprints. `export-case` creates a separate manual
preview and never shares it automatically.

Hooks receive Claude's exact `CLAUDE_PLUGIN_DATA` path explicitly. `ACGM_DATA_DIR` is
the higher-priority manual/test override. Without either environment value, the CLI
uses `${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/data/` plus the sanitized plugin ID; for
this plugin the default is
`~/.claude/plugins/data/agent-coding-governance-methodology-agent-coding-governance-methodology`.
This makes hooks and `acgm report` converge on the same store. Keep this data during
uninstall if you want the audit history to remain available.

## Upgrade and reload

Refresh the marketplace, update the plugin, and reload it:

```bash
claude plugin marketplace update agent-coding-governance-methodology
claude plugin update agent-coding-governance-methodology@agent-coding-governance-methodology
```

```text
/reload-plugins
```

Then verify the running identity and project state:

```bash
acgm version
acgm doctor --strict
```

An upgrade never migrates or deletes project governance assets automatically. If
doctor reports partial governance or drift, the human decides what to add or repair.

## Uninstall while keeping local data

```bash
claude plugin uninstall agent-coding-governance-methodology@agent-coding-governance-methodology --keep-data
```

`--keep-data` preserves plugin-managed Event Ledger data. Uninstalling the plugin does
not remove governance files from project repositories. ACGM deliberately has no
command that silently deletes project assets.

## Boundaries

- ACGM V3 is a Claude Code runtime implementation. The principles can be adapted to
  other agents, but this repository does not claim equivalent runtime enforcement.
- Compatible third-party API backends may behave differently from genuine Claude.
  ACGM governs the observed Claude Code runtime surface; it does not identify, rank,
  or tune the model behind a compatible endpoint.
- ACGM does not back up transcripts, bypass account restrictions, or reconstruct an
  inaccessible project. **ACGM Recover — Claude Code Project Recovery** is a separate
  product line and is not part of V3.
- Hook recognition is intentionally targeted. Human review remains the authority for
  business judgment, Constitution changes, ambiguous operations, and false positives.

## Repository map

```text
.claude-plugin/       plugin and marketplace identity
hooks/                Claude Code lifecycle wiring
bin/acgm              local CLI entry point
scripts/              hook runtime, scaffold, and checks
skills/               selective namespaced workflows
templates/            blank project-governance skeletons
tests/                automated fixtures plus manual Claude Code E2E
METHODOLOGY*.md       full method
CASES.md              real desensitized cases
EVIDENCE.md           public claim-maturity register
CHANGELOG.md          release history
RELEASING.md          release checklist
```

## License and origin

Methodology and prose documentation are CC-BY-4.0; mechanical code is MIT. See
[`LICENSING.md`](LICENSING.md) for the path mapping.

ACGM was distilled from long-running, multi-session development in which stale
handoffs, fabricated technical conclusions, branch placement, and destructive-action
mistakes repeatedly appeared. It is shared so other long-horizon projects can make
those failure modes visible before they compound.

---

# ACGM

**长周期 Agent Coding 漂移控制。**

Agent Coding Governance Methodology（ACGM）既是一套治理方法，也是一款面向
Claude Code 的插件，用于多 Session、长周期开发。它让反复出现的 Agent 漂移变得
可见、可拦截、可回滚，并能在本机审计。

[![Version: 0.3.0-rc.2](https://img.shields.io/badge/version-0.3.0--rc.2-orange.svg)](CHANGELOG.md)
[![Code: MIT](https://img.shields.io/badge/code-MIT-green.svg)](LICENSING.md)
[![Docs: CC--BY--4.0](https://img.shields.io/badge/docs-CC--BY--4.0-blue.svg)](LICENSING.md)

> **发布状态：** `0.3.0-rc.2` 是**尚未发布的测试候选版**，不是稳定版。源码中的版本号
> 变化不代表 Git tag 或 GitHub prerelease 已发布；只有实际发布 `v0.3.0-rc.2` 后，
> 下文的固定 ref 安装命令才可使用。本地运行时与回归测试可以在没有 Claude 账号时验证，
> 但升级为稳定版之前，必须通过
> [`tests/manual/CLAUDE_CODE_E2E.md`](tests/manual/CLAUDE_CODE_E2E.md) 中的真实
> Claude Code 验收。受控 Windows profile 尚未完成真机 E2E；当前不得把这个 RC 描述成
> 已经在 Windows 或最新版 Claude Code 上完整验证。

## 为什么需要 ACGM

长周期 Agent 开发会不断积累结构性漂移：

- **实施层漂移：** 技术困难时绕路、降级或掩盖问题。
- **认知层漂移：** 把摘要、记忆或过期文档当成当前真值。
- **结构放置漂移：** 治理或真值落在错误分支、工作树或位置。
- **范围漂移：** 软件边界之外的内容进入代码仓库。

ACGM 不声称消灭漂移。它提供规范方法、精准的运行时机制和审计记录，让漂移更早暴露并被
显式处理。完整方法见 [`METHODOLOGY.md`](METHODOLOGY.md)，真实脱敏案例见
[`CASES.md`](CASES.md)。

[`EVIDENCE.md`](EVIDENCE.md) 是公开的结论成熟度登记表。它区分 Observed、
Reproduced、Corroborated、Predictive 与 Rejected，防止活动次数或单次事故静默升级成
通用规则或被包装成战绩。

## V3 新增什么

V3 补上“插件已经安装”和“治理确实在运行”之间的断层：

- 有版本的发布身份（`0.3.0-rc.2`）与发布检查；
- 项目状态：`INSTALLED_NOT_BOOTSTRAPPED`、`PARTIALLY_GOVERNED`、`GOVERNED`、
  `DRIFTED`、`BROKEN`；
- Session 健康、高风险操作、治理文档写入、后验验证、回合停止与 Session 结束的确定性
  hook；
- 本地、源头最小化的 Event Ledger 和 Activity Report；
- `acgm init`、`doctor`、`report`、`export-case`、`resolve`、`version` 命令；
- 明确的升级、重载、卸载和验证步骤。

插件 ID 和仓库 slug 保持不变：

```text
agent-coding-governance-methodology@agent-coding-governance-methodology
johnrucnapier-sketch/Agent-Coding-Governance-Methodology
```

## 环境要求

- 当前可用的 Claude Code；记录实际版本，并通过只读 preflight 与真机 E2E 建立兼容性。
  本 RC 不主张一个尚无证据支撑的精确 Claude Code 最低版本；
- Python `3.10` 或更高版本（运行时使用现代 Python 语法；hooks、doctor、报告和
  Event Ledger 都需要）；
- Git，用于仓库和 worktree grounding。

RC2 的自动回归目标包括 macOS、Linux，以及一个受控 Windows 测试 profile：
**Windows 10/11 + Git for Windows/Git Bash + Python 3.10+ +
`CLAUDE_CODE_USE_POWERSHELL_TOOL=0`**。这个 Windows profile 在人工真机 E2E 通过前仍
只是测试候选范围。本 RC 不支持 native PowerShell hook，WSL 也不在已验证矩阵内。不得
因为方法论散文可移植或单元测试通过，就推断更广泛的 Windows 运行时已受支持。

如果 Python 不可用或 Python 运行时崩溃，ACGM 会明确报告为 `BROKEN`，wrapper 会对
**所有 Bash 失败关闭**，因为此时无法安全证明哪条命令无害。其他事件会显示健康警告，
而不会假装治理正常。

插件启用后，Claude Code 内部发起的 Bash 会获得 `acgm` 命令；普通 login shell 不保证
继承这条 PATH。从仓库 clone 运行时，如果没有 `acgm`，请使用 `./bin/acgm`。下文 ACGM
命令示例默认在插件已启用的 Claude Code Bash 中运行，另有说明的除外。

## 安装与初始化

先 clone 或下载准确的候选源码，在仓库根目录运行只读 preflight。按机器上可用的 launcher
选择命令：

```bash
python3 scripts/preflight.py --json
```

受控 Windows Git Bash profile 也可以使用 Windows Python launcher：

```bash
py -3 scripts/preflight.py --json
```

Preflight 只检查安装前提，并报告 `READY_FOR_RC_TEST` 或 `BLOCKED`；它不改 Claude 设置、
不安装插件、不初始化项目，也不推断运行路径背后的账号或模型。Windows 下，它要求有效的
`CLAUDE_CODE_USE_POWERSHELL_TOOL` 设置准确为 `0`，并能检测到 Git for Windows/Git Bash。
Ready 不等于真实 E2E 已通过。

只有 `v0.3.0-rc.2` tag 实际发布后，才能注册这个不可变来源并安装保持不变的插件 ID：

```bash
claude plugin marketplace add https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology.git#v0.3.0-rc.2
claude plugin install agent-coding-governance-methodology@agent-coding-governance-methodology
```

Tag 尚不存在时，这条固定 GitHub ref 命令不能工作；使用本地源码测试时必须记录准确 commit，
不得把它写成 GitHub 安装成功。下载本身不等于安装。Agent 可以继续执行只读 preflight 和
CLI 安装命令，但重载、项目健康检查与 bootstrap 复核仍是显式、可观察的独立步骤。

在已打开的 Claude Code Session 中重载插件：

```text
/reload-plugins
```

先核对实际运行包，再用不覆盖现有文件的脚手架初始化当前项目，然后复查状态：

```bash
acgm version
acgm doctor
acgm init .
acgm doctor --strict
```

`acgm init [PATH]` 是幂等的，不覆盖已有的 `CONSTITUTION.md`、`CLAUDE.md` 或
`AGENTS.md`。它只铺最小骨架，不会替用户编造宪法、范围、轨道、ADR 或快照。这些人的
决策通过以下完整 namespaced skill 完成：

```text
/agent-coding-governance-methodology:governance-bootstrap
```

bootstrap 完成后再次运行 `acgm doctor --strict`。部分治理或已经漂移的项目只会被报告，
不会被静默改写。ACGM 不提供自动修改用户治理文件的“project upgrade”。

Doctor 要把项目机械判定为 `GOVERNED`，需要无占位符的 Constitution、根规则，以及以下
全部可发现资产：

- `decisions/`、`docs/decisions/` 或 `.governance/decisions/` 中非空的决策索引或 ADR；
- `.governance/snapshots/`、`docs/snapshots/` 或 `snapshots/` 中非空的快照；
- `.governance/scope.yml` 或 `.governance/scope.yaml`，且同时包含 `in:` 与 `out:`。

项目仍可按方法论选择其他布局，但本 RC 会保持报告 `PARTIALLY_GOVERNED`；doctor 不会
假装能自动发现任意项目约定。

`acgm init` 的脚手架由纯 Python 实现，是 Windows 的初始化主路径，不依赖 POSIX 脚本。
如果只需要不含插件的静态脚手架，可在 macOS 或 Linux 克隆仓库后运行：

```bash
sh Agent-Coding-Governance-Methodology/scripts/governance-init.sh /path/to/project
```

`scripts/governance-init.sh` 只是在 POSIX 上使用的 fallback；它只写静态文件，不安装
hooks，也不提供 Event Ledger，并不是 Windows 初始化路径。

## 哪些会自动运行

hooks 和 skills 的保证不同。

插件健康且 Claude Code 发出匹配事件时，hook 命令会自动执行。但 hook 内部识别仍是有意
收窄的启发式规则；“自动”不等于“全知”。Skills 是模型选择或用户显式调用的指导流程，
本身不是强制机制。

| 事件 | 确定性机制 |
|---|---|
| `SessionStart` | 在 startup、resume、clear、compact 时检查包和项目健康，显示解析后的实际项目根以发现错 cwd，并注入状态与 grounding。 |
| `PreToolUse` | 门控已识别的高风险 Bash 操作，并拒绝 Agent 修改人类所有 Constitution 的路径，包括可能写入或含糊的 Bash；明确只读的 Bash 检查仍可使用。 |
| `PostToolUse` | 开启或关闭后验验证义务；发现治理文档风险结论时提醒，但不修改文件。 |
| `PostToolUseFailure` | 把失败或部分执行的高风险调用视为执行结果未知，并保持后验验证义务。 |
| `Stop` | 后验验证仍开启时阻止回合静默结束，并设有限次循环上限。 |
| `SessionEnd` | 在本地记录未解决义务与从未观察到执行结果的状态；不会把被拒绝或缺失 PostTool 事件武断写成“未执行”。 |

三个选择性 skills 是：

```text
/agent-coding-governance-methodology:session-grounding
/agent-coding-governance-methodology:truth-first
/agent-coding-governance-methodology:governance-bootstrap
```

## 高风险证据门

重新尝试被识别为高风险的操作之前，Agent 必须先做当前 Session 的只读取证，并在紧邻工具
调用之前的回复中写出以下四个精确字段：

```text
ACGM-EVIDENCE: <本 Session 当下来源与实际观察到的标识符>
ACGM-CURRENT-STATE: <刚刚读取的状态，不从摘要继承>
ACGM-VERIFY-AFTER: <操作后要执行的具体核验>
ACGM-ROLLBACK: <命中错误目标时的恢复方案>
```

取证、高风险状态变更和后验核验必须拆成三个独立工具调用。证据与当前状态字段必须绑定
实际目标；`ACGM-VERIFY-AFTER` 必须是同类别的独立检查。这样才能避免命令顺序、无关输出
或复合命令部分失败制造虚假验证。

字段缺失或本 Session 没有当下取证时，操作会在进入人工权限阶段之前被拒绝。四项齐全也
不代表获得授权：ACGM 随后仍会要求人明确批准，并保持后验验证义务，直到它被核验或记录
为 unresolved。

## Doctor、Activity Report 与案例导出

检查包身份、hook 是否齐全、项目状态、本地存储、Python 和连续性提醒：

```bash
acgm version
acgm doctor
acgm doctor --strict
acgm doctor --json
```

读取本地 Event Ledger：

```bash
acgm report --project current --limit 20
acgm report --project current --json
```

根据 event ID 生成本地脱敏案例预览；分享之前必须由人逐行检查：

```bash
acgm export-case evt_EXAMPLE -o acgm-case-preview.md
```

人工审查后给事件分类：

```bash
acgm resolve evt_EXAMPLE --status resolved
```

允许的状态是 `resolved`、`verified`、`human_override`、`false_positive` 和
`unresolved`。

## Event Ledger 隐私模型

Event Ledger 只在本机工作，并从源头最小化。它**绝不自动上传数据**，也不是先收集原始内容再
事后脱敏。原始 hook 输入只在内存中处理，随后丢弃；持久事件只使用本机不透明 ID 和枚举
字段。
事件日志仅存本机，不自动上传。

Ledger 不记录项目路径、文件名、命令、prompt、transcript 正文、模型或服务商名称、远程
URL、基础设施标识符、凭据，也不记录可重建的技术指纹。`export-case` 只生成另一份需要
人工检查的本地预览，绝不会自动分享。

Hooks 会显式获得 Claude 给出的准确 `CLAUDE_PLUGIN_DATA` 路径；`ACGM_DATA_DIR` 是优先级
更高的人工/测试覆盖。两个环境值都没有时，CLI 使用
`${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/data/` 加脱敏插件 ID；本插件默认路径是
`~/.claude/plugins/data/agent-coding-governance-methodology-agent-coding-governance-methodology`。
因此 hooks 与 `acgm report` 会收敛到同一存储。希望卸载后仍保留审计历史时，请保留这些
数据。

## 升级与重载

刷新 marketplace、更新插件并重载：

```bash
claude plugin marketplace update agent-coding-governance-methodology
claude plugin update agent-coding-governance-methodology@agent-coding-governance-methodology
```

```text
/reload-plugins
```

然后验证实际运行身份和项目状态：

```bash
acgm version
acgm doctor --strict
```

升级不会自动迁移或删除项目里的治理资产。doctor 若报告部分治理或漂移，由人决定补什么、
修什么。

## 卸载但保留本地数据

```bash
claude plugin uninstall agent-coding-governance-methodology@agent-coding-governance-methodology --keep-data
```

`--keep-data` 保留由插件管理的 Event Ledger 数据。卸载插件不会移除各项目仓库中的治理
文件。ACGM 不提供静默删除项目资产的命令。

## 边界

- ACGM V3 是 Claude Code 运行时实现。原则可以适配其他 Agent，但本仓不声称具有等价的
  跨平台强制能力。
- 兼容接口接入的第三方 API 后端可能与真正 Claude 表现不同。ACGM 治理可观察到的
  Claude Code 运行表面，不识别、不评价、也不针对兼容接口背后的模型做调优。
- ACGM 不备份 transcript、不绕过账号限制，也不负责从不可访问的平台重建项目。
  **ACGM Recover — Claude Code Project Recovery** 是独立产品线，不属于 V3。
- hook 识别有意保持精准和有限。业务判断、修宪、含糊操作与误报的最终裁定权始终属于人。

## 仓库结构

```text
.claude-plugin/       插件与 marketplace 身份
hooks/                Claude Code 生命周期接线
bin/acgm              本地 CLI 入口
scripts/              hook 运行时、脚手架与检查
skills/               选择性 namespaced 工作流
templates/            空白项目治理骨架
tests/                自动 fixtures 与 Claude Code 人工 E2E
METHODOLOGY*.md       完整方法论
CASES.md              真实脱敏案例
EVIDENCE.md           公开结论成熟度登记表
CHANGELOG.md          版本历史
RELEASING.md          发布验收清单
```

## License 与来源

方法论和散文文档采用 CC-BY-4.0；机械代码采用 MIT。路径映射见
[`LICENSING.md`](LICENSING.md)。

ACGM 来自真实的长周期、多 Session 开发：过期交接、虚构技术结论、分支放置错误和破坏性
操作风险反复出现。这套方法被公开，是为了让其他长期项目能在这些失效相互叠加之前看见它们。
