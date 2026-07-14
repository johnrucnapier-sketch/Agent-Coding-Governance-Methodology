# ACGM Claude onboarding / Claude 入口

Follow [AGENTS.md](AGENTS.md) and [INSTALL.md](INSTALL.md). This file adds only
Claude-specific routing. / 先遵守 [AGENTS.md](AGENTS.md) 与 [INSTALL.md](INSTALL.md)；
本文件只补充 Claude 专用路由。

- A checked-out repository is not an installed plugin. Do not claim ACGM is active
  because these files are readable. / 能读取 clone 后的文件，不代表插件已经安装或激活。
- The repository-plugin install/trust contract documented by RC4 requires the exact
  target Claude Code app to be `2.1.195+`. An old, unreadable, or unknown version is not
  a pass. / RC4 所采用的 repository-plugin 安装与信任契约要求准确目标 Claude Code app
  为 `2.1.195+`；旧版、不可读或未知版本都不能算通过。
- `.claude/settings.json` declares the ACGM marketplace and plugin at project scope,
  pinned to `v0.3.0-rc.4`. It is an onboarding request, not pre-granted trust. Wait for
  the human to approve Claude Code's trust and install prompts. / `.claude/settings.json`
  在 project scope 声明固定到 `v0.3.0-rc.4` 的 marketplace 与插件；它不是预先授予的
  信任，必须等待用户接受 Claude Code 的信任与安装提示。
  This bridge does not prove a user-wide installation; use the Plugins UI and the
  user's explicitly authorized scope for that separate step. / 该 bridge 不证明已经完成
  user-wide 安装；如需全局使用，必须在 Plugins UI 中按用户明确授权的 scope 另行完成。
- Full ACGM is intended for Claude Code CLI and Desktop Code Local/SSH after hooks are
  verified. Desktop Chat is skill-only; Cowork is experimental until its command-hook
  runtime passes E2E; Desktop Code Remote/WSL cannot load this plugin. / 完整 ACGM 面向
  已验证 hooks 的 Claude Code CLI 与 Desktop Code Local/SSH；Desktop Chat 仅 skill；
  Cowork 在 command-hook 真机 E2E 前属于实验范围；Desktop Code Remote/WSL 不加载插件。
- Do not identify the real provider or model. `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`, a
  model label, or an Anthropic-compatible endpoint does not prove what model is behind
  the host. / 不识别或猜测真实 provider/模型；host-managed 信号、模型显示名称或
  Anthropic-compatible endpoint 都不能证明底层模型身份。
- After an explicitly authorized install, do not declare success until the plugin is
  installed and enabled, `/reload-plugins` has completed where available, and the
  running package plus hooks have been verified as described in `INSTALL.md`.
  明确授权安装后，也必须完成插件安装与启用、可用时执行 `/reload-plugins`，并按
  `INSTALL.md` 核验运行包与 hooks，才可报告成功。
- Never turn a legacy public-GitHub installation or an unknown conflict into a
  `--upgrade-verified-snapshot` candidate. Follow `INSTALL.md` and present the explicit
  human migration plan instead. / 不得把旧公开 GitHub 安装或未知冲突伪装成
  `--upgrade-verified-snapshot` 候选；应按 `INSTALL.md` 给出明确的人工迁移计划。
