---
name: add-feature
description: Turn a new idea or change request into roadmap features and a proposed spec change, without implementing anything.
argument-hint: "<the idea>"
disable-model-invocation: true
---

# Plan a new feature (no code)

Idea: $ARGUMENTS

1. **Read only what you need:**
   - `node .claude/scripts/roadmap.mjs next` for roadmap status.
   - `grep -n '^## \|^- \[' docs/ROADMAP.md` for the item list.
   - `node .claude/scripts/spec.mjs --toc`, then `spec.mjs "<Heading>"` for the sections the idea touches, including anything marked out of scope.
   - `docs/design/DESIGN.md` if the idea is visible.
   - Grep `docs/DECISIONS.md` for the topic.
   - Never read ROADMAP.md or spec.md whole.
2. **Classify** the idea and say which it is:
   - **new**: the spec doesn't cover it
   - **change**: it alters something the spec defines
   - **contradiction**: it conflicts with a **[decided]** item, the audience and locale lock, the design lock, or a "Never break" invariant. Name the conflict. A change to the audience, locale or look after launch is expensive (it touches every screen and test); say so plainly.
3. **Clarify:** ask me up to 3 questions with AskUserQuestion, only where the answer changes the plan.
4. **Propose spec wording:** add it under `## Proposed spec changes` in `docs/DECISIONS.md`. Give the date, the target section, and the exact text to add or replace. Tell me to apply it to `docs/spec.md` myself. Never edit spec.md.
5. **Schedule:** insert new feature entries into `docs/ROADMAP.md` in the right milestone and order. Use the exact line format, `Spec:`, `Depends:`, concrete `Done when:` bullets and `Tests:`. Anything that ships only after my explicit approval (content I must review, a paid service) gets a `- Gate: <what I approve>` line, not a Done-when bullet. Use the next free ID, or a letter suffix (`F21a`) to slot between existing features. Each must fit one session (≤ ~10 files, ~600 lines). Read only the region you insert into (`grep -n`, then Read with offset/limit).
6. **Commit** only `docs/`: `docs: plan <idea>`. Do not push.
7. Report the new IDs and where they sit, then stop.

Never write app code, tests, or config in this skill.
