# Releasing ACGM / ACGM 发布流程

This runbook keeps the Git release, plugin manifest, installed cache, and documented
behavior on the same version. Commands are shown once and apply to both languages.

本流程用于保证 Git 发布、插件 manifest、本地安装缓存和文档行为处于同一版本。命令只写
一份，中英文共用。

## 1. Release status / 发布状态

`0.3.0-rc.4` is a testing prerelease candidate. The source version does not imply
that its Git tag or GitHub prerelease exists; verify live GitHub state. It may be published as a GitHub
prerelease for real-Claude-Code testing only after this runbook and human review, and
it must not be promoted or described as stable until
`tests/manual/CLAUDE_CODE_E2E.md` passes on a working Claude account. The controlled
Windows profile has not yet completed real-machine E2E.

`0.3.0-rc.4` 是测试预发布候选版；源码版本号不代表对应 Git tag 或 GitHub
prerelease 已存在，必须核对实时 GitHub 状态。只有本流程和人工复核完成后，才可以将它作为 GitHub prerelease 发布
给真实 Claude Code 测试。在 `tests/manual/CLAUDE_CODE_E2E.md` 未在可用 Claude 账号上
通过之前，不得升级或描述为稳定版。受控 Windows profile 尚未完成真机 E2E。

## 2. Freeze scope / 冻结范围

- Confirm the release branch contains only reviewed ACGM V3 work.
- Preserve the plugin ID and repository slug.
- Never build a public release from a mutable local plugin cache.
- Do not include ignored planning notes, credentials, personal/local settings,
  transcripts, or Event Ledger data. The reviewed project onboarding bridge at
  `.claude/settings.json` is the only allowed `.claude/` file.
- Confirm ACGM Recover remains outside this repository and release.
- Review every claim touched by the release against `EVIDENCE.md`; activity counts are
  not evidence of successful intervention.

- 确认发布分支只包含已审查的 ACGM V3 工作。
- 保持插件 ID 和仓库 slug 不变。
- 绝不从可变的本地插件缓存制作公开包。
- 不得包含 ignored 计划、凭据、个人/本机设置、transcript 或 Event Ledger 数据；经过
  审查的 project onboarding bridge `.claude/settings.json` 是唯一允许的 `.claude/` 文件。
- 确认 ACGM Recover 仍在本仓和本次发布范围之外。
- 用 `EVIDENCE.md` 复审本次涉及的每条结论；活动次数不等于干预成功证据。

## 3. Version consistency / 版本一致性

For an RC, `VERSION`, `.claude-plugin/plugin.json`, README, and CHANGELOG must all say
the same prerelease version. For stable, change them together to `0.3.0` and add the
stable changelog entry; never reuse the RC version for different content.

候选版的 `VERSION`、`.claude-plugin/plugin.json`、README 和 CHANGELOG 必须使用同一个
预发布版本。稳定版要同时改成 `0.3.0` 并新增 changelog；不得用同一 RC 版本承载不同内容。

```bash
python3 scripts/generate-package-manifest.py
python3 scripts/release_check.py --require-package-manifest
```

## 4. Automated verification / 自动验证

Run the dependency-free regression suite and release-contract check on a clean tree:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/generate-package-manifest.py --check
python3 scripts/release_check.py --require-package-manifest
git diff --check
git status --short
```

CI must run the first two commands on both Linux and macOS. A green CI result validates
the local runtime contract. RC4 also adds a `windows-latest` regression job for the
controlled candidate profile: Windows 10/11 behavior through Git for Windows/Git Bash,
Python 3.10+, and `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`. CI does not replace real Claude
Code E2E. Native PowerShell hooks are unsupported, WSL is unverified, and neither may
be inferred from a green Windows job.

在干净工作树上运行无第三方依赖的回归测试与发布契约检查。CI 必须在 Linux 和 macOS 上
运行前两条命令。RC4 还为受控候选 profile 增加 `windows-latest` 回归 job：Windows
10/11 行为通过 Git for Windows/Git Bash、Python 3.10+ 和
`CLAUDE_CODE_USE_POWERSHELL_TOOL=0` 测试。CI 通过只证明本地运行时契约，不能代替真实
Claude Code E2E。Native PowerShell hooks 不受支持，WSL 尚未验证，也不能从绿色 Windows
job 推断二者已受支持。

Before installation testing, run the read-only preflight from the exact source tree:

```bash
python3 scripts/preflight.py --surface claude-code-cli --json
```

On the controlled Windows Git Bash profile, use an available Windows launcher if
needed:

```bash
py -3 scripts/preflight.py --surface claude-code-cli --json
```

The result must be `READY_FOR_AUTOMATED_INSTALL`, with both Claude Code and the plugin
management capability checks green. Record only the status and reason codes; the
preflight does not install, edit settings, initialize a project, or prove live E2E.

For RC4 installer testing, Windows must resolve `claude` to a directly executable
native `claude.exe`. A legacy `.cmd` or `.bat` launcher is a blocker. The installer
materializes verified package bytes under `~/.acgm/marketplace-snapshots/`, verifies
that snapshot before each Claude mutation, and verifies Claude's reported install cache
afterward. Claude plugin uninstall does not remove these ACGM snapshots; review them
separately and never delete them as an implicit side effect of uninstall testing.

安装测试前，从准确源码树运行只读 preflight。结果必须是
`READY_FOR_AUTOMATED_INSTALL`，且 Claude Code 与 plugin management 能力检查均为绿色；
只记录状态和 reason codes。Preflight 不安装、不改设置、不初始化项目，也不能证明真实
E2E 已通过。

RC4 的 Windows 安装测试必须把 `claude` 解析为可直接执行的原生 `claude.exe`；旧式
`.cmd` 或 `.bat` launcher 属于阻塞项。安装器把验证过的包字节写入
`~/.acgm/marketplace-snapshots/`，每次改变 Claude 状态前重新核验，并在安装后核对
Claude 报告的缓存。Claude 插件卸载不会删除这些 ACGM 快照；应单独审查，不能把删除
快照当成卸载测试的隐式副作用。

## 5. Real Claude Code gate / 真实 Claude Code 门

Run every applicable step in:

```text
tests/manual/CLAUDE_CODE_E2E.md
```

Record Claude Code version, OS, ACGM version, installation source, date, tester, and
each result. Do not record account identifiers, API keys, prompts from real projects,
or infrastructure details. Any P0/P1 failure blocks stable release.

For the Windows candidate run, record and enforce this exact profile: Windows 10/11,
Git for Windows/Git Bash, Python 3.10+, and effective
`CLAUDE_CODE_USE_POWERSHELL_TOOL=0`. Do not execute the checklist through native
PowerShell or WSL and call that a supported Windows result.

逐项记录 Claude Code 版本、OS、ACGM 版本、安装来源、日期、测试人和结果。不得记录账号
标识、API key、真实项目 prompt 或基础设施细节。任何 P0/P1 失败都会阻止稳定发布。

Windows 候选验收必须记录并执行准确 profile：Windows 10/11、Git for Windows/Git Bash、
Python 3.10+，以及有效的 `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`。不得通过 native
PowerShell 或 WSL 跑完后写成受支持的 Windows 结果。

## 6. Review the package / 检查发布包

Verify the committed package rather than the developer's installed cache:

```bash
git ls-files
git archive --format=tar HEAD >/tmp/acgm-release.tar
tar -tf /tmp/acgm-release.tar
```

Check that runtime files are executable, JSON files parse, documentation names the
actual hook set, and no ignored/local-only material appears in the archive.

检查运行文件可执行、JSON 可解析、文档写的是实际 hook 集合，并确认 archive 不含任何
ignored 或 local-only 材料。

## 7. Commit, merge the default branch, and tag
## 提交、合入默认分支并打标签

Only after review and human approval:

```bash
git add -- \
  .claude .claude-plugin .github .gitattributes .gitignore \
  AGENTS.md CASES.md CHANGELOG.md CLAUDE.md CONTRIBUTING.md EVIDENCE.md INSTALL.md LICENSING.md \
  METHODOLOGY.en.md METHODOLOGY.md PACKAGE_MANIFEST.json \
  README.md RELEASING.md VERSION bin hooks scripts skills tests
git commit -m "feat: ACGM v0.3.0-rc.4 testing candidate"
git push --set-upstream origin HEAD
gh pr create --base master --head codex/acgm-v3-rc4-self-install \
  --title "feat: ACGM v0.3.0-rc.4 self-install routing" \
  --body-file /path/to/reviewed-pr-body.md
gh pr checks --watch
gh pr merge --merge
git fetch origin master
test "$(git rev-parse 'HEAD^{tree}')" = "$(git rev-parse 'origin/master^{tree}')"
git switch master
git merge --ff-only origin/master
python3 scripts/release_check.py --require-package-manifest
./scripts/build-release.sh
git tag -a v0.3.0-rc.4 "$(git rev-parse HEAD)" -m "ACGM v0.3.0-rc.4"
git push origin v0.3.0-rc.4
```

Do not tag the feature-branch commit before the default branch is merged. The tree at
`origin/master` must exactly equal the reviewed RC4 tree, and the annotated tag must
point to that final default-branch commit. Finally verify the remote default branch,
tag, and release separately. This prevents a published tag from coexisting with an
old repository homepage/default branch.

不得在默认分支合入前给 feature-branch commit 打 tag。`origin/master` 的 tree 必须与已
审查 RC4 tree 完全一致，annotated tag 必须指向最终默认分支 commit。最后分别核验远程
默认分支、tag 与 release，避免已经发布 tag、但仓库首页/默认分支仍停留在旧版。

Create the RC as a prerelease, not a stable release:

```bash
gh release create v0.3.0-rc.4 \
  --prerelease \
  --title "ACGM v0.3.0-rc.4" \
  --notes-file CHANGELOG.md \
  dist/Agent-Coding-Governance-Methodology-0.3.0-rc.4.tar.gz \
  dist/Agent-Coding-Governance-Methodology-0.3.0-rc.4.tar.gz.sha256
```

The attached tarball and checksum are audit/reproducibility assets, not installer
inputs. Release notes must direct installers to `git clone --branch v0.3.0-rc.4`;
`install.py` requires Git revision/index evidence and must reject extracted archives.
/ 附加 tarball 与 checksum 是审计/可复现资产，不是安装器输入。Release notes 必须把安装者
引向 `git clone --branch v0.3.0-rc.4`；`install.py` 要求 Git revision/index 证据，并必须
拒绝解压后的 archive。

These commands are a runbook, not authorization. The human reviews the exact diff,
commit, tag, and release before execution. Until the tag command and push have
actually succeeded, documentation must continue to call RC4 unreleased and the
`#v0.3.0-rc.4` install source unavailable.

以上命令只是 runbook，不构成授权。执行前由人审查准确 diff、commit、tag 与 release。
在 tag 创建并成功推送之前，文档必须继续把 RC4 写成尚未发布，`#v0.3.0-rc.4` 安装源也
仍不可用。

## 8. Fresh install and upgrade smoke tests / 全新安装与升级冒烟

Test the two supported installation shapes separately; the project bridge is an entry
to the Desktop shape, not a third shape. A CLI fresh install must start from the clean
RC4 checkout and use the verified snapshot installer:

```bash
python3 scripts/preflight.py --surface claude-code-cli --json
python3 scripts/install.py --surface claude-code-cli --dry-run --json
python3 scripts/install.py --surface claude-code-cli --json
```

For Desktop Local/SSH, open the same pinned-tag checkout, accept the human trust/install
prompts, and verify the `github_tag_desktop_ui` shape in that exact target surface. Do
not use direct GitHub CLI commands as a third installation path.

Then test a real strictly-forward upgrade in a disposable profile: install the prior
RC3 `verified_snapshot_user` package from its exact reviewed commit, close every ACGM
Claude/Code session, switch to the clean RC4 checkout, and run:

```bash
python3 scripts/install.py --surface claude-code-cli \
  --upgrade-verified-snapshot --dry-run --json
python3 scripts/install.py --surface claude-code-cli \
  --upgrade-verified-snapshot --json
```

The dry-run may issue read-only Claude version/help/list probes but must not mutate
state. Record proof that the old snapshot was unique, user-scope, enabled, byte-exact,
unused, and older; that `uninstall --scope user --keep-data` and scoped marketplace
removal were available; that the private Event Ledger backup verified; and that the
new cache and retained data verified. Inject one controlled failure and prove either a
fully verified rollback or an explicit partial-state/manual-repair result—never a
false success.

分别测试两种受支持的安装形态；project bridge 是 Desktop 形态入口，不是第三种形态。CLI
全新安装从 RC4 clean checkout 使用 verified snapshot installer；Desktop Local/SSH 从
同一固定 tag 接受人工 trust/install 提示，并在准确目标 surface 核验
`github_tag_desktop_ui`。不得用直接 GitHub CLI 命令制造第三条安装路径。

再在一次性 profile 中安装准确已审查 commit 的 RC3 `verified_snapshot_user`，关闭所有
ACGM Claude/Code session，切到 RC4 clean checkout，先 dry-run 再带
`--upgrade-verified-snapshot` 执行。记录旧 snapshot 唯一、user-scope、启用、字节准确、
未在使用且版本较低，带 scope 的 `--keep-data` 与 marketplace remove 可用，私有 Ledger
备份通过，新 cache 与保留数据通过。还要注入一次受控失败，证明完整回滚或明确的部分
状态/人工修复结果，绝不能误报成功。

Reload inside Claude Code, then verify the running package:

```text
/reload-plugins
/hooks
/skills
```

```bash
command -v acgm
acgm version
acgm doctor --json
```

The install command proves configuration only. Doctor's retained current-version
SessionStart event is historical corroboration and always reports
`sufficient_for_active_verified=false`; it cannot prove which surface produced an old
event. Record `ACTIVE_VERIFIED` only after the named target surface passes the
same-surface `/hooks`, `/skills`, version, and controlled-hook checklist. Project
governance is a separate stage and may remain unbootstrapped.

安装命令只证明配置层。Doctor 保留的当前版本 SessionStart 事件始终是历史旁证，并返回
`sufficient_for_active_verified=false`；它不能证明旧事件来自哪个 surface。只有已命名目标
surface 通过同一 surface 的 `/hooks`、`/skills`、版本与受控 hook 清单后，才能记录
`ACTIVE_VERIFIED`。项目治理是独立阶段，可以继续保持未初始化。

The pinned Desktop marketplace declaration is valid only after `v0.3.0-rc.4` is
published. Before that, a local-source smoke test must record the exact commit and must
not be reported as a successful GitHub install.

Run these commands through Bash launched by plugin-enabled Claude Code. On Windows,
that means the controlled Git for Windows/Git Bash profile with
`CLAUDE_CODE_USE_POWERSHELL_TOOL=0`. The plugin
does not promise an `acgm` PATH entry in an ordinary login shell; a repository clone
uses `./bin/acgm`. Verify that hook events and `acgm report` resolve the same official
plugin-data directory.

固定 Desktop marketplace 声明只在 `v0.3.0-rc.4` 发布后有效。此前的本地源码冒烟必须
记录准确 commit，不得写成 GitHub 安装成功。命令通过插件已启用的 Claude Code Bash 运行；Windows
下必须是 `CLAUDE_CODE_USE_POWERSHELL_TOOL=0` 的受控 Git for Windows/Git Bash profile。
插件不承诺普通 login shell 具有 `acgm` PATH；仓库 clone 使用 `./bin/acgm`。同时确认
hook 事件与 `acgm report` 解析到同一官方 plugin-data 目录。

Separately exercise the legacy public `0.1.0` / `v0.3.0-rc.1` diagnosis. It must return
the explicit human-migration plan without mutation and state that repo/ref/version are
not publisher-authenticity or installed-byte proof. Only after human authorization,
follow [INSTALL.md](INSTALL.md): preserve data with exact user-scope `uninstall
--keep-data`, verify plugin absence and data retention, remove the exact user-scope
marketplace, install one chosen RC4 shape, and verify it in the same surface. Any
duplicate, different scope/source/version, or ambiguous state remains blocked.

另行验证旧公开 `0.1.0` / `v0.3.0-rc.1` 诊断：它必须不作变更地返回明确人工迁移计划，
并说明 repo/ref/version 不能证明发布者真实性或安装字节。只有人明确授权后，才按
[INSTALL.md](INSTALL.md) 用准确 user-scope `uninstall --keep-data` 保留数据，核验插件
消失与数据保留，移除准确 user-scope marketplace，安装唯一选定的 RC4 形态，并在同一
surface 验证。重复、不同 scope/source/version 或含糊状态均继续阻断。

The installed and running version must match the release. Doctor may report project
governance as partial; that is not a package failure. Do not auto-modify user project
files during upgrade.

安装版本和运行版本必须与发布版本一致。Doctor 可以报告项目治理不完整；这不等于包损坏。
升级期间不得自动修改用户项目文件。

## 9. Uninstall and data retention / 卸载与数据保留

Verify that users can remove the plugin while retaining its local audit data:

```bash
claude plugin uninstall agent-coding-governance-methodology@agent-coding-governance-methodology --keep-data
```

Confirm project governance files remain untouched. Reinstall, reload, and confirm the
retained Event Ledger is still readable. ACGM never automatically uploads ledger data.

确认项目治理文件保持不变；重新安装并 reload 后，保留的 Event Ledger 仍可读取。ACGM
绝不自动上传 Ledger 数据。

## 10. Stable promotion / 稳定版升级

Promote to `0.3.0` only when all of the following are true:

- automated Linux, macOS, and controlled `windows-latest` checks pass;
- the real Claude Code E2E checklist passes;
- any Windows support claim is backed by a full real-machine pass on the exact
  controlled Windows Git Bash profile;
- no open P0/P1 mechanism or privacy defect remains;
- README claims match observed behavior;
- version, tag, release, marketplace source, and installed package agree.

只有满足以下条件才升级到 `0.3.0`：

- Linux、macOS 与受控 `windows-latest` 自动检查全部通过；
- 真实 Claude Code E2E 清单通过；
- 任何 Windows 支持声明都有准确受控 Windows Git Bash profile 的完整真机通过作为证据；
- 没有未解决的 P0/P1 机制或隐私缺陷；
- README 声明与实际观察一致；
- version、tag、release、marketplace 来源和安装包完全一致。

If a release fails after publication, stop promotion, document the observed behavior
in CHANGELOG, issue a new version, and use uninstall with `--keep-data` when local
evidence must be preserved. Never replace different bits under an existing version.

发布后发现失败时，停止升级，在 CHANGELOG 记录实际行为，发布新版本；需要保留本地证据时
使用带 `--keep-data` 的卸载。绝不在已有版本号下替换成不同内容。
