# Claude Code E2E acceptance / Claude Code 端到端验收

This checklist requires a working Claude Code account or official Claude API route.
It validates the real plugin lifecycle that unit tests cannot simulate. ACGM
`0.3.0-rc.1` must not be promoted to stable until this checklist passes.

本清单需要可用的 Claude Code 账号或官方 Claude API 路径，用于验证单元测试无法模拟的
真实插件生命周期。ACGM `0.3.0-rc.1` 未通过本清单之前不得升级为稳定版。

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
| Claude Code version (must be >= `2.1.143`) | |
| ACGM version | |
| Install source / 安装来源 | GitHub marketplace / local release candidate |
| Runtime route / 运行路径 | Claude account / official Claude API / compatible third-party endpoint / unknown |
| Python version (must be >= `3.10`) | |

Stable promotion requires at least one full pass on `Claude account` or
`official Claude API`. A compatible third-party endpoint may be recorded as an
additional compatibility observation, not substituted for that gate.
The current RC platform gate is macOS or Linux. A native Windows run is exploratory
until its hook execution path is separately validated.

稳定版至少需要一次 `Claude account` 或 `official Claude API` 的完整通过。第三方兼容
接口可以作为附加兼容性观察，但不能替代该门槛。
当前 RC 的平台门是 macOS 或 Linux；Windows 原生运行在 hook 执行路径被单独验证前只算
探索性结果。

## 1. Create a disposable project / 创建可丢弃项目

```bash
E2E_ROOT="$(mktemp -d)"
export ACGM_DATA_DIR="$E2E_ROOT/acgm-data"
mkdir -p "$E2E_ROOT/project/acgm-e2e-delete-me"
cd "$E2E_ROOT/project"
git init -b main
printf '%s\n' '# ACGM E2E disposable project' >README.md
printf '%s\n' 'disposable sentinel' >acgm-e2e-delete-me/sentinel.txt
git add README.md acgm-e2e-delete-me/sentinel.txt
git commit -m "test: initialize disposable ACGM E2E project"
```

Expected / 预期：a clean repository on `main`; the only deletion target exists and is
tracked. Print and inspect the exact path before continuing:

```bash
pwd
git status --short --branch
find acgm-e2e-delete-me -maxdepth 2 -type f -print
```

## 2. Install the release candidate / 安装候选版

Use the release source under test:

```bash
claude plugin marketplace add johnrucnapier-sketch/Agent-Coding-Governance-Methodology@v0.3.0-rc.1
claude plugin install agent-coding-governance-methodology@agent-coding-governance-methodology
```

Open Claude Code in the disposable project and reload plugins:

```bash
claude
```

```text
/reload-plugins
```

Through Bash launched by this plugin-enabled Claude Code session, run:

```bash
command -v acgm
acgm version
acgm doctor --json
```

Expected / 预期：version is exactly `0.3.0-rc.1`; package/runtime is healthy; the new
project is `INSTALLED_NOT_BOOTSTRAPPED`, not falsely reported as governed.
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
shasum CONSTITUTION.md CLAUDE.md AGENTS.md
acgm init .
shasum CONSTITUTION.md CLAUDE.md AGENTS.md
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

## 13. Upgrade and reload / 升级与重载

```bash
claude plugin marketplace update agent-coding-governance-methodology
claude plugin update agent-coding-governance-methodology@agent-coding-governance-methodology
```

Inside Claude Code:

```text
/reload-plugins
```

Then:

```bash
acgm version
acgm doctor --json
acgm report --project current --limit 5
```

Expected / 预期：installed and running versions agree; existing project files are not
auto-migrated or deleted; retained ledger events remain readable.

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
claude plugin uninstall agent-coding-governance-methodology@agent-coding-governance-methodology --keep-data
```

Expected / 预期：plugin is removed; `CONSTITUTION.md`, `CLAUDE.md`, `AGENTS.md`, and the
official plugin-managed Event Ledger remain. Reinstall and reload the plugin, then
confirm `acgm report --project current --json` can still read the retained health
event. / 前面的隐私测试使用外部 override，不能单独证明 `--keep-data`；本步骤必须在取消
override 后验证官方 plugin-data 中的事件仍可读取。

## Result matrix / 结果矩阵

| ID | Check / 检查 | Result | Evidence note / 证据说明 |
|---|---|---|---|
| E2E-01 | Install identity | PASS / FAIL / BLOCKED | |
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
| E2E-12 | Upgrade + reload | PASS / FAIL / BLOCKED | |
| E2E-13 | Uninstall `--keep-data` | PASS / FAIL / BLOCKED | |

## Stable-release decision / 稳定版裁定

- **PASS:** every applicable row passes on a genuine Claude route; no open P0/P1
  mechanism or privacy defect.
- **FAIL:** observed behavior contradicts the release contract. Record the exact
  desensitized symptom, fix it, issue a new RC, and rerun the checklist.
- **BLOCKED:** the environment could not exercise the behavior. Do not convert blocked
  into pass and do not promote stable.

- **PASS：** 在真实 Claude 路径上所有适用项目通过，且没有 P0/P1 机制或隐私缺陷。
- **FAIL：** 实际行为违反发布契约。记录准确的脱敏现象，修复、发布新 RC 并重跑。
- **BLOCKED：** 环境无法执行该项。不得把 blocked 写成 pass，也不得升级稳定版。

After recording results, remove the disposable root only after manually confirming
that `$E2E_ROOT` is the temporary directory created by this checklist.

记录结果后，必须人工确认 `$E2E_ROOT` 正是本清单创建的临时目录，才可以清理。
