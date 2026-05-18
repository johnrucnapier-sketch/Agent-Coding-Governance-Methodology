# Claude Code Governance —— AI 多会话开发治理体系

> 一句话：AI 驱动的长周期开发会**结构性地腐烂**——除非有治理。
> 这是一套从真实项目（十几个版本、数十 session、~20 亿 token 踩坑）提炼的可迁移治理逻辑 + 可直接用的 Claude Code skill 套件。

---

## 初衷 / 为什么会有这套东西

> 这一段是作者的个人表达——这是你的声音,按你自己的舒适度自由增删。

我有完美主义倾向,也长期与焦虑相处。过去很多年,我没法再像学生时代那样做长文本写作——脑子里的信息和思考,远远超过我能落到纸上的速度;执行能力追不上想法。在现实工作里,我总觉得被自己的局限性卡住。

AI / agent 的时代对我像是枷锁被打开:那些"想得太多、写得太慢"的缺点,反而变成了优势——天马行空的想法可以和 agent 结合,长出很多原本我做不出来的东西。

在长时间的 agent coding 实践里,我一次次踩坑,逐渐把"怎么让 agent 在多子项目、超长周期、大量迭代和需求变化中仍然保持一致、少犯错、少走错路"沉淀成了这套方法论。在我自己的项目里它效果很好;因为我本人是风险厌恶者,这套方法论也让 agent 更谨慎、破坏性的动作更少。

我把它开源,是想让同样在用 Claude Code 或 Codex 做长周期开发的人,不必把我踩过的坑再踩一遍。原则是骨架,拿去按你自己的项目长出血肉。

---

## 这是什么 / 为什么需要

用 Claude Code（或同类 AI 编码 agent）做**多会话、长周期、可能多人/多分支**的开发，到一定规模后必然遇到：

- 新 session 不知道前面发生过什么，靠交接文档重建 → 必然失真
- AI 整理文档时凭对话残留**编造技术结论**，不去读代码真值
- 旧方案被推翻但没标记，下个 session 读到就走错
- 治理/真值长在某功能分支，主干腐烂，新 session 落旧主干读到全错

**这不是操作失误，是这套工作流的天然成本。** 本仓库不消灭腐烂（不可能），而是让它**显性化、可拦截、可回滚**。

---

## 核心：四类漂移（最值得带走的心智模型）

| 漂移 | 错在哪 | 防线 |
|---|---|---|
| **① 实施层** | 技术不通就绕路（自写 polyfill / 降级 / 静默吞错） | 绕行禁令：先 root cause |
| **② 认知层** | 写文档凭印象，不验证真值 | 真值优先：结论必带 `文件:行号`，禁"我记得/应该" |
| **③ 结构放置** | 治理住错分支，主干腐烂 | 治理只在主干 author；主干永不准腐烂 |
| **④ 范围** | 不该进仓库的内容（企业经营/战略）混进来 | 范围边界：为软件上线=IN，为别的=OUT |

先学会**识别是哪一类**，再谈怎么修。

---

## 八条原则（详见 `METHODOLOGY.md`）

1. 按生命周期分层存内容（宪法/决策日志/快照/版本归档/契约/活交接）
2. 项目根规则文件 = 元规则+指针+行为约束，**绝不放事实**
3. 真值优先（绝对版，无灰色地带）
4. session 启动 grounding 仪式（先验证再动手）
5. 不过度执行（暴露歧义，不蛮干；销毁前硬检查点）
6. 按轨道隔离工作（不同认知上下文/验证方法不混）
7. 一个主干，永不腐烂
8. 范围边界（明确 IN/OUT）

---

## 仓库结构

```
README.md / README.en.md          ← 你正在读的（WHY + 索引），中英双语
METHODOLOGY.md / METHODOLOGY.en.md ← 完整方法论（八原则 + bootstrap 配方 + 失败模式）
.claude-plugin/
  plugin.json                     ← 本仓即一个 Claude Code plugin
  marketplace.json                ← 供 /plugin marketplace add 安装
hooks/hooks.json                  ← SessionStart hook（唯一自动机制）
scripts/grounding-inject.sh       ← hook 注入薄 grounding 指令，指向下面 skills
skills/
  session-grounding/SKILL.md      ← 调用时机：session 启动/续接，5步grounding+先报告
  truth-first/SKILL.md            ← 调用时机：写技术结论/不可逆操作前，强制来源
  governance-bootstrap/SKILL.md   ← 调用时机：新项目从零建治理，人驱动8步清单
templates/                        ← 全空白通用骨架，零业务
  CONSTITUTION.skeleton.md  ADR._TEMPLATE.md  SESSION_START.skeleton.md  drift-check.stub.js
LICENSING.md / LICENSE-DOCS / LICENSE-CODE  ← 双轨：文档 CC-BY-4.0，代码 MIT
```

---

## 快速开始

1. 本仓即一个 Claude Code plugin。经 `/plugin marketplace add <owner>/Agent-Coding-Governance-Methodology` 添加后安装(**确切安装命令以当前 Claude Code 官方文档为准**——CC 的 plugin/marketplace 命令可能随版本变化)
2. 新项目：调用 `governance-bootstrap`，跟着人驱动的 8 步把宪法/根文件/决策日志/快照建起来
3. 机制说明(**如实**):**只有 SessionStart hook 会自动**——它每次在 session 开始时注入一段薄 grounding 指令;该指令引导你/agent 调用 `session-grounding` skill 走 5 步;写结论/改文档/不可逆操作时按指令调用 `truth-first`。**skill 本身不自动点火,是被 Skill 工具调用的。**

---

## ⚠️ 适配指南：直接拿用 vs 必须按你项目改

**直接拿用（通用骨架）**：四类漂移分类 / 八原则 / 分层结构 / bootstrap 配方 / 自检红线。

**必须按你项目重新设计（照抄=另一种漂移）**：
- 轨道怎么分（取决于你项目核心价值在哪、有几个认知上下文）
- 范围边界 IN/OUT 具体清单
- 跨切面契约具体是哪些协议
- 红线具体内容（你的产品/合规决定）

> 原则是骨架，可迁移；血肉是你项目自己的。别把别人的轨道/契约清单照抄。

---

## 真实背景（最强的可信度）

这套体系**在被搭建的过程中，搭建者自己就犯了②号漂移**——从旧交接文档抄了一堆技术结论没去读代码，被项目所有者当场抓出。这恰恰证明：**纪律不是给"别人"的，是给当下每一次写字的你的。** 把这类真实事故永久写进治理文件当警示案例，比抽象规则有用十倍。

---

## License / 维护态度

- License：**双轨**——方法论/文档(`METHODOLOGY*.md`、`README*.md`、各 `SKILL.md` 正文)采用 **CC-BY-4.0**;代码/机械件(`scripts/`、`hooks/`、`templates/`、`.claude-plugin/`)采用 **MIT**。详见 `LICENSING.md`。
- 成本(未实测,作者判断):很可能消耗*更多* token(更多读码/验证/转述/停下确认),但换来更少错误与走错路,从而压缩最贵的返工。作者不缺 token、未实测,增减请在你自己项目上体验。
- 维护：方法论分享，欢迎 issue/PR，但**自行适配为主，不承诺重度支持**。

## 致谢

提炼自一个真实长周期 AI 驱动开发项目的治理实践。已剥离全部业务特质——仓库内**不含也永不接受**任何具体项目的业务/机密内容（这本身就是 §④ 范围边界的应用）。
