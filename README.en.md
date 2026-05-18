# Claude Code Governance — a governance system for multi-session AI development

> One sentence: long-horizon AI-driven development **rots structurally** — unless
> there is governance.
> This is a migratable governance logic distilled from a real project (a dozen-plus
> versions, dozens of sessions, ~2B tokens of mistakes) + a ready-to-use Claude Code
> plugin.

[中文版 / Chinese: `README.md`]

---

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

---

## Core: the four drift types (the mental model most worth taking with you)

| Drift | What's wrong | Defense |
|---|---|---|
| **① Implementation** | detours when the tech is hard (hand-rolled polyfill / downgrade / silent error swallow) | Detour ban: root-cause first |
| **② Cognitive** | writes docs from impression, doesn't verify | Truth-first: conclusions carry `file:line`, ban "I recall / should be" |
| **③ Structural placement** | governance on the wrong branch, trunk rots | govern only on the trunk; trunk never allowed to rot |
| **④ Scope** | content that shouldn't be in the repo (ops/strategy) creeps in | scope boundary: for software to ship = IN, for anything else = OUT |

First learn to **recognize which type it is**, then talk about how to fix it.

---

## The eight principles (see `METHODOLOGY.en.md`)

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

## Repo structure

```
README.md / README.en.md          ← what you're reading (WHY + index), bilingual
METHODOLOGY.md / METHODOLOGY.en.md ← full methodology (8 principles + bootstrap + failure modes)
.claude-plugin/
  plugin.json                     ← this repo IS a Claude Code plugin
  marketplace.json                ← for /plugin marketplace add install
hooks/hooks.json                  ← SessionStart hook (the ONLY automatic mechanism)
scripts/grounding-inject.sh       ← the hook injects a thin grounding directive → skills below
skills/
  session-grounding/SKILL.md      ← invoke at: session start/resume — 5-step grounding + report first
  truth-first/SKILL.md            ← invoke at: before a technical conclusion / irreversible op — force sources
  governance-bootstrap/SKILL.md   ← invoke at: bootstrap governance from zero — human-driven 8-step checklist
templates/                        ← fully blank generic skeletons, zero business
  CONSTITUTION.skeleton.md  ADR._TEMPLATE.md  SESSION_START.skeleton.md  drift-check.stub.js
LICENSING.md / LICENSE-DOCS / LICENSE-CODE  ← dual-track: docs CC-BY-4.0, code MIT
PUBLISHING.md                     ← beginner-grade publishing runbook
```

---

## Quick start

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
   **Skills themselves do not auto-fire — they are invoked by the Skill tool.** (This
   is the methodology's own Principle 5, truth-first, applied to this repo itself: do
   not overclaim automation.)

---

## ⚠️ Adaptation guide: take as-is vs. must adapt to your project

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

---

## Real background (the strongest credibility)

This system **committed drift ② against itself while being built** — the builder
copied a pile of technical conclusions out of old handoff docs without reading the
code, and was caught in the act by the project owner. That is exactly the proof:
**discipline is not for "other people", it is for you, every single time you write
something right now.** Writing a real incident like this permanently into the
governance file as a cautionary case is ten times more useful than an abstract rule.

---

## License / maintenance stance

- License: **dual-track** — the methodology/docs (`METHODOLOGY*.md`, `README*.md`,
  the prose of each `SKILL.md`) under **CC-BY-4.0**; the code/mechanical parts
  (`scripts/`, `hooks/`, `templates/`, `.claude-plugin/`) under **MIT**. See
  `LICENSING.md`.
- Maintenance: a methodology share — issues/PRs welcome, but **self-adaptation is the
  norm; no heavy support promised.**

## Acknowledgements

Distilled from the governance practice of a real long-horizon AI-driven development
project. All business specificity stripped — this repo **contains, and will never
accept,** any concrete project's business/confidential content (this is itself an
application of §④, the scope boundary).
