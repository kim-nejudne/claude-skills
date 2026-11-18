# Bash CLI stack: F01 scaffold

Used when the spec names Bash for a local command-line tool. It pairs with `DEPLOY_TARGET: "none"`: there is no server, no Docker image and no live URL. The autopilot builds, pushes, and waits for `ci.yml` to go green.

## Machine (phase 7, before F01)

`bats`, `shfmt` and `shellcheck` must be on PATH (Arch: `pacman -S bats shfmt shellcheck`). Check with `command -v bats shfmt shellcheck`. An unattended session can't install them.

## Layout

```
bin/<tool>         the entry point: `#!/usr/bin/env bash`, `set -Eeuo pipefail`, subcommand dispatch
lib/               sourced helpers, only once bin/ grows past one readable file
tests/*.bats       bats-core tests; tests/helpers.bash builds a temp git repo and fixtures per test
scripts/           autopilot.sh (bootstrap)
docs/              spec, review, roadmap, progress, decisions
```

- Resolve the repo from the script, not the cwd: `ROOT=$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")/.." && pwd)`, so a symlink in `~/.local/bin` works.
- Anything time-dependent reads an override env var (`<TOOL>_TODAY=YYYY-MM-DD`), so tests pin the date.
- Target GNU coreutils, gawk, sed and git: no extra runtime dependencies unless the spec names them.
- Tests never touch the real repo. Each test runs in `BATS_TEST_TMPDIR` with its own `git init` and commits, using `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` for history.

## Checks (CHECKS, CI and verify)

| name | cmd |
| --- | --- |
| `format` | `shfmt -d -i 2 -ci bin tests` |
| `lint` | `shellcheck -x bin/* tests/*.bash` |
| `test` | `bats tests` |

F01 adds one passing bats test (for example, `<tool> help` exits 0) so every check runs green from the start.

## bootstrap.json values

```json
"STACK": "bash",
"STACK_SUMMARY": "Bash 5, GNU coreutils/gawk/sed, git; bats-core, shellcheck, shfmt",
"NODE_VERSION": "24",
"INSTALL_CMD": "sudo apt-get update && sudo apt-get install -y bats shfmt",
"LOCKFILE": "",
"SCAFFOLD_FILE": "bin/<tool>",
"FORMAT_CMD": "shfmt -w -i 2 -ci bin tests",
"FORMATTER": { "bin": "shfmt", "args": ["-w", "-i", "2", "-ci"], "exts": [".sh", ".bash", ".bats"] },
"TYPECHECK": null,
"TEST_ONE_CMD": "bats <file>",
"UI": false, "WEB": false, "DB": false, "DRAIN": false,
"DEPLOY_TARGET": "none"
```

`NODE_VERSION` is unused for a non-Node stack, but the renderer requires it. The hooks and `roadmap.mjs` run on the host's Node. `INSTALL_CMD` is CI's install step (ubuntu-latest already has shellcheck). Locally the tools come from the machine check above, so sessions never run it. A formatter `bin` with no `/` resolves on PATH. The bin in `bin/<tool>` has no extension, so the format hook skips it, and the `format` check catches it instead.
