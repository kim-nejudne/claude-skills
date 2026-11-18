---
name: next-feature
description: Build the next feature from docs/ROADMAP.md end to end — plan, implement, test, review, log, commit. Run in a fresh session after /clear.
argument-hint: "[feature id, e.g. F07 — optional]"
disable-model-invocation: true
---

# Build the next roadmap feature

Requested feature: $ARGUMENTS (if empty, pick the next eligible one).

## 1. Orient
- Run `node .claude/scripts/roadmap.mjs next $ARGUMENTS`. It prints roadmap status, the feature to build (full entry), and the newest 3 entries of `docs/PROGRESS.md`. Do not read `docs/ROADMAP.md` or `docs/PROGRESS.md` whole.
{{^MONOREPO}}
- Run `git status --short` and `git log --oneline -5`.
{{/MONOREPO}}
{{#MONOREPO}}
- Run `git status --short -- .` and `git log --oneline -5 -- .`. This app is `{{APP_DIR}}/` of a monorepo: changes elsewhere in the repo are not yours; ignore them and never stage them.
{{/MONOREPO}}
- If there are uncommitted changes, STOP. List them and ask me whether to resume, commit, or discard. Never discard on your own.
- If a feature is marked `[~]`, it is unfinished from an earlier session. The script picks it; resume it instead of starting another.

## 2. Pick
- Use the feature the script printed. If it warns about unfinished dependencies or a gate on a requested ID, tell me and ask before building.
- If nothing is eligible, tell me why (done, blocked, or waiting on a gate) and stop. Never run `roadmap.mjs ungate`: gates are Kim's approvals.
- Run `node .claude/scripts/roadmap.mjs mark <ID> '~'`.

## 3. Load context
- Run `node .claude/scripts/spec.mjs <ID>` for the cited `docs/spec.md` sections. Never read spec.md whole. Need another section? `spec.mjs --toc`, then `spec.mjs "<Heading>"`.
- Anything visible: read `docs/design/DESIGN.md` and the mock it names for that screen. The mock is the target; the spec and DESIGN.md win where they disagree with it.
- Read the relevant entries in `docs/DECISIONS.md` (grep for the topic first) and the existing code you will touch.
- For broad code searches, use the Explore subagent so file dumps stay out of this conversation.

## 4. Plan
Post a plan of 15 lines or fewer: files to touch, approach, tests to write, and how each "Done when" bullet will be proven.
- If a choice is genuinely mine (ambiguous spec, a UX trade-off, a significant new dependency), ask with AskUserQuestion, at most 3 questions. Otherwise pick the simplest option that meets the spec, log it in DECISIONS.md, and continue without waiting.
- A new dependency needs a one-line justification in the plan and in the PROGRESS entry.
- If the feature is too big for one session, split it in ROADMAP.md (F07a/F07b), tell me, and build only the first part. Find the entry with `grep -n` and Read only that region before editing.

## 5. Implement
- For pure logic, write the tests first. Work in small steps and keep the app runnable.
- Follow `CLAUDE.md` and `.claude/rules/`.
- External services: code reads keys from environment variables and talks to them through one module each. Tests and development use a fake of that module. Never ask for, read or write a real key; `.env*` is off-limits. A new env var goes into `.env.example` in the same feature; mark it `# optional` on its line if the app starts without it. {{#DEPLOYS}}The deploy refuses to start while a required one is unset {{#ON_DROPLET}}on the droplet{{/ON_DROPLET}}{{#VERCEL}}in the Vercel project's production env{{/VERCEL}}, and Kim sets it there (add a Kim check naming it).{{/DEPLOYS}}{{#NO_DEPLOY}}Kim sets it in his own environment (add a Kim check naming it).{{/NO_DEPLOY}}
- Stay in scope. Put ideas and nice-to-haves under `## Backlog` in ROADMAP.md, not in the code.

## 6. Verify
- Run the `verify` skill and fix until every stage is green.
{{#WEB}}
- If the feature has UI, run the `playtest` skill with the feature ID. If the harness or a browser is unavailable, write exact manual test steps instead.
{{/WEB}}
{{#ANDROID}}
- If the feature changes phone UI, its Robolectric Compose tests drive the screen and call `captureRoboImage()` for each changed screen (at DESIGN.md's phone size, and at 1.3× font scale where text is dense). After `verify`, Read those PNGs under `android/app/build/outputs/roborazzi/` and fix what looks wrong. Device-only behaviour (camera, torch, OCR accuracy, install and update, real offline use) goes behind its interface with a fake, plus a Kim check.
{{/ANDROID}}
- Check every "Done when" bullet and note the evidence for each (test name, playtest step, command output).
- A bullet only a person can check (real devices, real accounts or keys, "Kim has reviewed …") does not block: build everything around it, then add exact steps under `## Kim checks` in `docs/PROGRESS.md` (`- [ ] F07: steps · what to look for`).
- If the same failure survives 3 genuine fix attempts, stop. Run `node .claude/scripts/roadmap.mjs mark <ID> '!' "<what blocks it>"` and report what you tried.

## 7. Review
- Run the `review-feature` skill (spec-checker).{{#HAS_REVIEWERS}} In parallel, in the same message, spawn {{REVIEWER_FANOUT}}. Give each the feature ID; they read the diff themselves.{{/HAS_REVIEWERS}}
- Fix every Must-fix, then re-run `verify`.
- Fix small Should-fix items now. Move larger ones to Backlog.

## 8. Record
- Add a PROGRESS.md entry right under the `<!-- entries below, newest first -->` marker, using the template. Find it with `grep -n` and Read only that region.
- Add any new decisions to DECISIONS.md, and check that every `DECISIONS N` you cited in code exists.
- Run `node .claude/scripts/roadmap.mjs mark <ID> x`. This collapses the entry to its checkbox line, so the PROGRESS entry must carry anything worth keeping.
- Update CLAUDE.md only if commands or invariants changed.

## 9. Commit
One commit for the feature: `feat: F07 <title>` (bugs: `fix: B03 <title>`). Stage by path (`git add -- <paths>` or `git add -A` after checking `git status`); never stage `.env*`. Do not push.
{{#MONOREPO}}
Monorepo: stage only this app and the root files the feature names (`git add -- . {{ROOT_REL}}.github/workflows/ci.yml`); never a bare `git add -A`, which would take other projects' changes too.
{{/MONOREPO}}

## 10. Hand off, then stop
Reply with:
- What was built (2–4 bullets)
- How to try it: exact commands, URLs, and which devices to use
- Decisions you made, and anything you need from me
- The next feature's ID and title
- The line: **Run `/clear`, then `/next-feature`.**

Do not start the next feature.

## Never
- Edit `docs/spec.md` or `scripts/autopilot.sh`, or run `roadmap.mjs ungate`
- Disable, skip, or weaken tests or checks
- Commit with failing checks
- Build more than one feature
- Push, deploy, ssh, scp{{#ON_DROPLET}}, or run docker against the droplet{{/ON_DROPLET}}{{#VERCEL}}, or run the vercel CLI or any Vercel MCP tool{{/VERCEL}}
