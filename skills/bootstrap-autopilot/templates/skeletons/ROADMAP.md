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
    - CI workflow `.github/workflows/ci.yml` runs <the checks> on push and pull request
    - `scripts/autopilot.sh`, `docs/` and `deploy/` from the bootstrap are committed with F01, unchanged
    - <web apps> `npm run playtest -- <scenario>` runs a Playwright scenario with one isolated browser context per role; `scripts/playtest/smoke.ts` opens the app and asserts no console errors
    - <design> the DESIGN.md tokens and fonts are wired in (CSS variables or the framework's theme) and the placeholder page uses them
  - Tests: <health route test>

- [ ] F02 <title>
  - Spec: <Heading (Sub, Sub)>; <Heading>
  - Depends: F01
  - Done when:
    - <observable, testable outcome>
    - <Kim-only part, if any: "Kim check: <what a person must try on a real device or account>">
  - Tests: <test files and what each proves>

## M<n> — Ship

- [ ] F<n-1> Docker image and smoke test
  - Spec: <stack/deploy sections>
  - Depends: <the last feature that changes runtime behaviour>
  - Done when:
    - `Dockerfile` (start from `docs/deploy-kit/Dockerfile.node` or write one for the stack): multi-stage, runs as a non-root user, `HEALTHCHECK` on `<health path>`, stops on SIGTERM in under 5 s
    - `scripts/docker-smoke.sh` (from `docs/deploy-kit/docker-smoke.sh`) builds the image, runs it with the settings in `deploy/compose.deploy.yaml` (port `127.0.0.1:<PORT>` → <container port>, `mem_limit`), and checks `<health path>`, the main page and <the app's critical paths>; wired as `<smoke:docker command>`
    - `mem_limit` in `deploy/compose.deploy.yaml` is set from a measured peak plus headroom and fits the droplet's free memory (DECISIONS row)
    - A smoke script that takes a base URL (`<smoke command> <URL>`) for use against the live site
  - Tests: the smoke script's own unit test where it has logic

- [ ] F<n> Deploy workflow to <domain>
  - Spec: <deploy section>
  - Depends: F<n-1>
  - Done when:
    - `.github/workflows/deploy-<app>.yml` from `docs/deploy-kit/deploy.yml`, keeping its job names (`checks`, `droplet`), step names and the `ABORT: N live connection(s) after 10 min` line, which `scripts/autopilot.sh` matches
    - The workflow runs the checks, builds and smoke-tests the image on the runner, ships it with `docker save | ssh docker load` as the `deploy` user, re-points `IMAGE_TAG`, waits for health, rolls back on failure, then runs the smoke script against `https://<domain>`
    - `README.md` has the runbook: deploy, rollback (`workflow_dispatch` with a tag), port, env vars (names only), break-glass manual steps
    - `docs/deploy-kit/` is deleted (its files now live in place)
    - Kim check: open https://<domain> on <real devices> and walk <the core flow>

## Bugs

## Backlog
