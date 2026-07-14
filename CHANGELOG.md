# Changelog

All notable ACGM changes are recorded here. The plugin ID remains
`agent-coding-governance-methodology@agent-coding-governance-methodology`.

## [0.3.0-rc.4] — 2026-07-14 (prerelease candidate)

RC4 repairs the first-use and proof-boundary gaps exposed by a real Desktop/third-party
endpoint installation attempt. It remains a test candidate, not a stable release, and
does not claim that every Claude surface or provider route has passed E2E.

### Added

- A surface-aware, schema-v2 preflight that distinguishes automated Claude Code CLI,
  Desktop Code Local/SSH UI, unknown, advisory-only Chat, experimental Cowork, and
  unsupported Code Cloud/WSL routes using observable capabilities only.
- Fail-closed surface conflict handling: an explicit target cannot override official
  Cloud or OS-level WSL runtime evidence and unlock an installer mutation.
- Tagged Git checkout is the only automated-installer source; GitHub source archives
  and release tarballs are labeled audit-only because they lack Git revision/index proof.
- The repository-plugin consent contract is version-gated at Claude Code `2.1.195+`;
  an older or unreadable CLI version cannot enter the automated mutation route.
- Thin `AGENTS.md`, `CLAUDE.md`, and bilingual `INSTALL.md` entrypoints, plus an official
  project-level marketplace declaration that keeps Claude's trust/install prompts.
- Doctor reports a current-version SessionStart health event only as retained historical
  corroboration, never as sufficient proof of live activation or target-surface identity.
- An explicitly authorized `--upgrade-verified-snapshot` transaction for one unique,
  enabled, user-scope, byte-verified older ACGM snapshot. It requires a strictly newer
  target, blocks an active `.in_use` cache, proves scoped removal and
  `uninstall --keep-data`, privately backs up/verifies the Event Ledger, verifies the
  replacement, and rolls back a known failure.
- A read-only legacy-public-install diagnosis and explicit human migration plan for the
  known `0.1.0` / `v0.3.0-rc.1` GitHub shape. Repository/ref/version/scope remain routing
  clues and are never elevated into publisher-authenticity or installed-byte proof.

### Changed

- Installation results now separate `SOURCE_VERIFIED`, `CONFIGURATION_VERIFIED`,
  runtime activation, and project governance. A verified install record/cache no longer
  reports the plugin as ready before reload and hook evidence.
- `claude --version` alone is no longer sufficient: the automated route also checks the
  official plugin-management subcommands before allowing an install plan.
- Missing standalone CLI becomes a Desktop Code UI plan when that surface is selected
  or observed, instead of being misreported as universal Desktop incompatibility.
- An explicit Desktop Local/SSH target remains on its UI/trust route even when a CLI is
  installed; cross-surface configuration is not accepted as Desktop activation.
- Ambiguous in-Claude `auto` detection now asks for the exact target surface instead of
  silently treating a Desktop task with a CLI binary as a CLI installation.
- Claude CLI capability/state probes and mutations use a fresh private neutral cwd, so
  this repository's project-scoped onboarding declaration cannot contaminate user-scope
  inspection or collide with the verified local snapshot.
- Installer dry-runs may execute read-only Claude version/help/list probes but never a
  mutation. Default conflicts remain fail-closed; the upgrade flag cannot absorb
  duplicate, project/local-scope, unknown-source, or legacy public-GitHub installs.
- Upgrade results distinguish verified success, verified rollback, and partial state
  requiring manual repair. Private backup locations are never reported; successful
  upgrades and verified rollbacks clean their temporary backup after data verification.
  If cleanup fails, `retained_backup_verified` distinguishes a reverified complete
  residual backup from a partial, unverified artifact before any recovery claim.

### Boundaries

- ACGM never infers the model/provider behind a gateway or host-managed route.
- Desktop Chat remains skill-only; Cowork command hooks require dedicated E2E; Code
  Cloud/WSL do not count as full-plugin support.
- Native PowerShell and controlled-Windows real-machine E2E remain release gates.

## [0.3.0-rc.3] — Unreleased

Unreleased testing candidate. RC3 has a new version identity because Claude Code uses
the explicit plugin version as its cache key; reusing RC2 after changing the package
could leave testers on stale code. This entry does not mean that `v0.3.0-rc.3` or a
GitHub prerelease has been published.

### Added

- A conservative one-command `scripts/install.py` path for a fresh user-scope install
  from a reviewed local clone, with stable JSON output and a true no-mutation dry-run.
- Exact Git-index/manifest inventory checks, a persistent content-addressed verified
  snapshot, explicit user-scope declaration checks, and post-install cache-byte proof.

### Changed

- The installer uses only fixed-argv Claude CLI mutations, never edits settings
  directly, never replaces a conflicting marketplace, excludes ignored/untracked
  checkout files, and treats an existing plugin as current only after exact scope,
  version, enabled-state, source, and cache verification.
- Installer reports replace the private checkout path with a stable token so shared
  diagnostics do not expose the local user directory.
- Windows installer preflight accepts a native `claude.exe` and rejects legacy batch
  launchers instead of relying on implicit `cmd.exe` parsing.

### Fixed

- Windows hook input and Git output are decoded as UTF-8 independently of the legacy
  code page; hook JSON output is ASCII-safe, and scaffold/manifest writes preserve LF.

### Boundaries

- Native PowerShell hook execution remains unsupported; WSL remains unverified.
- Real-machine Claude Code lifecycle and hook E2E are still required before promotion.

## [0.3.0-rc.2] — Unreleased

Unreleased testing candidate. This entry documents the RC2 source state; it does not
mean that `v0.3.0-rc.2` or a GitHub prerelease has been published. The controlled
Windows profile still requires real-machine Claude Code E2E before it can be described
as validated.

### Added

- A read-only `scripts/preflight.py --json` check that reports install readiness and
  explicit reason codes without changing settings, installing, initializing, or
  inferring an account/model identity.
- Automated regression coverage for the controlled Windows candidate profile and an
  LF checkout contract for cross-platform shell files.
- A Windows Git Bash branch in the manual Claude Code E2E checklist.

### Changed

- The controlled Windows scope is explicit: Windows 10/11, Git for Windows/Git Bash,
  Python 3.10+, and effective `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`.
- Hook commands use a quoted shell-form `sh` invocation, while launchers discover
  `python3`, `python`, or `py -3` instead of requiring one Unix command name.
- `acgm init` now creates the non-overwriting scaffold in Python. The
  `scripts/governance-init.sh` path remains a POSIX-only static fallback.
- Pinned marketplace examples use the full Git URL plus `#v0.3.0-rc.2` and state that
  the command is unavailable until that tag is actually published.

### Fixed

- Runtime locking now has explicit POSIX and Windows implementations, and Windows
  package checks no longer depend on Unix executable bits or a `python3` command name.
- Initialization cleans up only a partial file it created after an interrupted write
  and preserves every pre-existing governance file.

### Boundaries

- Native PowerShell hook execution is unsupported in RC2; WSL is unverified.
- Automated tests and a ready preflight do not substitute for real Claude Code E2E.

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
- Runtime requirements documented Python `3.10+` and automated support on macOS and
  Linux; RC1's then-stated exact Claude Code minimum was not evidence-backed and is
  superseded by RC2's preflight plus live-E2E compatibility gate.
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

[0.3.0-rc.4]: https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology/compare/v0.3.0-rc.1...v0.3.0-rc.4
[0.3.0-rc.3]: https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology/compare/v0.3.0-rc.1...HEAD
[0.3.0-rc.2]: https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology/compare/v0.3.0-rc.1...HEAD
[0.3.0-rc.1]: https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology/compare/50a642776e361be89fc24640c10a9f9fd742d8f0...v0.3.0-rc.1
[0.1.0]: https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology/commits/a558e9fa67565254c3e67810a8c3ec184b857091

---

# 更新日志

ACGM 的重要变更记录在这里。插件 ID 始终保持
`agent-coding-governance-methodology@agent-coding-governance-methodology`。

## [0.3.0-rc.4] — 2026-07-14（预发布候选）

RC4 修复一次真实 Desktop / 第三方兼容端点安装尝试暴露出的首次启用和证据边界缺口。
它仍是测试候选版，不是稳定版，也不声称所有 Claude surface 或 provider 路径已经通过
真机 E2E。

### 新增

- Schema v2 的 surface-aware preflight：只按可观察能力区分 Claude Code CLI 自动路径、
  Desktop Code Local/SSH UI 路径、未知路径、Chat 仅建议路径、Cowork 实验路径，以及
  不支持的 Code Cloud/WSL。
- Surface 冲突失败关闭：显式目标不能覆盖官方 Cloud 或 OS 级 WSL 运行时证据并解锁安装变更。
- 自动安装器只接受固定 tag 的 Git checkout；GitHub 源码压缩包和 release tarball 因缺少
  Git revision/index 证据而明确标为仅供审计。
- Repository-plugin 同意契约以 Claude Code `2.1.195+` 为门槛；旧版或不可读的 CLI
  版本不能进入自动变更路径。
- 薄 `AGENTS.md`、`CLAUDE.md`、双语 `INSTALL.md` 入口，以及保留 Claude 信任/安装提示的
  官方 project-scope marketplace 声明。
- Doctor 仅把当前版本 SessionStart health 事件作为保留的历史旁证；它永远不足以证明
  实时激活或目标 surface 身份。
- 新增由用户另行明确授权的 `--upgrade-verified-snapshot` 事务，只处理唯一、启用、
  user-scope、字节核验过的旧 ACGM snapshot。它要求目标版本严格更高，阻断仍有
  `.in_use` 的 cache，证明带 scope 的移除与 `uninstall --keep-data`，私下备份并核验
  Event Ledger，核验替换，并在状态明确的失败上回滚。
- 对已知 `0.1.0` / `v0.3.0-rc.1` GitHub 形态提供只读旧公开安装诊断与明确人工迁移
  计划；repository/ref/version/scope 始终只是路由线索，不会被提升为发布者真实性或
  安装字节证明。

### 变更

- 安装结果拆分为 `SOURCE_VERIFIED`、`CONFIGURATION_VERIFIED`、运行时激活和项目治理；
  配置记录与缓存字节通过后，不再在 reload 与 hook 证据缺失时宣称可用。
- `claude --version` 不再足够；自动路径还必须验证官方 plugin-management 子命令。
- 已选择或已观察到 Desktop Code surface 时，缺少独立 CLI 会得到 UI 安装计划，不再被
  错报成整个 Desktop 都不兼容。
- 显式 Desktop Local/SSH 即使同机存在 CLI，也保持 UI/trust 路径；跨 surface 配置不能
  充当 Desktop 激活证据。
- Claude 内部的 `auto` 若无法区分 CLI 与 Desktop，会要求准确 surface，不再因存在 CLI
  binary 而静默把 Desktop 任务当作 CLI 安装。
- Claude CLI 能力/状态 probe 与 mutation 使用全新私有 neutral cwd，避免本仓 project-scope
  onboarding 声明污染 user-scope 检查或与验证过的本地 snapshot 冲突。
- Installer dry-run 可以执行 Claude 的只读 version/help/list probe，但绝不 mutation。
  默认冲突继续失败关闭；升级 flag 不能吸收重复、project/local scope、未知来源或旧公开
  GitHub 安装。
- 升级结果区分核验成功、核验回滚与需要人工修复的部分状态；绝不报告私有 backup 路径，
  成功升级与核验回滚会在数据核验后清理临时 backup。
  cleanup 失败时，`retained_backup_verified` 会区分重新核验过的完整残留 backup 与部分、
  未验证 artifact，不能在重验前宣称可恢复。

### 边界

- ACGM 不推断 gateway 或 host-managed 路径背后的真实模型/provider。
- Desktop Chat 仍仅支持 skills；Cowork command hooks 必须独立 E2E；Code Cloud/WSL
  不计为完整插件支持。
- Native PowerShell 与受控 Windows 真机 E2E 仍是发布门槛。

## [0.3.0-rc.3] — 尚未发布

测试候选版。Claude Code 把显式插件版本作为缓存键；包内容改变后继续复用 RC2，可能让
测试者仍运行旧缓存，因此 RC3 使用新的版本身份。本节不代表 `v0.3.0-rc.3` tag 或
GitHub prerelease 已经发布。

### 新增

- 面向已审查本地 clone 的保守一命令 `scripts/install.py` 首次 user-scope 安装路径，
  提供稳定 JSON 输出和真正零变更的 dry-run。
- 对 Git index 与 manifest 做完整文件集合核对，建立持久、按内容寻址的验证快照，明确
  核对 user-scope 声明，并在安装后验证 Claude 缓存字节。

### 变更

- 安装器的 Claude 变更只使用固定 argv CLI，不直接编辑设置、不替换冲突 marketplace，
  不把 ignored/untracked 文件带入安装；已有插件只有在 scope、版本、启用状态、来源和
  缓存全部准确一致后才视为当前版本。
- 可分享的安装报告用稳定 token 代替私有 checkout 路径，避免泄露本机用户目录。
- Windows 安装预检只接受原生 `claude.exe`，拒绝旧式 batch launcher，避免依赖隐式
  `cmd.exe` 解析。

### 修复

- Windows hook 输入与 Git 输出独立于旧代码页按 UTF-8 解码；hook JSON 输出使用
  ASCII-safe wire，脚手架与 manifest 写入保持 LF。

### 边界

- Native PowerShell hook 仍不受支持；WSL 仍未验证。
- 提升版本前仍必须完成真实 Claude Code 生命周期与 hook E2E。

## [0.3.0-rc.2] — 尚未发布

测试候选版。这里记录的是 RC2 源码状态，不代表 `v0.3.0-rc.2` tag 或 GitHub
prerelease 已经发布。受控 Windows profile 在真实 Claude Code 真机 E2E 通过前，不得
描述成已经验证。

### 新增

- 只读 `scripts/preflight.py --json` 安装前检查：只报告 readiness 与明确 reason codes，
  不修改设置、不安装、不初始化，也不推断账号或模型身份。
- 受控 Windows 候选 profile 的自动回归覆盖，以及保证跨平台 shell 文件为 LF 的 checkout
  契约。
- 人工 Claude Code E2E 清单中的 Windows Git Bash 分支。

### 变更

- 受控 Windows 范围明确为：Windows 10/11、Git for Windows/Git Bash、Python 3.10+，
  以及有效的 `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`。
- Hook 命令改为路径加引号的 shell-form `sh` 调用；launcher 会发现 `python3`、`python`
  或 `py -3`，不再要求唯一的 Unix 命令名。
- `acgm init` 改用 Python 创建不覆盖的脚手架；`scripts/governance-init.sh` 仍只是 POSIX
  静态 fallback。
- 固定 marketplace 示例改为完整 Git URL 加 `#v0.3.0-rc.2`，并明确 tag 实际发布前
  该命令不可用。

### 修复

- 运行时锁具有明确的 POSIX 与 Windows 实现；Windows 包检查不再依赖 Unix 可执行位或
  `python3` 命令名。
- 初始化写入中断时，只清理本次创建的残缺文件，并保留所有预先存在的治理文件。

### 边界

- RC2 不支持 native PowerShell hook；WSL 尚未验证。
- 自动测试通过或 preflight ready 都不能代替真实 Claude Code E2E。

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
- 运行要求记录了 Python `3.10+`，自动化支持覆盖 macOS 与 Linux；RC1 当时写下的精确
  Claude Code 最低版本缺乏证据，已由 RC2 的 preflight 加真实 E2E 兼容性门取代。
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
