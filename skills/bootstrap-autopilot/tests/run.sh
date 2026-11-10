#!/usr/bin/env bash
# Tests for the bootstrap-autopilot templates. No network, no real claude or gh.
#
#   tests/run.sh            everything
#   tests/run.sh <name>...  only these scenarios (render, roadmap, guard, blocked, env, badenv, echo, early)
#
# render:   the three fixtures (standalone, monorepo, Android) render, and each autopilot.sh passes
#           bash -n and shellcheck.
# The rest run a rendered standalone app's scripts/autopilot.sh against a local bare origin, with
# tests/fake/{claude,gh} on PATH and a local web server as the live URL.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SKILL=$(dirname -- "$HERE")
WORK=$(mktemp -d "${TMPDIR:-/tmp}/autopilot-tests.XXXXXX")
trap 'rm -rf -- "$WORK"' EXIT
FAILED=0 PASSED=0

pass() { PASSED=$((PASSED + 1)) && echo "  ok   $*"; }
fail() { FAILED=$((FAILED + 1)) && echo "  FAIL $*"; }
check() { # check DESCRIPTION COMMAND...
  local what=$1
  shift
  if "$@" >/dev/null 2>&1; then pass "$what"; else fail "$what"; fi
}

render() { # render FIXTURE DIR
  mkdir -p "$2"
  node "$SKILL/templates/render.mjs" "$HERE/fixtures/$1.json" "$2" >/dev/null
}

t_render() {
  echo "render"
  local f d
  for f in standalone monorepo android; do
    d=$WORK/render-$f
    if ! render "$f" "$d"; then
      fail "$f renders"
      continue
    fi
    check "$f: bash -n" bash -n "$d/scripts/autopilot.sh"
    if command -v shellcheck >/dev/null; then
      check "$f: shellcheck" shellcheck "$d/scripts/autopilot.sh"
    fi
  done
}

# A standalone app at $APPDIR, F01 done, the given roadmap features to build, committed and clean.
# setup NAME WORKFLOW_AT_START "F02 Title|Depends" ...
setup() {
  local name=$1 wf=$2 spec id title deps
  shift 2
  T=$WORK/$name
  APPDIR=$T/app
  FAKE=$T/fake
  mkdir -p "$FAKE" "$T/www"
  : >"$FAKE/plan"
  : >"$FAKE/deploys"
  render standalone "$APPDIR"
  git init -q --bare "$T/origin.git"
  (
    cd "$APPDIR"
    git init -q -b main
    git config user.name test && git config user.email test@example.invalid
    git remote add origin "$T/origin.git"
    echo '{"name": "pantry"}' >package.json
    {
      echo '# Roadmap'
      echo
      echo '## M1 — Core'
      echo
      echo '- [x] F01 Project skeleton'
      for spec in "$@"; do
        id=${spec%% *} title=${spec#* } deps=${title#*|} title=${title%|*}
        [[ $deps == "$title" ]] && deps=none
        printf -- '- [ ] %s %s\n  - Depends: %s\n  - Done when:\n    - it exists\n' "$id" "$title" "$deps"
      done
    } >docs/ROADMAP.md
    if ((wf)); then
      mkdir -p .github/workflows
      echo 'name: Deploy (fake)' >.github/workflows/deploy-pantry.yml
    fi
    git add -A && git commit -qm 'chore: bootstrap'
  )
  echo '{"ok":true}' >"$T/www/healthz"
  echo 'pantry' >"$T/www/index.html"
}

# run_autopilot [ARGS...]: runs the app's autopilot, output in $T/out.txt, exit code in RC.
run_autopilot() {
  local port pid
  port=$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
  python3 -m http.server "$port" --bind 127.0.0.1 --directory "$T/www" >/dev/null 2>&1 &
  pid=$!
  RC=0
  (
    cd "$APPDIR"
    FAKE=$FAKE PATH="$HERE/fake:$PATH" XDG_CACHE_HOME=$T/cache AUTOPILOT_TEST=1 AUTOPILOT_PLAIN=1 \
      AUTOPILOT_INHIBITED=1 AUTOPILOT_WAIT_DIVISOR=60 AUTOPILOT_SESSION_TIMEOUT=60 \
      AUTOPILOT_LIVE_URL="http://127.0.0.1:$port" timeout 300 scripts/autopilot.sh "$@"
  ) >"$T/out.txt" 2>&1 || RC=$?
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  REPORT=$(find "$T/cache/pantry-autopilot" -name morning-report.md -path '*/2*' | sort | tail -1)
}

in_out() { grep -qE -- "$1" "$T/out.txt"; }
in_report() { grep -qF -- "$1" "$REPORT"; }
in_gh() { grep -qE -- "$1" "$FAKE/gh.log"; }
pushed() { [[ $(git -C "$T/origin.git" rev-parse main 2>/dev/null) == $(git -C "$APPDIR" rev-parse HEAD) ]]; }
roadmap_mark() { sed -nE "s/^- \[(.)\] $1 .*/\1/p" "$APPDIR/docs/ROADMAP.md"; }
not() { ! "$@"; }

t_roadmap() {
  echo "roadmap.mjs: features behind a blocked one wait, they don't stall"
  setup roadmap 1 'F02 Blocked one' 'F03 Needs it|F02'
  (cd "$APPDIR" && node .claude/scripts/roadmap.mjs mark F02 '!' 'stuck' >/dev/null)
  local out
  out=$(cd "$APPDIR" && node .claude/scripts/roadmap.mjs next)
  check "prints Nothing left" grep -q '^Nothing left: 1 feature(s) wait on blocked or gated features (F03)' <<<"$out"
  check "no Not eligible line" not grep -q '^Not eligible' <<<"$out"
}

t_guard() {
  echo "push guard after each commit: a real-looking fake key is taken back out and redone"
  setup guard 0 'F02 Keyed client' 'F03 Next thing|F02'
  echo 'F02 fakekey' >"$FAKE/plan"
  run_autopilot --no-deploy
  check "exit 0" test "$RC" -eq 0
  check "the runner un-committed F02" in_out 'F02.s commit fails the push guard'
  check "the second attempt got the guard's note" grep -qx 'F02 fakekey note=1' "$FAKE/sessions.log"
  check "no commit carries the key" test -z "$(git -C "$APPDIR" log -G 'sk-ant-api03' --format=%h)"
  check "F02 and F03 built" test "$(roadmap_mark F02)$(roadmap_mark F03)" = xx
}

t_blocked() {
  echo "a blocked feature doesn't stop the rest from shipping"
  setup blocked 1 'F02 Stuck' 'F03 Needs stuck|F02' 'F04 Independent'
  echo 'F02 block' >"$FAKE/plan"
  run_autopilot
  check "exit 0" test "$RC" -eq 0
  check "pushed" pushed
  check "F02 still blocked, F03 not built, F04 built" test "$(roadmap_mark F02)$(roadmap_mark F03)$(roadmap_mark F04)" = '! x'
  check "the report says what is blocked" in_report '**Blocked features**'
  check "the stash holds F02's half-built work" bash -c "git -C '$APPDIR' stash list | grep -q 'F02 blocked'"
}

t_env() {
  echo "missing env vars on the droplet: no re-run, no force, the report names them"
  setup env 1 'F02 Thing'
  echo 'missing-env' >"$FAKE/deploys"
  run_autopilot
  check "exit 1" test "$RC" -eq 1
  check "no re-run" not in_gh 'run rerun'
  check "no forced deploy" not in_gh 'force=true'
  check "no repair session" not grep -qx repair "$FAKE/sessions.log"
  check "the report names the vars" in_report '**Fix on the droplet:** set ADMIN_HASH MAIL_KEY in /opt/pantry/.env'
}

t_badenv() {
  echo "the app rejects a droplet env value: Kim's to fix, not a repair session"
  setup badenv 1 'F02 Thing'
  echo 'bad-env' >"$FAKE/deploys"
  run_autopilot
  check "exit 1" test "$RC" -eq 1
  check "no repair session" not grep -qx repair "$FAKE/sessions.log"
  check "no re-run" not in_gh 'run rerun'
  check "the report quotes the app's message" in_report 'rejected /opt/pantry/.env and the deploy rolled back: Invalid environment: ADMIN_HASH'
}

t_echo() {
  echo "an ABORT line only echoed in the workflow's script is not live connections"
  setup echo 1 'F02 Thing'
  printf 'echo-fail\nsuccess\n' >"$FAKE/deploys"
  run_autopilot
  check "exit 0" test "$RC" -eq 0
  check "no forced deploy" not in_gh 'force=true'
  check "one re-run" test "$(grep -c 'run rerun' "$FAKE/gh.log")" -eq 1
  check "live" in_out 'Live: http://127.0.0.1:[0-9]+/healthz'
}

t_early() {
  echo "early deploy: once, right after the workflow lands; a failure doesn't stop the build"
  setup early 0 'F02 Docker image' 'F03 Deploy workflow|F02' 'F04 Feature|F03' 'F05 Feature|F04'
  echo 'F03 workflow' >"$FAKE/plan"
  printf 'missing-env\nsuccess\n' >"$FAKE/deploys"
  run_autopilot
  check "exit 0" test "$RC" -eq 0
  check "the early deploy ran after F03" in_out 'Early deploy: deploy-pantry.yml exists now'
  check "it failed and the build went on" test "$(roadmap_mark F04)$(roadmap_mark F05)" = xx
  check "two pushed deploy runs" test "$(grep -c $'\tpush\t' "$FAKE/runs.tsv")" -eq 2
  check "the report has the early deploy's failure" in_report 'Early deploy (mid-run): failed:'
  check "the final deploy's success cleared the env warning" not in_report 'Fix on the droplet'
  check "pushed" pushed
}

ALL=(render roadmap guard blocked env badenv echo early)
for t in "${@:-${ALL[@]}}"; do
  "t_$t"
done
echo
echo "$PASSED passed, $FAILED failed"
((FAILED == 0))
