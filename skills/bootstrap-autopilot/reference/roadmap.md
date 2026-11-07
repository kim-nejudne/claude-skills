# Writing the roadmap

`docs/ROADMAP.md`, from `templates/skeletons/ROADMAP.md`. `roadmap.mjs`, `spec.mjs`, the session-context hook and the autopilot all parse it, so the format is exact.

## Format

```markdown
## M2 — Name

- [ ] F07 Title in sentence case
  - Spec: Heading (Subheading, Subheading); Another heading
  - Depends: F05, F06
  - Done when:
    - observable outcome, testable by a session
    - Kim check: what a person must try on a real device or account
  - Tests: file.test.ts — what it proves
  - Gate: Kim approves <what>          ← only when it must not ship without Kim
```

- Item line: `- [ ] F07 Title`. IDs are `F` + number (letter suffix to split: `F07a`). Bugs use `B` under `## Bugs`.
- `Spec:` cites `docs/spec.md` headings exactly as `spec.mjs` matches them: `Heading` prints the whole section; `Heading (Sub, Sub)` prints only those subsections (`intro` = the text before the first subheading). Separate citations with `;`. Prefix matching works, but cite exact headings.
- `Depends:` lists IDs or `none`. `roadmap.mjs` picks the first todo feature whose dependencies are all done, so order the file in build order too.
- `Gate:` keeps the item out of the queue until Kim runs `roadmap.mjs ungate <ID>`. Use it only for approvals (content Kim must review before it ships, a paid service Kim must sign up for). Everything else a person must do is a `Kim check:` bullet, which never blocks.

## Rules

- **M1 is the thinnest usable version**: at the end of it, the core loop works end to end, however plain. Every later milestone makes it fairer, safer, prettier or sturdier, and the app stays runnable after every feature.
- **One session per feature**: ≤ ~10 files and ~600 lines changed. Split anything bigger. A feature with UI includes its tests and its playtest scenario.
- **F01 is the scaffold plus CI**: the stack, every check command, a health route and its test, the CI workflow, DESIGN.md's tokens and fonts wired in, the playtest harness for web apps. F01 is built in prep (phase 7), not by the autopilot.
- **The last two features**: the Docker image plus smoke test (`docs/deploy-kit/Dockerfile.node` and `docker-smoke.sh` as starting points), then the deploy workflow (`docs/deploy-kit/deploy.yml`, keeping its job and step names) plus the README runbook. The deploy feature depends on the Docker one, and the Docker one on the last feature that changes runtime behaviour.
- **Every Done-when bullet is checkable** by a test, a command or a playtest step. "Works well" is not a bullet; "a 10-item list renders in under 100 ms on a 4× CPU throttle" is.
- **Flag person-only checks** as `Kim check:` bullets: real phones and browsers, a TV across the room, mobile data, real third-party accounts or keys, reviewing generated content. The session builds and tests everything around them and queues exact steps in PROGRESS.md.
- **Keyed services**: the feature that adds one also adds its fake and the env var names to `.env.example`; a Kim check covers trying it with the real key after deploy.
- **Security and limits** land with the feature that opens the surface (validation and rate limits ship with the endpoint, not in a later "hardening" milestone).
- **Gates late**: put gated items where as little as possible depends on them. Everything that depends on a gated item waits too; the autopilot ships the rest.
- **Backlog**: nice-to-haves from the review go under `## Backlog`, not into features.
- **Monorepo mode**: F01 pastes `docs/deploy-kit/ci-jobs.yml`'s two jobs into the root `.github/workflows/ci.yml` (nothing else there changes) instead of writing a CI workflow; it cites the root path relative to the app (`../.github/workflows/ci.yml`). The deploy feature writes `<root>/.github/workflows/deploy-<app>.yml` and adds the app to the root `README.md` in the same shape as its siblings. With `HUB` set, one more feature follows the deploy feature: **Hub spoke**, with a `Gate:` line (Kim approves putting the app on the public hub). It writes `<app>/CASE-STUDY.md`, the app's entry in `hub/src/spokes.ts`, its crop (`hub/crops/<app>`), the `deploy-hub.yml` paths line and anything else the hub's README lists for a new spoke, with a Kim check for the crop and the copy. GitHub profile and bio text stay Kim's.

## Check before committing

Copy the two scripts first (they have no placeholders; phase 5's render skips them as existing): `mkdir -p .claude/scripts && cp SKILL_DIR/templates/claude/scripts/{roadmap,spec}.mjs .claude/scripts/`. Then:

- `node .claude/scripts/roadmap.mjs next` → `Done: 0/N`, `Next eligible: F01`.
- `node .claude/scripts/spec.mjs <ID>` for F01, the deploy feature and two in between: no `<!-- not found -->` line.
- The deploy feature is last, and nothing but Backlog follows it (monorepo with `HUB`: only the gated Hub spoke follows it).
