# Claude Code Governance —— AI 多会话开发治理体系 / a governance system for multi-session AI development

> 中英逐段对照,单文件。 / Chinese and English, interleaved section by section, single file.

> 一句话:AI 驱动的长周期开发会**结构性地腐化**——除非有治理。
> 这是一套从真实项目(十几个版本、数十 session、~20 亿 token 踩坑)提炼的可迁移治理逻辑 + 可直接用的 Claude Code skill 套件。
>
> One sentence: long-horizon AI-driven development **rots structurally** — unless
> there is governance.
> This is a migratable governance logic distilled from a real project (a dozen-plus
> versions, dozens of sessions, ~2B tokens of mistakes) + a ready-to-use Claude Code
> plugin.

---

## 初衷 / Origin — why this exists

> 这一段是作者的个人表达——这是你的声音,按你自己的舒适度自由增删。
> This section is the author's personal voice — edit it freely to your own comfort.

我有完美主义倾向,也长期与焦虑相处。过去很多年,我没法再像学生时代那样做长文本写作——脑子里的信息和思考,远远超过我能落到纸上的速度;执行能力追不上想法。在现实工作里,我总觉得被自己的局限性卡住。

I have perfectionist tendencies, and I have lived with significant anxiety for a long
time. For years I could no longer do the kind of long-form writing I did as a
student — the information and thinking in my head far outran the speed at which I
could put it on paper; my execution could not keep up with my ideas. In real work, I
always felt boxed in by my own limitations.

AI / agent 的时代对我像是枷锁被打开:那些"想得太多、写得太慢"的缺点,反而变成了优势——天马行空的想法可以和 agent 结合,长出很多原本我做不出来的东西。

The AI / agent era felt like a shackle coming off: the very weaknesses — "thinking
too much, writing too slowly" — turned into strengths. Wide-ranging ideas could
combine with an agent and grow into things I could never have produced alone.

在长时间的 agent coding 实践里,我一次次踩坑,逐渐把"怎么让 agent 在多子项目、超长周期、大量迭代和需求变化中仍然保持一致、少犯错、少走错路"沉淀成了这套方法论。在我自己的项目里它效果很好;因为我本人是风险厌恶者,这套方法论也让 agent 更谨慎、破坏性的动作更少。

Over a long stretch of agent-coding practice, hitting pitfall after pitfall, I
gradually distilled into this methodology the answer to one question: how do you keep
an agent consistent — making fewer mistakes, taking fewer wrong turns — across many
sub-projects, ultra-long timelines, heavy iteration, and changing requirements? On my
own projects it works well; and because I am risk-averse by nature, this methodology
also makes the agent more cautious, with fewer destructive actions.

我把它开源,是想让同样在用 Claude Code 或 Codex 做长周期开发的人,不必把我踩过的坑再踩一遍。原则是骨架,拿去按你自己的项目长出血肉。

I am open-sourcing it so that people doing long-horizon development with Claude Code
or Codex don't have to fall into the same pits I did. The principles are the
skeleton — take them and grow your own project's flesh on them.

---

## 这是什么 / 为什么需要 / What this is / why you need it

用 Claude Code(或同类 AI 编码 agent)做**多会话、长周期、可能多人/多分支**的开发,到一定规模后必然遇到:

Doing **multi-session, long-horizon, possibly multi-person / multi-branch**
development with Claude Code (or a comparable AI coding agent), past a certain scale
you inevitably hit:

- 新 session 不知道前面发生过什么,靠交接文档重建 → 必然失真
- AI 整理文档时凭对话残留**编造技术结论**,不去读代码真值
- 旧方案被推翻但没标记,下个 session 读到就走错
- 治理/真值长在某功能分支,主干腐化,新 session 落旧主干读到全错

- a new session doesn't know what happened before; it rebuilds from handoff docs →
  necessarily distorted
- the AI **fabricates technical conclusions** from conversation residue instead of
  reading code ground truth
- an old plan is overturned but unmarked; the next session reads it and goes wrong
- governance/truth lives on a feature branch, the trunk rots, a new session on the
  old trunk reads all-wrong

**这不是操作失误,是这套工作流的天然成本。** 本仓库不消灭腐化(不可能),而是让它**显性化、可拦截、可回滚**。

**This is not operator error, it is the natural cost of this workflow.** This repo
does not eliminate rot (impossible) — it makes rot **visible, interceptable,
reversible.**

---

## 核心:四类漂移(最值得带走的心智模型) / Core: the four drift types (the mental model most worth taking with you)

先学会**识别是哪一类**,再谈怎么修。

First learn to **recognize which type it is**, then talk about how to fix it.

| 漂移 | 错在哪 | 防线 |
|---|---|---|
| **① 实施层** | 技术不通就绕路(自写 polyfill / 降级 / 静默吞错) | 绕行禁令:先 root cause |
| **② 认知层** | 写文档凭印象,不验证真值 | 真值优先:结论必带 `文件:行号`,禁"我记得/应该" |
| **③ 结构放置** | 治理住错分支,主干腐化 | 治理只在主干 author;主干永不准腐化 |
| **④ 范围** | 不该进仓库的内容(企业经营/战略)混进来 | 范围边界:为软件上线=IN,为别的=OUT |

| Drift | What's wrong | Defense |
|---|---|---|
| **① Implementation** | detours when the tech is hard (hand-rolled polyfill / downgrade / silent error swallow) | Detour ban: root-cause first |
| **② Cognitive** | writes docs from impression, doesn't verify | Truth-first: conclusions carry `file:line`, ban "I recall / should be" |
| **③ Structural placement** | governance on the wrong branch, trunk rots | govern only on the trunk; trunk never allowed to rot |
| **④ Scope** | content that shouldn't be in the repo (ops/strategy) creeps in | scope boundary: for software to ship = IN, for anything else = OUT |

---

## 八条原则(详见 `METHODOLOGY.md`)/ The eight principles (see `METHODOLOGY.en.md`)

1. 按生命周期分层存内容(宪法/决策日志/快照/版本归档/契约/活交接)
2. 项目根规则文件 = 元规则+指针+行为约束,**绝不放事实**
3. 真值优先(绝对版,无灰色地带)
4. session 启动 grounding 仪式(先验证再动手)
5. 不过度执行(暴露歧义,不蛮干;销毁前硬检查点)
6. 按轨道隔离工作(不同认知上下文/验证方法不混)
7. 一个主干,永不腐化
8. 范围边界(明确 IN/OUT)

1. Store content layered by lifecycle (constitution / decision log / snapshot /
   version archive / contract / live handoff)
2. The project root rules file = meta-rules + pointers + behavior constraints,
   **never facts**
3. Truth-first (the absolute version, no grey zone)
4. The session-start grounding ritual (verify before you act)
5. Don't over-execute (expose ambiguity, don't barrel through; hard checkpoint
   before destruction)
6. Isolate work by track (don't mix cognitive contexts / verification methods)
7. One trunk, never rotting
8. Scope boundary (explicit IN/OUT)

---

## 仓库结构 / Repo structure

```
README.md                          ← 你正在读的(WHY + 索引),中英逐段双语·单文件
METHODOLOGY.md / METHODOLOGY.en.md ← 完整方法论(八原则 + bootstrap 配方 + 失败模式)
.claude-plugin/
  plugin.json                      ← 本仓即一个 Claude Code plugin
  marketplace.json                 ← 供 /plugin marketplace add 安装
hooks/hooks.json                   ← SessionStart hook(唯一自动机制)
scripts/grounding-inject.sh        ← hook 注入薄 grounding 指令,指向下面 skills
skills/
  session-grounding/SKILL.md       ← 调用时机:session 启动/续接,5步grounding+先报告
  truth-first/SKILL.md             ← 调用时机:写技术结论/不可逆操作前,强制来源
  governance-bootstrap/SKILL.md    ← 调用时机:新项目从零建治理,人驱动8步清单
templates/                         ← 全空白通用骨架,零业务
  CONSTITUTION.skeleton.md  ADR._TEMPLATE.md  SESSION_START.skeleton.md  drift-check.stub.js
LICENSING.md / LICENSE-DOCS / LICENSE-CODE  ← 双轨:文档 CC-BY-4.0,代码 MIT
```

```
README.md                          ← what you're reading (WHY + index), single bilingual file
METHODOLOGY.md / METHODOLOGY.en.md ← full methodology (8 principles + bootstrap + failure modes)
.claude-plugin/
  plugin.json                      ← this repo IS a Claude Code plugin
  marketplace.json                 ← for /plugin marketplace add install
hooks/hooks.json                   ← SessionStart hook (the ONLY automatic mechanism)
scripts/grounding-inject.sh        ← the hook injects a thin grounding directive → skills below
skills/
  session-grounding/SKILL.md       ← invoke at: session start/resume — 5-step grounding + report first
  truth-first/SKILL.md             ← invoke at: before a technical conclusion / irreversible op — force sources
  governance-bootstrap/SKILL.md    ← invoke at: bootstrap governance from zero — human-driven 8-step checklist
templates/                         ← fully blank generic skeletons, zero business
  CONSTITUTION.skeleton.md  ADR._TEMPLATE.md  SESSION_START.skeleton.md  drift-check.stub.js
LICENSING.md / LICENSE-DOCS / LICENSE-CODE  ← dual-track: docs CC-BY-4.0, code MIT
```

---

## 快速开始 / Quick start

1. 本仓即一个 Claude Code plugin。经 `/plugin marketplace add <owner>/Agent-Coding-Governance-Methodology` 添加后安装(**确切安装命令以当前 Claude Code 官方文档为准**——CC 的 plugin/marketplace 命令可能随版本变化)
2. 新项目:调用 `governance-bootstrap`,跟着人驱动的 8 步把宪法/根文件/决策日志/快照建起来
3. 机制说明(**如实**):**只有 SessionStart hook 会自动**——它每次在 session 开始时注入一段薄 grounding 指令;该指令引导你/agent 调用 `session-grounding` skill 走 5 步;写结论/改文档/不可逆操作时按指令调用 `truth-first`。**skill 本身不自动点火,是被 Skill 工具调用的。**

1. This repo IS a Claude Code plugin. Install it after
   `/plugin marketplace add <owner>/Agent-Coding-Governance-Methodology` (**the exact
   install command follows current official Claude Code docs** — CC's plugin/
   marketplace commands may change by version).
2. New project: invoke `governance-bootstrap`, follow the human-driven 8 steps to
   build constitution/root-file/decision-log/snapshot.
3. Mechanism (**stated honestly**): **only the SessionStart hook is automatic** — it
   injects a thin grounding directive at each session start; that directive guides
   you/the agent to invoke the `session-grounding` skill and run the 5 steps; for a
   conclusion / doc edit / irreversible op, the directive points to `truth-first`.
   **Skills themselves do not auto-fire — they are invoked by the Skill tool.**

---

## 在 Codex / 其它 agent 上用 / Using this with Codex or other agents

唯一的自动机制(SessionStart hook 注入 grounding)是 Claude Code 专属的。Codex 等没有 CC 的 hook / Skill / plugin 系统,**不能"装上就自动生效"**。但方法论本身与 `templates/` 是工具无关的——逻辑可迁移,自动化只是 CC 的糖。

在 Codex(或任何 agent)上手工复刻:
1. 用 `templates/CONSTITUTION.skeleton.md` 在仓库里落一份宪法
2. 把 grounding 五步 + truth-first 规则写进 **`AGENTS.md`**(Codex 的指令文件,等价于 `CLAUDE.md`)或每个 session 的开场白——即手工写死 CC 里 hook 自动注入的那段指令
3. `templates/` 的 ADR / drift-check / SESSION_START 直接拿用
4. 代价:失去"每个 session 自动点火"的保证,改由指令遵循执行。**能否自动 ≠ 方法论能否用。**

The only automatic mechanism (the SessionStart hook injecting grounding) is Claude
Code-specific. Codex and others have no CC hook / Skill / plugin system, so this
**does not "just auto-work on install."** But the methodology itself and
`templates/` are tool-agnostic — the logic is portable; the automation is only CC
sugar.

To reproduce it by hand on Codex (or any agent):
1. Drop a constitution into the repo from `templates/CONSTITUTION.skeleton.md`
2. Put the 5-step grounding + truth-first rules into **`AGENTS.md`** (Codex's
   instruction file, the equivalent of `CLAUDE.md`) or each session's preamble —
   i.e., hard-write the directive that the CC hook injects automatically
3. Use the `templates/` ADR / drift-check / SESSION_START directly
4. Cost: you lose the "auto-fires every session" guarantee; it runs by
   instruction-following instead. **"Can it auto-fire" ≠ "can the methodology be
   used."**

---

## ⚠️ 适配指南:直接拿用 vs 必须按你项目改 / Adaptation guide: take as-is vs. must adapt to your project

**直接拿用(通用骨架)**:四类漂移分类 / 八原则 / 分层结构 / bootstrap 配方 / 自检红线。

**Take as-is (general skeleton)**: the four-drift classification / the eight
principles / the layered structure / the bootstrap recipe / the self-check redlines.

**必须按你项目重新设计(照抄=另一种漂移)**:
- 轨道怎么分(取决于你项目核心价值在哪、有几个认知上下文)
- 范围边界 IN/OUT 具体清单
- 跨切面契约具体是哪些协议
- 红线具体内容(你的产品/合规决定)

**Must redesign for your project (copying = another kind of drift)**:
- how tracks are split (depends on where your project's core value is, how many
  cognitive contexts)
- the concrete IN/OUT scope-boundary list
- exactly which protocols your cross-cutting contracts are
- the concrete content of the redlines (decided by your product/compliance)

> 原则是骨架,可迁移;血肉是你项目自己的。别把别人的轨道/契约清单照抄。
> Principles are the skeleton, migratable; the flesh is your project's own. Don't copy
> someone else's track/contract list.

---

## 真实背景(最强的可信度)/ Real background (the strongest credibility)

这套体系**在被搭建的过程中,搭建者自己就犯了②号漂移**——从旧交接文档抄了一堆技术结论没去读代码,被项目所有者当场抓出。这恰恰证明:**纪律不是给"别人"的,是给当下每一次写字的你的。** 把这类真实事故永久写进治理文件当警示案例,比抽象规则有用十倍。

This system **committed drift ② against itself while being built** — the builder
copied a pile of technical conclusions out of old handoff docs without reading the
code, and was caught in the act by the project owner. That is exactly the proof:
**discipline is not for "other people", it is for you, every single time you write
something right now.** Writing a real incident like this permanently into the
governance file as a cautionary case is ten times more useful than an abstract rule.

---

## License / 维护态度 / License / maintenance stance

- License:**双轨**——方法论/文档(`METHODOLOGY*.md`、`README.md`、各 `SKILL.md` 正文)采用 **CC-BY-4.0**;代码/机械件(`scripts/`、`hooks/`、`templates/`、`.claude-plugin/`)采用 **MIT**。详见 `LICENSING.md`。
- 成本(未实测,作者判断):很可能消耗*更多* token(更多读码/验证/转述/停下确认),但换来更少错误与走错路,从而压缩最贵的返工。作者不缺 token、未实测,增减请在你自己项目上体验。
- 维护:方法论分享,欢迎 issue/PR,但**自行适配为主,不承诺重度支持**。

- License: **dual-track** — the methodology/docs (`METHODOLOGY*.md`, `README.md`,
  the prose of each `SKILL.md`) under **CC-BY-4.0**; the code/mechanical parts
  (`scripts/`, `hooks/`, `templates/`, `.claude-plugin/`) under **MIT**. See
  `LICENSING.md`.
- Cost (untested, the author's judgment): it likely consumes *more* tokens (more
  reading code / verifying / restating / stopping to confirm), but buys fewer errors
  and fewer wrong turns, compressing the most expensive part — rework. The author is
  not token-constrained and has not measured it; assess it on your own project.
- Maintenance: a methodology share — issues/PRs welcome, but **self-adaptation is the
  norm; no heavy support promised.**

## 致谢 / Acknowledgements

提炼自一个真实长周期 AI 驱动开发项目的治理实践。已剥离全部业务特质——仓库内**不含也永不接受**任何具体项目的业务/机密内容(这本身就是 §④ 范围边界的应用)。

Distilled from the governance practice of a real long-horizon AI-driven development
project. All business specificity stripped — this repo **contains, and will never
accept,** any concrete project's business/confidential content (this is itself an
application of §④, the scope boundary).
