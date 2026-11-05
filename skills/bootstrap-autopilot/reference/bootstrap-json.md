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
| `DOCKER_FEATURE` / `DEPLOY_FEATURE` | `"F23"` / `"F24"` | The last two roadmap IDs |
| `BOOTSTRAP_DATE` | `"2026-11-02"` | Optional, defaults to today |

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
| `FORMATTER` | `{bin, args, exts}` for the format-on-edit hook, or `null`. A `bin` with a `/` is relative to the repo and the hook waits until it exists |
| `TYPECHECK` | `{cmd: [argv], exts, needs}` for the Stop hook, or `null` |
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
