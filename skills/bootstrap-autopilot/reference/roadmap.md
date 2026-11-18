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
- **F02 and F03 ship the skeleton**: F02 is the Docker image plus smoke test (`docs/deploy-kit/Dockerfile.node` and `docker-smoke.sh` as starting points), F03 the deploy workflow (`docs/deploy-kit/deploy.yml`, keeping its job and step names and its `ABORT:` and `never became healthy` lines) plus the README runbook. The autopilot deploys once right after F03, so the droplet, the secrets, the env check and the workflow are proven on day one, not after a day or two of building (Pinpoint's first deploy failed on a missing env var after the whole build). Later features change the Dockerfile and the smoke script when they need to.
- **Vercel** (`DEPLOY_TARGET: "vercel"`): F02 is the production build plus a smoke script run against `npm start` locally (no Docker), F03 the deploy workflow from `docs/deploy-kit/deploy.yml` (jobs `checks` and `vercel`, the `vercel build` step, the `ABORT: missing env:` and `never became healthy` lines), with `HEALTH_PATH`, `.env.example` and an additive `db:migrate` script if there is a database. The release check has no `mem_limit` to measure. New env vars get a Kim check to set them in the Vercel project's production env.
- **No deploy target** (`DEPLOY_TARGET: "none"`, a local tool such as a Bash CLI, `reference/stack-bash.md`): there is no F02 Docker feature and no F03 deploy feature. F01 is the scaffold, every check and `ci.yml`, with no health route. F02 is the first real feature. The autopilot pushes only at the end and waits for `ci.yml`. The release check makes sure the README's install steps work from a clean clone, `<tool> help` covers every command, and every check is green. It has no `mem_limit`, smoke script or deploy kit.
- **The last feature is the release check**: re-measure `mem_limit` (and the heap) on the finished app, finish the smoke script's critical paths and the runbook's env var list, delete `docs/deploy-kit/`, and the Kim check that walks the core flow on real devices. It depends on the last feature that changes runtime behaviour.
- **New env vars**: the feature that adds one puts it in `.env.example` (`# optional` on its line if the app starts without it) and adds a Kim check to set it on the droplet. The deploy refuses to start while a required one is unset there.
- **Every Done-when bullet is checkable** by a test, a command or a playtest step. "Works well" is not a bullet; "a 10-item list renders in under 100 ms on a 4× CPU throttle" is.
- **Flag person-only checks** as `Kim check:` bullets: real phones and browsers, a TV across the room, mobile data, real third-party accounts or keys, reviewing generated content. The session builds and tests everything around them and queues exact steps in PROGRESS.md.
- **Keyed services**: the feature that adds one also adds its fake and the env var names to `.env.example`; a Kim check covers trying it with the real key after deploy.
- **Security and limits** land with the feature that opens the surface (validation and rate limits ship with the endpoint, not in a later "hardening" milestone).
- **Gates late**: put gated items where as little as possible depends on them. Everything that depends on a gated item waits too; the autopilot ships the rest.
- **Backlog**: nice-to-haves from the review go under `## Backlog`, not into features.
- **Native Android client** (`ANDROID`): F01 builds both halves: the Node scaffold and `android/` per `reference/stack-android.md` (every Gradle check passing, one Robolectric Compose test with a Roborazzi screenshot, Java and Gradle in CI, `android/tools/fetch-ktlint.sh` run). Phone features prove their UI with Compose tests and Roborazzi captures, never an emulator. Device-only behaviour is always a `Kim check:` bullet, never a gate: camera and torch, OCR accuracy on real plates or text, install from the site, the in-app update, real offline use and sync when signal returns, background sync after the phone has slept. The **release APK feature** (`APK_FEATURE`) comes just before the release check: the release build type, `scripts/apk-release.sh` from `docs/deploy-kit/`, `apk/.gitkeep`, the server serving `/apk/version.json` and the APK, and its `.dockerignore` line. The early Docker and deploy features leave the APK out; this feature adds the Dockerfile's `COPY apk/` line (the kit's Dockerfile has it) and the kit's `decode the release keystore` and `build the release APK` steps to the deploy workflow, names unchanged.
- **Monorepo mode**: F01 pastes `docs/deploy-kit/ci-jobs.yml`'s two jobs into the root `.github/workflows/ci.yml` (nothing else there changes) instead of writing a CI workflow; it cites the root path relative to the app (`../.github/workflows/ci.yml`). The deploy feature writes `<root>/.github/workflows/deploy-<app>.yml` and adds the app to the root `README.md` in the same shape as its siblings. With `HUB` set, one more feature follows the release check: **Hub spoke**, with a `Gate:` line (Kim approves putting the app on the public hub). It writes `<app>/CASE-STUDY.md`, the app's entry in `hub/src/spokes.ts`, its crop (`hub/crops/<app>`), the `deploy-hub.yml` paths line and anything else the hub's README lists for a new spoke, with a Kim check for the crop and the copy. GitHub profile and bio text stay Kim's.

## Check before committing

Copy the two scripts first (they have no placeholders; phase 5's render skips them as existing): `mkdir -p .claude/scripts && cp SKILL_DIR/templates/claude/scripts/{roadmap,spec}.mjs .claude/scripts/`. Then:

- `node .claude/scripts/roadmap.mjs next` → `Done: 0/N`, `Next eligible: F01`.
- `node .claude/scripts/spec.mjs <ID>` for F01, F03, the release check and two in between: no `<!-- not found -->` line.
- F02 is the Docker feature and F03 the deploy feature; the release check is last, and nothing but Backlog follows it (monorepo with `HUB`: only the gated Hub spoke follows it).
