# Install ACGM V3 RC4 / 安装 ACGM V3 RC4

This guide is the authoritative onboarding route for `v0.3.0-rc.4`. Downloading or
cloning this repository is **not** installation. / 本文是 `v0.3.0-rc.4` 的权威引导；
下载或 clone 本仓库**不等于安装**。

The automated installer requires a clean Git checkout because its proof binds the
publishable index, commit, and package manifest. GitHub source archives and attached
tarballs are audit artifacts only and intentionally fail with
`CHECKOUT_REVISION_BLOCKED`; use the tagged `git clone` command below. / 自动安装器要求
clean Git checkout，因为证据会绑定可发布 index、commit 与 package manifest。GitHub
源码压缩包和附加 tarball 只能用于审计，会有意以 `CHECKOUT_REVISION_BLOCKED` 停止；请使用
下文固定 tag 的 `git clone`。

## Safety contract / 安全契约

- Stay read-only unless the user explicitly asks to install, enable, set up, or activate
  ACGM. / 除非用户明确要求安装、启用、配置或激活 ACGM，否则保持只读。
- A user must personally approve every workspace, marketplace, and plugin trust prompt.
  Project settings never bypass consent. / workspace、marketplace 与 plugin 的信任提示
  必须由用户本人确认；项目设置不绕过同意。
- The repository-plugin consent contract requires Claude Code `2.1.195+`. The CLI
  route blocks an older/unreadable version; a UI-only Local/SSH route must verify the
  exact target app version before accepting prompts. / Repository-plugin 同意契约要求
  Claude Code `2.1.195+`；CLI 路径会阻断旧版或不可读版本，只有 UI 的 Local/SSH 路径
  必须先核对准确目标 app 版本再接受提示。
- Do not infer the account, provider, or model behind a host or gateway. Route by
  observable surface and capability only. / 不猜测 host 或 gateway 背后的账号、provider
  或模型，只按可观察 surface 与能力路由。
- Stop on a source, ref, version, scope, cache, or existing-install conflict. The only
  automated replacement exception is an explicitly authorized
  `--upgrade-verified-snapshot` transaction described below. Unknown, duplicate,
  project/local-scope, and legacy public-GitHub installs remain fail-closed.
  / 遇到来源、ref、版本、scope、缓存或既有安装冲突时立即停止。唯一自动替换例外，是
  下文由用户明确授权的 `--upgrade-verified-snapshot` 事务；未知、重复、project/local
  scope 与旧公开 GitHub 安装仍然失败关闭。
- Plugin installation and project bootstrap are separate. Run `acgm init` only after a
  separate explicit request for the target project. / 插件安装与项目初始化相互独立；只有
  用户另行明确要求初始化目标项目时，才可运行 `acgm init`。

## Choose the surface / 选择运行表面

| Surface / 表面 | Route / 路由 | ACGM status / 状态 |
|---|---|---|
| Claude Code CLI on macOS/Linux | Verified CLI flow below | Full candidate; verify hooks / 完整候选，需核验 hooks |
| Claude Code CLI on controlled Windows Git Bash | Windows CLI flow below | RC candidate only / 仅 RC 候选 |
| Claude Desktop **Code Local** | Project trust prompts or plugin manager | Full candidate; Desktop E2E required |
| Claude Desktop **Code SSH** | Plugin manager; dependencies execute on the SSH host | Full candidate; verify on remote host |
| Claude Desktop **Chat** | Customize → Plugins | Skills only; hooks do not run / 仅 skills |
| Claude **Cowork** | Customize → Plugins | Experimental until ACGM command-hook E2E |
| Claude Desktop **Code Remote/Cloud** | No route | Plugins unavailable / 不支持插件 |
| Claude Desktop **Code WSL** | No route | Plugins unavailable; this RC also blocks WSL preflight |

RC4 exposes the installation shape in machine results:

- CLI installer: `verified_snapshot_user` — user-scope, content-addressed local
  snapshot, verified against the tagged clean checkout.
- Desktop Local/SSH: `github_tag_desktop_ui` — immutable GitHub-tag marketplace through
  the project bridge or Plugins UI; the actual project/user/local scope must be
  observed after human consent.

RC4 会在机器结果中显式给出安装形态：CLI 是 user-scope、内容寻址并绑定 clean tag clone
的 `verified_snapshot_user`；Desktop Local/SSH 是经 project bridge 或 Plugins UI 的固定
GitHub tag `github_tag_desktop_ui`，实际 project/user/local scope 必须在人同意后观察。不得在
同一 scope 把同名 marketplace 混用两种来源。

An explicit Desktop Local/SSH target stays on the Desktop plugin-manager route even
when a standalone CLI exists on the same host. Shared configuration is not proof that
the named Desktop surface loaded or trusted the plugin. / 显式 Desktop Local/SSH 目标即使
同机存在独立 CLI，也保持 Desktop plugin-manager 路径；共享配置不能证明已命名 Desktop
surface 已加载或信任插件。

When preflight runs inside Claude Code and both CLI and Desktop are plausible, `auto`
cannot identify the UI and returns `TARGET_SURFACE_REQUIRED`. Rerun with the exact
human-selected surface; do not infer it from a model label. / 当 preflight 位于 Claude
Code 内且 CLI、Desktop 都可能时，`auto` 无法识别 UI，会返回
`TARGET_SURFACE_REQUIRED`；按人实际选择的 surface 显式复跑，不得从模型名称推断。

## Claude Code CLI / CLI 安装

Use this route only after explicit installation authorization. Start from a clean
checkout of the published tag and record the actual commit. / 仅在获得明确安装授权后使用；
从已发布 tag 的 clean checkout 开始，并记录实际 commit。

```bash
git clone --branch v0.3.0-rc.4 --depth 1 \
  https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology.git \
  ACGM-v0.3.0-rc.4
cd ACGM-v0.3.0-rc.4
git status --short
python3 scripts/preflight.py --surface claude-code-cli --json
python3 scripts/install.py --surface claude-code-cli --dry-run --json
python3 scripts/install.py --surface claude-code-cli --json
```

The controlled Windows profile is Windows 10/11 + native `claude.exe` + Git for
Windows/Git Bash + Python 3.10+ + `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`:
/ 受控 Windows profile 为 Windows 10/11 + 原生 `claude.exe` + Git for Windows/Git
Bash + Python 3.10+ + `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`：

```bash
py -3 scripts/preflight.py --surface claude-code-cli --json
py -3 scripts/install.py --surface claude-code-cli --dry-run --json
py -3 scripts/install.py --surface claude-code-cli --json
```

The preflight and dry-run are read-only. They may execute Claude's read-only version,
help, and JSON list probes, but never a mutation. The real installer uses the official
Claude plugin CLI, verifies the package and installed cache, and stops rather than
replacing an unproved conflict. Do not work around a blocked result by editing
`~/.claude/settings.json`. / preflight 与 dry-run 只读；它们可以执行 Claude 的只读
version、help 与 JSON list 探针，但绝不变更状态。真实安装器使用官方 Claude plugin
CLI，核验发布包与安装缓存，遇到无法证明的冲突就停止。不得通过手改
`~/.claude/settings.json` 绕过阻塞。
`plugin_trust_contract.ok` must be true on the automated route. / 自动路径的
`plugin_trust_contract.ok` 必须为 true。

In an active Claude Code session, finish activation and verification:
/ 在活动 Claude Code session 中完成激活与核验：

```text
/reload-plugins
/hooks
```

```bash
acgm version
acgm doctor
```

Verify that `/hooks` lists ACGM's lifecycle hooks and that the running version is
`0.3.0-rc.4`. `acgm doctor` may correctly report that the current project is not yet
bootstrapped; that is not permission to initialize it. / 必须确认 `/hooks` 列出 ACGM
生命周期 hooks，且运行版本为 `0.3.0-rc.4`。`acgm doctor` 可以如实报告当前项目尚未
初始化；这不构成初始化授权。

## Upgrade one verified CLI snapshot / 升级已核验的 CLI snapshot

This automated upgrade route is deliberately narrower than a normal package-manager
update. Run it from the clean checkout of the new tag only after the user separately
asks to upgrade and every Claude Code or Desktop Code session using ACGM is closed:
/ 这条自动升级路径有意比普通包管理器 update 更窄。仅在用户另行明确要求升级、并关闭
所有正在使用 ACGM 的 Claude Code 或 Desktop Code session 后，从新 tag 的 clean
checkout 执行：

```bash
python3 scripts/install.py --surface claude-code-cli \
  --upgrade-verified-snapshot --dry-run --json
python3 scripts/install.py --surface claude-code-cli \
  --upgrade-verified-snapshot --json
```

The transaction is available only when the installer can prove one unique enabled
user-scope ACGM plugin, one unique older content-addressed `verified_snapshot_user`
marketplace, its exact cache bytes and declaration, a strictly newer target version,
an unused cache, scoped removal support, `uninstall --keep-data`, and a verified private
backup of the Event Ledger data. It uninstalls with `--keep-data`, replaces only that
proved snapshot, verifies the new cache, restores/verifies the ledger data, and rolls
the old snapshot back on a known failure. A dry-run reports the plan without mutation.
/ 只有安装器能够证明以下全部事实时事务才可用：唯一且启用的 user-scope ACGM 插件、
唯一旧版内容寻址 `verified_snapshot_user` marketplace、准确 cache 字节与声明、目标版本
严格更高、cache 未在使用、支持带 scope 的移除、支持 `uninstall --keep-data`，以及
Event Ledger 私有备份已核验。事务会用 `--keep-data` 卸载，只替换这个已证明 snapshot，
核验新 cache，恢复并核验 ledger；遇到状态明确的失败则回滚旧 snapshot。dry-run 只报告
计划，不执行变更。

If the installer reports an active `.in_use` cache, duplicate state, an unknown source,
a project/local-scope install, changed data during the transaction, or an unprovable
rollback state, stop. A manual-repair result is not success; preserve the opaque backup
token it reports and do not guess its filesystem location. Check
`retained_backup_verified`: `true` proves the retained artifact is still byte-exact;
`false` means the token identifies only an unverified residual artifact, so rely on the
verified live Ledger and manual repair rather than treating it as a recoverable backup.
/ 如果安装器报告正在使用的
`.in_use` cache、重复状态、未知来源、project/local scope、事务期间数据变化或无法证明
回滚状态，应立即停止。要求人工修复的结果不等于成功；保留其返回的不透明 backup token，
不得猜测或公开真实文件位置。还要检查 `retained_backup_verified`：`true` 才证明残留
artifact 字节准确；`false` 只说明 token 指向未验证残留，此时必须以已核验 live Ledger 与
人工修复为准，不能把它当成可恢复 backup。

After success, reopen the named target surface, reload, and repeat the same-surface
`/hooks`, `/skills`, `acgm version`, controlled-hook, and `acgm doctor` checks. A
configuration upgrade alone is not `ACTIVE_VERIFIED`. / 成功后重新打开已命名目标 surface，
reload，并在同一 surface 重做 `/hooks`、`/skills`、`acgm version`、受控 hook 与
`acgm doctor` 核验；只有配置升级成功，仍不等于 `ACTIVE_VERIFIED`。

## Migrate a legacy public-GitHub install / 迁移旧公开 GitHub 安装

The published `0.1.0` / `v0.3.0-rc.1` GitHub marketplace shape is not a verified local
snapshot and is never auto-converted by `--upgrade-verified-snapshot`. RC4 may diagnose
a unique known-shaped legacy record and return
`LEGACY_PUBLIC_GITHUB_INSTALL_REQUIRES_EXPLICIT_MIGRATION`; repository, ref, displayed
version, and scope are routing clues, **not** proof of publisher authenticity or exact
installed bytes. / 已发布的 `0.1.0` / `v0.3.0-rc.1` GitHub marketplace 形态不是已核验
本地 snapshot，`--upgrade-verified-snapshot` 绝不会自动转换它。RC4 可以只读识别唯一、
形态已知的旧记录并返回 `LEGACY_PUBLIC_GITHUB_INSTALL_REQUIRES_EXPLICIT_MIGRATION`；
repository、ref、显示版本与 scope 只是路由线索，**不能**证明发布者真实性或安装字节。

For a unique **user-scope** legacy record only, first review the diagnosis and close
all ACGM sessions. From the RC4 checkout, run the full privacy-safe Ledger report and
privately record the exact stdout SHA-256 plus event count. The very large explicit
limit avoids the ordinary recent-20 display boundary. On Windows Git Bash, use
`py -3` instead of `python3`. / 仅当诊断为唯一的 **user-scope** 旧记录时，先审查结果并
关闭全部 ACGM session。然后从 RC4 checkout 运行完整、脱敏的 Ledger report，并私下记录
准确 stdout SHA-256 与 event count。显式大 limit 用于避开普通 report 最近 20 条的显示
边界；Windows Git Bash 把 `python3` 换成 `py -3`。

```bash
python3 scripts/acgm_runtime.py report --project all \
  --limit 9223372036854775807 --json
```

Only after a separate human authorization, uninstall the exact user-scope plugin while
retaining data:
/ 只有获得另一次人工授权后，才卸载准确 user-scope plugin 并保留数据：

```bash
claude plugin uninstall \
  agent-coding-governance-methodology@agent-coding-governance-methodology \
  --scope user --keep-data
```

Before removing the marketplace, run `claude plugin list --json`, repeat the **same**
RC4 report command, and prove both postconditions: the exact plugin ID is absent, and
the after-report exact stdout SHA-256 plus event count equals the private baseline.
Stop if either check fails. Only after that verification gate may the separately
authorized marketplace removal run:
/ 移除 marketplace 前，先运行 `claude plugin list --json`，再重复**同一个** RC4 report
命令，并证明两个 postcondition：准确 plugin ID 已消失；after-report 的准确 stdout
SHA-256 与 event count 等于私下 baseline。任一失败都立即停止。只有该 verification gate
通过，才可执行另行授权的 marketplace remove：

```bash
claude plugin marketplace remove agent-coding-governance-methodology --scope user
```

Then choose exactly one RC4 target shape: run the verified CLI installer above for
`verified_snapshot_user`, or use the pinned-tag Desktop Plugins UI route for
`github_tag_desktop_ui`. Reopen, reload, verify the retained report, and run the
same-surface activation checklist. The machine result's ordered
`manual_migration_plan` is non-executable by default; every mutation still requires
separate human authorization. If scope/source/version is different, duplicated, or
ambiguous, do not run these commands; inspect manually. / 随后只选择一种 RC4 目标形态：
CLI 使用上文 `verified_snapshot_user` 安装器；Desktop 使用固定 tag 的 Plugins UI
`github_tag_desktop_ui`。重新打开、reload、核验保留的 report，并完成同 surface 激活
清单。机器结果中的有序 `manual_migration_plan` 默认不可自动执行，每个 mutation 仍需人
另行授权。若 scope、source、version 不同、重复或含糊，不得执行这些命令，应人工审查。

## Desktop Code Local or SSH without standalone CLI
## 没有独立 CLI 的 Desktop Code Local/SSH

1. Open this exact tagged checkout as a Local or SSH Code project. For SSH, Python,
   Git, the plugin cache, and hook commands live on the remote host.
   / 用 Local 或 SSH Code 打开这个准确 tag；SSH 的 Python、Git、插件缓存与 hook 命令
   位于远程主机。
   Run the read-only router with `python3 scripts/preflight.py --surface
   desktop-code-local --json` (or `desktop-code-ssh`). If standalone CLI is absent,
   it must return `MANUAL_INSTALL_PLAN_AVAILABLE`, not claim full activation. /
   运行只读路由（Local 使用 `--surface desktop-code-local`，SSH 使用
   `--surface desktop-code-ssh`）；缺少独立 CLI 时必须返回
   `MANUAL_INSTALL_PLAN_AVAILABLE`，不能宣称已经激活。
   Confirm the exact target app is Claude Code `2.1.195+`; absence of a standalone CLI
   leaves this as a required human verification, not a guessed pass. / 确认准确目标 app
   是 Claude Code `2.1.195+`；没有独立 CLI 时，这是必须人工核验的事项，不能猜测为通过。
2. Review `.claude/settings.json`. It declares the GitHub marketplace at the immutable
   `v0.3.0-rc.4` ref and enables ACGM for this project.
   / 检查 `.claude/settings.json`；它声明固定到不可变 `v0.3.0-rc.4` 的 GitHub
   marketplace，并为本项目启用 ACGM。
   This bridge can bootstrap the source project only; it is not proof of a user-wide
   install. / 这个 bridge 只能引导源码项目，不证明已经完成 user-wide 安装。
3. Claude Code must prompt the user to trust the folder, install the marketplace, and
   trust/install the plugin. The agent may explain each prompt but must not approve it.
   / Claude Code 必须提示用户信任目录、安装 marketplace、信任并安装插件；Agent 可以
   解释提示，但不能代为同意。
4. If the prompt does not appear, use `+ → Plugins → Add plugin` and select ACGM from
   the configured marketplace. Use project scope for a source-repo trial; choose user
   scope only when the user explicitly asked to install ACGM across projects. Do not
   claim that Chat/Cowork installation state has synchronized
   into Code. / 若未出现提示，使用 `+ → Plugins → Add plugin`，从已配置 marketplace
   选择 ACGM；除非用户另行要求全局安装，否则保持 project scope。不得假定
   Chat/Cowork 的安装状态已同步到 Code。
5. Reload plugins where available. Inspect the plugin manager, use `/hooks` when the
   surface exposes it, and trigger a controlled hook check; then run `acgm version` and
   `acgm doctor` from a plugin-enabled Bash tool. If `acgm` is absent or no hook can be
   observed, the installation is not fully verified. / 可用时重载插件；检查 plugin manager，
   surface 支持时使用 `/hooks`，并触发受控 hook 核验；再从插件启用后的 Bash 运行
   `acgm version` 与 `acgm doctor`。若没有 `acgm` 或无法观察任何 hook，安装尚未完整验证。

## Chat, Cowork, Remote, and WSL

- Desktop Chat can add the marketplace through `Customize → Plugins`, but plugin hooks
  and sub-agents do not run there. Label it `SKILL_ONLY`, never full governance.
  / Desktop Chat 可通过 `Customize → Plugins` 添加 marketplace，但 hooks 与 sub-agents
  不运行；只能标记为 `SKILL_ONLY`。
- Cowork supports plugins and hooks in general, but ACGM's command-hook runtime has not
  yet passed Cowork E2E. Label it `EXPERIMENTAL_UNVERIFIED`; do not promise enforcement.
  / Cowork 通常支持插件与 hooks，但 ACGM command-hook 尚未通过 Cowork 真机 E2E；只能
  标记为 `EXPERIMENTAL_UNVERIFIED`，不得承诺强制治理。
- Desktop Code Remote/Cloud and Desktop Code WSL do not support plugins. Stop and ask
  the user to choose CLI, Code Local, or Code SSH. This RC's preflight also rejects WSL.
  / Desktop Code Remote/Cloud 与 Desktop Code WSL 不支持插件；停止并请用户改用 CLI、
  Code Local 或 Code SSH。本 RC 的 preflight 也拒绝 WSL。
- `--surface` is a target choice, not authority to erase stronger environment facts.
  An official Cloud signal or OS-level WSL signal wins over a contradictory choice and
  returns `SURFACE_SIGNAL_CONFLICT` before any install mutation. / `--surface` 只是目标
  选择，不是抹掉更强环境事实的授权；官方 Cloud 或 OS 级 WSL 信号优先，矛盾时会在任何
  安装变更前返回 `SURFACE_SIGNAL_CONFLICT`。

## Report the proved state / 只报告已证明状态

- `DOWNLOADED`: source exists; nothing installed / 只有源码。
- `DECLARED_AWAITING_CONSENT`: project settings found; trust/install not approved.
  / 已声明，等待用户同意。
- `CONFIGURATION_VERIFIED`: exact install record/cache exists; running package or hooks not proven.
  / 有安装记录，运行包或 hooks 尚未证明。
- `ACTIVE_VERIFIED`: the exact version, enabled state, `/hooks`, `/skills`, and a
  controlled hook probe were verified in one named target surface after a recorded
  baseline. Doctor's retained SessionStart event is historical corroboration only.
  / 在一个已命名目标 surface 中、记录基线后，核验准确版本、启用状态、`/hooks`、
  `/skills` 与受控 hook probe；doctor 保留的 SessionStart 事件只能作为历史旁证。
- `BLOCKED_CONFLICT`: conflicting state found; no automatic repair performed.
  / 发现冲突，且未自动修复。

Official references / 官方依据:
[Claude Code settings](https://code.claude.com/docs/en/settings),
[Desktop Code](https://code.claude.com/docs/en/desktop),
[Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces), and
[Plugins in Claude](https://support.claude.com/en/articles/13837440-use-plugins-in-claude).
