# Droplet provisioning (phase 6, Kim watching)

Target: `https://<app>.$BOOTSTRAP_DOMAIN` on Kim's DigitalOcean droplet `$BOOTSTRAP_DROPLET_IP`, which runs Kim's personal apps (Buzzr, Sketchy, PokéTrack, the hub, ts-dojo…). It is never hosting for a client engagement. Root SSH works from Kim's machine (user-scope settings); the deploy workflow later uses only the unprivileged `deploy` user.

Rules for this phase:

- Show each command in a code block and say what it changes, then run it after Kim's go. Read-only commands can go as one batch.
- Never echo, print, log or read back a secret value. Key names and "set/empty" only.
- Every nginx change is gated by `nginx -t`; reload only after it passes. Never restart nginx (a reload keeps the other sites up).
- Note other vhosts' status codes before you touch nginx, and compare after.
- Replace `<app>`, `<port>`, `<domain>` and `<owner>` below. `R=root@$BOOTSTRAP_DROPLET_IP`; `SCRATCH` is your scratchpad directory (never the repo).

## 0. GitHub repo

```bash
gh api user --jq .login                                   # the owner
gh repo view <owner>/<app> >/dev/null 2>&1 && echo EXISTS # must not exist yet
gh repo create <owner>/<app> --public --source . --remote origin --description "<pitch>"
git remote -v
```

No push: the autopilot pushes once, at the end. Tell Kim beforehand that `docs/` (spec, review, roadmap, decisions) becomes public then.

## 1. DNS

```bash
dig +short <domain> A
dig +short @1.1.1.1 <domain> A
```

Both must print `$BOOTSTRAP_DROPLET_IP`. If not, stop: Kim adds the Namecheap A record (`<app>` → `$BOOTSTRAP_DROPLET_IP`) and you wait for it.

## 2. Read the box (one read-only batch)

```bash
ssh $R '
  echo "== listeners";  ss -Hltn | awk "{print \$4}" | grep -E "^127\.0\.0\.1:30[0-9]{2}$" | sort
  echo "== vhost ports"; grep -rhoE "proxy_pass http://127\.0\.0\.1:[0-9]+" /etc/nginx/sites-available | sort -u
  echo "== compose ports"; grep -hoE "127\.0\.0\.1:[0-9]+:" /opt/*/compose.yaml 2>/dev/null | sort -u
  echo "== memory"; free -m
  echo "== container limits"; docker ps --format "{{.Names}}" | xargs -r docker inspect -f "{{.Name}} {{.HostConfig.Memory}}"
  echo "== disk"; df -h / | tail -1
  echo "== nginx"; nginx -v 2>&1; ls /etc/nginx/sites-enabled
  echo "== certbot"; certbot --version 2>&1; ls /var/www/certbot >/dev/null && echo "webroot ok"
  echo "== deploy user"; id deploy; ls -ld /home/deploy/.ssh
  echo "== /opt"; ls -l /opt
  echo "== backups"; ls /etc/cron.d; ls -d /opt/backups 2>/dev/null
'
```

- **Port:** the lowest `30NN` above 3003 that no listener, vhost or compose file uses. Record it in bootstrap.json and DECISIONS row 1.
- **Memory:** available memory must cover the app's `MEM_LIMIT` with room to spare; containers' limits show what is already promised. If it is tight, say so and agree a lower limit with Kim (the Docker feature measures the real peak later).
- **Disk:** at least 3 GB free for two images (current + rollback). Below that, stop and tell Kim (`docker image prune` on the box is Kim's call).
- Check `/opt/<app>` doesn't exist yet and no vhost already names `<domain>`.

Snapshot the other sites first:

```bash
for h in $(ssh $R "grep -rhoE 'server_name [^;]+' /etc/nginx/sites-enabled | awk '{print \$2}' | sort -u"); do
  printf '%s %s\n' "$h" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$h/")"
done | tee "$SCRATCH/vhosts-before.txt"
```

## 3. Stack dir and .env

```bash
ssh $R 'install -d -o root -g deploy -m 1775 /opt/<app> \
  && install -o deploy -g deploy -m 600 /dev/null /opt/<app>/.env \
  && printf "IMAGE_TAG=\n" > /opt/<app>/.env \
  && ls -la /opt/<app>'
```

Then the key names from the spec, values empty (one `printf` with every name):

```bash
ssh $R 'printf "%s=\n" OPENAI_API_KEY SMTP_URL >> /opt/<app>/.env'
```

Kim fills the values **in his own terminal**, not through this session:

```
ssh -t root@$BOOTSTRAP_DROPLET_IP 'sudo -u deploy nano /opt/<app>/.env'
```

Verify without seeing values:

```bash
ssh $R "awk -F= '{ print \$1, (length(\$0) > length(\$1) + 1 ? \"set\" : \"EMPTY\") }' /opt/<app>/.env; stat -c '%U:%G %a' /opt/<app>/.env"
```

`IMAGE_TAG` stays empty until the first deploy. A key Kim doesn't have yet stays EMPTY: the app must boot without it (fakes or a disabled feature) and a Kim check covers it.

## 4. Placeholder, bootstrap vhost, certificate, full vhost

Files come from the rendered repo: `deploy/placeholder/index.html`, `deploy/nginx/<app>-bootstrap.conf`, `deploy/nginx/<app>.conf`.

```bash
ssh $R 'install -d -m 755 /var/www/<app>-placeholder /var/www/certbot'
scp deploy/placeholder/index.html $R:/var/www/<app>-placeholder/__placeholder.html

scp deploy/nginx/<app>-bootstrap.conf $R:/etc/nginx/sites-available/<app>
ssh $R 'ln -sfn /etc/nginx/sites-available/<app> /etc/nginx/sites-enabled/<app> && nginx -t && systemctl reload nginx'
curl -sI http://<domain>/.well-known/acme-challenge/x | head -1     # 404 from this vhost, not another site

ssh $R 'certbot certonly --webroot -w /var/www/certbot -d <domain> --non-interactive --keep-until-expiring'
ssh $R 'ls /etc/letsencrypt/live/<domain>/ && certbot renew --dry-run --cert-name <domain> 2>&1 | tail -2'

scp deploy/nginx/<app>.conf $R:/etc/nginx/sites-available/<app>
ssh $R 'nginx -t && systemctl reload nginx'
```

If `nginx -t` fails at any point: don't reload; put the previous file back (`<app>-bootstrap.conf`, or remove the symlink), run `nginx -t` again, and fix before going on. Certbot must not edit the vhost (that is why it is `certonly --webroot`).

Check:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://<domain>/          # 503: the placeholder, TLS valid
curl -sS https://<domain>/ | grep -o '<title>[^<]*'                  # the placeholder's title
curl -sS -o /dev/null -w '%{http_code}\n' https://<domain>/healthz   # 503, never 200 before the app exists
```

Then re-run the vhost snapshot and `diff` it with `vhosts-before.txt`: every other site must answer exactly as before.

## 5. Database (only if the spec has one)

```bash
ssh $R 'install -d -o 1000 -g 1000 -m 750 /opt/<app>/data'
```

The container's non-root user is uid 1000 (`node` in the official Node image); match it to the Dockerfile's user for other stacks.

Backups follow whatever the box already does (step 2 listed `/etc/cron.d` and `/opt/backups`). If there is no convention, propose this to Kim and install it after a go:

```bash
ssh $R 'install -d -m 700 /opt/backups/<app> && cat > /etc/cron.d/<app>-backup <<EOF
# Nightly SQLite backup for <domain>, kept 14 days (bootstrap-autopilot).
17 3 * * * root sqlite3 /opt/<app>/data/<app>.db ".backup /opt/backups/<app>/<app>-\$(date +\%F).db" && find /opt/backups/<app> -name "*.db" -mtime +14 -delete
EOF
chmod 644 /etc/cron.d/<app>-backup; command -v sqlite3'
```

Off-box copies (DigitalOcean backups or snapshots) are Kim's call; mention them. Add a Kim check for a restore drill once the app has data.

## 6. Deploy access and GitHub secrets

A key for this repo only, so it can be revoked alone:

```bash
K="$SCRATCH/<app>-deploy"
ssh-keygen -t ed25519 -N '' -C '<app>-deploy-gha' -f "$K" -q
ssh $R "install -d -o deploy -g deploy -m 700 /home/deploy/.ssh && printf 'restrict %s\n' '$(cat "$K.pub")' >> /home/deploy/.ssh/authorized_keys && chown deploy:deploy /home/deploy/.ssh/authorized_keys && chmod 600 /home/deploy/.ssh/authorized_keys"
ssh -i "$K" -o IdentitiesOnly=yes -o BatchMode=yes deploy@$BOOTSTRAP_DROPLET_IP 'id -un; docker ps --format "{{.Names}}" | head -3; test -w /opt/<app> && echo "can write /opt/<app>"'
```

`restrict` turns off forwarding and PTYs; the workflow needs neither (`docker load` over a pipe, `scp`, and a `bash -s` script all work).

Set the secrets on the new repo. The known-hosts line comes from Kim's own verified `known_hosts`, not a fresh keyscan:

```bash
gh secret set SSH_HOST --repo <owner>/<app> --body $BOOTSTRAP_DROPLET_IP
gh secret set SSH_USER --repo <owner>/<app> --body deploy
gh secret set SSH_KEY --repo <owner>/<app> < "$K"
ssh-keygen -F $BOOTSTRAP_DROPLET_IP -f ~/.ssh/known_hosts | grep -v '^#' | gh secret set SSH_KNOWN_HOSTS --repo <owner>/<app>
gh secret list --repo <owner>/<app>
```

If `ssh-keygen -F` finds nothing (hashed or missing), use `ssh-keyscan -t ed25519 $BOOTSTRAP_DROPLET_IP` and compare its fingerprint with `ssh $R 'ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub'` before using it.

Then remove the private key: GitHub holds the only copy. Rotating it means repeating this step (and deleting the old line from `authorized_keys`).

```bash
shred -u "$K"; rm -f "$K.pub"
```

App secrets the build needs at image build time (rare: a public client key) are set the same way with `gh secret set`, and the deploy feature passes them as build args. Runtime secrets stay only in `/opt/<app>/.env`.

## 7. Record

- bootstrap.json: `PORT`, `MEM_LIMIT` if agreed lower. Re-render `deploy/compose.deploy.yaml`, `deploy/nginx/<app>.conf` (if the port changed after installing it, install it again with `nginx -t`), `docs/DECISIONS.md` row 1 (by hand: it may already hold more rows), `scripts/autopilot.sh`, `docs/deploy-kit/*`, `CLAUDE.md`.
- Commit `chore: droplet vhost and compose` with whatever changed under `deploy/`, `docs/` and `scripts/`.
- Tell Kim: the live URL shows the placeholder; the deploy user and secrets are set; which `.env` keys are still EMPTY.
