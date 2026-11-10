# {{APP_TITLE}}

{{APP_PITCH}}

Stack: {{STACK_SUMMARY}}. Live at {{LIVE_URL}} (Kim's droplet, `127.0.0.1:{{PORT}}`).

Read in this order, through the scripts. Never read ROADMAP.md, PROGRESS.md or spec.md whole:

1. `node .claude/scripts/roadmap.mjs next [ID]`: roadmap status, the feature's entry, and the newest 3 PROGRESS entries.
2. `node .claude/scripts/spec.mjs <ID>`: only the spec sections that feature cites. Use `--toc` to find others, then `spec.mjs "<Heading>"`.
3. `docs/DECISIONS.md`: grep for the topic.
{{#UI}}
4. `docs/design/DESIGN.md` for anything visible, and the mock it names under `docs/design/`.
{{/UI}}

Change roadmap markers with `roadmap.mjs mark <ID> <todo|~|x|!> [note]`. Marking `x` collapses the entry to one line. A `Gate:` line is Kim's approval; never remove it (`roadmap.mjs ungate` is Kim's).

## Repository

{{^MONOREPO}}
- Standalone {{REPO_VISIBILITY}} repo `{{GH_REPO}}`. Commit messages: `feat: F07 <title>`, `fix: B03 <title>`, `docs: …`, `chore: …`.
- `.claude/`, `CLAUDE.md` and `.env*` are gitignored and stay local. Docs, the roadmap, `scripts/autopilot.sh` and the workflows are committed.
{{/MONOREPO}}
{{#MONOREPO}}
- This app is `{{APP_DIR}}/` of the {{REPO_VISIBILITY}} monorepo `{{GH_REPO}}`. Work, run commands and stage files from this directory. Commit messages: `feat: F07 <title>`, `fix: B03 <title>`, `docs: …`, `chore: …`.
- Other projects in the repo are read-only references: copy patterns, never import across projects or edit them. The only root files this app touches are `{{ROOT_REL}}.github/workflows/ci.yml` (its jobs), `{{ROOT_REL}}.github/workflows/{{WORKFLOW_FILE}}` and its row in `{{ROOT_REL}}README.md`{{#HUB}}, plus its spoke in `{{ROOT_REL}}{{HUB_DIR}}/` (a gated feature){{/HUB}}.
- `git status -- .` and `git add -- <paths>`; never a bare `git add -A`, which would take other projects' changes. The autopilot builds in a worktree on branch `{{BRANCH}}` and pushes only commits inside these paths.
- `.claude/`, `CLAUDE.md` and `.env*` are gitignored and stay local; never commit them (the repo's history was purged of agent files once). Docs, the roadmap and `scripts/autopilot.sh` are committed.
{{/MONOREPO}}

## Commands

```
{{COMMANDS_BLOCK}}
```

{{#ANDROID}}
Phone app: `android/` is its own Gradle build. Run Gradle from this directory as `android/gradlew -p android <task>`. No emulator or device here and no adb: phone UI is proven with Robolectric Compose tests, and each changed screen gets a Roborazzi screenshot (`android/app/build/outputs/roborazzi/`). Camera, torch, OCR accuracy, APK install and update, real offline use and background sync on a real phone are Kim checks. The release APK ships inside the image ({{APK_FEATURE}}, `scripts/apk-release.sh`); its signing key never exists locally.

{{/ANDROID}}
Deploy target: {{LIVE_URL}} via `{{#MONOREPO}}{{ROOT_REL}}{{/MONOREPO}}.github/workflows/{{WORKFLOW_FILE}}` (written by {{DEPLOY_FEATURE}}). `scripts/autopilot.sh` pushes and deploys once, at the end; sessions never do.

## Never break

{{NEVER_BREAK_MD}}
- **No real keys in sessions.** Code reads secrets from environment variables. Tests and development use fakes. Real keys exist only in the droplet's `.env` and GitHub secrets. Never read or write `.env*`.

## Working rules

- One feature per session.
- Never edit `docs/spec.md`. A hook blocks it. Never create `.claude/spec-unlocked`. Never edit `scripts/autopilot.sh` (also blocked).
- Record spec gaps in `docs/DECISIONS.md`. Add a `// SPEC-QUESTION:` comment at the code site.
- Logic ships with tests, written first for pure logic.
- Justify any new dependency in one line, in the plan and in the PROGRESS entry.
- Make one commit per feature. Do not push.
- Never weaken, skip or delete tests to get green.
- Nice-to-haves go under `## Backlog` in `docs/ROADMAP.md`, not into code.
- Checks only Kim can do (real devices, real accounts or keys, reviewing content) go under `## Kim checks` in `docs/PROGRESS.md` as exact steps.

## Finishing

When the feature is committed, stop. Tell Kim to run `/clear`, then `/next-feature`. Do not start the next feature.
