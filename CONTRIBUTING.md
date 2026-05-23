# Contributing

Thanks for your interest. This is short and honest — please read it first.

**What this project is.** A shared *methodology*, packaged as a Claude Code plugin
(plus a plugin-free generic scaffold). It is **not** a heavily-maintained product.
Self-adaptation to your own project is the expected default; **no heavy support is
promised.**

**Issues / PRs are welcome**, with these expectations:

- Response may be slow or absent — that is the stated maintenance stance, not neglect.
- Keep the package **self-consistent with its own methodology**:
  - **Scope boundary (§④):** this repo stays zero-business — only generic, blank
    skeletons. PRs adding any concrete project's business / strategy / ops content,
    or project-specific specifics, will be declined.
  - **Truth-first (§5):** doc/claim changes must be accurate and sourced; no
    "should be / usually / I recall" hand-waving; do not over-promise mechanism
    behavior. A summary is never code-truth (Principle Three · corollary).
  - **Honest onboarding:** never describe a smoother install than reality; keep the
    "you'll know it worked when…" signals truthful.
- **Bilingual docs convention:** user-facing docs are a single file, **English first
  (complete) then Chinese (complete)** — not paragraph-interleaved. Keep both in
  sync. (`METHODOLOGY.md` / `METHODOLOGY.en.md` are the grandfathered split pair.)

**Good contributions:** clearer wording, translation fixes, portability of the
generic skeletons, honest corrections to claims, bug fixes in `scripts/`.

**Out of scope:** anything tying the repo to a specific product / company / private
context; "do my project's governance for me"; large framework-style additions.

## Evidence requirements for new normative content (the 2-independent-evidence rule)

New normative content (principles, corollaries, Meta-observations, hook
mechanisms) must be supported by **at least two independent supporting events** to
enter the main clause list. Evidence may be:

- **Observed events:** the same failure mode occurring in different sessions,
  different tasks, different times — transcript / log indexable.
- **Reasoned predictions:** failure forms inferable from known agent / tool
  behavior patterns — the reasoning must be stated.

**Clauses supported by only one observed event:** label them as **"advisory
clause · single direct event of support, pending second-evidence confirmation"** at
the top of the clause body; grace period **≤ 30 days**. If a second independent
event is not produced in that window, downgrade the clause to Meta-observations or
remove it.

**Predictive content with no observed event:** does not enter main clauses; goes
to the Meta-observations chapter as "predicted but not observed". Re-evaluate per
the 2-independent-evidence rule upon the first observation.

**This rule's purpose:** prevent the methodology from being shaped 1:1 by any
single incident. Incident-shaped content is a code smell; principle-shaped content
generalizes. Strong observed-event support is the only way through.

> This rule applies to ACGM itself: any future change to METHODOLOGY (new
> corollaries, Meta-observations, mechanism additions) must declare its evidence
> status under this rule explicitly. Past clauses are grandfathered.

## Contributing a drift case (zero-code path)

If the methodology caught a real drift in your work, a PR adding it to `CASES.md`
is welcome. Follow the structure of the existing cases:

- **Drift type:** one or a combination of ①②③④
- **Trigger:** which principle / hook / mechanism caught it
- **Situation:** what you were doing (abstract — no infra/product specifics)
- **The drift:** the specific wrong thing (abstract)
- **Correction:** how it was caught — key steps in order
- **Fix:** the root-cause minimal change (described, no real diff needed)
- **If uncaught:** the blast radius / impact

**Desensitization (required, non-negotiable):** replace internal project/product
names, code symbols, sensitive paths, model/infra names, version numbers, schema
hints, table/row counts with neutral placeholders. Keep only the *drift mechanism*.
Generic, well-known technical terms and code patterns may stay. A case that needs
its infrastructure fingerprint to make sense is too thin — leave it out.

**Licensing of contributions (inbound = outbound).** By contributing you agree your
contribution is licensed under this repo's dual-track terms: methodology/docs prose
under **CC-BY-4.0**, code / mechanical parts under **MIT** (see `LICENSING.md`).

---

# 贡献指南

感谢关注。这段很短,也很实在——请先读。

**这个项目是什么。** 一套可分享的*方法论*,打包成 Claude Code 插件(另附一个无需
插件的通用脚手架)。它**不是**重维护的产品。默认你自行按项目适配;**不承诺重度
支持。**

**欢迎 issue / PR**,但请有以下预期:

- 回复可能很慢或没有——这是写明的维护态度,不是怠慢。
- 保持包**与它自己的方法论自洽**:
  - **范围边界(§④):** 本仓零业务——只放通用空骨架。任何加入具体项目业务 /
    战略 / 经营内容或项目特定细节的 PR,会被婉拒。
  - **真值优先(§5):** 改文档/结论必须准确、带来源;不"应该是 / 通常 / 我记得"
    含糊;不夸大机制行为。摘要永不作为代码真值(第三原则·推论)。
  - **诚实上手:** 绝不把安装写得比现实更顺;"成功的样子"信号要属实。
- **双语文档约定:** 面向用户的文档是单文件、**英文完整在前,中文完整在后**——
  不逐段交错;两边保持同步。(`METHODOLOGY.md` / `METHODOLOGY.en.md` 是历史遗留
  的分文件对。)

**好的贡献:** 更清楚的措辞、翻译修正、通用骨架的可移植性、对结论的诚实更正、
`scripts/` 的 bug 修复。

**不在范围:** 把仓库绑到具体产品 / 公司 / 私有上下文;"替我做我项目的治理";
庞大的框架式新增。

## 新规范内容的证据要求(2-独立证据规则)

新规范内容(原则、推论、元观察、hook 机制)必须有**至少 2 个独立支撑事件**才能进入
主条款列表。证据可以是:

- **已观察事件:** 不同 session、不同任务、不同时间发生的同类失效——transcript / 日志可指。
- **合理预测事件:** 基于已知 agent / 工具行为模式可推断的失效形态——**推断依据必须明文**。

**只有 1 个已观察事件支撑的条款:** 在条款正文顶部标注 **"建议性条款 · 单次直接事件
支撑,待第二独立证据确认"**;**过渡期 ≤ 30 天**。若该窗口内未补到第二独立证据,降级
到元观察章节,或删除。

**无任何观察事件的预测性内容:** 不入主条款,进元观察章节作为"预测但未观察"。一旦
观察到首例,按 2-独立证据规则重新评估。

**本规则的目的:** 防止方法论被任一次事故 1:1 塑形。事故反推式(incident-shaped)
的条款是代码气味;原理推演式(principle-shaped)才能泛化。强观察证据支撑是唯一通路。

> 本规则适用于 ACGM 自身:METHODOLOGY 未来任何改动(新推论、元观察、机制新增)必须
> 在条款里明文声明本规则下的证据状态。历史条款 grandfathered(不溯及既往)。

## 贡献漂移案例(零代码门槛)

如果方法论在你的工作中抓到过真实漂移,欢迎 PR 加入 `CASES.md`。沿用现有案例结构:

- **漂移类型:** ①②③④ 之一或组合
- **触发点:** 哪条原则 / 哪个 hook / 哪个机制抓到的
- **情境:** 你当时在做什么(抽象——不带基础设施/产品细节)
- **漂移内容:** 具体的错(抽象)
- **纠错动作:** 怎么被抓出来——按时序列关键步骤
- **修复:** root-cause 最小改动(描述即可,不需真实 diff)
- **如果未拦截:** 后果范围 / 影响半径

**脱敏(必须,不可商量):** 把内部项目/产品名、代码符号、敏感路径、模型/基础设施
名、版本号、schema 提示、表数/行数,全部换成中性占位符。只留*漂移机制*。通用的、
公开熟知的技术名词与代码模式可保留。一个离开基础设施指纹就讲不通的案例 = 太薄,
不要收。

**贡献的许可(inbound = outbound)。** 提交贡献即表示同意按本仓双轨授权:方法论 /
文档散文 **CC-BY-4.0**,代码 / 机械件 **MIT**(见 `LICENSING.md`)。
