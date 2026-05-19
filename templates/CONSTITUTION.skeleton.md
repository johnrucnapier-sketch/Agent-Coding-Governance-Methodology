# <项目名> 宪法 / Constitution

> 通用空骨架。把 `<...>` 全部替换成你项目的内容。**宪法只有人能改**;AI 试图改 = 违规。
> Blank generic skeleton. Replace every `<...>`. Only humans change the constitution.

## 0. 元规则 / Meta-rules
- 本文件只有项目所有者(人)能修改。
- 新增条款追加,注明日期与触发案例,不挪动既有编号。
- 推翻条款在修订记录里说明原因,不删原文。

## 1. 不可妥协原则 / Non-negotiable principles
- <原则 1：在此填写——例如真值优先、grounding 仪式…>
- <原则 2：…>

## 2. 红线 / Redlines（绝不可做)
- <红线 1：你的产品/合规决定的硬禁止项>
- <红线 2：…>

## 3. 角色边界 / Role boundaries
- 人的职责:<业务判断、价值判断、不可逆决策授权…>
- AI 的职责:<把已定的事做对;不替人做业务判断…>

## 4. 范围边界 / Scope boundary (IN / OUT)
- 判据:这件事为软件能开发/上线/运行 = IN;为别的(经营/战略/与软件无关)= OUT。
- IN:<列你项目的 IN 清单>
- OUT:<列你项目的 OUT 清单>

## 5. 四类漂移防线 / Four-drift defenses
- ① 实施层(技术不通就绕路)→ <你的防线>
- ② 认知层(写文档凭印象)→ <你的防线>
- ③ 结构放置(治理住错分支/主干腐化)→ <你的防线>
- ④ 范围(不该进仓库的内容混进来)→ <你的防线>

## 6. 修宪流程 / Amendment process
- <推翻或新增条款的流程:谁提案、谁批准、如何记录>

## 7. 工作树纪律 / Worktree discipline
- 一线一工作树、钉死分支;主树永远=主干=治理 author + 汇聚点,严禁在主树切别分支 /
  one line = one worktree pinned to its branch; the main tree is always trunk =
  governance author + convergence point; never switch branches in it
- 汇聚只经主干,禁线间直接 merge;git 外基建在主干以 ADR/快照记录 /
  converge only via the trunk, no direct line-to-line merge; non-git infra recorded
  on the trunk as ADR/snapshots
- session 启动验证所在工作树/分支;主树非主干即停 / session-start verifies the
  worktree/branch; if the main tree is not the trunk, stop

## 修订记录 / Revision log
- <YYYY-MM-DD> 初版,触发案例:<…>
