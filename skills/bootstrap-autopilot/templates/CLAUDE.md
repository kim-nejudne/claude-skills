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

- Standalone public repo `{{GH_REPO}}`. Commit messages: `feat: F07 <title>`, `fix: B03 <title>`, `docs: …`, `chore: …`.
- `.claude/`, `CLAUDE.md` and `.env*` are gitignored and stay local. Docs, the roadmap, `scripts/autopilot.sh` and the workflows are committed.

## Commands

```
{{COMMANDS_BLOCK}}
```

Deploy target: {{LIVE_URL}} via `.github/workflows/{{WORKFLOW_FILE}}` (written by {{DEPLOY_FEATURE}}). `scripts/autopilot.sh` pushes and deploys once, at the end; sessions never do.

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
