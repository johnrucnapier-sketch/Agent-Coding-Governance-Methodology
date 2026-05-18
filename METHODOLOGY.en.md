# A Governance Methodology for Claude Code Projects

> **This is a shareable, general-purpose methodology** — it contains no business
> specifics of any concrete project.
> Audience: teams doing **multi-session, long-horizon, possibly multi-person /
> multi-branch** software development with Claude Code (or a comparable AI coding agent).
> It solves one specific problem: **AI-driven development rots over time, and the rot
> is structural and unavoidable — unless there is governance.**
>
> This is the logic distilled from a real project (a dozen-plus version iterations,
> dozens of sessions, ~2 billion tokens burned) and its mistakes.
> Take it and instantiate it to your own project. **Abstract principles first, the
> hands-on recipe after.**

---

## 0. In one sentence

Store "facts" and "rules" separately; rules constrain how the AI works, facts are
regenerated only from code; every session verifies the current state before acting;
no working from impression, no detouring, no overstepping, no letting the trunk rot.

---

## 1. Why multi-session AI development rots (know the enemy first)

A single session has limited context. Once a project runs long, you keep opening new
sessions, writing handoff docs, asking the AI to summarize progress. Rot starts here,
through five mechanisms:

1. **Context loss**: a new session does not know what happened before; it rebuilds
   from handoff docs and "memory" — and rebuilding necessarily distorts.
2. **Fabrication from impression**: when the AI writes handoffs/docs it tends to
   summarize from residue in the conversation context rather than reading the code's
   ground truth. An early, already-abandoned claim happens to be sitting in context,
   so it gets written into the doc as "the current state".
3. **Append-only updates**: the AI tends to add paragraphs and not delete old ones.
   An overturned old plan lies in the doc with no "deprecated" marker; the next
   session reads it and goes wrong.
4. **Handoff contamination propagation**: handoff for direction A carries A-specific
   temporary detours; direction B takes it wholesale and drifts.
5. **Trunk rot**: governance/truth grows on some feature branch while the trunk is
   abandoned in a very old state. A new session landing on the old trunk = reading
   entirely wrong information.

**The key realization: none of the above is "operator error" — it is the natural cost
of this workflow.** Every large-span migration (platform switch, stack replacement,
person handoff, version freeze) is a rot blowout point. The goal of governance is not
to eliminate rot (impossible) but to **make rot visible, interceptable, reversible.**

---

## 2. The four drift types (the diagnostic core, the most worth migrating)

Group all rot into four types. Each has its own line of defense. Any session that
touches one of them must stop and run the corresponding process.

| Drift type | What's wrong | Typical signs | Defense |
|---|---|---|---|
| **① Implementation drift** | Detours when the tech is hard | hand-rolled polyfill faking a native capability, downgrading an API, silently swallowing errors in try-catch, bending the business to fit a bug | **Detour ban**: root-cause first; exploratory hacks need explicit human authorization + a record + a deadline |
| **② Cognitive drift** | Writes docs from impression, doesn't verify ground truth | "should be X" / "I recall it's X", copying technical conclusions from old docs/handoffs, no source given | **Truth-first**: any technical conclusion must grep/read code with `file:line`; if you can't cite, mark it explicitly "unverified" |
| **③ Structural-placement drift** | Governance/truth lives in the wrong place; trunk rots | constitution/rules grow on a feature branch; trunk abandoned in an old state; a new session on the old trunk reads all-wrong | **Governance home**: govern only on the trunk; the trunk is never allowed to rot; sub-dir rule files are thin pointers only |
| **④ Scope drift** | Content that shouldn't be in this repo creeps in | business operations / commercial strategy / non-software content accumulating in the code repo | **Scope boundary**: explicit IN/OUT; criterion "for software to ship/run = IN, for anything else = OUT" |

This table is the diagnostic dashboard for the whole methodology. **First learn to
recognize which type it is, then talk about how to fix it.**

> Meta-lesson (the strongest proof): this anti-drift system **committed drift ②
> against itself while it was being built** — the builder copied a pile of technical
> conclusions out of old handoff docs without reading the code. This is exactly the
> proof: **discipline is not for "other people", it is for you, every single time you
> write something right now.** Take a real incident like this from your own project
> and write it permanently into the governance file as a cautionary case — it is ten
> times more useful than an abstract rule.

---

## 3. Principle One: store content layered by "lifecycle"

The root cause of rot is **content with different lifecycles piled together and
cross-contaminating**: product vision (almost never changes), architecture decisions
(replaced when they change), current state (changes constantly), historical archive
(immutable) — all mixed in one file, and a new session cannot tell which is
"constitution" and which is "snapshot".

Solution: physical layering. Each layer has a different change frequency, write rule,
and who can change it.

| Layer | Content | Change freq | Write rule | Who can change |
|---|---|---|---|---|
| **Constitution** | non-negotiable principles, redlines, role boundaries, scope boundary | almost never | overturning a clause needs an amendment process | **only the project owner (a human)** |
| **Decision log (ADR)** | one file per architecture/tech/product decision | append-only | don't edit old ones; an overturned one is marked "superseded by X" or "withdrawn", **original text not deleted** | AI writes, human reviews |
| **Current-state snapshot** | architecture/interface/config as-is | synced with code | **regenerated by code scan**, not incrementally edited; top-stamped "generated from commit X on Y" | script/AI regenerates |
| **Version archive** | full state at each freeze | frozen at freeze | immutable | locked after writing |
| **Cross-cutting contract** | protocols multiple ends/modules must strictly align on | change one place, three-way impact | a change must explicitly declare blast radius + verification + human approval | bound by strict process |
| **Live handoff** | session relay still in effect | archived when stale | move to history when stale | AI writes |

Two history zones that are easy to confuse but must be separated:
- **Completed archive**: a record of facts that did happen (old session reports etc.).
  It is "history"; read-only.
- **Overturned docs**: a whole doc once thought right, now wrong. Must carry a
  "superseded by X" banner at the top.

> Telling them apart matters: history can be browsed safely; misreading an overturned
> doc will kill the next session.

---

## 4. Principle Two: the project root rules file = meta-rules + pointers + behavior constraints, **never facts**

Most teams treat the "project description file" (in Claude Code, `CLAUDE.md`) as a
compendium of facts: architecture, database choice, deploy method, model version… all
written in. **This is the number-one source of rot** — restating, in the description
file, something you could re-derive from the code, manufactures a second drifting
source of truth.

The right way:

- **Things that don't change** (product positioning, hard constraints, things not to
  do) → into the constitution.
- **Facts that change** (architecture, interfaces, config, versions) → **write no
  answer, write a pointer**: "the truth for X lives at `code path`, read it before
  changing."
- The root rules file itself holds only three things:
  1. **Meta-rules**: how to maintain this file itself (check `git log` before
     editing; no inlining facts; overturning a clause must delete the old text, not
     stack on top)
  2. **Pointers**: where to find the truth (pointing to code / each layer's docs)
  3. **Behavior constraints**: the working discipline every session must obey

The shorter the root rules file, the better; the longer it is, the easier it hides
fossils. It degenerates into a "protocol layer", it carries no knowledge.

---

## 5. Principle Three: truth-first (the absolute version, no grey zone)

Any technical conclusion written into a doc / commit message / code comment / report
to a human:

- ❌ Not allowed from conversation-context memory
- ❌ Not allowed to copy technical conclusions from "history archive / overturned docs
  / old handoffs / old version snapshots"
- ❌ Not allowed to use phrasing like "should be" / "usually" / "I recall" / "by
  convention"
- ❌ Not allowed to write a technical conclusion without a `file:line`
- ✅ Must grep / read the code · config · schema ground truth; every conclusion
  carries its source
- ✅ When you cannot read the truth, you must say plainly "I did not read X, this
  conclusion is not trustworthy" — **fabrication not allowed**

**Self-check redline**: the moment "I recall" / "should be" surfaces in your head, or
you want to cite an old doc → stop immediately, go verify. Wrote a paragraph with no
source → delete it or add the source.

This one must be made **absolute**, it cannot be softened. The instant you leave a
"usually the case" loophole, drift crawls in through it.

---

## 6. Principle Four: the session-start grounding ritual (verify before you act)

Every session (new / resumed / picking up a half-done task) must run, before starting:

1. **Read the constitution + the root rules file** (mandatory, no skim-reading)
2. **Determine which track/scope this session falls in** (see Principle Six), and
   additionally read that layer's docs
3. **Report 5 things, then wait for the human to confirm before acting**:
   - which track I'm in
   - the current state shown by `git log` + `git status`
   - the relevant structure I saw from actually reading the code (not from impression)
   - the list of files I intend to change (concrete paths)
   - the execution steps I intend to take
4. After changes, run the verification scripts
5. Closing report + commit draft, wait for human approval before committing

Make this into a **generic startup phrase**, solidified into a file. Paste it as the
first line of any session, append the concrete task at the end. This way you don't
re-explain the rules every time; a new session auto-joins governance. **This step cuts
more than half of handoff cost.**

> Key: **restate first, then act.** The deviation exposed at the restate stage is an
> order of magnitude cheaper than the one found after the code is written.

---

## 7. Principle Five: don't over-execute (expose ambiguity, don't barrel through)

When an instruction is ambiguous, the AI tends to "guess the least-effort
interpretation and finish the job". This turns a vague "delete it" into "destroyed
content the user never evaluated".

Rules:
- Before an instruction involving an **irreversible operation** (delete file/branch/
  history), if there is any ambiguity or it rests on an unverified assumption,
  **verify; if it doesn't check out, stop and ask.**
- If you find a change's blast radius is bigger than it looks (touches many docs,
  includes tracked decisions), **list the blast radius and let the human decide** —
  do not decide for them.
- Destructive operations need a **hard human checkpoint**: list + write the rollback +
  quote the authorization verbatim. Bypassing a safety checkpoint is itself drift ①.
- Separate "the user's business judgment" from "the AI's execution": the former
  (whether to do a thing, whether some content has value) is the human's; the AI only
  does the decided thing correctly.

> Real payoff: an AI that "stops to confirm" reworks far less than one that "charges
> ahead". Rework is the most expensive token.

---

## 8. Principle Six: isolate work by "track"

Work of different natures has different cognitive contexts, verification methods, risk
profiles, rollback mechanisms. Mixing them in one session makes decisions interfere
with each other and post-hoc attribution hard.

Per your project's reality, split work into several **tracks**. Each track:
- has its own working-directory scope
- has its own verification method (code via tests/build; content/AI-behavior via an
  eval set / baseline)
- has its own risk profile (a code bug is a hard failure, locatable; a quality
  regression is a soft failure, hard to spot)
- one session works in one track only; a cross-track task is split into consecutive
  sessions

> Example (illustrative only, change it to your project): a typical project splits at
> least a "code track" and a "content/AI-behavior track". If the product's core value
> is AI behavior itself (prompt/knowledge/retrieval), that track must have an
> **evaluation baseline** — otherwise every prompt tweak is by feel, quality
> regressions are found late, losses are large. **Build the eval infrastructure
> before AI behavior becomes the main battlefield.**

Physical isolation means (as needed, light to heavy):
- one sub-dir rules file per track (thin pointer + that dir's specific rules);
  entering a dir auto-lands you on that track
- only go to worktrees when concurrency is truly high (parallel dirs that don't step
  on each other)
- worktrees coordinate via contract files, not verbal handoff

---

## 9. Principle Seven: one trunk, never rotting

- **A single trunk** (usually `main`) is the canonical source of the project's
  current truth.
- **The trunk is never allowed to rot**: being de facto replaced by a feature branch
  while the trunk stalls = a violation.
- **Governance/general-truth files are authored only on the trunk.** Feature branches
  only consume; to change governance → propose → land on the trunk → feature branch
  syncs. Authoring governance on a feature branch = the root error of
  structural-placement drift.
- Feature branches fork from the trunk, develop in isolation, merge back when done.
- If any session start finds itself on a rotten trunk / governance lagging behind
  some branch → stop immediately and report, do not "make do".

> This is the most counter-intuitive one and the most often violated. The governance
> system, the first time, is often built on a feature branch — because the moment you
> start building governance, you happen to be doing some feature. Move it home to the
> trunk as early as possible.

---

## 10. Principle Eight: scope boundary

Be explicit about what content belongs in this development repo.

- **Criterion in one sentence**: is this for the **software to be developed/shipped/
  run**, or for **something else** (how the company operates, commercial strategy,
  planning unrelated to software)? The former is IN, the latter is OUT.
- Technical infrastructure (domain/email/deploy/compliance filing etc. directly
  bearing on whether the software can ship and run), though it has "non-code"
  elements, serves the software → IN.
- Pure operations/strategy/org decisions → OUT, not authored or tracked in this repo;
  anything already mixed in is, after confirmation, deleted or moved out.
- The AI does not proactively produce, in the dev repo, content that doesn't belong here.
- Boundary in doubt → apply the criterion; still unclear → stop and ask, **do not
  unilaterally widen a deletion**.

---

## 11. Authority and revision model

- **Only a human can change the constitution.** An AI attempting to change the
  constitution = a violation. New clauses are appended, dated, with the triggering
  case noted; existing numbering is not moved; overturning a clause is explained in
  the revision log.
- **Decisions go through ADRs.** One decision per file, append-only.
- **Superseded vs. withdrawn must be distinguished**:
  - *Superseded*: the decision is still valid, just replaced by a newer decision →
    mark `Superseded by ADR-NNNN`
  - *Withdrawn*: the decision itself is void, not replaced → mark `Withdrawn`
- Cross-cutting contract changes: must be a separate commit + written blast radius +
  verification run + human approval before merge.
- Important boundary/scope rulings also leave a traceable record (append to the
  relevant ADR is fine).

---

## 12. The hands-on recipe (bootstrap on a new project)

Build in this order, from minimum-viable to complete:

**Step 0 · Audit first (read-only, no code)**
Open an audit-only session: read all existing description files + history handoffs,
compare against the current code. Output three lists: ① still valid ② outdated, to
delete ③ contradictory, needs a human ruling. This output is the input to the
refactor that follows.

**Step 1 · Build the constitution**
Write the unchanging parts of "still valid" (redlines, role boundaries, scope
boundary, the four-drift defenses) into the constitution. Only a human can change the
constitution.

**Step 2 · Rewrite the root rules file**
Cut every fact, keep only: meta-rules + pointers + behavior constraints. Hold it to
about one page.

**Step 3 · Build the decision log**
Build an ADR directory + template + index. Backfill the key decisions that already
happened into ADRs (post-hoc backfill marked "reconstructed from then-known info", and
be especially wary of drift ②). Mark overturned ones clearly Superseded/Withdrawn.

**Step 4 · Build the snapshot mechanism**
The current-state doc is **generated by code scan**, top-stamped "based on commit X".
Write a few **drift-check scripts** alongside (even just grep verifying the doc
matches the code) — scripts built together with docs, not after.

**Step 5 · Build the startup-phrase file**
Solidify Principle Six's grounding ritual into a generic startup phrase + a few
typical scenario templates. From then on, just copy it when opening a session.

**Step 6 · Draw tracks + scope boundary**
Split tracks per your project's reality, one thin sub-dir rules file per track. Make
IN/OUT explicit.

**Step 7 · Make periodic audit a habit**
Re-run the snapshot at each version freeze; re-run the root-file audit every few
versions. Make "make rot visible" a periodic mechanism.

> On a project that has already accumulated significant scale, spending 1–2 days on
> this refactor is high-return — the repeated reconciliation and tokens saved on each
> subsequent version are substantial.

---

## 13. Failure modes & self-check list

This system itself will also be violated. Common failures:

- Facts written back into the root rules file → Principle 4 breached
- Technical conclusions from impression, no source → Principle 5 breached (most frequent)
- Session acts directly without grounding → Principle 6 breached
- A vague instruction barreled into irreversible destruction → Principle 7 breached
- Governance grown on a feature branch again, trunk rotting → Principle 9 breached
- A cross-cutting contract changed silently, undeclared → §11 breached

**Redline for reviewers**: see any "I think / should / usually / I recall" phrasing,
any technical conclusion with no source, any overturned doc cited as truth — reject
directly, no discussion.

---

## 14. What to take as-is, what to adapt to your project

**Take as-is (general)**:
- Section 1 problem diagnosis, Section 2 four-drift classification
- Principles 3–7 (layering / root file holds only rules / truth-first / grounding
  ritual / no over-execution)
- Principle 9 (one trunk, no rot), §11 authority model, §12 hands-on recipe,
  §13 self-check

**Instantiate to your project (specific)**:
- How **tracks are split** in Principle 8 (depends on where your project's core value
  is, how many cognitive contexts you have)
- The concrete IN/OUT list of the Principle 10 scope boundary
- Exactly which protocols the cross-cutting contracts are (multi-end? multi-service?
  API? data format?)
- The concrete directory naming of each layer's docs, ADR numbering rules, what the
  verification scripts do
- The concrete content of the redlines (this is decided by your product/compliance)

> Principles are the skeleton, portable; the flesh is your project's own. **Don't copy
> someone else's track split / contract list** — that is another project's
> specificity, copying it is just another kind of drift.

---

## 15. A paragraph for the skeptical colleague

> "This looks heavy, is it really necessary?"
>
> At a certain scale (multi-version, multi-session, possibly multi-person/
> multi-branch), the rot of AI-assisted development is not a question of whether but
> of when. Once rot sets in, the time you spend on handoff reconciliation, information
> verification, and rework grows exponentially, and project velocity instead gets
> slower and slower.
>
> A workflow that cuts 30% of repeated work and rework is equivalent to a free,
> faster, cheaper model. The 1–2 days of structural investment up front buys you 6–12
> months of not being repeatedly dragged down by the same class of problem.
>
> The ROI of this methodology is far higher than agonizing over which model to pick.

---

## Appendix: the origin and boundary of this methodology

- This text is the **logical skeleton** distilled from the governance practice of a
  real long-horizon project, with all of that project's business specificity stripped.
- It is not theory, it is sediment from mistakes — including the meta-level crash of
  "violating governance while building the governance system".
- **On cost (untested, the author's judgment)**: this discipline likely consumes
  *more* tokens per task — more reading code, verifying, restating, stopping to
  confirm — but it buys fewer errors and fewer wrong turns, compressing the most
  expensive part: rework. The author is not token-constrained and has not measured
  it; assess the actual delta on your own project.
- Your project's specificity differs; **when instantiating, redesign the tracks and
  contracts, do not copy the concrete lists.**
- This file itself should also be governed by its own rules: it is methodology (the
  rule layer), it holds no concrete facts; before changing it, be clear whether you
  are changing "general logic" or "some project's specificity" — the latter should
  not enter this file.
