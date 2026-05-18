---
name: session-grounding
description: Use at the START of every session, when resuming or continuing prior work, or when picking up a half-done task in a governed project — before taking ANY action. 在每个 session 启动、续接、接半截活时,动手前先走此流程。Runs the 5-step grounding ritual — read constitution + root rules, identify the track, report 5 items and WAIT for human confirmation, verify after changes, get approval before commit. Restate before you act.
---

# Session Grounding

A new or resumed session rebuilds context from handoffs and "memory" — and that
reconstruction always distorts. This ritual catches the distortion *before* code is
written, where it is an order of magnitude cheaper to fix.

**Restate first, then act.** This is the whole point.

## The 5 steps (do not skip, do not skim)

1. **Read the constitution + the root rules file in full.** Not skim-read. These are
   the non-negotiable principles and the pointers to where truth lives.
2. **Identify which track / scope this session falls in.** Load that layer's docs too.
   One session works in one track; cross-track work is split into consecutive sessions.
3. **Report these 5 things, then WAIT for the human to confirm before acting:**
   - which track you are in
   - current state from `git log` + `git status`
   - the relevant structure you saw *by actually reading the code* (not from memory)
   - the exact list of files you intend to change (concrete paths)
   - the execution steps you intend to take
4. **After changes, run the verification scripts.**
5. **Closing report + commit draft — wait for human approval before committing.**

> The deviation exposed at the restate stage is far cheaper than the one found after
> the code is written. If you cannot read a truth source, say so explicitly — do not
> guess. (Before any technical conclusion or irreversible action, the `truth-first`
> skill applies.)

---

# Session 启动 grounding(先验证再动手)

新开/续接的 session 靠交接和"记忆"重建上下文,重建必然失真。这套仪式在**写代码之前**
就把失真抓出来——那时修正便宜一个数量级。

**先转述,再动手。** 这就是全部要义。

## 五步(不跳读、不省略)

1. **完整读宪法 + 根规则文件。** 不是跳读。这是不可妥协的原则和"真值在哪"的指针。
2. **判断本次落在哪个轨道/范围**,加读对应层文档。一个 session 只在一个轨道;跨轨道
   任务拆成连续多个 session。
3. **报告这 5 件事,然后等人确认再动手:**
   - 我落在哪个轨道
   - `git log` + `git status` 显示的现状
   - 我**实际读代码**看到的相关结构(不凭印象)
   - 我打算改的文件清单(具体路径)
   - 我打算的执行步骤
4. **改完跑验证脚本。**
5. **收尾报告 + commit 草稿,等人审批再 commit。**

> 转述阶段暴露的偏差,比写完代码再发现便宜一个数量级。读不到真值就直说,不许编。
> (写技术结论或做不可逆操作前,适用 `truth-first` skill。)
