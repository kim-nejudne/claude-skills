# Vercel provisioning (phase 6 with `DEPLOY_TARGET: "vercel"`, Kim watching)

Target: a Vercel project deployed only by the app's GitHub workflow with the Vercel CLI. Use it
when the spec names Vercel, or for a client POC under `~/Documents/work/` that Kim has explicitly
chosen to host on his own GitHub and Vercel until the client takes it over. It never touches the
droplet. Standalone only (no monorepo, no Android).

Rules for this phase:

- Use the **Vercel CLI only**, and run `vercel whoami` and `vercel teams ls` first. The Vercel MCP
  plugin may be logged into a different account (a client's), so never use it here. Every command
  passes `--scope <VERCEL_SCOPE>`.
- Show each command and say what it changes; run it after Kim's go. A read-only batch can share one go.
- Never echo, print, log or read back a secret value. Names and "set/empty" only. `vercel env pull`
  and `vercel env ls` with values are never run in this session.
- `SCRATCH` is your scratchpad directory (never the repo).

## 0. GitHub repo

Same as `droplet.md` step 0 (standalone). A private repo's Actions minutes count against the
account's private allowance.

## 1. Project

```bash
vercel project add <project> --scope <scope>
vercel link --yes --project <project> --scope <scope>     # writes .vercel/ (gitignored)
vercel project inspect <project> --scope <scope>
```

Don't connect the Git repository: the deploy workflow is the only way code reaches Vercel, so an
unchecked commit never ships. If `<project>.vercel.app` was already taken, Vercel gives the project
another domain. Read the real production domain from the dashboard or from the first deploy (step
4), and put it in `DOMAIN`.

## 2. Storage and keyed services

Add what the spec needs from the Marketplace or Vercel storage, and connect it to the project, so
its env vars land in the production env:

```bash
vercel integration add neon --no-env-pull --scope <scope>                   # Postgres: DATABASE_URL and friends (interactive: Kim may run it with `! `)
vercel blob create-store <project>-files --access private --region <region> -e production -e development --yes --scope <scope>   # BLOB_READ_WRITE_TOKEN
vercel env ls production --scope <scope>                                    # names only
```

`--no-env-pull` matters: without it the CLI writes the real values into `.env.local` in the repo.
Private Blob access unless the spec wants public URLs. Pick the region nearest the users. Generated app secrets go straight into the env and are never
shown: `openssl rand -base64 32 | vercel env add SESSION_SECRET production --scope <scope>`.
Kim types third-party keys into `vercel env add NAME production` in **his own terminal**.

## 3. Deploy secrets

1. Kim creates a token at vercel.com/account/settings/tokens, scoped to `<scope>`, expiring when the
   POC is due to end (90 days at most). He runs `gh secret set VERCEL_TOKEN -R <owner>/<app>` in his
   own terminal and pastes it there.
2. `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` come from `.vercel/project.json` (`orgId`, `projectId`):
   `jq -r .orgId .vercel/project.json | gh secret set VERCEL_ORG_ID -R <owner>/<app>`, and the same
   for the project.
3. `gh secret list -R <owner>/<app>` shows all three names.

## 4. Placeholder

A one-file static deploy, so the live URL answers over TLS from day one:

```bash
mkdir -p SCRATCH/placeholder && cd SCRATCH/placeholder
printf '<!doctype html><title><App></title><p><App> is being built.</p>\n' > index.html
vercel link --yes --project <project> --scope <scope>
vercel deploy --prod --yes --scope <scope>
curl -sI https://<domain>/ | head -1                       # 200
```

The first push from the autopilot (right after F03) replaces it with the app.

## 5. bootstrap.json

Set `DEPLOY_TARGET: "vercel"`, `VERCEL_SCOPE`, `VERCEL_PROJECT` and `DOMAIN`, re-render, then commit
anything under `docs/` that changed. There is nothing under `deploy/`: no port, memory budget or
vhost.
