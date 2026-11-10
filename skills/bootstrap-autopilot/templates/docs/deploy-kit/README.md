# Deploy kit

Rendered by the bootstrap for {{DEPLOY_FEATURE}} and {{DOCKER_FEATURE}}. These are starting points, not live files:

| File | Moves to | Feature |
| --- | --- | --- |
{{#NODE}}
| `Dockerfile.node` | `Dockerfile` | {{DOCKER_FEATURE}} |
{{/NODE}}
{{^NODE}}
| (write one for the stack: multi-stage, non-root, `HEALTHCHECK` on `{{HEALTH_PATH}}`) | `Dockerfile` | {{DOCKER_FEATURE}} |
{{/NODE}}
| `docker-smoke.sh` | `scripts/docker-smoke.sh` | {{DOCKER_FEATURE}} |
{{#ANDROID}}
| `apk-release.sh` | `scripts/apk-release.sh` | {{APK_FEATURE}} |
{{/ANDROID}}
{{^MONOREPO}}
| `deploy.yml` | `.github/workflows/{{WORKFLOW_FILE}}` | {{DEPLOY_FEATURE}} |
{{/MONOREPO}}
{{#MONOREPO}}
| `deploy.yml` | `{{ROOT_REL}}.github/workflows/{{WORKFLOW_FILE}}` (the monorepo's root, not this app's folder) | {{DEPLOY_FEATURE}} |
| `ci-jobs.yml` | its two jobs into `{{ROOT_REL}}.github/workflows/ci.yml` (nothing else in that file changes) | F01 |

{{DEPLOY_FEATURE}} also adds {{APP_TITLE}} to the root `{{ROOT_REL}}README.md` in the same shape as the other apps (their table row and provenance line).
{{/MONOREPO}}

Keep in `deploy.yml`: the job names `checks` and `droplet`, the step name `build and smoke-test the image`{{#ANDROID}}, the step name `build the release APK`{{/ANDROID}}, the check step names, and the line `ABORT: N live connection(s) after 10 min`. `scripts/autopilot.sh` matches them to tell a code failure (repair session) from an infrastructure one (one re-run) and to force a deploy past live connections.

Already live, do not change: `deploy/nginx/{{APP}}.conf` (installed on the droplet in prep; nginx is root's), `deploy/compose.deploy.yaml` (shipped by the workflow; the smoke test reads its port and `mem_limit`).

{{^MONOREPO}}
GitHub secrets set in prep: `SSH_HOST`, `SSH_USER` (`deploy`), `SSH_KEY` (a key for this repo only), `SSH_KNOWN_HOSTS`. App secrets live only in `/opt/{{APP}}/.env` on the droplet; the container reads them through `env_file`.
{{/MONOREPO}}
{{#MONOREPO}}
GitHub secrets: the monorepo's shared deploy secrets ({{DEPLOY_SECRETS}}, environment `{{DEPLOY_ENVIRONMENT}}`), which the other apps' deploy workflows use too. Never change them. App secrets live only in `/opt/{{APP}}/.env` on the droplet; the container reads them through `env_file`.
{{/MONOREPO}}

{{#ANDROID}}
Android release key: GitHub secrets `{{ANDROID_SECRET_PREFIX}}ANDROID_KEYSTORE_B64`, `{{ANDROID_SECRET_PREFIX}}ANDROID_KEYSTORE_PASSWORD` and `{{ANDROID_SECRET_PREFIX}}ANDROID_KEY_ALIAS`, set in prep; Kim holds the only other copy, offline. Phones accept an update only when it is signed with the same key, so a lost key means reinstalling the app (and losing the phone's data) on every phone. The workflow decodes it on the runner for `scripts/apk-release.sh`; it never reaches the image, the repo or a session.

{{/ANDROID}}
The release check (the roadmap's last feature) deletes this folder once every file is in place{{#ANDROID}}; {{APK_FEATURE}} still needs `apk-release.sh` from it{{/ANDROID}}.
