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

## Evidence maturity for normative content

Every proposed principle, operational rule, Meta-observation, or hook mechanism
must have an entry in [`EVIDENCE.md`](EVIDENCE.md). Evidence matures by what has
actually been established, not by an arbitrary number of days or by counting
mentions:

- **Observed** — one traceable real occurrence. It establishes that the event
  happened, not that a general rule or mechanism is already justified.
- **Reproduced** — the same failure or mechanism has been produced again under
  documented conditions, with the causal path checked.
- **Corroborated** — independent observations or an observation plus a faithful
  reproduction support the same general claim. Stable normative rules and default
  blocking mechanisms require this level.
- **Predictive** — a reasoned, testable hypothesis with no direct observation yet.
  It may guide instrumentation or a Meta-observation, but not a default hard gate.
- **Rejected** — contradicted, misattributed, or too incident-shaped to retain as
  an active claim. Keep the evidence record so the mistake is not rediscovered.

Status applies to a **claim**, not to an entire case. A case may contain an
Observed weak form and a Predictive strong form. Hook activation, a skill name in a
transcript, or an agent citing a principle is not independent evidence that the
governance prevented anything; initiator, timing, outcome, and verification must be
established.

### Release gate

Before a stable release:

1. Every changed normative or mechanical claim is indexed in `EVIDENCE.md` with
   sources, limits, and its current maturity.
2. Stable rules and default blocking behavior are **Corroborated**. Observed or
   Reproduced trials may ship only in a prerelease, explicitly scoped and with a
   test/review decision recorded.
3. Predictive claims stay non-blocking and visibly labeled. Rejected claims are
   removed from active rules and mechanisms.
4. No unresolved trial silently crosses the release boundary: promote, keep it in
   a prerelease, merge it into an already-supported rule, or reject it.

This preserves the original purpose — prevent one incident from shaping the whole
methodology — without an unenforced "two events within 30 days" timer. Review is a
release decision backed by evidence, not a calendar ritual.

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

## 新规范内容的证据成熟度

任何拟新增的原则、操作规则、元观察或 hook 机制,都必须在
[`EVIDENCE.md`](EVIDENCE.md) 建立条目。证据按真正建立了什么来成熟,不按任意天数或
提及次数计算:

- **Observed(已观察)** —— 一次可追溯的真实事件。它只能证明事件发生过,不能直接证明
  一条通用规则或机制已经成立。
- **Reproduced(已复现)** —— 在有记录的条件下再次产生同类失效或机制行为,并核过因果链。
- **Corroborated(已佐证)** —— 独立观察,或一次观察加一次忠实复现,共同支持同一通用
  结论。稳定规范和默认阻断机制必须达到此级。
- **Predictive(预测性)** —— 有推理依据、可测试,但尚无直接观察。可指导埋点或元观察,
  不得直接成为默认硬门。
- **Rejected(已否决)** —— 被证据反驳、归因错误,或过度贴合单一事故。保留证据记录,
  但从活跃规则中移除,避免以后重犯。

状态属于一条**结论**,不是整个案例。一个案例可以同时包含 Observed 的弱形态和
Predictive 的强形态。Hook 触发、transcript 出现 skill 名、agent 引用某条原则,都不
等于治理真的阻止了问题;必须核清 initiator、发生在动作前还是后、结果和验证。

### Release gate(发布门)

稳定版发布前:

1. 本次改动涉及的每条规范或机械结论,都在 `EVIDENCE.md` 登记来源、限制和成熟度。
2. 稳定规则及默认阻断行为必须是 **Corroborated**。Observed / Reproduced 的试验只能
   进入预发布版,且必须明确范围、测试和复审决定。
3. Predictive 结论保持非阻断并显式标注;Rejected 结论退出活跃规则与机制。
4. 未决试验不得静默跨过发布边界:必须晋级、继续留在预发布版、并入已有成熟规则,
   或否决。

这样保留原规则的目的——防止一次事故把方法论 1:1 塑形——但不再依赖一个无人执行的
"两事件 + 30 天"计时器。复审是有证据的发布决策,不是日历仪式。

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
