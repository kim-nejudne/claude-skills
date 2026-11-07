---
name: bootstrap-autopilot
description: Turn an app spec (plus optional design mocks) into a repo (standalone, or an app directory inside a monorepo) that an unattended autopilot can build and deploy to <app>.$BOOTSTRAP_DOMAIN. One interactive prep session: intake, design reference, four-lens spec review, Q&A, roadmap, Claude Code tooling, droplet provisioning, F01, autopilot dry run. Kim launches the autopilot; this skill never does.
argument-hint: "[--private] <spec.md> [mock files...]"
disable-model-invocation: true
---

# Bootstrap an app for autopilot

Arguments: $ARGUMENTS (first: the spec; the rest: mock files, HTML or claude.ai artifact links). `--private` anywhere in them makes the GitHub repo private (`REPO_VISIBILITY` in bootstrap.json); without it the repo is public. In a monorepo `--private` does nothing: the parent repo decides. Also use private, after asking Kim, when the spec says the repo must be private.

You run one prep session with Kim at the keyboard. It ends with everything an unattended run needs and the exact command for Kim to launch it. **You never launch the autopilot.** Stop at every **GATE** and wait for Kim.

Skill files (read each when its phase starts, not before):

- `reference/lessons.md`: what Sketchy and Buzzr taught. Read it now, in full.
- `reference/review-lenses.md` (phase 2), `reference/roadmap.md` (phase 4), `reference/bootstrap-json.md` (phase 5), `reference/droplet.md` (phase 6), `reference/stack-node.md` (phase 7, default stack only).
- `templates/render.mjs` renders `templates/` into the repo from `.claude/bootstrap.json`. `templates/skeletons/` holds formats you fill by hand (spec review, DESIGN.md, ROADMAP.md).

`SKILL_DIR` below is this skill's directory (`~/.claude/skills/bootstrap-autopilot`).

## Fixed policies

- **Repo visibility:** public by default, private with `--private`. Both run the same pipeline.
- **Personal apps only.** If the repo is under `~/Documents/work/`, stop at once: client engagements never use Kim's droplet, accounts or GitHub (global CLAUDE.md, "Engagements"). Never carry anything from a client engagement into a repo, a template or an example.
- **Stack:** the spec decides. If it names none, use the default: Node 24, TypeScript, Vite + React, vitest, eslint + prettier, npm (`reference/stack-node.md`).
- **Secrets:** build sessions never see real keys. Code reads env vars; tests and development use fakes. Real keys exist only in `/opt/<app>/.env` on the droplet and in GitHub secrets. Never echo, log, commit or read back a key's value.
- **Local-only agent files:** `.claude/` and `CLAUDE.md` are gitignored from the first commit. Docs, roadmap, `scripts/autopilot.sh`, `deploy/` and workflows are committed.
- **Sessions:** one feature per session, one commit per feature, sessions never push. Never weaken tests.
- **Outward-facing steps** (creating the GitHub repo, anything on the droplet, setting secrets) are shown first and run only after Kim says go.
- **Monorepo mode** (the app is a subdirectory of a bigger repo, e.g. `portfolio/pinpoint`): the same pipeline with `MONOREPO`, `APP_DIR` and the parent repo as `GH_REPO` in bootstrap.json (`reference/bootstrap-json.md`). No new GitHub repo; visibility is the parent's (public means the app's `docs/` go public on the push). Deploy secrets are the parent's shared ones, never set again. The root `.gitignore` must ignore `.claude/` and `CLAUDE.md` at any depth (check `git check-ignore -v <app>/.claude <app>/CLAUDE.md`); the portfolio's history was purged of agent files once, so never commit them. Every `git add` and `git commit` names paths; `git status`, `git diff` and `git log` take `-- .`. Sibling projects are read-only references: never import across projects. The autopilot runs in a git worktree on `autopilot/<app>` and pushes only commits inside `PUSH_ALLOWED`.

## 0. Intake

1. Resolve the repo: the current directory. Run the `~/Documents/work/` check. If `git rev-parse --show-toplevel` succeeds and is not the current directory, the app sits in a monorepo: ask Kim once with AskUserQuestion ("Monorepo mode: build <dir> as `<path from root>/` of `<origin's owner/repo>`?", Monorepo recommended, Stop). On Monorepo, follow the Monorepo mode policy for the rest of the skill; read the parent's root `README.md`, `.gitignore`, `.github/workflows/` (its CI and a sibling `deploy-*.yml`) and, if there is one, `hub/README.md`, since bootstrap.json's monorepo facts come from them.
2. Read the spec **in full**, and every mock in full (HTML files; for a claude.ai artifact link use the Artifact tool's `read`). Note anything the mocks show that the spec doesn't, and the reverse.
3. Standalone: `git init -b main` if needed. Monorepo: never `git init` (it would nest a repo). Copy `SKILL_DIR/templates/gitignore` to `.gitignore` (it has no placeholders; in a monorepo it sits beside the root one). Copy the spec to `docs/spec.md` and HTML mocks to `docs/design/` (artifact mocks: save the HTML the read returns). If the spec is already in place under another name (`docs/SPEC.md`), move it to `docs/spec.md` rather than keeping two copies.
4. First commit: `docs: spec and mocks as received` (`.gitignore`, `docs/`). Check `git status --short -- .` shows no `.claude/`, `CLAUDE.md` or `.env*` first. In a monorepo, commit with explicit paths (`git add -- .gitignore docs` then `git commit -- .gitignore docs`): the rest of the repo may hold Kim's unrelated work.
5. Tell Kim in 3–5 lines what the app is, the stack the spec implies (or the default), whether it has a UI, a web client, keyed services, a database. No gate yet.

## 1. Design reference

- Mocks present: write `docs/design/DESIGN.md` from `templates/skeletons/design/DESIGN.md`: tokens, type, components with states, one section per screen naming its mock, target viewports and browsers, a UI definition of done. Extract real values from the mock HTML (colours, fonts, sizes, radii), not impressions.
- No mocks: extract the same from the spec's own words. Where the spec is silent on look, say so in DESIGN.md and list it as a design finding for phase 2. This skill checks a design; it doesn't invent one.
- No UI at all (an API, a CLI): skip DESIGN.md and say so.

## 2. Four-lens review

Read `reference/review-lenses.md`. Write `docs/spec-review.md` from `templates/skeletons/spec-review.md`, covering all four lenses: product designer, architect / tech lead, security / privacy, ops / deploy. Every finding has a severity, a kind (clear-cut or fork), the exact proposed spec text and a default. Fill the **Locks** section (audience and locale, look, stack, keyed services, data); these are fixed before the roadmap.

## 3. GATE: Q&A

1. Apply every clear-cut finding to `docs/spec.md` as its default. Note each in the review's "Applied" block.
2. Ask Kim with AskUserQuestion, **one question per call**, only for:
   - real forks from the review (product or cost choices with no single right answer), recommended option first;
   - project facts: the app name and subdomain (`<app>.$BOOTSTRAP_DOMAIN`; the slug is also the repo (standalone), container, `/opt` dir and cache dir), stack confirmation, each keyed service (which provider, does Kim have an account and key), database and backups.
   - Never ask what the spec, the code or a sensible default already answers.
3. Apply the answers. Show Kim the **full spec diff** (`git diff -- docs/spec.md`) for one approval. Revise until approved.
4. Commit `docs: spec review applied` (`docs/spec.md`, `docs/spec-review.md`, `docs/design/`). From here the spec is locked: the protect-files hook (phase 5) blocks edits, and gaps go to `docs/DECISIONS.md` plus a `// SPEC-QUESTION:` comment.

## 4. Roadmap

Read `reference/roadmap.md`. Copy `roadmap.mjs` and `spec.mjs` into `.claude/scripts/` (they have no placeholders) so you can check the roadmap as you write it. Write `docs/ROADMAP.md` from `templates/skeletons/ROADMAP.md`: milestones, F01 = scaffold + CI, the last two features = Docker image + smoke test, then the deploy workflow (monorepo with a hub: then a gated Hub spoke feature, `reference/roadmap.md`). Every feature has `Spec:` citations that `spec.mjs` resolves, `Depends:`, concrete `Done when:` bullets and `Tests:`. Person-only parts are flagged as `Kim check:` bullets; anything that must not ship without Kim's approval gets a `Gate:` line. Check it as `reference/roadmap.md` says (every citation resolves). Show Kim the milestone list, feature count, Kim checks and gates, then commit `docs: roadmap`.

## 5. Tooling

1. Read `reference/bootstrap-json.md`. Write `.claude/bootstrap.json` with the project facts. Port, droplet facts and `MEM_LIMIT` may be provisional until phase 6; re-render then.
2. Derive from the spec, into bootstrap.json:
   - `NEVER_BREAK`: the spec's invariants, each one testable, written as rules ("Only the owner sees X", "The reducer is pure: …"). Typically 4–8.
   - `INVARIANT_REVIEWERS`: one read-only reviewer per cluster of invariants that a plain spec check would miss (secrecy, money, auth, concurrency…), each with the paths that trigger it and a concrete checklist. One or two is normal; zero is fine for a simple app.
   - `RULES`: path-scoped conventions (`.claude/rules/`) for the main code areas, from the spec and DESIGN.md.
3. Render: `node SKILL_DIR/templates/render.mjs .claude/bootstrap.json .` Read every rendered file once; fix bootstrap.json and re-render with `--force --only <path>` rather than hand-editing, so a re-render never loses a fix.
4. Check: `node .claude/scripts/roadmap.mjs next` reports `Next eligible: F01`; `node .claude/scripts/spec.mjs F01` and `spec.mjs <a later ID>` print sections (fix any `<!-- not found -->` citation in the roadmap); pipe a crafted `{"tool_input":{"file_path":"docs/spec.md"}}` into `.claude/hooks/protect-files.mjs` and expect exit 2, likewise for `scripts/autopilot.sh` and `.env`; `bash -n scripts/autopilot.sh`; `shellcheck scripts/autopilot.sh` if installed.
5. Commit `chore: autopilot, decisions and progress logs, deploy kit` (`scripts/autopilot.sh`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/deploy-kit/`, `deploy/`, and in a monorepo `.dockerignore`). `.github/workflows/ci.yml` (monorepo: this app's jobs in the root `ci.yml`) goes in with F01. Check `git status --short --ignored -- .` shows `.claude/` and `CLAUDE.md` as ignored, never staged.
6. Tell Kim: hooks and skills written in this session may not be live until a restart. Phase 7 follows the next-feature skill file directly, so a restart is optional.

## 6. GATE: droplet provisioning (Kim watching)

Read `reference/droplet.md` and follow it step by step. Before each command, show it in a code block and say what it changes; run it after Kim's go (one go may cover a read-only batch). In order:

1. Create the GitHub repo: `gh repo create <owner>/<app> --public|--private --source . --remote origin` (no push), matching `REPO_VISIBILITY`. Public: tell Kim first that `docs/` (spec, review, roadmap, decisions) will be public once the autopilot pushes. Private: tell Kim that Actions minutes count against the private-repo allowance. Monorepo: skip creating; check origin and the parent's visibility instead (`reference/droplet.md` step 0).
2. DNS: Kim added the Namecheap A record beforehand; `dig +short <app>.$BOOTSTRAP_DOMAIN A` must return `$BOOTSTRAP_DROPLET_IP`. If not, stop and ask.
3. Pick the next free `127.0.0.1` port (listeners, nginx vhosts and `/opt/*/compose.yaml` all count). Check free memory against `MEM_LIMIT`.
4. `/opt/<app>` (root:deploy, 1775) and its `.env` (deploy, 600) with `IMAGE_TAG=` and the key names, values empty. Kim pastes the real values in **his own terminal**; you verify names as set/empty only, never values.
5. Placeholder page, bootstrap vhost, `nginx -t`, reload, certbot once (webroot), full vhost, `nginx -t`, reload. The live URL now shows the placeholder (503), and every other vhost still answers as before.
6. Database: data dir and nightly backups, following the droplet's existing convention.
7. Deploy access: a per-repo SSH key for the `deploy` user, the four `gh secret set` calls, a test login, then the private key is shredded (GitHub holds the only copy). Monorepo: no key and no `gh secret set` (they would replace the secrets every sibling deploys with); check the shared secret names and the environment exist (`reference/droplet.md` step 6).
8. Update bootstrap.json (port, memory) and re-render what changed. Commit `chore: droplet vhost and compose` if `deploy/` changed.

## 7. GATE: build F01 in prep

Follow `.claude/skills/next-feature/SKILL.md` for F01 yourself, with Kim watching (default stack: `reference/stack-node.md`). Install dependencies here, interactively: an unattended session can't approve a prompt, which blocked Sketchy's F01. Run the verify stages until green, write the PROGRESS entry, `roadmap.mjs mark F01 x`, one commit `feat: F01 Project skeleton, tooling and CI`. Show Kim the verify table. Do not push. Monorepo: F01 pastes `docs/deploy-kit/ci-jobs.yml`'s jobs into the root `ci.yml` and changes nothing else there; the commit names its paths (`git commit -- . ../.github/workflows/ci.yml`).

## 8. Autopilot

`scripts/autopilot.sh` was rendered in phase 5 from `templates/autopilot.sh`. Check it still matches the facts (port, health path, checks, workflow name, scaffold file) and re-render if bootstrap.json changed. It keeps everything Sketchy's runner had: a fresh `claude -p "/next-feature"` per feature, `--dangerously-skip-permissions` plus a hard deny list, push URL and `gh` token dead inside sessions, retries, one extra pass for blocked features with their work stashed, usage-limit waits, the pinned status area, logs under `~/.cache/<app>-autopilot/<UTC>/`, running from a copy of itself. At the end: final gate, push guard, **one** push, watch the deploy workflow, smoke-test the live URL, and write the **morning report** (`~/.cache/<app>-autopilot/morning-report.md`). Kim checks never block; gated features wait for Kim without blocking the deploy of the rest.

Monorepo mode adds: the run checks that `main` carries no unpushed commits outside `PUSH_ALLOWED` and that the app in Kim's checkout has no uncommitted changes, then works in a git worktree (`~/.cache/<app>-autopilot/worktree`, branch `autopilot/<app>`, from `main`) with `.claude/` and `CLAUDE.md` copied in and dependencies installed there. Kim can keep working and committing anywhere in the repo meanwhile. The push guard also refuses any path outside `PUSH_ALLOWED`; the push goes from the branch to `origin/main`. Once the deploy is live it copies the reviewers' memory back and removes the worktree and branch; a stopped or failed run keeps them, and the next run resumes there.

## 9. GATE: handoff

1. Run `scripts/autopilot.sh --dry-run`. Every check must pass: queue, push guard, gh auth, the repo and its four deploy secrets, droplet reachable with disk and stack dir, the live URL over TLS (monorepo also: nothing foreign unpushed on `main`, the app clean in the checkout, rsync). Fix and re-run until green.
2. Print, for Kim to run himself:

   ```
   tmux new-session -d -s <app>-autopilot -c <repo> scripts/autopilot.sh
   tmux attach -t <app>-autopilot        # detach: Ctrl-b d
   ```

   `<repo>` is the app's directory (in a monorepo, `<root>/<app_dir>` in Kim's checkout; the script makes its worktree itself).

   Then: where the status and logs are (`~/.cache/<app>-autopilot/`), that Ctrl-C stops cleanly and a re-run resumes from the `[~]` feature, that `--no-deploy` builds without pushing, where the morning report lands, and how many Kim checks and gates exist so far. Monorepo: until the run has pushed, the build lives only on `autopilot/<app>` (look at it in the worktree); don't edit the app in the checkout meanwhile, and after a live deploy run `git pull --rebase`. Ungating a gate later: pull, `roadmap.mjs ungate <ID>` in the checkout, commit it, start the autopilot again.
3. Save a project memory: the app, its repo, live URL, port, that the autopilot is ready, and the tmux command. Then stop. **Never launch the autopilot.**
