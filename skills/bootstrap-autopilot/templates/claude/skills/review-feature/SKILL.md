---
name: review-feature
description: Independent review of uncommitted changes for the in-progress roadmap feature against docs/spec.md. Use after a feature is implemented and verified, before committing.
context: fork
agent: spec-checker
background: false
---

# Review the in-progress feature

You cannot see the conversation that built this feature. Work only from the files.

## 1. Find the feature
- Run `node .claude/scripts/roadmap.mjs next`. Its "In progress" line names the `[~]` item (a feature `F..` or a bug `B..`), and its entry follows: Spec, Depends, Done when, Tests. Do not read `docs/ROADMAP.md` whole.
- Run `node .claude/scripts/spec.mjs <ID>` for the cited `docs/spec.md` sections (never read spec.md whole), and grep `docs/DECISIONS.md` for related entries.
- If no item is `[~]`, say so and stop.

## 2. Read the changes
- `git diff HEAD` for tracked changes.
- `git status --short` and read every untracked file in full.
- Read surrounding code where you need context to judge a change.
- Run the tests yourself to see them pass or fail.

## 3. Check four areas
- **Done when:** every bullet is met. Name the evidence: a test name, a code path, or a command output.
- **Spec conformance:** names, shapes, states and transitions, limits and timings exactly as the cited sections say; DECISIONS rows respected.
- **Invariants** (CLAUDE.md, "Never break"):
{{NEVER_BREAK_MD}}
- **Tests and quality:** would each test actually fail if the code broke? Are the spec's edge cases covered? Is the code clear, and does it match the surrounding code? No real keys, no network calls to real services in tests.

## 4. Output, in this order
1. Verdict: `PASS`, `PASS WITH FIXES`, or `FAIL`
2. **Must-fix:** each with `file:line`, why it matters, and the fix
3. **Should-fix:** same format, lower stakes
4. A ✔/✘ checklist of the Done-when bullets, one line each, with the evidence

## 5. Never edit files
This review is read-only. Do not write, edit, stage or commit anything.
