# .claude/bootstrap.json

The project facts `templates/render.mjs` renders from. It lives at `<repo>/.claude/bootstrap.json` (local, gitignored). Re-render a file after changing a fact: `node SKILL_DIR/templates/render.mjs .claude/bootstrap.json . --force --only <path>`. `--list` prints every output path.

Strings are plain unless noted. Every key below is required unless marked optional; the renderer stops on a missing key, an unknown `{{KEY}}` or a leftover tag.

## Identity and deploy

| Key | Example | Notes |
| --- | --- | --- |
| `APP` | `"pantry"` | Lowercase slug: repo name, subdomain, container, `/opt/<app>`, cache dir, stash prefix |
| `APP_TITLE` | `"Pantry"` | Display name |
| `APP_PITCH` | `"A shared shopping list for a household."` | One sentence, ends with a full stop |
| `OWNER` | `"kim-nejudne"` | GitHub owner (`gh api user --jq .login`) |
| `GH_REPO` | `"kim-nejudne/pantry"` | The autopilot refuses any other origin |
| `REPO_VISIBILITY` | `"private"` | Optional: `"public"` (default) or `"private"`, from the `--private` flag. The dry run checks GitHub agrees |
| `REPO_URL` | `"https://github.com/kim-nejudne/pantry.git"` | What `gh repo create` set as origin |
| `DOMAIN` | `"pantry.$BOOTSTRAP_DOMAIN"` | |
| `DROPLET` | `"$BOOTSTRAP_DROPLET_IP"` | |
| `PORT` | `3007` | Host loopback port, picked in phase 6 |
| `CONTAINER_PORT` | `3000` | |
| `HEALTH_PATH` | `"/healthz"` | Returns 200 `{ok: true}` |
| `MEM_LIMIT` | `"256m"` | Provisional until the Docker feature measures it |
| `HEAP_MB` | `128` | Optional, Node only: `--max-old-space-size`, about half of `MEM_LIMIT` |
| `MAX_BODY` | `"1m"` | Optional: nginx `client_max_body_size` |
| `DOCKER_FEATURE` / `DEPLOY_FEATURE` | `"F02"` / `"F03"` | The Docker and deploy features, right after F01 (`reference/roadmap.md`) |
| `BOOTSTRAP_DATE` | `"2026-11-02"` | Optional, defaults to today |

## Monorepo mode

Set when the app is a subdirectory of a bigger repo (phase 0 detects it: `git rev-parse --show-toplevel` is not the app dir). Absent or `false`: standalone, and every template renders exactly as before.

| Key | Example | Notes |
| --- | --- | --- |
| `MONOREPO` | `true` | Optional |
| `APP_DIR` | `"pinpoint"` | Required with `MONOREPO`: the app's path from the repo root |
| `GH_REPO` / `REPO_URL` | `"kim-nejudne/portfolio"` | The parent repo (`git remote get-url origin`), not a new one |
| `REPO_VISIBILITY` | `"public"` | The parent repo's, read with `gh repo view`; never chosen |
| `HUB` | `{"dir": "hub"}` | Optional: set when `<root>/hub/src/spokes.ts` exists. Lets the gated hub-spoke feature touch `hub/` and `deploy-hub.yml` |
| `PUSH_ALLOWED` | | Optional regex of root-relative paths the autopilot may push. Default: the app dir, the root `ci.yml`, `deploy-<app>.yml`, the root `README.md`, and with `HUB` the hub dir and `deploy-hub.yml` |
| `DEPLOY_SECRETS` | `["SSH_HOST", "SSH_USER", "SSH_KEY", "SSH_KNOWN_HOSTS"]` | Optional: the shared secret names the sibling `deploy-*.yml` use (read them there) |
| `DEPLOY_ENVIRONMENT` | `"production"` | Optional: the environment the sibling deploy jobs use |
| `BRANCH` | `"autopilot/pinpoint"` | Optional: the worktree's branch, default `autopilot/<app>` |
| `DEV_PORTS` | | Pick ports no sibling app's dev server uses (read their vite and server configs); Kim may run those meanwhile |

In this mode `APP` is still the subdomain, container, `/opt/<app>`, cache dir and stash prefix, but not the repo name. The render writes `docs/deploy-kit/ci-jobs.yml` (F01 pastes its two jobs into the root `ci.yml`) and `.dockerignore` instead of `.github/workflows/ci.yml`, and `docs/deploy-kit/deploy.yml` gets a `paths:` filter, the app's working directory and a tag from the last commit that changed the app.

## Stack and commands

| Key | Notes |
| --- | --- |
| `STACK` | `"node"` renders the Node-specific parts (setup-node in workflows, `Dockerfile.node`, `NODE_OPTIONS`); anything else skips them |
| `STACK_SUMMARY` | Optional one line for CLAUDE.md and the spec-checker |
| `NODE_VERSION` | `"24"` (used only when `STACK` is `node`, but always required; any value for other stacks) |
| `INSTALL_CMD` | Clean install for CI (`npm ci`) |
| `LOCKFILE` | Protected from hand edits (`package-lock.json`); `""` for none |
| `SCAFFOLD_FILE` | Exists once F01 ran (`package.json`); the autopilot skips checks before it |
| `CHECKS` | Ordered array of `{name, cmd, ciName?, ci?}`: the verify skill, the autopilot gate and CI. `ciName` is the CI step name (the autopilot matches it); `ci: false` keeps a step out of CI |
| `FORMAT_CMD` | Fixes formatting (`npm run format`) |
| `FORMATTER` | `{bin, args, exts}` for the format-on-edit hook (it runs `bin args <file>`), or `null`. A `bin` with a `/` is relative to the repo and the hook waits until it exists. An array runs several: each entry after the first needs a `name` and gets its own `.claude/hooks/format-file-<name>.mjs` |
| `TYPECHECK` | `{cmd: [argv], exts, needs}` for the Stop hook, or `null`. An array the same way (`stop-typecheck-<name>.mjs`); each runs only when files with its `exts` changed |
| `TEST_ONE_CMD` | Runs one test file (`npx vitest run <file>`) |
| `DEV_CMD` / `DEV_URL` / `DEV_PORTS` | The dev server, its URL, and every port it listens on (stray servers on these are killed between sessions) |
| `SMOKE_CMD` | Optional, default `npm run smoke --`: runs the smoke script against a base URL |
| `PLAYTEST_CMD` | Optional, default `npm run playtest --` |
| `TEST_GLOBS` | Optional array for `.claude/rules/tests.md` |
| `EXTRA_ALLOW` | Optional array of commands sessions may run without a prompt (`npm install`, `npx tsx`…). Each becomes `Bash(cmd)` and `Bash(cmd *)` |
| `EXTRA_COMMANDS_MD` | Optional extra lines for CLAUDE.md's command block |

## Shape

| Key | Notes |
| --- | --- |
| `UI` | `true` renders `ui-reviewer` and the DESIGN.md read step. Needs `UI_REVIEW_CHECKS` (Markdown bullets, `- **Fit:** …`, from DESIGN.md's targets) and optional `UI_WHEN` (`"client/ changed"`) |
| `WEB` | `true` renders the `playtester` agent and `playtest` skill (browser app with the Playwright harness) |
| `DB` | `true` adds the data volume (`/opt/<app>/data` → `/data`, `DATA_DIR=/data`) to the compose file |
| `DRAIN` | Informational: the app holds live connections or in-memory state (the drain wait is always in the workflow; it is harmless for plain HTTP) |
| `ANDROID` | Optional: `true` adds the native Android client in `android/` (`reference/stack-android.md`): Java and Gradle in CI, the release APK built and signed in the deploy and copied into the image, the keystore secrets in the dry run and push guard, Gradle daemons stopped between sessions, phone-screen review from Roborazzi screenshots. Works standalone and in a monorepo |
| `APK_FEATURE` | Required with `ANDROID`: the roadmap ID of the release APK feature (just before the release check) |

With `ANDROID`, the deploy reads three GitHub secrets set in phase 6: `ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`. In a monorepo they carry the app's name first (`PINPOINT_ANDROID_KEYSTORE_B64`), because the apps share one set of repo secrets.

## Derived from the spec (phase 5)

`NEVER_BREAK`: array of rules, each a Markdown string, usually starting with a bold claim:

```json
"NEVER_BREAK": [
  "**Only a list's members see it.** No list, item or member name reaches another household's view, a log line or an error.",
  "**The server is the source of truth.** Clients render the latest snapshot and hold no business rules."
]
```

`INVARIANT_REVIEWERS`: array, one agent each (`.claude/agents/<NAME>.md`):

```json
{
  "NAME": "privacy-reviewer",
  "DESCRIPTION": "Read-only reviewer for Pantry's household isolation (cross-household leaks, auth on every route, invite tokens). Use on any change to server/ or shared/.",
  "WHEN": "server/ or shared/ changed",
  "SPEC_SECTIONS": "Data model, Households and invites, Security",
  "CHECKS": [
    "**Isolation:** every query is scoped by household id from the session, never from the request body.",
    "**Invites:** tokens are single-use, expire after 7 days, and are compared in constant time."
  ]
}
```

`RULES`: array, one path-scoped rule file each (`.claude/rules/<FILE>`):

```json
{ "FILE": "server.md", "PATHS": ["server/**", "shared/**"], "TITLE": "Server conventions", "BODY": ["Validate every inbound body with the zod schema from shared/schemas.ts.", "…"] }
```

In both arrays, a list value becomes a Markdown bullet list, except `PATHS`, which becomes a JSON array for the frontmatter.
