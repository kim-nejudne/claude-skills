# The four review lenses

Read the spec in full once per lens, as that person would. Write findings into `docs/spec-review.md` (skeleton: `templates/skeletons/spec-review.md`). Each finding:

- **Severity:** Must (blocks an unattended build, or ships something broken or unsafe) · Should (real cost if skipped) · Could (polish).
- **Kind:** clear-cut (one sensible answer: applied as the default at the gate) · fork (a genuine product or cost choice: one AskUserQuestion to Kim).
- **Where:** the spec sections it changes.
- **What goes wrong:** a concrete scene, not an abstraction. "Ana opens the link on a budget Android over 4G and waits 9 s on a white screen" beats "performance may suffer".
- **Proposed spec text:** the exact wording to add or replace, ready to paste.
- **Default:** what gets applied if Kim doesn't choose.

Aim for findings that change the build. Skip style nits. A short review with ten real findings beats forty weak ones. Mark challenges to **[decided]** items as **Reverses [decided]**.

## Product designer

- **Flows:** walk every role through first use, the core loop, and the unhappy paths (wrong input, lost connection, back button, refresh, two tabs, the empty state, the 100th item). Where does a first-timer freeze? Where is there dead time?
- **Scope:** what the first real use needs and what it doesn't. Move nice-to-haves to the Backlog; pull forward anything the first real use can't do without.
- **Audience and locale lock** (Locks section, mandatory): who uses it, on what devices, where, in which language(s), US or UK spelling, units, time zones, currencies. Sketchy reversed its audience after launch and paid a milestone for it.
- **Look lock** (Locks section): which mock is the target, light or dark or both, the fonts. A missing look is a fork for Kim, not something a session invents later.
- **Spec vs mocks:** every screen in the spec has a mock or a written layout; every element in a mock is in the spec or explicitly out. List each mismatch and which side wins.
- **Copy:** tone, the words for key actions and errors, consistent terms (one name per thing).
- **Accessibility:** contrast, keyboard use, screen reader labels, reduced motion, touch target sizes.

## Architect / tech lead

- **Stack:** named by the spec, or the default (Node 24, TypeScript, Vite + React, vitest, eslint + prettier, npm). Flag anything that won't run in one container on a small droplet.
- **Data model:** every entity, its owner, its lifetime; what is derived vs stored; where the source of truth is. In-memory vs SQLite on a volume vs a hosted DB (a hosted DB needs a key and a fake).
- **Unattended buildability**, per feature-sized chunk: can a session with no human build it and prove it with automated tests? Anything that needs a real device, a real account or a human judgement becomes a Kim check (the automated part still gets built and tested) or a `Gate:` (if it must not ship without approval).
- **Fakes for every keyed service:** each external API (payments, email, maps, LLMs, auth providers, storage) sits behind one module with a fake used in tests and development. Name the module, the env vars it reads, and what the fake does. No session ever needs a real key.
- **Testability:** pure logic separated from I/O; injectable clock and randomness; a seam for every network boundary. Name the invariants that need dedicated tests (they become CLAUDE.md's "Never break" and the invariant reviewers).
- **Health and smoke:** a `GET /healthz` (or the stack's equivalent) returning `{ok: true}`, and the few critical paths a smoke script must hit against a base URL.
- **Size:** the roadmap must split into features of one session each (≤ ~10 files, ~600 lines). Flag spec areas too tangled to split.

## Security / privacy

- **Auth:** who can do what; how identity is established (none, a token, a magic link, OAuth via a keyed provider); session lifetime; what an unauthenticated visitor can reach.
- **Input validation:** every inbound payload validated at the boundary with a schema (zod for TS), with length and count limits. Name them.
- **Secrets:** the env var names, where each real value lives (droplet `.env`, GitHub secrets), that none reaches the client bundle, logs or errors. Any client-side "public" key is called out as such.
- **Abuse:** rate limits per IP or per account (behind nginx, `TRUST_PROXY=1` so the real IP is used), enumeration of codes or ids, spam, uploads (type, size, storage), cost attacks on keyed services.
- **Privacy and retention:** what personal data is stored, for how long, how it is deleted; no analytics or third-party trackers unless the spec says so; what is logged.
- **Output:** escaping, no raw HTML injection, CSP if the app renders user content, CORS kept tight.

## Ops / deploy

- **Target:** `https://<app>.$BOOTSTRAP_DOMAIN` on Kim's droplet (`$BOOTSTRAP_DROPLET_IP`), one container on a loopback port behind nginx with TLS. Anything else (serverless, a managed DB, a second service) is a fork for Kim with its cost.
- **Docker:** multi-stage, built on the GitHub runner (never on the droplet), non-root user, `HEALTHCHECK`, stops on SIGTERM in under 5 s.
- **Droplet fit:** a memory cap (`mem_limit`) from a measured peak plus headroom that fits next to the other apps (check `free -m` in phase 6); a free port; disk for images (two kept for rollback).
- **Health and smoke:** `/healthz` on the container; a smoke script against any base URL (container on the runner, then the live URL after deploy).
- **Deploy and rollback:** push to main deploys via `.github/workflows/deploy-<app>.yml` (from the deploy kit); the previous image stays for a `workflow_dispatch` re-point; automatic rollback when health fails.
- **State on restart:** in-memory state dies on deploy. Say whether that's acceptable, and keep the drain wait (live connections) if users can be mid-session.
- **Backups** if there is a database: what, how often, where, retention, and a restore drill as a Kim check. Default: nightly SQLite `.backup` on the droplet, 14 days, following any existing convention there.
- **Logs and monitoring:** container logs only by default; what a failure looks like and how Kim would notice (the morning report covers the first deploy).

## A native Android client (when the spec has one)

Each lens also reads the phone app as its person would (`reference/stack-android.md` is the build).

- **Product:** the phone in its real place: sunlight on the screen, gloves or wet hands, one hand, a queue waiting. Touch targets of at least 48dp, text that survives the phone's font size setting, every action reachable without typing where possible. What the person sees while offline, while syncing, after an update. Install and first run are someone's job (who, with what steps).
- **Architect:** the phone's local database is the working copy and the server the record: client-generated ids (UUIDs) so uploads are idempotent, a queue that survives restarts, and a stated rule for every conflict. Background sync runs on WorkManager: periodic work is 15 minutes at best, Doze and OEM battery savers delay it further, so say what "synced" promises and add a Kim check on the real phone. Seams with fakes for the camera, OCR, installer, clock and server. APK size (a bundled ML Kit model is native; filter ABIs to ARM). minSdk against the target phones.
- **Security / privacy:** permissions, each with its reason (camera, network, install packages; nothing else). `allowBackup="false"` and no cleartext traffic. Where the device token lives (app-private storage) and how it is revoked. Photos and records stay in app-private storage, with their retention job. Update integrity: HTTPS, the sha256 in `version.json`, and the same signing key (Android enforces it). Whether the APK download is public (it holds no secrets) or behind the owner's login. Key custody: the release keystore only in GitHub secrets and Kim's offline backup.
- **Ops / deploy:** the APK ships inside the image (`scripts/apk-release.sh`, the APK feature before Docker), versionCode counts the commits that changed `android/`, phones never downgrade (a rollback serves an older APK they ignore), losing the key means reinstalling on every phone. Phone setup, restore onto a replacement and the first install are Kim checks with exact steps.
