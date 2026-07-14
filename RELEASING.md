# Releasing ACGM / ACGM 发布流程

This runbook keeps the Git release, plugin manifest, installed cache, and documented
behavior on the same version. Commands are shown once and apply to both languages.

本流程用于保证 Git 发布、插件 manifest、本地安装缓存和文档行为处于同一版本。命令只写
一份，中英文共用。

## 1. Release status / 发布状态

`0.3.0-rc.1` is a release candidate. It may be published as a GitHub prerelease for
real-Claude-Code testing, but it must not be promoted or described as stable until
`tests/manual/CLAUDE_CODE_E2E.md` passes on a working Claude account.

`0.3.0-rc.1` 是候选版，可以作为 GitHub prerelease 发布给真实 Claude Code 测试，但
`tests/manual/CLAUDE_CODE_E2E.md` 未在可用 Claude 账号上通过之前，不得升级或描述为稳定版。

## 2. Freeze scope / 冻结范围

- Confirm the release branch contains only reviewed ACGM V3 work.
- Preserve the plugin ID and repository slug.
- Never build a public release from a mutable local plugin cache.
- Do not include ignored planning notes, credentials, local settings, transcripts, or
  Event Ledger data.
- Confirm ACGM Recover remains outside this repository and release.
- Review every claim touched by the release against `EVIDENCE.md`; activity counts are
  not evidence of successful intervention.

- 确认发布分支只包含已审查的 ACGM V3 工作。
- 保持插件 ID 和仓库 slug 不变。
- 绝不从可变的本地插件缓存制作公开包。
- 不得包含 ignored 计划、凭据、本地设置、transcript 或 Event Ledger 数据。
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
the local runtime contract; it does not replace real Claude Code E2E.
Native Windows hook execution is outside this RC's validated platform matrix.

在干净工作树上运行无第三方依赖的回归测试与发布契约检查。CI 必须在 Linux 和 macOS 上
运行前两条命令。CI 通过只证明本地运行时契约，不能代替真实 Claude Code E2E。
Windows 原生 hook 执行不在本 RC 已验证的平台矩阵内。

## 5. Real Claude Code gate / 真实 Claude Code 门

Run every applicable step in:

```text
tests/manual/CLAUDE_CODE_E2E.md
```

Record Claude Code version, OS, ACGM version, installation source, date, tester, and
each result. Do not record account identifiers, API keys, prompts from real projects,
or infrastructure details. Any P0/P1 failure blocks stable release.

逐项记录 Claude Code 版本、OS、ACGM 版本、安装来源、日期、测试人和结果。不得记录账号
标识、API key、真实项目 prompt 或基础设施细节。任何 P0/P1 失败都会阻止稳定发布。

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

## 7. Commit and tag / 提交与标签

Only after review and human approval:

```bash
git add -- \
  .claude-plugin .github .gitignore \
  CASES.md CHANGELOG.md CONTRIBUTING.md EVIDENCE.md LICENSING.md \
  METHODOLOGY.en.md METHODOLOGY.md PACKAGE_MANIFEST.json \
  README.md RELEASING.md VERSION bin hooks scripts skills tests
git commit -m "feat: ACGM v0.3.0-rc.1 release candidate"
./scripts/build-release.sh
git tag -a v0.3.0-rc.1 -m "ACGM v0.3.0-rc.1"
git push origin HEAD
git push origin v0.3.0-rc.1
```

Create the RC as a prerelease, not a stable release:

```bash
gh release create v0.3.0-rc.1 \
  --prerelease \
  --title "ACGM v0.3.0-rc.1" \
  --notes-file CHANGELOG.md \
  dist/Agent-Coding-Governance-Methodology-0.3.0-rc.1.tar.gz \
  dist/Agent-Coding-Governance-Methodology-0.3.0-rc.1.tar.gz.sha256
```

These commands are a runbook, not authorization. The human reviews the exact diff,
commit, tag, and release before execution.

以上命令只是 runbook，不构成授权。执行前由人审查准确 diff、commit、tag 与 release。

## 8. Fresh install and upgrade smoke tests / 全新安装与升级冒烟

Test both a clean install and an update from the previously published plugin:

```bash
claude plugin marketplace add johnrucnapier-sketch/Agent-Coding-Governance-Methodology@v0.3.0-rc.1
claude plugin install agent-coding-governance-methodology@agent-coding-governance-methodology
claude plugin marketplace update agent-coding-governance-methodology
claude plugin update agent-coding-governance-methodology@agent-coding-governance-methodology
```

Reload inside Claude Code, then verify the running package:

```text
/reload-plugins
```

```bash
command -v acgm
acgm version
acgm doctor --strict
```

Run these commands through Bash launched by plugin-enabled Claude Code. The plugin
does not promise an `acgm` PATH entry in an ordinary login shell; a repository clone
uses `./bin/acgm`. Verify that hook events and `acgm report` resolve the same official
plugin-data directory.

这些命令通过插件已启用的 Claude Code Bash 运行。插件不承诺普通 login shell 具有
`acgm` PATH；仓库 clone 使用 `./bin/acgm`。同时确认 hook 事件与 `acgm report` 解析到
同一官方 plugin-data 目录。

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

- automated Linux and macOS checks pass;
- the real Claude Code E2E checklist passes;
- no open P0/P1 mechanism or privacy defect remains;
- README claims match observed behavior;
- version, tag, release, marketplace source, and installed package agree.

只有满足以下条件才升级到 `0.3.0`：

- Linux 与 macOS 自动检查全部通过；
- 真实 Claude Code E2E 清单通过；
- 没有未解决的 P0/P1 机制或隐私缺陷；
- README 声明与实际观察一致；
- version、tag、release、marketplace 来源和安装包完全一致。

If a release fails after publication, stop promotion, document the observed behavior
in CHANGELOG, issue a new version, and use uninstall with `--keep-data` when local
evidence must be preserved. Never replace different bits under an existing version.

发布后发现失败时，停止升级，在 CHANGELOG 记录实际行为，发布新版本；需要保留本地证据时
使用带 `--keep-data` 的卸载。绝不在已有版本号下替换成不同内容。
