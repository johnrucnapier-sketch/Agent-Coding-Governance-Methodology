# Changelog

All notable ACGM changes are recorded here. The plugin ID remains
`agent-coding-governance-methodology@agent-coding-governance-methodology`.

## [0.3.0-rc.1] — 2026-07-12

Release candidate. This version is not stable until the real-Claude-Code checklist in
`tests/manual/CLAUDE_CODE_E2E.md` has passed and the results have been reviewed.

### Added

- A versioned V3 package identity shared by `VERSION` and the plugin manifest.
- Project-state assessment: `INSTALLED_NOT_BOOTSTRAPPED`, `PARTIALLY_GOVERNED`,
  `GOVERNED`, `DRIFTED`, and `BROKEN`.
- A single local runtime for `SessionStart`, `PreToolUse`, `PostToolUse`,
  `PostToolUseFailure`, `Stop`, and `SessionEnd`.
- A fail-closed wrapper for all Bash when Python is unavailable or crashes; without
  the runtime, the wrapper cannot prove a command is harmless.
- A local, source-minimized Event Ledger, Activity Report, manual case export, and
  human event-resolution states.
- `acgm init`, `version`, `doctor`, `report`, `export-case`, and `resolve` commands.
- Automated regression fixtures, release-contract checks, and a real Claude Code E2E
  checklist.
- A public `EVIDENCE.md` claim-maturity register for release decisions and corrected
  mechanism attribution.
- Explicit install, update, reload, and uninstall-with-data-retention instructions.

### Changed

- Product title shortened to **ACGM**, with the tagline “Drift control for
  long-horizon agent coding.”
- Hooks are described as deterministic mechanisms for matching Claude Code events;
  skills are described as selective, model- or user-invoked workflows.
- High-risk operations use four exact fields:
  `ACGM-EVIDENCE:`, `ACGM-CURRENT-STATE:`, `ACGM-VERIFY-AFTER:`, and
  `ACGM-ROLLBACK:`.
- High-risk source checks, state changes, and declared verification run as separate
  target-bound calls; compound high-risk commands are denied.
- SessionStart now covers startup, resume, clear, and compact and reports the actual
  project governance state.
- Governance-file checking no longer appends marker comments to user files.
- Full skill references use the plugin namespace.
- Runtime requirements are explicit: Claude Code `2.1.143+`, Python `3.10+`, with
  automated support on macOS and Linux; native Windows hooks remain unvalidated.
- Hooks receive the official plugin-data path explicitly; the CLI uses the same
  default, while `ACGM_DATA_DIR` remains an explicit manual/test override.
- The `acgm` PATH guarantee is limited to Bash launched by plugin-enabled Claude Code;
  repository clones use `./bin/acgm` in an ordinary shell.

### Fixed

- The public package now has a new version identity instead of reusing `0.1.0` for
  materially different runtime content.
- Doctor can expose a stale installed version, incomplete package, unwritable ledger,
  missing Python, partial bootstrap, and governance drift.
- A generic `CLAUDE.md` alone is no longer described as proof that complete governance
  is operating.
- Post-action verification can remain open through Stop and be recorded at SessionEnd
  instead of relying only on the acting Agent remembering it.
- Failed or interrupted high-risk Bash is no longer treated as proof that no state
  changed; exact declared verification remains open after possible partial effects.
- Verification obligations are target/project-bound, serialized across parallel
  hooks, checked as a complete set at Stop, and fail closed when local state is
  corrupt or post-action correlation fails.
- Long transcripts are read from a bounded tail, invalid explicit init paths fail
  instead of falling back to the current repository, and `DRIFTED` remains sticky
  until required governance assets are restored.

### Privacy

- Persistent events exclude raw project paths, file names, commands, prompts,
  transcripts, model/provider names, remote URLs, infrastructure identifiers,
  credentials, and reconstructable technical fingerprints.
- ACGM never automatically uploads the Event Ledger or exported case previews.

## [0.1.0] — 2026-05-18

### Added

- Initial public Claude Code plugin and marketplace metadata.
- Session grounding, truth-first, and governance-bootstrap skills.
- Bilingual methodology, cases, templates, and dual licensing.
- Initial SessionStart injection, generic scaffold, and later v2-era hook experiments
  published without a corresponding package-version increment.

[0.3.0-rc.1]: https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology/compare/50a642776e361be89fc24640c10a9f9fd742d8f0...v0.3.0-rc.1
[0.1.0]: https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology/commits/a558e9fa67565254c3e67810a8c3ec184b857091

---

# 更新日志

ACGM 的重要变更记录在这里。插件 ID 始终保持
`agent-coding-governance-methodology@agent-coding-governance-methodology`。

## [0.3.0-rc.1] — 2026-07-12

候选版。`tests/manual/CLAUDE_CODE_E2E.md` 尚未在真实 Claude Code 上通过并完成审查
之前，本版本不是稳定版。

### 新增

- 由 `VERSION` 与 plugin manifest 共同确定的 V3 版本身份。
- 项目状态：`INSTALLED_NOT_BOOTSTRAPPED`、`PARTIALLY_GOVERNED`、`GOVERNED`、
  `DRIFTED`、`BROKEN`。
- `SessionStart`、`PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`Stop`、
  `SessionEnd` 的统一本地运行时。
- Python 不可用或崩溃时，对所有 Bash 失败关闭；没有运行时就无法证明命令无害。
- 本地、源头最小化的 Event Ledger、Activity Report、人工案例导出和事件人工分类状态。
- `acgm init`、`version`、`doctor`、`report`、`export-case`、`resolve` 命令。
- 自动回归 fixtures、发布契约检查和真实 Claude Code E2E 清单。
- 面向发布决策和机制归因更正的公开 `EVIDENCE.md` 结论成熟度登记表。
- 明确的安装、更新、重载和保留数据卸载说明。

### 变更

- 产品标题缩短为 **ACGM**，tagline 为 “Drift control for long-horizon agent
  coding.”
- Hooks 被准确描述为匹配 Claude Code 事件时的确定性机制；skills 被描述为模型或用户
  选择调用的工作流。
- 高风险操作使用四个精确字段：`ACGM-EVIDENCE:`、`ACGM-CURRENT-STATE:`、
  `ACGM-VERIFY-AFTER:`、`ACGM-ROLLBACK:`。
- 高风险取证、状态变更与声明的核验使用彼此独立且绑定目标的调用；复合高风险命令会被拒绝。
- SessionStart 覆盖 startup、resume、clear、compact，并报告实际项目治理状态。
- 治理文档检查不再向用户文件追加 marker comment。
- Skill 引用统一使用完整插件命名空间。
- 运行要求明确为 Claude Code `2.1.143+`、Python `3.10+`；自动化支持覆盖 macOS 与
  Linux，Windows 原生 hooks 尚未验证。
- Hooks 显式获得官方 plugin-data 路径；CLI 使用同一默认值，`ACGM_DATA_DIR` 保留为
  人工/测试覆盖。
- `acgm` PATH 只保证插件已启用的 Claude Code Bash；仓库 clone 在普通 shell 中使用
  `./bin/acgm`。

### 修复

- 公开包使用新版本身份，不再让明显不同的运行时内容继续复用 `0.1.0`。
- Doctor 可以暴露安装版本过期、包不完整、Ledger 不可写、缺少 Python、bootstrap 不完整
  和治理漂移。
- 普通 `CLAUDE.md` 不再被描述成完整治理正在运行的证明。
- 后验验证可以通过 Stop 保持开启，并在 SessionEnd 留下记录，不再只依赖当事 Agent
  自己记住。
- 高风险 Bash 失败或中断不再被当成“状态没有变化”的证明；可能部分执行时，准确声明的
  后验核验继续保持开启。
- 验证义务绑定目标与项目，并行 hooks 通过锁串行更新；Stop 检查全部义务，本地状态损坏
  或动作后无法关联时失败关闭。
- 长 transcript 改为有界尾部读取；显式 init 路径无效时不再回退当前仓库；`DRIFTED`
  会保持到必要治理资产恢复。

### 隐私

- 持久事件排除原始项目路径、文件名、命令、prompt、transcript、模型或服务商名称、
  远程 URL、基础设施标识符、凭据和可重建技术指纹。
- ACGM 绝不自动上传 Event Ledger 或导出的案例预览。

## [0.1.0] — 2026-05-18

### 新增

- 初始公开 Claude Code 插件和 marketplace 元数据。
- Session grounding、truth-first、governance-bootstrap skills。
- 双语方法论、案例、模板和双轨许可证。
- 初始 SessionStart 注入、通用脚手架，以及后来在没有同步提升包版本时发布的 v2-era
  hook 实验。
