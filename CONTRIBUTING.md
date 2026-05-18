# Contributing

Thanks for your interest. This is short and honest — please read it first.

**What this project is.** A shared *methodology*, packaged as a Claude Code plugin +
a one-command scaffolder for Codex / any agent. It is **not** a heavily-maintained
product. Self-adaptation to your own project is the expected default; **no heavy
support is promised.**

**Issues / PRs are welcome**, with these expectations:

- Response may be slow or absent — that is the stated maintenance stance, not neglect.
- Keep the package **self-consistent with its own methodology**:
  - **Scope boundary (§④):** this repo stays zero-business — only generic, blank
    skeletons. PRs adding any concrete project's business / strategy / ops content,
    or project-specific specifics, will be declined.
  - **Truth-first (§5):** doc/claim changes must be accurate and sourced; no
    "should be / usually / I recall" hand-waving; do not over-promise mechanism
    behavior (only the CC hook auto-fires; skills are invoked; Codex auto-reads
    `AGENTS.md`).
  - **Honest onboarding:** never describe a smoother install than reality; keep the
    "you'll know it worked when…" signals truthful.
- **Bilingual docs convention:** user-facing docs are a single file, **English first
  (complete) then Chinese (complete)** — not paragraph-interleaved. Keep both in sync.

**Good contributions:** clearer wording, translation fixes, portability of the
generic skeletons, honest corrections to claims, bug fixes in `scripts/`.

**Out of scope:** anything tying the repo to a specific product / company / private
context; "do my project's governance for me"; large framework-style additions.

**Licensing of contributions (inbound = outbound).** By contributing you agree your
contribution is licensed under this repo's dual-track terms: methodology/docs prose
under **CC-BY-4.0**, code / mechanical parts under **MIT** (see `LICENSING.md`).

---

# 贡献指南

感谢关注。这段很短,也很实在——请先读。

**这个项目是什么。** 一套可分享的*方法论*,打包成 Claude Code 插件 + 给 Codex /
任意 agent 的一键脚手架。它**不是**重维护的产品。默认你自行按项目适配;**不承诺
重度支持。**

**欢迎 issue / PR**,但请有以下预期:

- 回复可能很慢或没有——这是写明的维护态度,不是怠慢。
- 保持包**与它自己的方法论自洽**:
  - **范围边界(§④):** 本仓零业务——只放通用空骨架。任何加入具体项目业务 /
    战略 / 经营内容或项目特定细节的 PR,会被婉拒。
  - **真值优先(§5):** 改文档/结论必须准确、带来源;不"应该是 / 通常 / 我记得"
    含糊;不夸大机制行为(只有 CC hook 自动点火;skill 是被调用的;Codex 自动读
    `AGENTS.md`)。
  - **诚实上手:** 绝不把安装写得比现实更顺;"成功的样子"信号要属实。
- **双语文档约定:** 面向用户的文档是单文件、**英文完整在前,中文完整在后**——
  不逐段交错;两边保持同步。

**好的贡献:** 更清楚的措辞、翻译修正、通用骨架的可移植性、对结论的诚实更正、
`scripts/` 的 bug 修复。

**不在范围:** 把仓库绑到具体产品 / 公司 / 私有上下文;"替我做我项目的治理";
庞大的框架式新增。

**贡献的许可(inbound = outbound)。** 提交贡献即表示同意按本仓双轨授权:方法论 /
文档散文 **CC-BY-4.0**,代码 / 机械件 **MIT**(见 `LICENSING.md`)。
