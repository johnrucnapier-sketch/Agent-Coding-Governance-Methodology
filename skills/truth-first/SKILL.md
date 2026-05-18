---
name: truth-first
description: Use BEFORE writing any technical conclusion (into docs, commit messages, code comments, or reports), before editing documentation, and before any irreversible or destructive action (deleting files, branches, or history). 写技术结论 / 改文档 / 做不可逆或破坏性操作前调用。Enforces file:line sourcing, bans "I think / should be / usually / I recall", and requires list + rollback + quoted authorization before destructive ops.
---

# Truth-First

AI writing docs tends to summarize from conversation residue instead of reading the
code. Stale claims left in context get written down as "current". This skill closes
that hole — absolutely, no grey zone.

## Any technical conclusion you write — these are hard rules

- NOT from conversation memory.
- NOT copied from history / superseded docs / old handoffs / old version snapshots.
- NOT phrased "should be / usually / I think / I recall / by convention".
- NOT a technical conclusion without a `file:line` source.
- MUST grep / read the code · config · schema and attach a source to every claim.
- If you cannot read the truth source: say plainly "I did not read X, this conclusion
  is not trustworthy." Do not fabricate.

**Self-check redline:** the moment "I recall / should be" appears in your head, or you
want to cite an old doc → STOP, go verify. Wrote a paragraph with no source → delete it
or add the source.

## Before irreversible / destructive actions (§7)

- Any ambiguity or unverified assumption before deleting files/branches/history →
  verify; if it does not check out, STOP and ask.
- If the change's blast radius is bigger than it looks (touches many docs, tracked
  decisions) → list the blast radius and let the human decide. Do not decide for them.
- Destructive ops require a hard human checkpoint: **list what will be destroyed +
  write the rollback + quote the authorization verbatim.** Bypassing a safety
  checkpoint is itself a drift.
- Separate the user's business judgment (whether to do a thing, whether content has
  value) from the AI's execution (doing the decided thing correctly). The first is
  the human's.

---

# 真值优先

AI 写文档倾向用对话残留总结,而不去读代码。上下文里的过期说法就被当"现状"写下。
这条做成**绝对**的,无灰色地带。

## 任何你写下的技术结论 —— 硬规则

- 不许凭对话记忆。
- 不许从历史/被推翻文档/旧交接/旧版本快照抄技术结论。
- 不许用"应该是/通常是/我记得/按惯例"措辞。
- 不许写技术结论却不给 `文件:行号`。
- 必须 grep / 读 代码·配置·schema,每条结论带来源。
- 读不到真值时直说"我没读 X,本结论不可信",**不许编**。

**自检红线:** 脑子里冒出"我记得/应该是",或想引用旧文档 → 立即停,去验证。写完一段
没带来源 → 删掉或补来源。

## 不可逆 / 破坏性操作前(§7)

- 删文件/分支/历史前有任何歧义或未验证假设 → 先验证;过不了就**停下问**。
- 改动影响面比表面大(牵连多文档、被追踪决策)→ **列出影响面让人定**,别替人判断。
- 销毁性操作要硬人工检查点:**列清单 + 写回滚 + 引用授权原话**。绕过安全检查点本身
  就是漂移。
- 区分"用户的业务判断"(要不要做、内容有没有价值)和"AI 的执行"(把已定的事做对)。
  前者是人的。
