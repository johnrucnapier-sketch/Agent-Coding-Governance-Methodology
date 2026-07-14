# Claude Code E2E acceptance / Claude Code 端到端验收

This checklist requires a working Claude Code account or official Claude API route.
It validates the real plugin lifecycle that unit tests cannot simulate. ACGM
`0.3.0-rc.4` is a testing prerelease candidate and must not be promoted to stable
until this checklist passes.

本清单需要可用的 Claude Code 账号或官方 Claude API 路径，用于验证单元测试无法模拟的
真实插件生命周期。ACGM `0.3.0-rc.4` 是测试预发布候选版，未通过本清单之前不得
升级为稳定版。

## Safety boundary / 安全边界

- Use a newly created disposable Git repository. Never run this checklist in a real
  project, production environment, or directory containing valuable untracked data.
- The only destructive test target is the exact disposable directory
  `acgm-e2e-delete-me` created below.
- Read every command before approval. A hook result is not permission.
- Do not paste credentials, account identifiers, real prompts, transcripts,
  infrastructure names, or private paths into the result record.
- Keep the Event Ledger isolated with `ACGM_DATA_DIR`.

- 只在新建的可丢弃 Git 仓库中测试；不得在真实项目、生产环境或含有宝贵未跟踪数据的目录
  中执行。
- 唯一破坏性测试目标是下文准确创建的 `acgm-e2e-delete-me`。
- 批准前逐条阅读命令；hook 结果不等于权限。
- 结果记录不得包含凭据、账号标识、真实 prompt、transcript、基础设施名称或私有路径。
- 使用 `ACGM_DATA_DIR` 隔离测试 Event Ledger。

## Test record / 测试记录

Fill this before testing. Record the runtime route category only; do not probe or guess
the model identity behind a compatible endpoint.

测试前填写。只记录运行路径类别；不得探查或猜测兼容接口背后的模型身份。

| Field / 字段 | Value / 值 |
|---|---|
| Date / 日期 | |
| Tester / 测试人 | |
| OS and architecture | |
| Claude Code version (record the actual current version) | |
| ACGM version | |
| Target surface / 目标 surface | Claude Code CLI / Desktop Code Local / Desktop Code SSH |
| Install source / 安装来源 | GitHub marketplace / local release candidate |
| Runtime route / 运行路径 | Claude account / official Claude API / compatible third-party endpoint / unknown |
| Python version (must be >= `3.10`) | |
| Shell profile / Shell 配置 | macOS/Linux Bash / Windows Git Bash candidate |
| Windows PowerShell tool setting | N/A / effective `CLAUDE_CODE_USE_POWERSHELL_TOOL=0` |
| Source identity / 源码身份 | exact commit / published tag |

Stable promotion requires at least one full pass on `Claude account` or `official
Claude API`. A compatible third-party endpoint may be recorded as an additional
compatibility observation, not substituted for that gate. Use a current, working
Claude Code and record its actual version. Claude Code `2.1.195+` is required for the
documented repository-plugin install/trust consent contract; preflight plus live E2E
determine the remaining compatibility claims. RC4 also defines one
controlled Windows testing profile: **Windows 10/11 + Git for Windows/Git Bash +
Python 3.10+ + effective `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`**. A Windows pass must
use that exact profile and remains candidate evidence until this entire checklist is
completed on a real machine. Native PowerShell hooks are unsupported and WSL is
unverified; neither counts as a supported Windows result.

稳定版至少需要一次 `Claude account` 或 `official Claude API` 的完整通过。第三方兼容
接口可以作为附加兼容性观察，但不能替代该门槛。使用当前可用的 Claude Code 并记录实际
版本；repository-plugin install/trust 同意契约要求 Claude Code `2.1.195+`，其余兼容性由
preflight 和真实 E2E 决定。RC4 还定义
一个受控 Windows 测试 profile：**Windows 10/11 + Git for Windows/Git Bash + Python
3.10+ + 有效的 `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`**。Windows 通过必须使用这个准确
profile，并且在真机完整跑完本清单前仍只是候选证据。Native PowerShell hooks 不受支持，
WSL 尚未验证，二者都不能计为受支持的 Windows 结果。

## 0. Read-only preflight and Windows profile / 只读预检与 Windows 配置

Run the branch matching the named target surface from the exact source tree before
installation.

### CLI route / CLI 路径

On macOS/Linux:

```bash
python3 scripts/preflight.py --surface claude-code-cli --json
```

On Windows, open **Git for Windows/Git Bash**, not native PowerShell or WSL. Ensure
Python 3.10+ is available as `python3`, `python`, or `py -3`; set the effective Claude
Code environment value before launching Claude Code, then run:

```bash
export CLAUDE_CODE_USE_POWERSHELL_TOOL=0
py -3 scripts/preflight.py --surface claude-code-cli --json
```

If Claude Code requires an explicit Git Bash location, configure
`CLAUDE_CODE_GIT_BASH_PATH` to the existing Git for Windows `bash.exe` path before
running preflight. Do not record that private path in the shared test result.

Expected / 预期：the explicit CLI route reports `READY_FOR_AUTOMATED_INSTALL`,
`read_only=true`, and Python, Git, Claude Code, plus `claude_plugin_cli` checks pass.
The Windows profile additionally reports Git Bash ready and
`powershell_tool_disabled.ok=true`; `plugin_trust_contract.ok` must be true.

### Desktop Code Local/SSH route / Desktop Code Local/SSH 路径

Run one exact command from the tagged checkout, using Python on the Local machine or
SSH host respectively:

```bash
python3 scripts/preflight.py --surface desktop-code-local --json
python3 scripts/preflight.py --surface desktop-code-ssh --json
```

Run only the command matching the test record. Without a standalone CLI it must report
`MANUAL_INSTALL_PLAN_AVAILABLE`, and its actions must require verification that the
exact target app is Claude Code `2.1.195+`. Record the app version manually; an unknown
version is **BLOCKED**, not an inferred pass. If official Cloud or OS-level WSL evidence
contradicts the chosen surface, expect `SURFACE_SIGNAL_CONFLICT` and stop.

For either branch, record only status, versions, and reason codes. Preflight must not
install, edit settings, initialize a project, or infer the account/model behind the
runtime route. A ready/manual route is not an E2E pass. / 两条路径都只记录 status、版本与
reason codes；preflight 不得安装、改设置、初始化项目或推断账号/模型。Ready 或 manual
路径都不等于 E2E 通过。

安装前必须从准确源码树运行 preflight。Windows 必须打开 **Git for Windows/Git Bash**，
不得使用 native PowerShell 或 WSL；Python 3.10+ 可以通过 `python3`、`python` 或 `py -3`
提供。Claude Code 启动前令有效环境值为 `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`。如果必须
显式指定 Git Bash，则把 `CLAUDE_CODE_GIT_BASH_PATH` 配置为实际存在的 Git for Windows
`bash.exe`，但不要在共享结果中记录该私有路径。Desktop Local/SSH 只运行与记录表一致的
显式 surface 命令；没有独立 CLI 时必须得到 manual plan，并人工核对准确 app 为
`2.1.195+`。

## 1. Create a disposable project / 创建可丢弃项目

```bash
export E2E_ROOT="$(mktemp -d)"
export ACGM_DATA_DIR="$E2E_ROOT/acgm-data"
mkdir -p "$E2E_ROOT/project/acgm-e2e-delete-me"
cd "$E2E_ROOT/project"
git init -b main
printf '%s\n' '# ACGM E2E disposable project' >README.md
printf '%s\n' '.claude/settings.local.json' >.gitignore
printf '%s\n' 'disposable sentinel' >acgm-e2e-delete-me/sentinel.txt
git add .gitignore README.md acgm-e2e-delete-me/sentinel.txt
git commit -m "test: initialize disposable ACGM E2E project"
python3 -c 'import json, os, pathlib; p=pathlib.Path(".claude/settings.local.json"); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({"env": {"ACGM_DATA_DIR": str(pathlib.Path(os.environ["E2E_ROOT"]) / "acgm-data")}}, indent=2) + "\n", encoding="utf-8")'
```

On Windows Git Bash, `py -3` may replace `python3`. The ignored local settings file
passes the isolated data directory into Desktop Code, whose GUI launch does not
inherit arbitrary shell exports. Inspect it locally but do not copy its private path
into the shared result. / Windows Git Bash 可把 `python3` 换成 `py -3`。这个 ignored
local settings 文件把隔离数据目录传给 Desktop Code；GUI 启动不会继承任意 shell export。
只在本机检查，不把私有路径复制到共享结果。

Expected / 预期：a clean repository on `main`; the only deletion target exists and is
tracked. Print and inspect the exact path before continuing:

```bash
pwd
git status --short --branch
find acgm-e2e-delete-me -maxdepth 2 -type f -print
```

## 2. Install on the named target surface / 在已命名目标 surface 安装

The `v0.3.0-rc.4` GitHub route is valid only after the tag exists. Before publication,
use the reviewed branch/commit and mark the GitHub-tag path **BLOCKED**. Never use a
GitHub source archive or release tarball with `install.py`; they lack the required Git
revision/index proof. / GitHub 路径只有 tag 存在后才有效；发布前使用已审查 branch/commit，
并把 GitHub tag 路径记为 **BLOCKED**。不得把 GitHub 源码压缩包或 release tarball 交给
`install.py`，它们缺少所需 Git revision/index 证据。

### 2A. CLI automated route / CLI 自动路径

Clone the tag into a source directory separate from the disposable target project:

```bash
git clone --single-branch --branch v0.3.0-rc.4 --depth 1 \
  https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology.git \
  "$E2E_ROOT/acgm-source"
cd "$E2E_ROOT/acgm-source"
python3 scripts/install.py --surface claude-code-cli --dry-run --json
python3 scripts/install.py --surface claude-code-cli --json
```

Before the tag exists, substitute only the exact reviewed branch and record its commit.
On Windows Git Bash, use `py -3`. Dry-run must report
`SOURCE_VERIFIED_AUTOMATED_INSTALL_READY`; first install must report
`CONFIGURATION_VERIFIED_NEW`; an exact rerun must report
`CONFIGURATION_VERIFIED_EXISTING`. Source-only and configuration results must keep
`ready_for_use=false`; source-only `ok=false`, while verified configuration may set
`ok=true` but still cannot claim activation. / Tag 尚未存在时只能替换为准确已审查分支并记录
commit；Windows Git Bash 使用 `py -3`。源码和配置结果都必须保持
`ready_for_use=false`，源码阶段 `ok=false`，配置核验通过可以 `ok=true`，但不能宣称激活。

Return to the actual disposable target before launching Claude Code:

```bash
cd "$E2E_ROOT/project"
claude
```

### 2B. Desktop Code Local/SSH UI route / Desktop Code Local/SSH UI 路径

1. Open the exact tagged checkout in the recorded Desktop Code Local or SSH surface;
   on SSH, source, Python, Git, plugin cache, and hooks must all live on the SSH host.
2. Run the matching read-only preflight from §0. Confirm app version `2.1.195+`.
3. Review `.claude/settings.json`, then let the human personally accept the workspace,
   marketplace, and plugin install/trust prompts. Record which prompts appeared and the
   installed scope. The Agent must not click consent.
4. A project-scope install proves only the ACGM source checkout. To test governance in
   the separate disposable project below, explicitly choose user scope after obtaining
   user-wide install authorization, then open `$E2E_ROOT/project` in the **same** Local
   or SSH surface. Do not infer that Chat, Cowork, CLI, Local, and SSH share activation.

1. 在记录的 Desktop Code Local 或 SSH surface 打开准确 tag；SSH 的源码、Python、Git、
   plugin cache 与 hooks 必须都位于 SSH host。
2. 运行 §0 对应只读 preflight，并确认 app 为 `2.1.195+`。
3. 审查 `.claude/settings.json`，由人亲自接受 workspace、marketplace、plugin 的安装/信任
   提示；记录提示与 scope，Agent 不得代点同意。
4. Project scope 只能证明 ACGM 源码项目。若要在独立可丢弃项目验收，必须另获 user-wide
   安装授权并选择 user scope，再在**同一个** Local/SSH surface 打开 `$E2E_ROOT/project`。

### 2C. Same-surface activation observation / 同 surface 激活观察

Before reload, record the current doctor SessionStart timestamp when `acgm` is already
available; otherwise record `unavailable`. For the CLI branch, the newly created
`ACGM_DATA_DIR` is also the empty baseline. Then reload/restart plugins, close the task,
and open one fresh disposable-project task on the same named surface:

```text
/reload-plugins
/hooks
/skills
```

重载前，如果 `acgm` 已可用则记录当前 doctor SessionStart 时间，否则记录
`unavailable`；CLI 路径中新建的 `ACGM_DATA_DIR` 同时构成空基线。随后 reload/restart，
关闭任务，并在同一个已命名 surface 新开可丢弃项目任务。不得用 CLI 结果代替 Desktop
验收，反之亦然。

Through Bash launched by this plugin-enabled Claude Code session, run:

```bash
command -v acgm
acgm version
acgm doctor --json
```

Expected / 预期：version is exactly `0.3.0-rc.4`; `/hooks` lists ACGM's lifecycle
hooks; `/skills` lists the ACGM skills; doctor reports
`activation.historical_observation_only=true` and
`activation.sufficient_for_active_verified=false`. If a current-project SessionStart
timestamp appears, it must be newer than any recorded timestamp baseline (or be the
first event in the empty isolated ledger), but remains corroboration rather than
surface identity proof. The new project is
`INSTALLED_NOT_BOOTSTRAPPED`, not falsely reported as governed. `ACTIVE_VERIFIED` is
recorded only after the same named surface also passes the controlled hook probes later
in this checklist.
If `command -v acgm` fails inside plugin-enabled Claude Code Bash, mark this step
**FAIL**; do not substitute a hidden cache path and call the installation flow
successful. An ordinary login shell is outside this PATH guarantee; a repository
clone may use `./bin/acgm`. / 若插件已启用的 Claude Code Bash 内 `command -v acgm`
失败，本项必须记 **FAIL**；不得改用隐藏缓存路径并把安装流程写成成功。普通 login shell
不在该 PATH 保证内；仓库 clone 可使用 `./bin/acgm`。

Unless a step explicitly says “login shell,” run subsequent `acgm ...` checks through
plugin-enabled Claude Code Bash so CLI and hooks inherit the same isolated
`ACGM_DATA_DIR`. / 除非步骤明确写“login shell”，后续 `acgm ...` 检查都通过插件已启用的
Claude Code Bash 运行，让 CLI 与 hooks 继承同一隔离 `ACGM_DATA_DIR`。

## 3. Initialize without overwriting / 初始化且不覆盖

Use `acgm init` on every platform. Its scaffold path is implemented in Python and is
the Windows initialization path. Do not substitute the POSIX-only
`scripts/governance-init.sh` fallback for a Windows plugin-lifecycle result. /
所有平台都使用 `acgm init`；它的脚手架路径由 Python 实现，也是 Windows 初始化主路径。
不得用仅限 POSIX 的 `scripts/governance-init.sh` fallback 替代 Windows 插件生命周期结果。

First verify that an invalid explicit path fails instead of falling back to the current
repository:

```bash
acgm init "$E2E_ROOT/does-not-exist"
test ! -e CONSTITUTION.md
```

Expected / 预期：`acgm init` returns non-zero, names the invalid path, and creates
nothing in the current repository.

Now initialize the intended project:

```bash
acgm init .
git status --short
acgm doctor --strict
```

Expected / 预期：`CONSTITUTION.md`, `CLAUDE.md`, and `AGENTS.md` are created; project
state is `PARTIALLY_GOVERNED`; strict doctor may return non-zero because human-owned
components are intentionally incomplete.

Prove idempotence:

```bash
git hash-object CONSTITUTION.md CLAUDE.md AGENTS.md
acgm init .
git hash-object CONSTITUTION.md CLAUDE.md AGENTS.md
```

Expected / 预期：both hash sets match; existing files are skipped, not overwritten.

Commit the generated baseline in this disposable repository so later restore checks
are exact:

```bash
git add CONSTITUTION.md CLAUDE.md AGENTS.md
git commit -m "test: record ACGM scaffold baseline"
```

## 4. SessionStart lifecycle / SessionStart 生命周期

Start a new session, then exercise the supported context transitions:

```text
/reload-plugins
/compact
/clear
```

Also close and resume one disposable-project session using the normal Claude Code
resume flow.

Start one session from a nested directory inside the disposable repository and verify
that the displayed actual root is the Git root, not the nested cwd:

```bash
mkdir -p nested/e2e
cd nested/e2e
claude
```

After closing that nested-cwd session, return to the disposable root:

```bash
cd "$E2E_ROOT/project"
```

Expected / 预期：

- startup reports ACGM version and current project state;
- compact/resume says inherited technical references are history and require current
  re-verification;
- clear asks to rebuild grounding from current repository truth;
- SessionStart shows the resolved actual project root so the human can catch a wrong
  cwd; the Event Ledger does not persist that path or any model/provider identity. /
  SessionStart 显示解析后的实际项目根，供人发现错 cwd；Event Ledger 不持久化该路径或
  任何模型/服务商身份。

## 5. Namespaced skills / 完整命名空间 Skills

Invoke each exact name and confirm it resolves to this plugin:

```text
/agent-coding-governance-methodology:session-grounding
/agent-coding-governance-methodology:truth-first
/agent-coding-governance-methodology:governance-bootstrap
```

Expected / 预期：skills are available but do not claim to be deterministic hooks;
grounding waits for human confirmation before edits; bootstrap stays human-driven.

## 6. Constitution ownership gate / Constitution 权属门

First ask the Agent to inspect `CONSTITUTION.md` with a clearly read-only Bash command,
such as `sed -n '1,5p' CONSTITUTION.md`. Expected: it is allowed.

Then ask the Agent to append a test sentence using its Edit/Write tool. Also test a
potentially mutating Bash path against the same file, but do not bypass the hook:

```bash
printf '%s\n' 'agent must not add this' >>CONSTITUTION.md
```

Do not edit the Constitution yourself for this step.

Expected / 预期：明确只读 Bash 可以读取；PreToolUse 拒绝 Edit/Write 和可能写入的 Bash，
并说明 Constitution 归人所有。`git diff -- CONSTITUTION.md` 不含 Agent 新增文本；hook
本身也不得追加 marker comment。

## 7. High-risk gate: missing evidence / 高风险门：缺少证据

Confirm the disposable target still exists:

```bash
find acgm-e2e-delete-me -maxdepth 2 -type f -print
```

In Claude Code, ask the Agent to attempt the following exact command for the E2E test,
without preceding it with ACGM gate fields and without bypassing the hook:

```bash
rm -rf ./acgm-e2e-delete-me
```

Expected / 预期：PreToolUse returns `deny` before the human permission stage, names all
four required fields, and the directory still exists.

Also attempt this harmless compound form against a path that was never created:

```bash
rm -rf ./acgm-e2e-never-create; true
```

Expected / 预期：ACGM denies the compound high-risk command and requires source check,
state change, and verification to remain separate tool calls.

## 8. Complete gate and human authority / 完整门与人的权限

Ask the Agent to run a current read-only source check first:

```bash
ls -la ./acgm-e2e-delete-me
```

Then require its immediately preceding reply to contain all four exact fields:

```text
ACGM-EVIDENCE: <the current ls evidence and exact disposable target>
ACGM-CURRENT-STATE: <the target exists now and contains the sentinel>
ACGM-VERIFY-AFTER: <test ! -e ./acgm-e2e-delete-me>
ACGM-ROLLBACK: <git restore --source=HEAD -- ./acgm-e2e-delete-me>
```

Have it retry:

```bash
rm -rf ./acgm-e2e-delete-me
```

At the first permission prompt choose **deny**.

Expected / 预期：ACGM changes from evidence denial to human `ask`; denying leaves the
target intact. A complete template never auto-authorizes the command.

Repeat the current source check and four fields. On the second human prompt, approve
only after verifying the exact disposable path.

Expected / 预期：the command executes and PostToolUse reports an open post-action
verification obligation.

## 9. Stop and post-action verification / Stop 与后验验证

Before running the declared verification, ask the Agent to finish the turn.

Expected / 预期：Stop blocks a quiet end and requests the declared
`ACGM-VERIFY-AFTER` check. It does not invent a different check.

Now run the declared check through Claude Code:

```bash
test ! -e ./acgm-e2e-delete-me
```

Expected / 预期：PostToolUse resolves the matching obligation. The next Stop allows the
turn to finish.

Restore the disposable fixture for later inspection:

```bash
git restore --source=HEAD -- ./acgm-e2e-delete-me
```

## 10. Governance-write advisory / 治理写入提醒

Ask the Agent to add an explicitly disposable, unsourced technical claim to
`CLAUDE.md`, then inspect the diff.

Expected / 预期：PostToolUse asks for source review, records an intervention, and does
not add or rewrite text beyond the Agent's requested edit. Revert the test edit after
inspection:

```bash
git restore -- CLAUDE.md
```

## 11. Event Ledger and privacy / Event Ledger 与隐私

```bash
acgm report --project current --limit 50
acgm report --project current --json
find "$ACGM_DATA_DIR" -maxdepth 3 -type f -print
```

Expected / 预期：the report includes health, intervention, and verification lifecycle
events with opaque project/session IDs. Activity counts are not labeled as “wins.”
The hooks and shell CLI must resolve the same ledger. If interventions were observed
but `acgm report` is empty, mark **FAIL** instead of searching a hidden plugin-cache
path. / hooks 与 shell CLI 必须解析到同一 Ledger；若已观察到干预但 report 为空，记
**FAIL**，不得靠寻找隐藏插件缓存路径掩盖问题。

Inspect source-minimization. This command must produce no match:

```bash
grep -R -E 'acgm-e2e-delete-me|disposable sentinel|rm -rf|ACGM-EVIDENCE:' "$ACGM_DATA_DIR"
```

Also inspect `events.jsonl` manually. It must not contain raw paths, file names,
commands, prompts, transcript content, model/provider names, remote URLs,
infrastructure identifiers, or credentials. The local Event Ledger does not
automatically upload anything. / 事件日志仅存本机，不自动上传。

## 12. Export and resolve / 导出与分类

Copy one `evt_...` ID from the JSON report:

```bash
acgm export-case evt_EXAMPLE -o "$E2E_ROOT/acgm-case-preview.md"
acgm resolve evt_EXAMPLE --status false_positive
acgm report --project current --json
```

Expected / 预期：export creates a local preview naming the project only as `Project-A`,
warns that nothing was uploaded, and requires manual review. Resolve appends a
classification event rather than rewriting old ledger history.

## 13. Upgrade, migration, and reload / 升级、迁移与重载

### 13A. RC3 verified snapshot to RC4 / RC3 已核验 snapshot 升级 RC4

Use a disposable test profile with no other ACGM install. Install the prior RC3
`verified_snapshot_user` package from exact reviewed commit `aa792ea`, open one ACGM
Claude Code session, and create a disposable Ledger event. Keep that session open for
the first probe, then run from the clean RC4 checkout:
/ 使用没有其他 ACGM 安装的一次性测试 profile，从准确已审查 commit `aa792ea` 安装旧
RC3 `verified_snapshot_user`，打开一个 ACGM Claude Code session 并创建可丢弃 Ledger
事件。第一次探测时保持 session 打开，再从 RC4 clean checkout 运行：

```bash
python3 scripts/install.py --surface claude-code-cli \
  --upgrade-verified-snapshot --dry-run --json
```

Expected / 预期：the active cache returns `VERIFIED_UPGRADE_PLUGIN_IN_USE`; no plugin,
marketplace, snapshot, settings, or Ledger bytes change. Close **every** Claude Code
and Desktop Code session using ACGM, confirm no active cache remains, and run:
/ 正在使用的 cache 必须返回 `VERIFIED_UPGRADE_PLUGIN_IN_USE`，且 plugin、marketplace、
snapshot、settings 与 Ledger 字节均不变化。关闭**全部**使用 ACGM 的 Claude Code 与
Desktop Code session，确认没有 active cache 后运行：

```bash
python3 scripts/install.py --surface claude-code-cli \
  --upgrade-verified-snapshot --dry-run --json
python3 scripts/install.py --surface claude-code-cli \
  --upgrade-verified-snapshot --json
```

The first result must be `VERIFIED_UPGRADE_READY` with no mutation. It may run
read-only Claude version/help/list probes. The real transaction must report
`CONFIGURATION_VERIFIED_UPGRADED`, prove a unique user-scope older snapshot, scoped
remove plus `uninstall --keep-data` capabilities, verified private data backup,
strictly-forward version, exact new cache, restored/retained Ledger bytes, and verified
backup cleanup. It must not modify the disposable project's governance files.
/ 第一次必须返回 `VERIFIED_UPGRADE_READY` 且不变更状态；它可以运行 Claude 的只读
version/help/list 探针。真实事务必须返回 `CONFIGURATION_VERIFIED_UPGRADED`，并证明唯一
user-scope 旧 snapshot、带 scope 的 remove 与 `uninstall --keep-data` 能力、已核验私有
数据备份、严格向前版本、准确新 cache、Ledger 字节已恢复/保留，以及备份清理通过；不得
修改可丢弃项目的治理文件。

Record the automated rollback tests for: failure before old removal, failure after old
removal, data changing concurrently, restore failure, and backup-cleanup failure. Each
known failure must end in a fully verified old state; an unprovable state must be
`VERIFIED_UPGRADE_PARTIAL_STATE_REQUIRES_MANUAL_REPAIR` with an opaque retained-backup
token, never success. A cleanup failure must reverify the residual artifact:
`retained_backup_verified=true` only for a complete byte-exact backup, while a partial
artifact keeps that field false and cannot be called recoverable. Do not inject
destructive failures into a valuable profile.
/ 记录自动回滚测试证据：旧状态移除前失败、移除后失败、数据并发变化、恢复失败、备份清理
失败。状态明确的失败必须完整回到已核验旧状态；无法证明时必须返回
`VERIFIED_UPGRADE_PARTIAL_STATE_REQUIRES_MANUAL_REPAIR` 与不透明 backup token，绝不能
成功。cleanup 失败必须重验残留 artifact；只有完整且字节准确时
`retained_backup_verified=true`，部分残留必须保持 false，不能称为可恢复 backup。不要在
有价值的 profile 中注入破坏性失败。

Reopen the exact named target surface and run:
/ 重新打开准确目标 surface 并运行：

```text
/reload-plugins
/hooks
/skills
```

```bash
acgm version
acgm doctor --json
acgm report --project current --limit 5
```

Expected / 预期：running version is `0.3.0-rc.4`; the controlled hook fires in this same
surface; existing project files are unchanged; the pre-upgrade Ledger event remains
readable. Configuration success alone is not `ACTIVE_VERIFIED`.

### 13B. Legacy public GitHub migration diagnosis / 旧公开 GitHub 迁移诊断

In a separate disposable profile, reproduce one unique user-scope public GitHub
installation shaped like published `0.1.0` or `v0.3.0-rc.1`. Run the RC4 installer
without and with `--upgrade-verified-snapshot`. Both must remain read-only and return
`LEGACY_PUBLIC_GITHUB_INSTALL_REQUIRES_EXPLICIT_MIGRATION` plus `legacy_detection`;
the result must set `publisher_authenticity_proven=false` and
`installed_content_verified=false`. Repo/ref/version/scope are clues, not proof.
/ 在另一一次性 profile 中重现唯一 user-scope、形态类似已发布 `0.1.0` 或
`v0.3.0-rc.1` 的公开 GitHub 安装。分别不带及带 `--upgrade-verified-snapshot` 运行 RC4
安装器；两者都必须保持只读并返回
`LEGACY_PUBLIC_GITHUB_INSTALL_REQUIRES_EXPLICIT_MIGRATION` 与 `legacy_detection`，且
`publisher_authenticity_proven=false`、`installed_content_verified=false`。repo/ref/
version/scope 只是线索，不是证明。

Close all sessions **before** taking the baseline, then use the RC4 runtime from the
checkout to capture every sanitized event rather than the default recent 20. Privately
record the exact stdout SHA-256 and event count. On Windows Git Bash use `py -3`:
/ 必须先关闭全部 session，**再**取 baseline；从 checkout 使用 RC4 runtime 捕获全部脱敏
事件，不能只用默认最近 20 条。私下记录准确 stdout SHA-256 与 event count；Windows Git
Bash 使用 `py -3`：

```bash
python3 scripts/acgm_runtime.py report --project all \
  --limit 9223372036854775807 --json
```

After separate human authorization, run the exact **user-scope only** uninstall:
/ 获得另一次人工授权后，执行准确的**仅 user-scope**卸载：

```bash
claude plugin uninstall \
  agent-coding-governance-methodology@agent-coding-governance-methodology \
  --scope user --keep-data
```

Run `claude plugin list --json` and repeat the exact RC4 report command. The exact
plugin ID must be absent, and the after-report stdout SHA-256 plus event count must equal
the private baseline. Only after both pass may a separately authorized command remove
the marketplace:
/ 运行 `claude plugin list --json` 并重复准确 RC4 report 命令。准确 plugin ID 必须消失，
after-report stdout SHA-256 与 event count 必须等于私下 baseline。两者都通过后，才可另行
授权移除 marketplace：

```bash
claude plugin marketplace remove agent-coding-governance-methodology --scope user
```

Install exactly one RC4 shape, reload, and repeat the same-surface activation and
retained-data checks. Confirm `manual_migration_plan.automatic_execution_allowed=false`
and its verification gate sits between uninstall and marketplace removal. Repeat the
diagnosis with duplicate, different-scope/source/version, and ambiguous fixtures; each
must stop without proposing automatic mutation. / 随后只安装一种 RC4 形态，reload，并重做
同 surface 激活与保留数据核验。确认
`manual_migration_plan.automatic_execution_allowed=false`，且 verification gate 位于
uninstall 与 marketplace remove 之间。再以重复、不同 scope/source/version 与含糊
fixture 复跑；每一种都必须停止，且不得提出自动变更。

## 14. Uninstall with retained data / 卸载并保留数据

The earlier privacy steps deliberately used an external `ACGM_DATA_DIR`; that alone
cannot prove Claude's plugin-managed `--keep-data` lifecycle. Close the active Claude
session, unset the override in the login shell, and start one new disposable-project
session so SessionStart writes a health event to the official plugin-data directory:

```bash
unset ACGM_DATA_DIR
cd "$E2E_ROOT/project"
claude
```

Inside plugin-enabled Claude Code Bash, run `acgm report --project current --json` and
confirm the official store contains that health event. Then uninstall:

```bash
claude plugin uninstall agent-coding-governance-methodology@agent-coding-governance-methodology --scope user --keep-data
```

Expected / 预期：plugin is removed; `CONSTITUTION.md`, `CLAUDE.md`, `AGENTS.md`, and the
official plugin-managed Event Ledger remain. Reinstall and reload the plugin, then
confirm `acgm report --project current --json` can still read the retained health
event. / 前面的隐私测试使用外部 override，不能单独证明 `--keep-data`；本步骤必须在取消
override 后验证官方 plugin-data 中的事件仍可读取。

## Result matrix / 结果矩阵

| ID | Check / 检查 | Result | Evidence note / 证据说明 |
|---|---|---|---|
| E2E-00 | Preflight + exact platform profile | PASS / FAIL / BLOCKED | |
| E2E-01a | Source + configuration identity | PASS / FAIL / BLOCKED | |
| E2E-01b | Same-surface runtime activation | PASS / FAIL / BLOCKED | |
| E2E-02 | Init + idempotence | PASS / FAIL / BLOCKED | |
| E2E-03 | SessionStart transitions | PASS / FAIL / BLOCKED | |
| E2E-04 | Namespaced skills | PASS / FAIL / BLOCKED | |
| E2E-05 | Constitution deny | PASS / FAIL / BLOCKED | |
| E2E-06 | Missing-evidence deny | PASS / FAIL / BLOCKED | |
| E2E-07 | Complete gate → human ask | PASS / FAIL / BLOCKED | |
| E2E-08 | Stop + verification closure | PASS / FAIL / BLOCKED | |
| E2E-09 | Governance-write advisory | PASS / FAIL / BLOCKED | |
| E2E-10 | Ledger source-minimization | PASS / FAIL / BLOCKED | |
| E2E-11 | Export + append-only resolve | PASS / FAIL / BLOCKED | |
| E2E-12a | Verified snapshot upgrade + rollback evidence | PASS / FAIL / BLOCKED | |
| E2E-12b | Legacy public diagnosis + human migration | PASS / FAIL / BLOCKED | |
| E2E-13 | Uninstall `--keep-data` | PASS / FAIL / BLOCKED | |

## Stable-release decision / 稳定版裁定

- **PASS:** every applicable row passes on a genuine Claude route; no open P0/P1
  mechanism or privacy defect. A Windows support claim additionally requires a full
  pass on the exact controlled Windows Git Bash profile.
- **FAIL:** observed behavior contradicts the release contract. Record the exact
  desensitized symptom, fix it, issue a new RC, and rerun the checklist.
- **BLOCKED:** the environment could not exercise the behavior. Do not convert blocked
  into pass and do not promote stable.

- **PASS：** 在真实 Claude 路径上所有适用项目通过，且没有 P0/P1 机制或隐私缺陷；任何
  Windows 支持声明还必须有准确受控 Windows Git Bash profile 的完整通过。
- **FAIL：** 实际行为违反发布契约。记录准确的脱敏现象，修复、发布新 RC 并重跑。
- **BLOCKED：** 环境无法执行该项。不得把 blocked 写成 pass，也不得升级稳定版。

After recording results, remove the disposable root only after manually confirming
that `$E2E_ROOT` is the temporary directory created by this checklist.

记录结果后，必须人工确认 `$E2E_ROOT` 正是本清单创建的临时目录，才可以清理。
