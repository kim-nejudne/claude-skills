# Lessons from Sketchy and Buzzr

Sketchy (74 features, built unattended from 2026-10-30, live at sketchy.$BOOTSTRAP_DOMAIN) and Buzzr before it are where this skill comes from. Each lesson says what happened and what the skill does about it.

## Lock design and audience before the roadmap

- **A redesign came after launch.** Sketchy shipped with a generic dark look. Kim then compared five mockups and picked a light "spiral sketchbook" one, which cost a whole milestone (M12, 12 features: tokens, fonts, every surface, motion, a bundle-budget fight over web fonts). The build was fine; the design was never pinned down before it.
  → Phase 1 writes `docs/design/DESIGN.md` from real mocks before anything is built, and every UI feature and the ui-reviewer work against it from F01. No mocks means the spec's words are extracted and the gaps are a review finding, not something a session invents.
- **An audience reversal came after launch.** Sketchy was built for Filipino groups (Taglish copy, six Tagalog word packs, a language setting, Tagalog in matching and blocklists). Kim then made it flat English for everyone: another milestone (M13, 7 features) to rip out i18n plumbing, content and tests.
  → The product lens must produce an explicit **audience and locale lock** (who, where, which languages, spelling, units) in the review's Locks section, and Kim confirms it at the Q&A gate.

## Human-only checks go in a queue, approvals are gates

- Real phones, mobile data, a TV across the room, reviewing word lists: an unattended run can't do these. Sketchy queued them as `- [ ] Fnn: steps · what to look for` under `## Kim checks` in PROGRESS.md and marked the feature done. That worked: the run never stalled on a person, and Kim got exact steps.
- **But an approval is not a check.** Sketchy's English spicy pack was split into a draft (F72) and a build (F73) so Kim could approve the words before they shipped. The autopilot's retry pass reset F73 to todo automatically, and only a careful session noticed that shipping it would push unreviewed content live (DECISIONS 98).
  → Anything that must not ship without Kim gets a `Gate:` line in the roadmap. `roadmap.mjs` never picks a gated item, the retry pass never touches it, sessions are denied `roadmap.mjs ungate`, and the autopilot ships everything else and lists gates in the morning report.

## Unattended sessions can't answer a prompt

- **F01 blocked on `npm install`.** It was an `ask` rule in `.claude/settings.json`; the first unattended session wrote every F01 file and then stopped, because nobody could approve the install. Even with `--dangerously-skip-permissions`, an ask rule was a refusal.
  → F01 is built in prep with Kim watching (dependencies installed interactively), and everything later sessions need (checks, formatter, installs) is in `allow`. Things they must never do are in the autopilot's `--disallowedTools`, not in `ask`.
- **`/next-feature` may not resolve in headless mode.** The runner detects that from the session's init event and falls back to inlining the skill file as the prompt.
- **Sessions leave things behind.** Stray dev servers on the dev ports (the runner kills only those whose cwd is the repo), screenshots or scratch files after a commit (the runner stashes them so the next session doesn't stop on a dirty tree).

## The push guard exists for a reason

- In the monorepo, Kim committed elsewhere during a run; without the guard, the autopilot's push would have shipped and deployed Kim's unrelated work unreviewed. A standalone repo removes that case but not the class: the guard refuses to push when the remote isn't the app's own repo, when commits carry agent files (`.claude/`, `CLAUDE.md`), `.env*`, keys or secret-looking strings, or when `docs/spec.md` or `scripts/autopilot.sh` changed during the run (a session that got past the edit hook with a shell command).
- **Kim's RTK hook rewrites commands** (`git push` becomes `rtk git push`) before the deny list sees them; a real session ran `git push --dry-run` that way. The deny list carries the `rtk` forms of every rule, and the session environment also kills the push URL, the `gh` token and the SSH agent, so a slip still fails.
- Sessions never get SSH or deploy rights. Kim rejected that outright. The droplet's root steps happen in prep with Kim watching; the autopilot deploys only through the GitHub workflow as the unprivileged `deploy` user.

## Droplet prep is more than an A record

- Sketchy's bootstrap needed: DNS checked, a free loopback port (PokéTrack 3004, Buzzr 3005, Sketchy 3006, then the hub and ts-dojo), `/opt/<app>` as root:deploy with the sticky bit, `.env` owned by `deploy` (600), an HTTP-only bootstrap vhost so certbot could answer the challenge (the TLS vhost fails `nginx -t` until the cert exists), certbot by webroot, then the real vhost, `nginx -t` gating every reload, and a memory budget (the droplet had ~700 MB free; Buzzr is capped at 384m, Sketchy at 256m after measuring a 10-player game's peak).
  → Phase 6 does all of it in order, plus a placeholder page so the live URL shows something from day one, and per-repo deploy secrets.
- **nginx keeps no upstream keepalive**, so established connections to the app's port are real clients. The deploy workflow waits for them to drain (in-memory state dies on restart) and the autopilot forces once with `force=true` if a forgotten tab holds a socket open.
- The droplet's nginx predates `http2 on;`; the vhost uses `listen 443 ssl http2`.

## The deploy workflow and the runner are coupled

- The autopilot tells a code failure (a repair session) from an infrastructure failure (one re-run) by the deploy run's job and step names, and spots the drain timeout by its exact `ABORT:` line. A session that "tidied" those names would break recovery silently.
  → The deploy kit says to keep them; the dry run checks they're there once the workflow exists.
- Build the image on the runner and ship it with `docker save | ssh docker load`: the droplet has no memory to spare for builds. Keep the previous image for rollback, re-point `IMAGE_TAG`, gate on health, roll back automatically.

## Paperwork drifts first

- The spec-checker's most frequent finding across Sketchy (F34, F48, F56, F66, F67): code cites `DECISIONS N` before row N exists, superseded rows aren't marked, the PROGRESS entry or Kim checks are missing at review time.
  → The spec-checker checks paperwork explicitly; next-feature step 8 says to verify every cited row.
- Reviewers with project memory (`memory: project`) got better over the run: the secrecy reviewer carried open issues forward ("still open for F19") until a later feature closed them. Keep memory on for invariant reviewers.

## Sessions must not read big files whole

- Sketchy's spec was 1,660 lines, PROGRESS grew past 450 KB, DECISIONS past 180 KB. `roadmap.mjs next` (one entry plus the newest three PROGRESS entries) and `spec.mjs <ID>` (only the cited sections) kept each session's context small. Marking a feature `x` collapses its roadmap entry, so the PROGRESS entry must carry anything worth keeping.
- Roadmap `Spec:` citations must resolve. Phase 5 runs `spec.mjs` on F01 and a later ID; fix any "not found" before handing off.

## Running for a day or two

- 52 features took about 16 hours of sessions plus usage-limit waits: plan on one to two days, not one night. The runner waits out usage limits (reset time from the rate-limit event, else 15/30/60 min backoff) and API outages (5–30 min, 8 tries), keeps the machine awake with `systemd-inhibit`, holds a lock, runs from a copy of itself (bash reads scripts as it goes), and stops after three give-ups in a row rather than burning the rest of the queue.
- A feature that grows too big is split by its session (F95 into F95a/F95b); the runner's counts follow the split.
- Kim stops a run with Ctrl-C (the session's process group is signalled, the summary is written) and resumes by starting it again: the `[~]` feature and its uncommitted work are picked up.
