# Decisions

Only Kim edits `docs/spec.md`. Gaps and conflicts found while building go here, newest last. Code that relies on a row cites it (`// SPEC-QUESTION: DECISIONS 12`); add the row before citing it.

## Open spec questions

Mirrored from the spec's open questions. Until Kim says otherwise, a feature that hits one uses the recommendation and records it under "Decisions made".

## Decisions made

| # | Date | Feature | Decision | Why |
| --- | --- | --- | --- | --- |
{{^VERCEL}}
| 1 | {{BOOTSTRAP_DATE}} | bootstrap | Live at `{{DOMAIN}}` on Kim's droplet, host port `127.0.0.1:{{PORT}}` (checked free with `ss -ltn`), stack dir `/opt/{{APP}}` (root:deploy, 1775) with its `.env`; nginx vhost and certbot certificate installed in prep; the vhost is `deploy/nginx/{{APP}}.conf` | Root steps can't run unattended; the deploy uses only the `deploy` user |
{{/VERCEL}}
{{#VERCEL}}
| 1 | {{BOOTSTRAP_DATE}} | bootstrap | Live at `{{DOMAIN}}` on Vercel (`{{VERCEL_SCOPE}}/{{VERCEL_PROJECT}}`), created in prep with no Git connection; its env (database, storage, secrets) set in prep; `.github/workflows/{{WORKFLOW_FILE}}` deploys with the Vercel CLI and a token held only in GitHub secrets | Sessions never reach Vercel; the push is the only way code ships |
{{/VERCEL}}
| 2 | {{BOOTSTRAP_DATE}} | bootstrap | Unattended runs queue person-only checks under "Kim checks" in PROGRESS.md and mark the feature done; anything that must not ship without Kim's approval carries a `Gate:` line in the roadmap instead | A start-to-finish run must not block on a person, but approvals are not checks |
| 3 | {{BOOTSTRAP_DATE}} | bootstrap | Real keys exist only in {{^VERCEL}}`/opt/{{APP}}/.env`{{/VERCEL}}{{#VERCEL}}the Vercel project's env{{/VERCEL}} and GitHub secrets. Code reads env vars; tests and development use fakes | Build sessions never see real keys |

## Proposed spec changes
