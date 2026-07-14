# ACGM evidence register

> English first (full). 中文完整版在下半部分.

This register tracks the maturity of **claims**, not the popularity of wording.
It prevents a single incident, a repeated reminder, or an attractive explanation
from silently becoming a universal rule. Sensitive raw transcripts remain local;
the public register records only desensitized evidence references and limitations.

**Register review:** 2026-07-14 (ACGM V3 RC4 prerelease preparation).

## Maturity states

| State | What has been established | What may ship |
|---|---|---|
| **Observed** | One traceable real occurrence | A case, instrumentation, or a scoped prerelease trial — not a universal claim |
| **Reproduced** | The same failure/mechanism occurs again under documented conditions | A scoped prerelease trial with explicit limits |
| **Corroborated** | Independent observations, or observation + faithful reproduction, support the same general claim | Stable normative wording and default behavior, subject to normal safety review |
| **Predictive** | Reasoned and testable, but not directly observed | Meta-observation, test plan, or non-blocking instrumentation |
| **Rejected** | Contradicted, misattributed, or incident-shaped | Historical record only; remove from active claims/mechanisms |

A state belongs to one claim. One case can contain an Observed weak form and a
Predictive strong form. Status changes are append-only: add a dated row or note;
do not rewrite away the earlier judgment.

## Current register

| ID | Claim | State | Evidence | Limits / release effect |
|---|---|---|---|---|
| E-001 | "ACGM's own hook intercepted Case 1" | **Rejected** | Case 1 attribution audit: a third-party pre-execution gate held the command | ACGM truth-first is relevant to the subsequent grounding, but the mechanical interception is not an ACGM win |
| E-002 | High-risk actions need current target/state/authority/postcondition evidence | **Corroborated** | Case 1: an impression-derived target list plus a self-check sharing the same bad premise; Case 9: a stale operational alias and unverified current state | A mechanism may check only a subset; a filled template is not proof |
| E-003 | A started or exit-zero action retains a post-action verification obligation | **Corroborated** | Case 1: an all-green self-check would miss the intended postcondition; Case 9: a started background service was not followed to a verified state | A runtime unable to wake later must record `pending verification`, not promise automatic completion |
| E-004a | Performative compliance, weak form: complete ritual with facts inherited from summary/impression | **Observed** | Case 9's mixed-source grounding report | Covered by summaries-not-truth and evidence attribution |
| E-004b | Performative compliance, strong form: agent claims a verification tool ran when it did not | **Predictive** | Reasoned extension only; the historical audit did not establish this strong form | Keep as a Meta-observation; do not claim it happened or build a default blocker solely for it |
| E-005 | Repeated governance injection can become semantically ignored | **Predictive** | Design hypothesis; no attributable saturation event has been established | Guide low-noise instrumentation; no fixed trigger-count threshold |
| E-006 | "Two events within 30 days" is a sufficient clause lifecycle | **Rejected** | The rule had no registry, owner, expiry action, or release gate; elapsed time alone did not decide claim quality | Replaced by maturity states and a release decision |
| E-007 | Governance outcomes require initiator, pre/post timing, outcome, verification, and false-positive attribution | **Corroborated** | Case 1's corrected mechanism attribution; Case 9 was found by external human audit after the risky chain | Event Ledger activity counts cannot be marketed as wins |
| E-008 | Downloaded source or a verified plugin record/cache does not prove that the target runtime loaded the hooks | **Observed** | RC3 installer code stopped at configuration/cache verification while reload and `/hooks` remained future steps; a real Desktop installation attempt was reported unusable after download/install | RC4 must expose separate source, configuration, activation, and project-governance stages; a retained SessionStart health event is historical corroboration, not target-surface activation proof |
| E-009 | A caller-selected surface label must not override stronger Cloud/WSL runtime evidence | **Reproduced** | Pre-RC4 repros returned an automated-ready route when explicit Local/CLI labels contradicted official Cloud or OS-level WSL signals | RC4 fails closed as `SURFACE_SIGNAL_CONFLICT`; unknown surfaces still require an explicit human-selected target |
| E-010 | A successful planning/source-inspection operation is not a successful installation | **Reproduced** | Pre-RC4 manual UI and dry-run results returned process success while configuration and runtime remained false | RC4 separates `operation_ok`, `ok`, and `ready_for_use`; source-only results cannot set installation success |
| E-011 | Updating one pinned tag or immutable local snapshot cannot silently migrate to a different release | **Corroborated** | Claude's marketplace contract refreshes the configured source; RC3 content-addressed snapshots remain fixed, and a different RC4 snapshot is a source conflict | Cross-version migration requires explicit authorization, predecessor proof, fixed-scope replacement, postconditions, and rollback; unknown sources remain blocked |
| E-012 | An extracted GitHub/release archive cannot satisfy a Git-index-bound installer proof | **Corroborated** | Release archives contain package bytes but no `.git` revision/index; the installer intentionally requires both | Archives remain audit/reproducibility assets; automated installation starts from a clean immutable-tag clone |
| E-013 | User-scope plugin inspection executed from a plugin-declaring project can be contaminated by that project's settings | **Reproduced** | The same marketplace-list probe returned promptly from a neutral directory but stalled when its cwd was the RC4 repository containing the project bridge | All Claude CLI probes and mutations run from a fresh private neutral cwd; repository Git identity is read separately with explicit `git -C` |

## Release review

Before a stable release, review every entry touched by the release:

1. No changed normative or mechanical claim is unregistered.
2. Default hard gates and stable rules are Corroborated.
3. Observed/Reproduced trials are either kept in a prerelease with explicit scope,
   promoted with evidence, merged into an already-supported rule, or rejected.
4. Predictive entries remain non-blocking and have a test or instrumentation path.
5. Rejected claims are absent from active documentation and behavior, while their
   correction remains visible here.

---

# ACGM 证据登记表

本表跟踪的是**结论**的成熟度,不是某种说法出现得多不多。它防止一次事故、一条重复
提醒或一个听起来很好的解释,静默升级成通用规则。敏感 raw transcript 留在本机;公开
登记表只记录脱敏证据引用和限制。

**登记表复审:** 2026-07-14(ACGM V3 RC4 预发布准备)。

## 成熟度状态

| 状态 | 真正建立了什么 | 可以发布什么 |
|---|---|---|
| **Observed(已观察)** | 一次可追溯的真实事件 | 案例、埋点或限定范围的预发布试验——不能直接写成通用结论 |
| **Reproduced(已复现)** | 在有记录的条件下再次出现同类失效/机制行为 | 明确限制的预发布试验 |
| **Corroborated(已佐证)** | 独立观察,或观察 + 忠实复现,支持同一通用结论 | 经正常安全审查后进入稳定规范和默认行为 |
| **Predictive(预测性)** | 有推理依据、可测试,但尚无直接观察 | 元观察、测试计划或非阻断埋点 |
| **Rejected(已否决)** | 被反驳、归因错误或过度贴合单一事故 | 只保留历史记录;退出活跃结论/机制 |

状态属于一条结论。一个案例可以同时包含 Observed 的弱形态和 Predictive 的强形态。
状态变化采用 append-only:追加带日期的行或说明,不把旧判断改得像从未发生。

## 当前登记

| ID | 结论 | 状态 | 证据 | 限制 / 发布影响 |
|---|---|---|---|---|
| E-001 | "案例 1 是 ACGM 自己的 hook 拦下" | **Rejected** | 案例 1 归因审计:机械拦截来自第三方执行前 gate | 后续 grounding 与 ACGM 真值优先一致,但机械拦截不能算 ACGM 战绩 |
| E-002 | 高风险动作需要目标/状态/授权/postcondition 的当下证据 | **Corroborated** | 案例 1:凭印象的目标列表 + 与坏前提同源的自检;案例 9:过期操作别名 + 未核当前状态 | 机制只能检查子集;填满模板不等于有证据 |
| E-003 | 动作 started 或 exit 0 后仍负有动作后验证义务 | **Corroborated** | 案例 1:全绿自检仍会漏掉意图 postcondition;案例 9:后台服务启动后未跟到 verified | runtime 无法日后唤醒时,必须记 `pending verification`,不能承诺自动完成 |
| E-004a | 假装合规弱形态:仪式完整,事实却从摘要/印象继承 | **Observed** | 案例 9 的混合来源 grounding 报告 | 由摘要不作真值和证据归因覆盖 |
| E-004b | 假装合规强形态:agent 声称跑过验证工具,实际没跑 | **Predictive** | 只有原理推演;历史审计没有建立这个强形态 | 留在元观察;不得宣称已经发生,也不得仅凭它建默认硬门 |
| E-005 | 治理注入反复出现后可能被语义忽略 | **Predictive** | 设计假设;尚无可归因的饱和事件 | 指导低噪声埋点;不设固定触发次数阈值 |
| E-006 | "两事件 + 30 天"足以构成条款生命周期 | **Rejected** | 旧规则没有登记表、负责人、到期动作或发布门;时间流逝本身不能决定结论质量 | 改由成熟度状态 + 发布决策替代 |
| E-007 | 治理成效必须记录 initiator、动作前后、结果、验证和误报归因 | **Corroborated** | 案例 1 的机制归因更正;案例 9 是外部人审在风险链发生后发现 | Event Ledger 的活动次数不得包装成战绩 |
| E-008 | 已下载源码或已验证 plugin 记录/缓存，不等于目标运行时已经加载 hooks | **Observed** | RC3 安装器停在配置/缓存核验，而 reload 与 `/hooks` 仍只是后续步骤；一次真实 Desktop 安装尝试在下载/安装后被报告为不可用 | RC4 必须分别报告源码、配置、激活和项目治理；保留的 SessionStart health 事件只是历史旁证，不是目标 surface 激活证明 |
| E-009 | 调用者选择的 surface 名称不能覆盖更强的 Cloud/WSL 运行时证据 | **Reproduced** | RC4 修复前，显式 Local/CLI 与官方 Cloud 或 OS 级 WSL 信号矛盾时仍会返回自动 ready | RC4 以 `SURFACE_SIGNAL_CONFLICT` 失败关闭；未知 surface 仍需人显式选择目标 |
| E-010 | 规划/源码检查操作成功不等于安装成功 | **Reproduced** | RC4 修复前，manual UI 与 dry-run 会返回进程成功，但配置与运行时仍为 false | RC4 分开 `operation_ok`、`ok` 与 `ready_for_use`；只有源码不能设置安装成功 |
| E-011 | 刷新一个固定 tag 或不可变本地 snapshot，不能静默迁移到另一版本 | **Corroborated** | Claude marketplace 只刷新已配置来源；RC3 内容寻址 snapshot 保持不变，RC4 的不同 snapshot 会形成来源冲突 | 跨版本迁移必须显式授权、证明前任、限定 scope、核验 postcondition 并可回滚；未知来源继续阻断 |
| E-012 | 解压后的 GitHub/release archive 无法满足绑定 Git index 的安装证据 | **Corroborated** | Release archive 有包字节但没有 `.git` revision/index，而安装器有意同时要求二者 | Archive 仅供审计/复现；自动安装必须从 clean、固定 tag clone 开始 |
| E-013 | 在声明插件的项目 cwd 中检查 user-scope plugin 状态，会被该项目 settings 污染 | **Reproduced** | 同一 marketplace-list probe 在 neutral 目录快速返回，在含 project bridge 的 RC4 仓库 cwd 中停滞 | 所有 Claude CLI probe 与 mutation 都从新建私有 neutral cwd 运行；仓库 Git 身份另用显式 `git -C` 读取 |

## 发布复审

稳定版发布前,复审本次发布涉及的每个条目:

1. 改动过的规范或机械结论没有漏登记。
2. 默认硬门和稳定规则达到 Corroborated。
3. Observed / Reproduced 试验必须选择:明确范围继续留在预发布版、补证据晋级、并入
   已有成熟规则,或否决。
4. Predictive 条目保持非阻断,并有测试或埋点路径。
5. Rejected 结论退出活跃文档与行为,但更正记录继续留在本表。
