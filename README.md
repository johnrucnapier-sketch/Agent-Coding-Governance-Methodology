# Agent Coding Governance

**A governance system for multi-session, long-horizon AI development.**
**Works with both Claude Code and Codex (and any agent) — two parallel one-command-ish paths.**

[![Code: MIT](https://img.shields.io/badge/code-MIT-green.svg)](LICENSING.md) [![Docs: CC--BY--4.0](https://img.shields.io/badge/docs-CC--BY--4.0-blue.svg)](LICENSING.md) [![Dual-license](https://img.shields.io/badge/license-dual--track-lightgrey.svg)](LICENSING.md)

> English first (full). 中文完整版在下半部分 — scroll past the English.

---

> **One sentence:** long-horizon AI-driven development **rots structurally** — unless
> there is governance.
>
> Distilled from a real project (a dozen-plus versions, dozens of sessions, ~2B
> tokens of mistakes). What you get: an agent that takes fewer wrong turns, makes
> fewer fabricated claims, and does fewer destructive actions across long timelines —
> at the cost of it stopping to verify more. Claude Code uses it as a plugin
> (runtime-automatic); Codex / any agent uses a one-command scaffold (then
> auto-reads `AGENTS.md` every session).

## What this is / why you need it

Doing **multi-session, long-horizon, possibly multi-person / multi-branch**
development with Claude Code (or a comparable AI coding agent), past a certain scale
you inevitably hit:

- a new session doesn't know what happened before; it rebuilds from handoff docs →
  necessarily distorted
- the AI **fabricates technical conclusions** from conversation residue instead of
  reading code ground truth
- an old plan is overturned but unmarked; the next session reads it and goes wrong
- governance/truth lives on a feature branch, the trunk rots, a new session on the
  old trunk reads all-wrong

**This is not operator error, it is the natural cost of this workflow.** This repo
does not eliminate rot (impossible) — it makes rot **visible, interceptable,
reversible.**

## Core: the four drift types (the mental model most worth taking with you)

First learn to **recognize which type it is**, then talk about how to fix it.

| Drift | What's wrong | Defense |
|---|---|---|
| **① Implementation** | detours when the tech is hard (hand-rolled polyfill / downgrade / silent error swallow) | Detour ban: root-cause first |
| **② Cognitive** | writes docs from impression, doesn't verify | Truth-first: conclusions carry `file:line`, ban "I recall / should be" |
| **③ Structural placement** | governance on the wrong branch, trunk rots | govern only on the trunk; trunk never allowed to rot |
| **④ Scope** | content that shouldn't be in the repo (ops/strategy) creeps in | scope boundary: for software to ship = IN, for anything else = OUT |

## Quick start: two parallel paths

CC = plugin (runtime-automatic). Codex / any agent = one-command scaffold, then the
agent auto-reads `AGENTS.md` every session.

### Path A · Claude Code (plugin, runtime-automatic)

Two steps (honest — not literally one command):

1. Register the marketplace:
   ```
   /plugin marketplace add johnrucnapier-sketch/Agent-Coding-Governance-Methodology
   ```
2. Install the plugin (from the `/plugin` menu, or):
   ```
   /plugin install agent-coding-governance-methodology@agent-coding-governance-methodology
   ```

**Exact commands follow current official Claude Code docs** — CC's plugin/marketplace
syntax may change by version; if `/plugin install` differs, just open the `/plugin`
menu and install it from the marketplace you added in step 1.

*You'll know it worked when:* at the next session start the SessionStart hook
injects a grounding directive — the agent acknowledges governance and runs the
5-step grounding (or, if the project has no governance docs yet, points you to
`governance-bootstrap`) instead of diving straight into edits.

### Path B · Codex / any agent (one-command scaffold)

```
git clone https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology
sh Agent-Coding-Governance-Methodology/scripts/governance-init.sh /path/to/your-project
```

One command scaffolds `CONSTITUTION.md` + `AGENTS.md` (the governance directive) +
a `CLAUDE.md` pointer into your project (**idempotent & non-destructive** — existing
files are skipped, never overwritten). The script is reviewable; `curl|sh` is
deliberately avoided.

*You'll know it worked when:* the script prints the files it created, and your next
Codex session opens having already read `AGENTS.md` — it follows the grounding /
truth-first rules without you pasting anything.

### How "automatic" differs (stated honestly)

- **CC:** the hook is a *runtime* mechanism — genuinely auto-injected every session;
  skills are invoked by the Skill tool, they do not auto-fire.
- **Codex / any agent:** no such hook; it relies on the agent natively auto-reading
  `AGENTS.md` (a static directive). The script is a *scaffolder*, not a Codex
  runtime — Codex has none. **"Runtime hook or not" ≠ "can the methodology be used."**
- Either path only wires auto-grounding + a constitution skeleton. Full governance
  (decision log / snapshots / tracks) is **human-driven**: invoke
  `governance-bootstrap` (CC) or follow `METHODOLOGY.en.md` §12 by hand.

## The eight principles (full text: `METHODOLOGY.en.md`)

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

## Repo structure

```
README.md                          ← what you're reading (WHY + index); English then 中文
METHODOLOGY.md / METHODOLOGY.en.md ← full methodology (8 principles + bootstrap + failure modes)
.claude-plugin/
  plugin.json                      ← this repo IS a Claude Code plugin
  marketplace.json                 ← for /plugin marketplace add install
hooks/hooks.json                   ← SessionStart hook (the ONLY automatic mechanism)
scripts/grounding-inject.sh        ← (CC) the hook injects a thin grounding directive → skills
scripts/governance-init.sh         ← (Codex/any agent) one-command scaffold: AGENTS.md/constitution/pointer
skills/
  session-grounding/SKILL.md       ← invoke at: session start/resume — 5-step grounding + report first
  truth-first/SKILL.md             ← invoke at: before a technical conclusion / irreversible op — force sources
  governance-bootstrap/SKILL.md    ← invoke at: bootstrap governance from zero — human-driven 8-step checklist
templates/                         ← fully blank generic skeletons, zero business
  CONSTITUTION.skeleton.md  ADR._TEMPLATE.md  SESSION_START.skeleton.md  drift-check.stub.js
LICENSING.md / LICENSE-DOCS / LICENSE-CODE  ← dual-track: docs CC-BY-4.0, code MIT
```

## Adaptation guide: take as-is vs. must adapt to your project

**Take as-is (general skeleton)**: the four-drift classification / the eight
principles / the layered structure / the bootstrap recipe / the self-check redlines.

**Must redesign for your project (copying = another kind of drift)**:
- how tracks are split (depends on where your project's core value is, how many
  cognitive contexts)
- the concrete IN/OUT scope-boundary list
- exactly which protocols your cross-cutting contracts are
- the concrete content of the redlines (decided by your product/compliance)

> Principles are the skeleton, migratable; the flesh is your project's own. Don't copy
> someone else's track/contract list.

## Real background (the strongest credibility)

This system **committed drift ② against itself while being built** — the builder
copied a pile of technical conclusions out of old handoff docs without reading the
code, and was caught in the act by the project owner. That is exactly the proof:
**discipline is not for "other people", it is for you, every single time you write
something right now.** Writing a real incident like this permanently into the
governance file as a cautionary case is ten times more useful than an abstract rule.

## Origin — why this exists

> This section is the author's personal voice — edit it freely to your own comfort.

I have perfectionist tendencies, and I have lived with significant anxiety for a long
time. For years I could no longer do the kind of long-form writing I did as a
student — the information and thinking in my head far outran the speed at which I
could put it on paper; my execution could not keep up with my ideas. In real work, I
always felt boxed in by my own limitations.

The AI / agent era felt like a shackle coming off: the very weaknesses — "thinking
too much, writing too slowly" — turned into strengths. Wide-ranging ideas could
combine with an agent and grow into things I could never have produced alone.

Over a long stretch of agent-coding practice, hitting pitfall after pitfall, I
gradually distilled into this methodology the answer to one question: how do you keep
an agent consistent — making fewer mistakes, taking fewer wrong turns — across many
sub-projects, ultra-long timelines, heavy iteration, and changing requirements? On my
own projects it works well; and because I am risk-averse by nature, this methodology
also makes the agent more cautious, with fewer destructive actions.

I am open-sourcing it so that people doing long-horizon development with Claude Code
or Codex don't have to fall into the same pits I did. The principles are the
skeleton — take them and grow your own project's flesh on them.

## License / maintenance stance

- **License: dual-track** — the methodology/docs (`METHODOLOGY*.md`, `README.md`,
  the prose of each `SKILL.md`) under **CC-BY-4.0**; the code/mechanical parts
  (`scripts/`, `hooks/`, `templates/`, `.claude-plugin/`) under **MIT**. See
  `LICENSING.md`.
- **Cost (untested, the author's judgment):** it likely consumes *more* tokens (more
  reading code / verifying / restating / stopping to confirm), but buys fewer errors
  and fewer wrong turns, compressing the most expensive part — rework. The author is
  not token-constrained and has not measured it; assess it on your own project.
- **Maintenance:** a methodology share — issues/PRs welcome, but **self-adaptation is
  the norm; no heavy support promised.**

## Acknowledgements

Distilled from the governance practice of a real long-horizon AI-driven development
project. All business specificity stripped — this repo **contains, and will never
accept,** any concrete project's business/confidential content (this is itself an
application of §④, the scope boundary).

---
---

# 中文版(完整)

# Agent Coding Governance —— AI 多会话开发治理体系

**面向多会话、长周期 AI 开发的治理体系。**
**同时支持 Claude Code 与 Codex(及任意 agent)——两条并列的近乎一键的路径。**

> 英文完整版在上半部分;以下为中文完整版。

---

> **一句话:** AI 驱动的长周期开发会**结构性地腐化**——除非有治理。
>
> 提炼自一个真实项目(十几个版本、数十 session、~20 亿 token 踩坑)。你能得到的:
> 在长周期里,agent 走错路更少、编造结论更少、破坏性动作更少——代价是它会更频繁地
> 停下来核实。Claude Code 走插件(运行时自动);Codex / 任意 agent 走一键脚手架
> (之后每 session 自动读 `AGENTS.md`)。

## 这是什么 / 为什么需要

用 Claude Code(或同类 AI 编码 agent)做**多会话、长周期、可能多人/多分支**的开发,
到一定规模后必然遇到:

- 新 session 不知道前面发生过什么,靠交接文档重建 → 必然失真
- AI 整理文档时凭对话残留**编造技术结论**,不去读代码真值
- 旧方案被推翻但没标记,下个 session 读到就走错
- 治理/真值长在某功能分支,主干腐化,新 session 落旧主干读到全错

**这不是操作失误,是这套工作流的天然成本。** 本仓库不消灭腐化(不可能),而是让它
**显性化、可拦截、可回滚**。

## 核心:四类漂移(最值得带走的心智模型)

先学会**识别是哪一类**,再谈怎么修。

| 漂移 | 错在哪 | 防线 |
|---|---|---|
| **① 实施层** | 技术不通就绕路(自写 polyfill / 降级 / 静默吞错) | 绕行禁令:先 root cause |
| **② 认知层** | 写文档凭印象,不验证真值 | 真值优先:结论必带 `文件:行号`,禁"我记得/应该" |
| **③ 结构放置** | 治理住错分支,主干腐化 | 治理只在主干 author;主干永不准腐化 |
| **④ 范围** | 不该进仓库的内容(企业经营/战略)混进来 | 范围边界:为软件上线=IN,为别的=OUT |

## 快速开始:两条并列路径

CC 走插件(运行时自动);Codex / 任意 agent 走一键脚手架,之后 agent 每 session
自动读 `AGENTS.md`。

### 路径 A · Claude Code(插件,运行时自动)

两步(老实说,不是字面上的一条命令):

1. 注册 marketplace:
   ```
   /plugin marketplace add johnrucnapier-sketch/Agent-Coding-Governance-Methodology
   ```
2. 安装插件(用 `/plugin` 菜单,或):
   ```
   /plugin install agent-coding-governance-methodology@agent-coding-governance-methodology
   ```

**确切命令以当前 Claude Code 官方文档为准**——CC 的 plugin/marketplace 语法可能随
版本变化;若 `/plugin install` 形式不同,就打开 `/plugin` 菜单,从第 1 步加的
marketplace 里装。

*成功的样子:* 下次 session 启动时,SessionStart hook 会注入一段 grounding 指令——
agent 会先确认治理、走 5 步 grounding(或在项目还没治理文档时,引导你调
`governance-bootstrap`),而不是直接埋头改代码。

### 路径 B · Codex / 任意 agent(一键脚手架)

```
git clone https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology
sh Agent-Coding-Governance-Methodology/scripts/governance-init.sh /你的项目路径
```

一条命令把 `CONSTITUTION.md` + `AGENTS.md`(治理指令)+ `CLAUDE.md` 指针铺进你的
项目(**幂等、非破坏**,已存在的文件只跳过、绝不覆盖)。脚本可审阅,故意不用
`curl|sh`。

*成功的样子:* 脚本打印出新建的文件;下次 Codex session 一开,它已读过
`AGENTS.md`——不用你贴,它就按 grounding / truth-first 规则走。

### 机制差异(如实)

- **CC:** hook 是*运行时*机制,每 session 真·自动注入;skill 由 Skill 工具调用,
  不自动点火。
- **Codex / 任意 agent:** 没有这种 hook;靠 agent 原生自动读 `AGENTS.md`(静态
  指令)。脚本是*脚手架*,不是给 Codex 造运行时——Codex 没有那东西。
  **能否运行时 hook ≠ 方法论能否用。**
- 两条路径都只给"自动 grounding 接线 + 宪法骨架"。完整治理(决策日志/快照/轨道)
  是**人驱动**的:新项目调用 `governance-bootstrap`(CC)或照 `METHODOLOGY.md`
  §12 手做。

## 八条原则(完整正文:`METHODOLOGY.md`)

1. 按生命周期分层存内容(宪法/决策日志/快照/版本归档/契约/活交接)
2. 项目根规则文件 = 元规则+指针+行为约束,**绝不放事实**
3. 真值优先(绝对版,无灰色地带)
4. session 启动 grounding 仪式(先验证再动手)
5. 不过度执行(暴露歧义,不蛮干;销毁前硬检查点)
6. 按轨道隔离工作(不同认知上下文/验证方法不混)
7. 一个主干,永不腐化
8. 范围边界(明确 IN/OUT)

## 仓库结构

```
README.md                          ← 你正在读的(WHY + 索引);英文在前,中文在后
METHODOLOGY.md / METHODOLOGY.en.md ← 完整方法论(八原则 + bootstrap 配方 + 失败模式)
.claude-plugin/
  plugin.json                      ← 本仓即一个 Claude Code plugin
  marketplace.json                 ← 供 /plugin marketplace add 安装
hooks/hooks.json                   ← SessionStart hook(唯一自动机制)
scripts/grounding-inject.sh        ← (CC)hook 注入薄 grounding 指令,指向下面 skills
scripts/governance-init.sh         ← (Codex/任意 agent)一键脚手架:铺 AGENTS.md/宪法/指针
skills/
  session-grounding/SKILL.md       ← 调用时机:session 启动/续接,5步grounding+先报告
  truth-first/SKILL.md             ← 调用时机:写技术结论/不可逆操作前,强制来源
  governance-bootstrap/SKILL.md    ← 调用时机:新项目从零建治理,人驱动8步清单
templates/                         ← 全空白通用骨架,零业务
  CONSTITUTION.skeleton.md  ADR._TEMPLATE.md  SESSION_START.skeleton.md  drift-check.stub.js
LICENSING.md / LICENSE-DOCS / LICENSE-CODE  ← 双轨:文档 CC-BY-4.0,代码 MIT
```

## 适配指南:直接拿用 vs 必须按你项目改

**直接拿用(通用骨架)**:四类漂移分类 / 八原则 / 分层结构 / bootstrap 配方 /
自检红线。

**必须按你项目重新设计(照抄=另一种漂移)**:
- 轨道怎么分(取决于你项目核心价值在哪、有几个认知上下文)
- 范围边界 IN/OUT 具体清单
- 跨切面契约具体是哪些协议
- 红线具体内容(你的产品/合规决定)

> 原则是骨架,可迁移;血肉是你项目自己的。别把别人的轨道/契约清单照抄。

## 真实背景(最强的可信度)

这套体系**在被搭建的过程中,搭建者自己就犯了②号漂移**——从旧交接文档抄了一堆技术
结论没去读代码,被项目所有者当场抓出。这恰恰证明:**纪律不是给"别人"的,是给当下
每一次写字的你的。** 把这类真实事故永久写进治理文件当警示案例,比抽象规则有用十倍。

## 初衷 / 为什么会有这套东西

> 这一段是作者的个人表达——这是你的声音,按你自己的舒适度自由增删。

我有完美主义倾向,也长期与焦虑相处。过去很多年,我没法再像学生时代那样做长文本写作
——脑子里的信息和思考,远远超过我能落到纸上的速度;执行能力追不上想法。在现实工作里,
我总觉得被自己的局限性卡住。

AI / agent 的时代对我像是枷锁被打开:那些"想得太多、写得太慢"的缺点,反而变成了
优势——天马行空的想法可以和 agent 结合,长出很多原本我做不出来的东西。

在长时间的 agent coding 实践里,我一次次踩坑,逐渐把"怎么让 agent 在多子项目、超长
周期、大量迭代和需求变化中仍然保持一致、少犯错、少走错路"沉淀成了这套方法论。在我
自己的项目里它效果很好;因为我本人是风险厌恶者,这套方法论也让 agent 更谨慎、破坏性
的动作更少。

我把它开源,是想让同样在用 Claude Code 或 Codex 做长周期开发的人,不必把我踩过的坑
再踩一遍。原则是骨架,拿去按你自己的项目长出血肉。

## License / 维护态度

- **License:双轨**——方法论/文档(`METHODOLOGY*.md`、`README.md`、各 `SKILL.md`
  正文)采用 **CC-BY-4.0**;代码/机械件(`scripts/`、`hooks/`、`templates/`、
  `.claude-plugin/`)采用 **MIT**。详见 `LICENSING.md`。
- **成本(未实测,作者判断):** 很可能消耗*更多* token(更多读码/验证/转述/停下
  确认),但换来更少错误与走错路,从而压缩最贵的返工。作者不缺 token、未实测,增减
  请在你自己项目上体验。
- **维护:** 方法论分享,欢迎 issue/PR,但**自行适配为主,不承诺重度支持**。

## 致谢

提炼自一个真实长周期 AI 驱动开发项目的治理实践。已剥离全部业务特质——仓库内**不含也
永不接受**任何具体项目的业务/机密内容(这本身就是 §④ 范围边界的应用)。
