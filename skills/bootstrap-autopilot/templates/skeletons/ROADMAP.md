# Roadmap

Status: [ ] todo · [~] in progress · [x] done · [!] blocked (see note)

Change markers with `node .claude/scripts/roadmap.mjs mark`. A done item collapses to one line; its details are in PROGRESS.md and git history. Each `Spec:` line cites headings of `docs/spec.md` in `spec.mjs` form: `Heading (Subheading, Subheading)`. A `Gate:` line holds an item out of the queue until Kim approves and runs `roadmap.mjs ungate <ID>`; nothing else removes it.

<One paragraph: what M1 delivers (the thinnest usable version) and what each later milestone adds. The app stays runnable after every feature.>

## M1 — <name>

- [ ] F01 Project skeleton, tooling and CI
  - Spec: <stack and layout sections>
  - Depends: none
  - Done when:
    - <dev server command> starts the app; <each check command> exists and passes; <start command> serves the built app; `GET <health path>` returns 200 with `{ok: true}`
    - CI workflow `.github/workflows/ci.yml` runs <the checks> on push and pull request <monorepo: "this app's two jobs from `docs/deploy-kit/ci-jobs.yml` are in the root `../.github/workflows/ci.yml`; nothing else in it changed">
    - `scripts/autopilot.sh`, `docs/` and `deploy/` from the bootstrap are committed with F01, unchanged
    - <web apps> `npm run playtest -- <scenario>` runs a Playwright scenario with one isolated browser context per role; `scripts/playtest/smoke.ts` opens the app and asserts no console errors
    - <design> the DESIGN.md tokens and fonts are wired in (CSS variables or the framework's theme) and the placeholder page uses them
    - <android> `android/` per `reference/stack-android.md`: `android/gradlew -p android ktlintCheck lintDebug testDebugUnitTest assembleDebug` pass; one Robolectric Compose test renders the placeholder screen with the DESIGN.md theme and writes its Roborazzi screenshot; CI sets up Java 21 and Gradle; `android/tools/fetch-ktlint.sh` installs the format hook's ktlint
  - Tests: <health route test>

- [ ] F02 Docker image and smoke test
  - Spec: <stack/deploy sections>
  - Depends: F01
  - Done when:
    - `Dockerfile` (start from `docs/deploy-kit/Dockerfile.node` or write one for the stack): multi-stage, runs as a non-root user, `HEALTHCHECK` on `<health path>`, stops on SIGTERM in under 5 s <android: `.dockerignore` lists `android`; the `COPY apk/` line waits for the release APK feature>
    - `scripts/docker-smoke.sh` (from `docs/deploy-kit/docker-smoke.sh`) builds the image, runs it with the settings in `deploy/compose.deploy.yaml` (port `127.0.0.1:<PORT>` → <container port>, `mem_limit`), and checks `<health path>` and the main page; wired as `<smoke:docker command>`. Later features add their critical paths to it
    - A smoke script that takes a base URL (`<smoke command> <URL>`) for use against the live site
  - Tests: the smoke script's own unit test where it has logic

- [ ] F03 Deploy workflow to <domain>
  - Spec: <deploy section>
  - Depends: F02
  - Done when:
    - `.github/workflows/deploy-<app>.yml` from `docs/deploy-kit/deploy.yml`, keeping its job names (`checks`, `droplet`), step names and its `ABORT:` and `never became healthy` lines, which `scripts/autopilot.sh` matches <android: without the `decode the release keystore` and `build the release APK` steps yet; the release APK feature adds them>
    - The workflow runs the checks, builds and smoke-tests the image on the runner, ships it and `.env.example` with `docker save | ssh docker load` as the `deploy` user, stops before the swap if an env var `.env.example` names is unset in `/opt/<app>/.env`, re-points `IMAGE_TAG`, waits for health, rolls back on failure, then runs the smoke script against `https://<domain>`
    - `README.md` has the runbook: deploy, rollback (`workflow_dispatch` with a tag), port, env vars (names only), break-glass manual steps
    - <monorepo: "the workflow lives at the repo root (`../.github/workflows/deploy-<app>.yml`), and the root `../README.md` lists the app like its siblings">
    - The autopilot deploys right after this feature (the health route and placeholder page go live); every later feature ships with the final deploy
  - Tests: none beyond the checks the workflow runs

- [ ] F04 <title>
  - Spec: <Heading (Sub, Sub)>; <Heading>
  - Depends: F03 <or the feature it really builds on>
  - Done when:
    - <observable, testable outcome>
    - <Kim-only part, if any: "Kim check: <what a person must try on a real device or account>">
    - <a new env var: it is in `.env.example` (`# optional` on its line if the app starts without it), and "Kim check: set <NAME> in /opt/<app>/.env">
  - Tests: <test files and what each proves>

## M<n> — Ship

<android only:>
- [ ] F<n-1> Release APK and update channel
  - Spec: <platform, distribution and update sections>
  - Depends: <the last feature that changes the phone app>
  - Done when:
    - `scripts/apk-release.sh` (from `docs/deploy-kit/apk-release.sh`) builds the R8 release APK and writes `apk/<app>-<code>.apk` and `apk/version.json`; it runs unsigned here
    - `apk/.gitkeep` is committed and `/apk/*` ignored; the server serves `GET /apk/version.json` and the APK from `APK_DIR`, and answers 404 when there is none
    - The `Dockerfile` copies `apk/`; the deploy workflow gains the kit's `decode the release keystore` and `build the release APK` steps, names unchanged
    - Kim check: install the signed APK from https://<domain> on the real phone, then deploy a phone change and accept the in-app update
  - Tests: the server routes; the app's update check against a fake server

- [ ] F<n> Release check
  - Spec: <deploy section>
  - Depends: <the last feature that changes runtime behaviour>
  - Done when:
    - `mem_limit` in `deploy/compose.deploy.yaml` (and the heap size) is set from a measured peak of the finished app under <its heaviest realistic load> plus headroom, and fits the droplet's free memory (DECISIONS row)
    - `scripts/docker-smoke.sh` covers <the app's critical paths>; the README runbook lists every env var `.env.example` has
    - `docs/deploy-kit/` is deleted (its files now live in place)
    - Kim check: open https://<domain> on <real devices> and walk <the core flow>
  - Tests: none beyond the smoke script

<monorepo with HUB only:>
- [ ] F<n+1> Hub spoke
  - Spec: <overview section>
  - Depends: F<n>
  - Done when:
    - `CASE-STUDY.md` in the app dir, in the shape of the siblings' case studies
    - The app's entry in `../hub/src/spokes.ts`, its crop, the `../.github/workflows/deploy-hub.yml` paths line, and anything else `../hub/README.md` lists for a new spoke; the hub's own checks pass
    - Kim check: the crop and the case study read well on the live hub
  - Gate: Kim approves adding <app> to the public hub

## Bugs

## Backlog
