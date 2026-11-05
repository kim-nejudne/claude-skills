#!/usr/bin/env bash
# Unattended roadmap runner for {{APP_TITLE}} (rendered by the bootstrap-autopilot skill from the
# runner proven on two earlier apps). Builds every remaining docs/ROADMAP.md feature with one
# fresh `claude -p "/next-feature"` session each (a fresh session is the same as /clear), retries
# failures, gives blocked features one more pass, then gates, pushes once and deploys to
# {{DOMAIN}} once nothing is left.
#
#   scripts/autopilot.sh [--dry-run] [--no-deploy] [--max-attempts N]
#
# --dry-run builds nothing. It checks the queue, the push guard, gh auth and the repo's deploy
# secrets, SSH reachability and disk on the droplet, and the live URL, then stops.
#
# It runs from a copy of itself (sessions never edit this file, and bash reads a script as it
# goes). Sessions run with --dangerously-skip-permissions and a hard deny list (push, reset,
# clean, checkout, rebase, remote, gh, ssh, scp, docker, rm -rf, sudo, roadmap ungate). Their
# environment also points origin's push URL nowhere and gives gh a dead token, so a push or gh
# call that slips past the deny list still fails. This script does the push and deploy itself,
# after the push guard: the right remote, no secrets or agent files in the commits, and
# docs/spec.md and this file unchanged since the run started.
# Checks only Kim can do are queued under "Kim checks" in docs/PROGRESS.md; they never block the
# run. Features with a "Gate:" line wait for Kim and never block the deploy of the rest.
# Logs: ~/.cache/{{APP}}-autopilot/<UTC timestamp>/ (run.log, status.txt, summary.txt,
# morning-report.md, one .jsonl per session). ~/.cache/{{APP}}-autopilot/morning-report.md
# always points at the newest report.
#
# Test hooks (environment; unset in a real run): AUTOPILOT_SESSION_TIMEOUT (default 3h),
# AUTOPILOT_LIVE_URL (default {{LIVE_URL}}), AUTOPILOT_WAIT_DIVISOR (default 1; divides every
# fixed wait, backoff and poll interval, but not the wait for a usage-limit reset),
# AUTOPILOT_PLAIN=1 (no pinned status area), AUTOPILOT_OFFLINE=1 (dry runs and --no-deploy only: skip gh,
# ssh and the live URL, allow a local origin). XDG_CACHE_HOME moves the logs and lock.

# Functions called from traps or through dry_check look unused to shellcheck; jq and sed
# programs are single-quoted on purpose.
# shellcheck disable=SC2329,SC2016,SC2017
set -Eeuo pipefail

# ---------------------------------------------------------------------------------------------
# Options and paths

DRY_RUN=0
DEPLOY=1
MAX_ATTEMPTS=3
MAX_SESSIONS=150
MAX_GIVEUPS_IN_A_ROW=3
SESSION_TIMEOUT=${AUTOPILOT_SESSION_TIMEOUT:-3h}
LIVE_URL=${AUTOPILOT_LIVE_URL:-'{{LIVE_URL}}'}
WAIT_DIVISOR=${AUTOPILOT_WAIT_DIVISOR:-1}
OFFLINE=${AUTOPILOT_OFFLINE:-}

# Project facts, rendered once by the bootstrap.
APP='{{APP}}'
APP_TITLE='{{APP_TITLE}}'
GH_REPO='{{GH_REPO}}'
REPO_VISIBILITY='{{REPO_VISIBILITY}}'
DROPLET='{{DROPLET}}'
HEALTH_PATH='{{HEALTH_PATH}}'
WORKFLOW='{{WORKFLOW_FILE}}'
# Exists once F01 has scaffolded the project; before that there is nothing to check.
SCAFFOLD_FILE='{{SCAFFOLD_FILE}}'
# The checks, in order: "name|command". The same list as the verify skill and CI.
GATE=(
{{CHECKS_BASH}}
)
# Dev servers a session may leave behind (killed only when they run from this repo).
DEV_PORTS_SS='( {{DEV_PORTS_SS}} )'
# Deploy steps whose failure is the code's (a repair session), not the infrastructure's.
CI_STEPS=$'^checks\t({{CI_STEPS_RE}})$|\tbuild and smoke-test the image$'
# Commits a feature session makes (the commit that proves a feature was built).
FEAT_RE='^feat(\([^)]*\))?: '
# The option loop shifts them away; the re-execs below need them all.
ORIG_ARGS=("$@")

while (($#)); do
  case $1 in
    --dry-run) DRY_RUN=1 ;;
    --no-deploy) DEPLOY=0 ;;
    --max-attempts)
      MAX_ATTEMPTS=${2:?--max-attempts needs a number}
      shift
      ;;
    -h | --help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done
[[ $MAX_ATTEMPTS =~ ^[1-9][0-9]*$ ]] || {
  echo "--max-attempts needs a positive number" >&2
  exit 2
}
[[ $WAIT_DIVISOR =~ ^[1-9][0-9]*$ ]] || {
  echo "AUTOPILOT_WAIT_DIVISOR needs a positive number" >&2
  exit 2
}

SELF=$(realpath -- "${BASH_SOURCE[0]}")
CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/$APP-autopilot
mkdir -p "$CACHE"

# Run from a copy: bash reads a script as it executes, so an edit to scripts/autopilot.sh while
# it runs would corrupt the run. AUTOPILOT_HOME carries the project directory across.
if [[ -z ${AUTOPILOT_HOME:-} ]]; then
  export AUTOPILOT_HOME
  AUTOPILOT_HOME=$(dirname -- "$(dirname -- "$SELF")")
  copy=$(mktemp "$CACHE/running.XXXXXX.sh")
  cp -- "$SELF" "$copy"
  chmod +x "$copy"
  exec "$copy" "${ORIG_ARGS[@]}"
fi
PROJECT=$AUTOPILOT_HOME
cd "$PROJECT"
REPO=$(git rev-parse --show-toplevel)
# Client engagements never use Kim's droplet, accounts or this runner.
case $PROJECT/ in
  "$HOME"/Documents/work/*)
    echo "$PROJECT is a client engagement (~/Documents/work); this runner is for personal apps only." >&2
    exit 1
    ;;
esac
ROADMAP_JS=(node .claude/scripts/roadmap.mjs)

# Keep the machine awake for the whole run (Kim is away). Re-exec once under systemd-inhibit.
if [[ -z ${AUTOPILOT_INHIBITED:-} ]] && command -v systemd-inhibit >/dev/null &&
  systemd-inhibit --what=idle:sleep:handle-lid-switch --who="$APP-autopilot" --why=probe true 2>/dev/null; then
  export AUTOPILOT_INHIBITED=1
  exec systemd-inhibit --what=idle:sleep:handle-lid-switch --who="$APP-autopilot" \
    --why="$APP_TITLE autopilot is building the roadmap" --mode=block "$SELF" "${ORIG_ARGS[@]}"
fi
# Children never inherit fd 9 (see run_session), so a stray dev server cannot keep the lock.
exec 9>"$CACHE/lock"
if ! flock -n 9; then
  echo "Another autopilot run holds $CACHE/lock." >&2
  exit 1
fi

RUN="$CACHE/$(date -u +%Y%m%dT%H%M%SZ)"
# Two runs in the same second (a quick dry run, then the real one) must not share a log dir.
[[ -e $RUN ]] && RUN+="-$$"
STATE="$RUN/state"
mkdir -p "$STATE"
RUN_LOG="$RUN/run.log"

# ---------------------------------------------------------------------------------------------
# Terminal UI: a scrolling timeline with a pinned 4-row status area at the bottom.

UI_TTY=0
[[ -t 1 && -z ${AUTOPILOT_PLAIN:-} ]] && UI_TTY=1
# All UI output goes to fd 3, so functions whose stdout is captured with $( ) stay clean.
exec 3>&1
ROWS=0
COLS=80
C_DIM=$'\e[2m' C_BOLD=$'\e[1m' C_GOLD=$'\e[33m' C_RED=$'\e[31m' C_GREEN=$'\e[32m' C_OFF=$'\e[0m'
SPIN=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
SPIN_I=0

term_size() { stty size </dev/tty 2>/dev/null || echo '24 80'; }

ui_setup() {
  ((UI_TTY)) || return 0
  read -r ROWS COLS < <(term_size)
  if ((ROWS < 10 || COLS < 30)); then
    # Too small for a pinned area, or a pty that reports 0 0: plain timeline from here on.
    UI_TTY=0
    printf '\e[r' >&3
    return 0
  fi
  {
    printf '\n%.0s' $(seq 1 4)
    tput csr 0 $((ROWS - 5))
    tput cup $((ROWS - 5)) 0
  } >&3
}

ui_teardown() {
  ((UI_TTY)) || return 0
  local r c
  read -r r c < <(term_size)
  {
    # \e[r resets the scroll region to the whole screen, whatever its size is now.
    printf '\e[r'
    ((r > 0)) && tput cup $((r - 1)) 0
    printf '\n\e]0;%s\a' "$APP_TITLE autopilot: stopped"
  } >&3 || true
}

ui_check_resize() {
  ((UI_TTY)) || return 0
  local r c
  read -r r c < <(term_size)
  if ((r != ROWS || c != COLS)); then
    tput clear >&3
    ui_setup
  fi
}

# Globals the status reads. The session reader (a subshell) updates its own copies.
RUN_START=$(date +%s)
SESSION_START=0
FEATURE='' FEATURE_TITLE='' FEATURE_MS='' ATTEMPT=0
PHASE='starting'
LAST='—'
TOOLS=0 EDITS=0
SESSION_COST=0 TOTAL_COST=0
RL_5H='' RL_7D=''
START_TODO=0 DONE_IN_RUN=0 RM_DONE=0 RM_TOTAL=0

fmt_dur() {
  local s=$1
  if ((s >= 3600)); then
    printf '%dh%02dm' $((s / 3600)) $((s % 3600 / 60))
  else
    printf '%dm%02ds' $((s / 60)) $((s % 60))
  fi
}

pct() {
  if [[ -n $1 ]]; then awk -v u="$1" 'BEGIN { printf "%d%%", u * 100 + 0.5 }'; else printf '?'; fi
}

# eta: remaining features times the average wall time per feature committed this run (usage
# limit waits included, so it stays honest about the night).
eta() {
  local left=$((START_TODO - DONE_IN_RUN))
  ((DONE_IN_RUN > 0 && left > 0)) || return 0
  printf ' · ETA ~%s' "$(fmt_dur $(((now - RUN_START) / DONE_IN_RUN * left)))"
}

bar() {
  local done=$1 total=$2 width=20 fill=0 out='' i
  ((total > 0)) && fill=$((done * width / total))
  for ((i = 0; i < width; i++)); do
    if ((i < fill)); then out+='█'; else out+='░'; fi
  done
  printf '%s' "$out"
}

render_status() {
  local now l1 l2 l3 elapsed sess=''
  now=$(date +%s)
  elapsed=$(fmt_dur $((now - RUN_START)))
  ((SESSION_START > 0)) && sess=" · $(fmt_dur $((now - SESSION_START)))"
  SPIN_I=$(((SPIN_I + 1) % ${#SPIN[@]}))
  l1="$APP_TITLE autopilot  [$(bar "$RM_DONE" "$RM_TOTAL")] $RM_DONE/$RM_TOTAL built · $DONE_IN_RUN this run · ⏱ $elapsed$(eta) · ≈\$$(printf '%.2f' "$TOTAL_COST")"
  if [[ -n $FEATURE ]]; then
    l2="${SPIN[SPIN_I]} ${FEATURE_MS:+$FEATURE_MS }$FEATURE $FEATURE_TITLE · attempt $ATTEMPT/$MAX_ATTEMPTS$sess · $PHASE"
  else
    l2="${SPIN[SPIN_I]} $PHASE"
  fi
  l3="last: $LAST · $TOOLS tools · $EDITS edits"
  [[ -n $RL_5H ]] && l3+=" · 5h $(pct "$RL_5H") · 7d $(pct "$RL_7D")"

  printf '%s\n%s\n%s\n' "$l1" "$l2" "$l3" >"$RUN/status.txt" 2>/dev/null || true
  ((UI_TTY)) || return 0
  ui_check_resize
  {
    tput sc
    tput cup $((ROWS - 4)) 0
    tput el
    printf '%s' "$C_DIM${C_GOLD}$(printf '━%.0s' $(seq 1 "$COLS"))$C_OFF"
    tput cup $((ROWS - 3)) 0
    tput el
    printf '%s' "$C_BOLD${l1:0:COLS-1}$C_OFF"
    tput cup $((ROWS - 2)) 0
    tput el
    printf '%s' "$C_GOLD${l2:0:COLS-1}$C_OFF"
    tput cup $((ROWS - 1)) 0
    tput el
    printf '%s' "$C_DIM${l3:0:COLS-1}$C_OFF"
    tput rc
    printf '\e]0;%s\a' "$APP_TITLE $RM_DONE/$RM_TOTAL · ${FEATURE:-$PHASE}"
  } >&3
}

# log LEVEL message. LEVEL: info | ok | warn | err | dim
log() {
  local level=$1 color=''
  shift
  local line
  line="$(date +%T) $*"
  printf '%s\n' "$line" >>"$RUN_LOG"
  case $level in
    ok) color=$C_GREEN ;;
    warn) color=$C_GOLD ;;
    err) color=$C_RED ;;
    dim) color=$C_DIM ;;
  esac
  if ((UI_TTY)); then
    printf '%s\n' "$color${line:0:COLS}$C_OFF" >&3
    render_status
  else
    printf '%s\n' "$line" >&3
  fi
}

notify() {
  command -v notify-send >/dev/null && notify-send -a "$APP_TITLE autopilot" "$1" "${2:-}" 2>/dev/null || true
}

# Sleep while keeping the status line alive.
wait_with_status() {
  local seconds=$1 label=$2 end
  end=$(($(date +%s) + seconds))
  while (($(date +%s) < end)); do
    PHASE="$label · $(fmt_dur $((end - $(date +%s)))) left"
    render_status
    sleep 1
  done
}

# secs N: a fixed wait or poll interval, shortened by AUTOPILOT_WAIT_DIVISOR in tests.
secs() {
  local s=$(($1 / WAIT_DIVISOR))
  echo $((s > 0 ? s : 1))
}

STOP_REASON=''
die() {
  STOP_REASON=$*
  log err "STOP: $*"
  notify 'Autopilot stopped' "$*"
  exit 1
}

# What happened to the push and deploy, for the summary and the morning report.
DEPLOY_STATE='not reached (the run stopped before the push)'
LIVE_STATE='not checked'

# The morning report: what Kim reads first. Always written, whatever stopped the run.
write_report() {
  local rc=$1 report="$RUN/morning-report.md" blocked gated feats
  feats=$(git log --reverse --format='%h %s' "$RUN_HEAD_AT_START..HEAD" 2>/dev/null | grep -E " (feat|fix)(\([^)]*\))?: " || true)
  blocked=$(awk '/^- \[!\] / { id = $3; sub(/^- \[!\] /, ""); line = $0 } /^ *- Blocked:/ && line { sub(/^ *- Blocked: */, ""); print "- " line " — " $0; line = "" }' docs/ROADMAP.md 2>/dev/null || true)
  gated=$(roadmap_next | sed -n 's/^Gated: //p' | grep -v '^none$' | tr ';' '\n' | sed 's/^ */- /' || true)
  {
    echo "# $APP_TITLE autopilot — morning report"
    echo
    echo "Run \`$(basename "$RUN")\` · $(fmt_dur $(($(date +%s) - RUN_START))) · exit $rc · ≈\$$(printf '%.2f' "$TOTAL_COST")"
    [[ -n $STOP_REASON ]] && echo && echo "**Stopped:** $STOP_REASON"
    echo
    echo "## Roadmap"
    echo
    roadmap_next | grep -E '^(Done|In progress|Blocked|Gated):' | sed 's/^/- /'
    echo
    echo "## Built this run ($DONE_IN_RUN)"
    echo
    if [[ -n $feats ]]; then printf -- '- %s\n' "${feats//$'\n'/$'\n- '}"; else echo "- nothing"; fi
    echo
    echo "## Blocked"
    echo
    if [[ -n $blocked ]]; then echo "$blocked"; else echo "- none"; fi
    echo
    echo "## Waiting on Kim's approval (Gate:)"
    echo
    if [[ -n $gated ]]; then echo "$gated"; echo; echo "Approve, then \`node .claude/scripts/roadmap.mjs ungate <ID>\` and start the autopilot again."; else echo "- none"; fi
    echo
    echo "## Stashes (half-built work set aside)"
    echo
    git stash list | grep "$APP-autopilot:" | sed 's/^/- /' || echo "- none"
    echo
    echo "## Deploy"
    echo
    echo "- $DEPLOY_STATE"
    echo "- Live check: $LIVE_STATE"
    echo "- Live URL: $LIVE_URL"
    echo
    echo "## Kim checks"
    echo
    echo "- $(kim_checks) open under \"## Kim checks\" in docs/PROGRESS.md"
    echo
    echo "## Files"
    echo
    echo "- Logs: $RUN (run.log, summary.txt, one .jsonl per session)"
  } >"$report" 2>/dev/null || return 0
  ln -sfn "$report" "$CACHE/morning-report.md" 2>/dev/null || true
}

cleanup() {
  local rc=$?
  stop_session
  kill_strays
  {
    echo "$APP_TITLE autopilot run $(basename "$RUN")"
    echo "exit code: $rc"
    [[ -n $STOP_REASON ]] && echo "stopped: $STOP_REASON"
    echo "duration: $(fmt_dur $(($(date +%s) - RUN_START)))"
    echo "features committed this run: $DONE_IN_RUN of $START_TODO"
    echo "approx. API cost: \$$(printf '%.2f' "$TOTAL_COST")"
    echo "roadmap: $(roadmap_next | grep -E '^(Done|In progress|Blocked|Gated):' | paste -sd' ' -)"
    echo "stashes made by autopilot:"
    git stash list | grep "$APP-autopilot:" || echo "  none"
    echo "deploy: $DEPLOY_STATE"
    echo "live: $LIVE_STATE"
    echo "Kim checks queued in docs/PROGRESS.md: $(kim_checks)"
    echo "commits this run:"
    git log --oneline "$RUN_HEAD_AT_START..HEAD" 2>/dev/null || true
  } >"$RUN/summary.txt" 2>&1 || true
  ((DRY_RUN)) || write_report "$rc"
  ui_teardown
  [[ $SELF == "$CACHE"/running.*.sh ]] && rm -f -- "$SELF"
  {
    echo
    cat "$RUN/summary.txt" 2>/dev/null || true
    ((DRY_RUN)) || echo "Morning report: $RUN/morning-report.md"
    echo "Logs: $RUN"
  } >&3
}

# ---------------------------------------------------------------------------------------------
# Repo helpers

roadmap_next() { "${ROADMAP_JS[@]}" next 2>/dev/null; }

# The feature the roadmap would build now ("Resume:" or "Next eligible:"), or nothing.
next_target() {
  roadmap_next | sed -nE 's/^(Resume|Next eligible): ([FB][0-9]+[a-z]?).*/\2/p' | head -1
}

refresh_counts() {
  local line
  line=$(roadmap_next | sed -nE 's/^Done: ([0-9]+)\/([0-9]+).*/\1 \2/p')
  RM_DONE=${line% *}
  RM_TOTAL=${line#* }
  DONE_IN_RUN=$((RM_DONE - RM_DONE_AT_START))
  # A session may split a feature (F95 into F95a and F95b), which grows the total.
  START_TODO=$((DONE_IN_RUN + RM_TOTAL - RM_DONE))
}

feature_title() { sed -nE "s/^- \[.\] $1 (.*)/\1/p" docs/ROADMAP.md | head -1; }
feature_ms() { awk -v id="$1" '/^## M[0-9]+/ { m = $2 } $0 ~ "^- \\[.\\] " id " " { print m; exit }' docs/ROADMAP.md; }
feature_mark() { sed -nE "s/^- \[(.)\] $1 .*/\1/p" docs/ROADMAP.md | head -1; }
# Open "- [ ] " lines under "## Kim checks" in docs/PROGRESS.md.
kim_checks() {
  local n
  n=$(sed -n '/^## Kim checks/,/^<!-- entries below/p' docs/PROGRESS.md 2>/dev/null | grep -c '^- \[ \] ') || true
  echo "${n:-0}"
}
dirty() { [[ -n $(git status --porcelain --untracked-files=all -- .) ]]; }

# Kill dev servers left behind by an earlier session, only if they run from this repo.
kill_strays() {
  local pid cwd
  for pid in $(ss -ltnpH "$DEV_PORTS_SS" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u); do
    cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
    if [[ $cwd == "$PROJECT" || $cwd == "$PROJECT"/* ]]; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}

stash_changes() {
  local msg=$1
  if dirty; then
    git stash push --include-untracked -m "$APP-autopilot: $msg" -- . >/dev/null
    log warn "Stashed uncommitted changes as \"$APP-autopilot: $msg\" ($(git stash list | head -1 | cut -d: -f1))"
  fi
}

commit_docs() {
  local msg=$1 f files=()
  for f in docs/ROADMAP.md docs/DECISIONS.md docs/PROGRESS.md; do
    [[ -n $(git status --porcelain -- "$f") ]] && files+=("$f")
  done
  ((${#files[@]})) || return 0
  git add -- "${files[@]}"
  # Only these files: a blocked session may have staged half-built code as well.
  git commit -q -m "$msg" -m "Recorded by scripts/autopilot.sh while running unattended." -- "${files[@]}"
  log info "Committed ${files[*]}: $msg"
}

run_gate() {
  local step
  : >"$RUN/gate.log"
  [[ -e $SCAFFOLD_FILE ]] || {
    log err "$SCAFFOLD_FILE is missing, so there is nothing to check (F01 creates it)"
    return 1
  }
  for step in "${GATE[@]}"; do
    PHASE="checks: ${step%%|*}"
    render_status
    echo "\$ ${step#*|}" >>"$RUN/gate.log"
    if ! bash -c "${step#*|}" >>"$RUN/gate.log" 2>&1 </dev/null; then
      log err "${step%%|*} failed (see $RUN/gate.log)"
      return 1
    fi
  done
  log ok "All checks green: $(printf '%s\n' "${GATE[@]}" | cut -d'|' -f1 | paste -sd, - | sed 's/,/, /g')"
}

# ---------------------------------------------------------------------------------------------
# Push guard and remote checks

# origin must be this app's own GitHub repo, so nothing ever lands in another project's (or a
# client's) repository, whatever happens to be configured.
check_remote() {
  local url
  url=$(git remote get-url --push origin 2>/dev/null) || die "no origin remote; the bootstrap adds it (gh repo create)"
  if [[ $url =~ ^(https://github\.com/|git@github\.com:|ssh://git@github\.com/)(.+)$ ]]; then
    [[ ${BASH_REMATCH[2]%.git} == "$GH_REPO" ]] || die "origin points at ${BASH_REMATCH[2]%.git}, not $GH_REPO; nothing runs"
  elif [[ -z $OFFLINE ]]; then
    die "origin ($url) is not github.com/$GH_REPO; nothing runs"
  else
    log warn "Offline test: origin is $url (a real run needs github.com/$GH_REPO)."
  fi
}

# The range a push would carry: everything not yet on origin/main (the whole history on the
# first push).
push_range() {
  if git rev-parse -q --verify origin/main >/dev/null; then echo 'origin/main..HEAD'; else echo 'HEAD'; fi
}

# Before every push: no agent files or secrets in what would ship, and the files only Kim
# changes unchanged since the run started (a session that got past the hook with a shell edit).
# Prints the problems to $RUN/push-guard.txt and returns 1 if there are any.
SECRET_RE='-----BEGIN ([A-Z]+ )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-(proj-)?[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN OPENSSH PRIVATE KEY-----'
FORBIDDEN_PATHS_RE='(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_(rsa|ed25519|ecdsa)(\.pub)?|CLAUDE(\.local)?\.md)$|^\.claude/'
push_guard() {
  local range out="$RUN/push-guard.txt" bad paths hits
  range=$(push_range)
  : >"$out"
  paths=$(git log --format= --name-only "$range" | sed '/^$/d' | sort -u)
  bad=$(grep -E "$FORBIDDEN_PATHS_RE" <<<"$paths" | grep -vE '(^|/)\.env\.example$' || true)
  [[ -n $bad ]] && printf 'Agent files or secrets in commits (%s):\n%s\n\n' "$range" "$bad" >>"$out"
  # This file holds the patterns themselves; any change to it is caught below instead.
  hits=$(git log -p --format='commit %h' "$range" -- . ':!scripts/autopilot.sh' | grep -E '^(commit |\+)' | grep -E "^commit |$SECRET_RE" |
    awk '/^commit / { c = $2; next } { print c ": " substr($0, 1, 60) "…" }' || true)
  [[ -n $hits ]] && printf 'Lines that look like secrets:\n%s\n\n' "$hits" >>"$out"
  if command -v gitleaks >/dev/null && ! gitleaks git --no-banner --redact --log-opts="$range" >>"$out" 2>&1; then
    printf 'gitleaks found leaks (above).\n\n' >>"$out"
  fi
  if ! git diff --quiet "$RUN_HEAD_AT_START" HEAD -- docs/spec.md scripts/autopilot.sh; then
    printf 'Changed during this run (only Kim changes them):\n%s\n\n' \
      "$(git diff --name-only "$RUN_HEAD_AT_START" HEAD -- docs/spec.md scripts/autopilot.sh)" >>"$out"
  fi
  [[ -s $out ]] && return 1
  return 0
}

check_push_scope() {
  push_guard && return 0
  notify 'Not pushed' "the push guard refused (see $RUN/push-guard.txt)"
  die "the push guard refused: $(head -1 "$RUN/push-guard.txt") (see $RUN/push-guard.txt); nothing pushed"
}

# --dry-run: everything a real run would need, checked without building, pushing or deploying.
DRY_FAILS=0
dry_check() {
  local label=$1
  shift
  if "$@" >>"$RUN/dry-run.log" 2>&1; then
    log ok "  ✔ $label"
  else
    log err "  ✘ $label (see $RUN/dry-run.log)"
    DRY_FAILS=$((DRY_FAILS + 1))
  fi
}
gh_repo_ok() {
  local vis
  vis=$(gh repo view "$GH_REPO" --json visibility --jq '.visibility | ascii_downcase') || return 1
  echo "$GH_REPO $vis"
  [[ $vis == "$REPO_VISIBILITY" ]] || {
    echo "visibility is $vis, bootstrap.json says $REPO_VISIBILITY"
    return 1
  }
}
gh_secrets_ok() {
  local names s
  names=$(gh secret list --repo "$GH_REPO" --json name --jq '.[].name')
  for s in SSH_HOST SSH_USER SSH_KEY SSH_KNOWN_HOSTS; do
    grep -qx "$s" <<<"$names" || {
      echo "missing secret $s"
      return 1
    }
  done
}
# Read-only, and only in a dry run with Kim at the keyboard: real runs never ssh anywhere.
droplet_ok() {
  ssh -o BatchMode=yes -o ConnectTimeout=10 "root@$DROPLET" "
    set -e
    df -P / | awk 'NR == 2 { free = \$4 / 1048576; printf \"disk: %.1f GB free on /\\n\", free; if (free < 3) { print \"under 3 GB free\"; exit 1 } }'
    free -m | awk '/^Mem:/ { print \"memory: \" \$7 \" MB available\" }'
    test -d /opt/$APP && stat -c 'stack dir: %n %U:%G %a' /opt/$APP
    test -f /opt/$APP/.env && echo '.env present'
    docker info >/dev/null && echo 'docker up'
    id deploy >/dev/null && echo 'deploy user present'
  "
}
live_ok() {
  local code
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "$LIVE_URL/")
  echo "GET $LIVE_URL/ -> $code (TLS verified)"
  [[ $code == 200 || $code == 503 ]]
}
queue_report() {
  roadmap_next | grep -E '^(Done|In progress|Blocked|Gated|Open bugs|Resume|Next eligible|Nothing left|Not eligible):' | sed 's/^/    /' |
    while IFS= read -r line; do log info "$line"; done
  log info "    queue: $(grep -cE '^- \[ \] F' docs/ROADMAP.md || true) todo, of which $(roadmap_next | sed -n 's/^Gated: //p' | grep -v '^none$' | tr ';' '\n' | grep -c . || true) gated"
}
dry_run_checks() {
  log info "Dry run checks:"
  queue_report
  dry_check "push guard: $(push_range) carries no secrets or agent files" push_guard
  dry_check "roadmap.mjs and spec.mjs answer" bash -c 'node .claude/scripts/roadmap.mjs next >/dev/null && node .claude/scripts/spec.mjs --toc >/dev/null'
  dry_check "claude CLI runs" claude --version
  if [[ -n $OFFLINE ]]; then
    log warn "  - gh, deploy secrets, droplet and live URL skipped (AUTOPILOT_OFFLINE)"
  else
    dry_check "gh is logged in" gh auth status
    dry_check "GitHub repo $GH_REPO exists and is $REPO_VISIBILITY" gh_repo_ok
    dry_check "deploy secrets set on $GH_REPO" gh_secrets_ok
    dry_check "droplet $DROPLET reachable, disk and stack dir fine" droplet_ok
    dry_check "$LIVE_URL answers over TLS (placeholder 503 or app 200)" live_ok
  fi
  if [[ -f .github/workflows/$WORKFLOW ]]; then
    dry_check "$WORKFLOW keeps the job and step names this script matches" \
      bash -c "grep -q 'name: checks' .github/workflows/$WORKFLOW && grep -q 'name: droplet' .github/workflows/$WORKFLOW && grep -q 'build and smoke-test the image' .github/workflows/$WORKFLOW"
  else
    log info "  - $WORKFLOW not written yet ({{DEPLOY_FEATURE}} writes it from docs/deploy-kit/)"
  fi
  if ((DRY_FAILS)); then
    die "dry run: $DRY_FAILS check(s) failed"
  fi
  log ok "Dry run passed. A real run would build the queue above, then run the checks, push once and deploy."
}

# ---------------------------------------------------------------------------------------------
# Claude sessions

UNATTENDED_RULES=$(
  cat <<EOF
You are running unattended, launched by scripts/autopilot.sh. Kim is away and cannot answer.
- Never ask questions and never wait for input. Wherever a skill or instruction says to ask Kim, choose the option a careful senior engineer would pick (simplest choice that meets the spec, the roadmap entry and docs/design/DESIGN.md), record it in docs/DECISIONS.md, and continue.
- At the start, if the repo has uncommitted changes and a roadmap feature is marked [~], they are an earlier unattended attempt at that feature: inspect them, keep what is sound, fix the rest, and resume. Never discard them.
- If the repo has uncommitted changes and no feature is marked [~], put them aside with \`git stash push --include-untracked -m "$APP-autopilot: unexplained changes"\` and continue.
- If the feature's roadmap entry has a "Blocked:" line, an earlier attempt gave up on it. Read the note, and look for its unfinished work with \`git stash list | grep $APP-autopilot\` (inspect with \`git stash show -p stash@{N}\`; apply only what helps). Try a different approach.
- A "Gate:" line is Kim's approval and is never yours to remove. Never run roadmap.mjs ungate, and never build a gated feature.
- Checks only a person can do (real devices, real accounts or keys, live third-party services, "Kim has reviewed …") never block: build and test everything around them (Playwright emulation and fakes count for the automated part), then add exact steps under "## Kim checks" in docs/PROGRESS.md (\`- [ ] F09: steps · what to look for\`) and mark the feature done.
- If Playwright or the playtest skill cannot run, write exact manual test steps in the PROGRESS entry instead and continue.
- The roadmap mark, the PROGRESS entry, any Kim checks and any DECISIONS rows go into the feature's single commit.
- If a feature is genuinely blocked after three real fix attempts, mark it with roadmap.mjs as the skill describes, and leave the code uncommitted.
- Real keys never exist in this session. Code reads env vars; tests and development use fakes. Never read, write or create .env files other than .env.example.
- Never push, deploy, run gh, ssh, scp, docker against the droplet, or sudo. Never change git remotes or git config. Never edit docs/spec.md or scripts/autopilot.sh. The script does the push and deploy.
- Never stage .claude/, CLAUDE.md or .env* (they are gitignored; never force-add them).
- Build exactly one feature, commit it, then stop.
EOF
)

DISALLOWED=(
  'Bash(git push:*)' 'Bash(git reset:*)' 'Bash(git clean:*)' 'Bash(git checkout:*)'
  'Bash(git rebase:*)' 'Bash(git restore:*)' 'Bash(git remote:*)' 'Bash(git config:*)'
  'Bash(git add -f:*)' 'Bash(git add --force:*)'
  'Bash(gh:*)' 'Bash(ssh:*)' 'Bash(scp:*)' 'Bash(rsync:*)' 'Bash(sftp:*)'
  'Bash(docker:*)' 'Bash(rm -rf:*)' 'Bash(sudo:*)'
  'Bash(node .claude/scripts/roadmap.mjs ungate:*)' 'AskUserQuestion'
)
# Kim's user-level RTK hook rewrites some commands to `rtk <command>` before the deny list
# sees them (a real session ran `git push --dry-run` that way), so deny those forms too.
for rule in "${DISALLOWED[@]}"; do
  [[ $rule == Bash\(* ]] && DISALLOWED+=("Bash(rtk ${rule#Bash(}")
done
DISALLOWED+=('Bash(rtk proxy:*)')

# One line per stream-json event that matters, tab-separated. Non-JSON lines are skipped.
JQ_FILTER='
def clip(n): tostring | gsub("[\r\n\t]+"; " ") | if length > n then .[0:n] + "…" else . end;
fromjson? |
if .type == "system" and .subtype == "init" then
  "init\t" + (if any(.slash_commands[]?; . == "next-feature") then "1" else "0" end)
elif .type == "assistant" then
  (if (.parent_tool_use_id // "") == "" then "0" else "1" end) as $sub
  | (.message.content // [])[] | select(.type == "tool_use")
  | "tool\t\($sub)\t\(.name)\t" + ((.input.command // .input.file_path // .input.skill
      // .input.subagent_type // .input.description // .input.pattern // .input.url // "") | clip(160))
elif .type == "rate_limit_event" then
  .rate_limit_info as $r
  | "rl\t\($r.status // "")\t\($r.resetsAt // 0)\t\($r.unifiedWindows.five_hour.utilization // "")\t\($r.unifiedWindows.seven_day.utilization // "")"
elif .type == "result" then
  "result\t\(.subtype // "")\t\(.is_error // false)\t\(.total_cost_usd // 0)\t\(.duration_ms // 0)\t\(.num_turns // 0)\t" + ((.result // "") | clip(400))
else empty end'

# Reads the jq lines, logs the timeline and redraws the status once a second.
session_reader() {
  set +e
  local kind a b c d e f
  while :; do
    if IFS=$'\t' read -r -t 1 kind a b c d e f; then
      case $kind in
        init)
          [[ $a == 1 ]] || echo 1 >"$STATE/no_skill"
          ;;
        tool)
          TOOLS=$((TOOLS + 1))
          [[ $b =~ ^(Edit|Write|MultiEdit|NotebookEdit)$ ]] && EDITS=$((EDITS + 1))
          if [[ $a == 1 ]]; then
            LAST="↳ $b ${c:0:90}"
          else
            LAST="$b ${c:0:90}"
            case $b in
              Skill | Agent | Task) log info "  ▸ $b ${c:0:120}" ;;
              Bash)
                if [[ $c == *'git commit'* ]]; then log ok "  ▸ commit"; else log dim "  · $b ${c:0:120}"; fi
                ;;
              *) log dim "  · $b ${c:0:120}" ;;
            esac
          fi
          ;;
        rl)
          RL_5H=$c RL_7D=$d
          printf '%s\t%s\t%s\t%s\n' "$a" "$b" "$c" "$d" >"$STATE/rl"
          ;;
        result)
          printf '%s\n' "$a" >"$STATE/result_subtype"
          printf '%s\n' "$b" >"$STATE/result_is_error"
          printf '%s\n' "$c" >"$STATE/result_cost"
          printf '%s\n' "$f" >"$STATE/result_text"
          [[ $c =~ ^[0-9.eE+-]+$ ]] || c=0
          [[ $d =~ ^[0-9]+$ ]] || d=0
          log info "  session ended: $a · turns $e · $(fmt_dur $((d / 1000))) · ≈\$$(printf '%.2f' "$c")"
          ;;
      esac
      render_status
    else
      (($? > 128)) || break
      render_status
    fi
  done
}

# run_session LABEL PROMPT: one fresh claude -p session. Sets SESSION_RC.
# The pipeline runs in the background and the shell waits for it, so Ctrl-C and SIGTERM reach
# the traps at once instead of after the session (bash defers traps during a foreground job).
# timeout leads a process group of its own, which the terminal's Ctrl-C never reaches, so
# stop_session signals that group. The session gets neither the lock (fd 9) nor the UI (fd 3).
SESSION_PIPE=''
run_session() {
  local label=$1 prompt=$2 jsonl="$RUN/$1.jsonl" err="$RUN/$1.err"
  rm -f "$STATE"/result_* "$STATE/rc" "$STATE/no_skill" "$STATE/rl" "$STATE/session_pid"
  TOOLS=0 EDITS=0 LAST='starting session'
  SESSION_START=$(date +%s)
  kill_strays
  {
    local rc=0
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.pushurl \
      GIT_CONFIG_VALUE_0=autopilot-sessions-never-push GH_TOKEN=autopilot-sessions-never-use-gh \
      GITHUB_TOKEN=autopilot-sessions-never-use-gh SSH_AUTH_SOCK='' \
      timeout --kill-after=60 "$SESSION_TIMEOUT" claude -p "$prompt" \
      --output-format stream-json --verbose \
      --dangerously-skip-permissions \
      --disallowedTools "${DISALLOWED[@]}" \
      --append-system-prompt "$UNATTENDED_RULES" \
      </dev/null 2>"$err" 3>&- 9>&- &
    echo $! >"$STATE/session_pid"
    wait $! || rc=$?
    echo "$rc" >"$STATE/rc"
  } | tee -a "$jsonl" | jq -R -r --unbuffered "$JQ_FILTER" 2>>"$err" | session_reader &
  SESSION_PIPE=$!
  wait || true
  SESSION_PIPE=''
  rm -f "$STATE/session_pid"
  SESSION_RC=$(cat "$STATE/rc" 2>/dev/null || echo 1)
  SESSION_COST=$(cat "$STATE/result_cost" 2>/dev/null || echo 0)
  TOTAL_COST=$(awk -v a="$TOTAL_COST" -v b="$SESSION_COST" 'BEGIN { printf "%.4f", a + b }')
  if [[ -f $STATE/rl ]]; then
    IFS=$'\t' read -r _ _ RL_5H RL_7D <"$STATE/rl" || true
  fi
  # The reader's counters lived in its own subshell; keep a summary for the status line.
  LAST="session $label ended (exit $SESSION_RC)"
  SESSION_START=0
  kill_strays
}

# Ctrl-C, SIGTERM or SIGHUP mid-session: end the session's process group, then its pipeline.
stop_session() {
  local pid i
  pid=$(cat "$STATE/session_pid" 2>/dev/null) || return 0
  if kill -0 "$pid" 2>/dev/null; then
    log warn "Stopping the running claude session…"
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for i in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    kill -KILL -- "-$pid" 2>/dev/null || true
  fi
  if [[ -n $SESSION_PIPE ]]; then
    for i in $(seq 1 10); do
      kill -0 "$SESSION_PIPE" 2>/dev/null || break
      sleep 0.5
    done
    kill "$SESSION_PIPE" 2>/dev/null || true
  fi
  rm -f "$STATE/session_pid"
}

# Was the session stopped by a usage limit or an overloaded API? Echo "limit EPOCH" or "busy".
# Only a session that errored or died counts: one that ended normally chose to stop, and its
# last message may well mention rate limits or a 503 in the code it was working on. A timeout
# is a failed attempt, not a blocker.
session_blocker() {
  local text status=allowed resets=0
  [[ $(cat "$STATE/result_is_error" 2>/dev/null) == false ]] && return 0
  ((SESSION_RC == 124 || SESSION_RC == 137)) && return 0
  text="$(cat "$STATE/result_text" "$RUN/$1.err" 2>/dev/null || true)"
  if [[ -f $STATE/rl ]]; then
    IFS=$'\t' read -r status resets _ _ <"$STATE/rl" || true
  fi
  if [[ $status != allowed && $status != allowed_warning && -n $status ]] ||
    grep -qiE 'usage limit|limit reached|hit your limit|5-hour limit|weekly limit|rate_limit_error|API Error: 429' <<<"$text"; then
    echo "limit $resets"
  elif grep -qiE 'API Error|overloaded|Connection error|Request timed out|ECONNRESET|ETIMEDOUT|EAI_AGAIN|socket hang up' <<<"$text"; then
    echo busy
  fi
  return 0
}

# Sleep until a usage limit resets (plus 2 min), or back off when the reset time is unknown.
LIMIT_WAITS=0
wait_for_limit() {
  local resets=$1 now wait
  now=$(date +%s)
  LIMIT_WAITS=$((LIMIT_WAITS + 1))
  [[ $resets =~ ^[0-9]+$ ]] || resets=0
  ((resets > 100000000000)) && resets=$((resets / 1000)) # milliseconds
  if ((resets > now && resets < now + 8 * 86400)); then
    wait=$((resets - now + $(secs 120)))
  else
    wait=$(secs $((LIMIT_WAITS >= 3 ? 3600 : LIMIT_WAITS == 2 ? 1800 : 900)))
  fi
  log warn "Usage limit hit. Waiting $(fmt_dur "$wait") (until $(date -d "@$((now + wait))" '+%a %H:%M'))."
  notify 'Usage limit' "Waiting $(fmt_dur "$wait")"
  wait_with_status "$wait" 'usage limit'
}

# The one extra pass: every [!] feature goes back to todo (its "Blocked:" note stays, and the
# session is told to read it and the stash) with a fresh set of attempts. Returns 1 when there
# is nothing to retry.
retry_blocked() {
  local ids id
  RETRY_PASS=1
  ids=$(sed -nE 's/^- \[!\] ([FB][0-9]+[a-z]?) .*/\1/p' docs/ROADMAP.md)
  [[ -n $ids ]] || return 1
  log warn "━━ Extra pass for blocked features: $(paste -sd' ' - <<<"$ids")"
  notify 'Retrying blocked features' "$(paste -sd' ' - <<<"$ids")"
  for id in $ids; do
    "${ROADMAP_JS[@]}" mark "$id" todo >/dev/null || die "could not reset $id to todo"
    ATTEMPTS[$id]=0
  done
  commit_docs "docs: retry blocked features (autopilot)"
  GIVEUPS_IN_A_ROW=0
  return 0
}

feature_prompt() {
  if [[ -f $STATE/inline_skill ]]; then
    awk 'BEGIN { n = 0 } /^---$/ && n < 2 { n++; next } n >= 2' .claude/skills/next-feature/SKILL.md |
      sed 's/\$ARGUMENTS/(none: pick the next eligible one)/g'
  else
    printf '/next-feature'
  fi
}

# ---------------------------------------------------------------------------------------------
# Preflight

RUN_HEAD_AT_START=$(git rev-parse HEAD)
RM_DONE_AT_START=0
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
# errexit stops the script without a word; leave the failing command in run.log.
# Only the main shell: inside $( ) a failing grep is routine.
err_note() {
  ((BASH_SUBSHELL == 0)) || return 0
  printf '%s command failed (exit %s) at line %s: %s\n' "$(date +%T)" "$1" "$2" "$3" >>"$RUN_LOG"
}
trap 'err_note "$?" "$LINENO" "$BASH_COMMAND"' ERR
ui_setup
log info "$APP_TITLE autopilot · logs in $RUN"
((DRY_RUN)) && log warn "Dry run: nothing is built, pushed or deployed."

for tool in claude node git gh jq curl ss timeout flock; do
  command -v "$tool" >/dev/null || die "missing tool: $tool"
done
if [[ -n $OFFLINE ]]; then
  ((DRY_RUN || !DEPLOY)) || die "AUTOPILOT_OFFLINE is for dry runs and --no-deploy runs only"
  log warn "Offline test: gh, ssh and the live URL are skipped."
else
  gh auth status >/dev/null 2>&1 || die "gh is not logged in (gh auth login)"
fi
[[ $(git rev-parse --abbrev-ref HEAD) == main ]] || die "not on main"
[[ -f .claude/skills/next-feature/SKILL.md ]] || die ".claude/skills/next-feature/SKILL.md is missing; the bootstrap writes it"
check_remote
git fetch -q origin 2>>"$RUN_LOG" || log warn "git fetch failed; continuing offline until the push"

RM_DONE_AT_START=$(roadmap_next | sed -nE 's/^Done: ([0-9]+)\/.*/\1/p') || true
[[ -n $RM_DONE_AT_START ]] || die "roadmap.mjs did not report progress"
refresh_counts
log info "Roadmap: $RM_DONE/$RM_TOTAL done, $START_TODO to build."

RESUMING=0
if dirty; then
  if roadmap_next | grep -q '^Resume:'; then
    RESUMING=1
    log warn "Uncommitted changes belong to the [~] feature; the first session resumes them."
  elif ((DRY_RUN)); then
    log warn "The repo has uncommitted changes; a real run would refuse to start."
  else
    # Kim is still at the keyboard at this point, so ask for a clean tree rather than stash.
    die "the repo has uncommitted changes; commit or stash them, then start again"
  fi
fi

if ((DRY_RUN)); then
  log info "Skipping the baseline checks in a dry run."
elif [[ ! -e $SCAFFOLD_FILE ]]; then
  log info "Skipping the baseline checks: no $SCAFFOLD_FILE yet (F01 creates it)."
elif ((RESUMING)); then
  # Half-built work is not expected to pass yet; the session's own verify step checks it.
  log info "Skipping the baseline checks: they would run on the [~] feature's unfinished work."
else
  PHASE='baseline checks'
  log info "Baseline checks before the first feature…"
  run_gate || die "the checks fail before any feature is built; fix main first"
fi

# ---------------------------------------------------------------------------------------------
# Feature loop

declare -A ATTEMPTS=()
RETRY_PASS=0
SESSIONS=0
GIVEUPS_IN_A_ROW=0
BUSY_WAITS=0

while :; do
  refresh_counts
  FEATURE=$(next_target)
  if [[ -z $FEATURE ]]; then
    ((!DRY_RUN && !RETRY_PASS)) && retry_blocked && continue
    break
  fi
  FEATURE_TITLE=$(feature_title "$FEATURE")
  FEATURE_MS=$(feature_ms "$FEATURE")
  ATTEMPTS[$FEATURE]=$((${ATTEMPTS[$FEATURE]:-0} + 1))
  ATTEMPT=${ATTEMPTS[$FEATURE]}
  PHASE='building'

  if ((DRY_RUN)); then
    log info "Would run: claude -p \"$(feature_prompt | head -c 60)\" for $FEATURE $FEATURE_TITLE"
    FEATURE=''
    dry_run_checks
    PHASE='dry run complete'
    render_status
    exit 0
  fi

  ((SESSIONS < MAX_SESSIONS)) || die "reached $MAX_SESSIONS sessions; something is wrong"
  SESSIONS=$((SESSIONS + 1))
  before=$(git rev-parse HEAD)
  log info "━━ $FEATURE $FEATURE_TITLE · attempt $ATTEMPT/$MAX_ATTEMPTS · session $SESSIONS"
  run_session "$FEATURE-a$ATTEMPT" "$(feature_prompt)"

  mark=$(feature_mark "$FEATURE")
  new_feat=$(git log --format=%s "$before..HEAD" | grep -cE "$FEAT_RE" || true)

  if [[ $mark == '!' ]]; then
    log err "$FEATURE was marked blocked: $(sed -n "/^- \[!\] $FEATURE /,/^- \[/p" docs/ROADMAP.md | grep -m1 'Blocked:' | sed 's/^ *- Blocked: *//')"
    notify "$FEATURE blocked" "$FEATURE_TITLE"
    # Keep the marker and its notes; set the half-built code aside.
    commit_docs "docs: $FEATURE blocked (autopilot)"
    stash_changes "$FEATURE blocked, uncommitted work"
    GIVEUPS_IN_A_ROW=$((GIVEUPS_IN_A_ROW + 1))
  elif [[ -f $STATE/no_skill && ! -f $STATE/inline_skill && $before == "$(git rev-parse HEAD)" ]]; then
    log warn "/next-feature was not recognised in headless mode; inlining its SKILL.md from now on."
    echo 1 >"$STATE/inline_skill"
    ATTEMPTS[$FEATURE]=$((ATTEMPT - 1))
    continue
  elif ((new_feat > 0)) && [[ $mark != '~' ]]; then
    log ok "✔ $FEATURE committed: $(git log -1 --format=%s)"
    notify "$FEATURE done" "$FEATURE_TITLE"
    # Stray files (screenshots, a scratch note) would make the next session stop and stash.
    if dirty; then
      stash_changes "$FEATURE leftovers after its commit"
    fi
    GIVEUPS_IN_A_ROW=0
    BUSY_WAITS=0
    LIMIT_WAITS=0
  else
    blocker=$(session_blocker "$FEATURE-a$ATTEMPT")
    if [[ $blocker == limit* ]]; then
      ATTEMPTS[$FEATURE]=$((ATTEMPT - 1))
      wait_for_limit "${blocker#limit }"
      continue
    elif [[ $blocker == busy ]]; then
      ATTEMPTS[$FEATURE]=$((ATTEMPT - 1))
      BUSY_WAITS=$((BUSY_WAITS + 1))
      ((BUSY_WAITS <= 8)) || die "the API stayed unavailable through 8 retries"
      # 5, 10, 15 … 30 min: about 2.75 h in all before giving up on the API.
      busy_wait=$((BUSY_WAITS * 300 > 1800 ? 1800 : BUSY_WAITS * 300))
      log warn "API busy or network error; retrying in $(fmt_dur "$busy_wait") (retry $BUSY_WAITS/8)."
      wait_with_status "$(secs "$busy_wait")" 'API busy'
      continue
    fi
    if ((SESSION_RC == 124 || SESSION_RC == 137)); then
      log err "✘ $FEATURE attempt $ATTEMPT timed out after $SESSION_TIMEOUT (see $RUN/$FEATURE-a$ATTEMPT.jsonl)."
    else
      log err "✘ $FEATURE attempt $ATTEMPT did not finish (exit $SESSION_RC; see $RUN/$FEATURE-a$ATTEMPT.jsonl)."
    fi
    if ((ATTEMPT >= MAX_ATTEMPTS)); then
      log err "Giving up on $FEATURE after $ATTEMPT sessions."
      notify "Gave up on $FEATURE" "$FEATURE_TITLE"
      stash_changes "$FEATURE gave up after $ATTEMPT sessions"
      # An uncommitted split (F95 into F95a/F95b) went into the stash: mark the original.
      target=$FEATURE
      [[ -n $(feature_mark "$target") ]] || target=${FEATURE%[a-z]}
      "${ROADMAP_JS[@]}" mark "$target" '!' "autopilot: $ATTEMPT unattended sessions did not finish it; logs in $RUN" >/dev/null ||
        die "could not mark $target blocked in docs/ROADMAP.md"
      commit_docs "docs: $target blocked (autopilot)"
      GIVEUPS_IN_A_ROW=$((GIVEUPS_IN_A_ROW + 1))
    else
      wait_with_status "$(secs 60)" 'retrying soon'
    fi
  fi
  ((GIVEUPS_IN_A_ROW < MAX_GIVEUPS_IN_A_ROW)) || die "$GIVEUPS_IN_A_ROW features in a row were blocked; stopping before burning the rest"
done

FEATURE=''
refresh_counts
summary=$(roadmap_next | grep -E '^(Done|Blocked|Gated|Not eligible)' | paste -sd' ' -)
log info "Roadmap loop finished: $summary"
if ! roadmap_next | grep -q '^Blocked: none'; then
  notify 'Autopilot finished with blocked features' "$summary"
  die "some features are still blocked after the extra pass, so nothing is pushed or deployed"
fi
# No eligible feature but nothing blocked: a dependency is missing or circular. Features that
# only wait on Kim's gates count as nothing left: what is built ships, and the report lists them.
roadmap_next | grep -q '^Nothing left' || die "features remain but none is eligible: $summary"
if ! roadmap_next | grep -q '^Gated: none'; then
  log warn "Waiting on Kim's approval: $(roadmap_next | sed -n 's/^Gated: //p'). Shipping what is built."
fi
if ((DRY_RUN)); then
  log info "Dry run: nothing left to build."
  dry_run_checks
  exit 0
fi

# ---------------------------------------------------------------------------------------------
# Final gate, push, deploy

# repair LABEL CONTEXT: one session that fixes failing checks. Waits out usage limits and API
# errors as the feature loop does, so they do not use up a repair.
repair() {
  local label=$1 context=$2 try=1 name blocker
  while :; do
    name=$label
    ((try == 1)) || name+="-r$try"
    run_session "$name" "Every buildable roadmap feature is built and committed, but these checks fail:

$context

Fix only what makes them fail, without weakening, skipping or deleting tests. Run the verify skill until it is green, then make one commit: fix: <what you fixed>. Do not start any roadmap feature."
    blocker=$(session_blocker "$name")
    [[ -n $blocker ]] || return 0
    ((try < 8)) || die "repair sessions kept hitting usage limits or API errors"
    if [[ $blocker == limit* ]]; then
      wait_for_limit "${blocker#limit }"
    else
      log warn "API busy or network error during a repair; retrying in 5 min."
      wait_with_status "$(secs 300)" 'API busy'
    fi
    try=$((try + 1))
  done
}

PHASE='final checks'
FEATURE_TITLE='' ATTEMPT=0
for try in 1 2 3; do
  run_gate && break
  ((try < 3)) || die "checks still fail after 2 repair sessions; nothing pushed"
  log warn "Repair session $try for the failing checks…"
  repair "repair-gate-$try" "$(tail -80 "$RUN/gate.log")"
  dirty && stash_changes "repair $try leftovers"
done

if ((!DEPLOY)); then
  DEPLOY_STATE='skipped (--no-deploy): built and checked, not pushed'
  log ok "All features built and checked. --no-deploy: not pushing."
  notify 'Autopilot done' 'Built and checked; not pushed (--no-deploy)'
  exit 0
fi

# Fetch, rebase onto origin/main if it moved, run the push guard, push. Each try fetches again,
# so a push that lost a race with another push rebases and goes again. The first push of a new
# repo has no origin/main to compare with.
push_main() {
  local i
  PHASE='pushing'
  for i in 1 2 3; do
    if ! git fetch -q origin >>"$RUN_LOG" 2>&1; then
      log warn "git fetch failed (try $i)."
    else
      if git rev-parse -q --verify origin/main >/dev/null && ! git merge-base --is-ancestor origin/main HEAD; then
        log warn "origin/main moved; rebasing onto it."
        if ! git -C "$REPO" rebase --autostash origin/main >>"$RUN_LOG" 2>&1; then
          git -C "$REPO" rebase --abort >/dev/null 2>&1 || true
          die "rebase onto origin/main conflicted; nothing pushed"
        fi
      fi
      check_remote
      check_push_scope
      if git push -q origin HEAD:main >>"$RUN_LOG" 2>&1; then
        log ok "Pushed $(git rev-parse --short HEAD) to origin/main."
        DEPLOY_STATE="pushed $(git rev-parse --short HEAD); waiting for $WORKFLOW"
        return 0
      fi
      log warn "git push failed (try $i)."
    fi
    ((i < 3)) || break
    log warn "Retrying the push in $((i * 30)) s."
    wait_with_status "$(secs $((i * 30)))" 'push retry'
  done
  DEPLOY_STATE='not pushed: git push failed three times'
  die "git push failed three times"
}

# find_run EVENT SINCE_EPOCH [SHA]: newest matching deploy run id, waiting up to 5 min.
find_run() {
  local event=$1 since=$2 sha=${3:-} id='' i
  for i in $(seq 1 30); do
    id=$(gh run list --workflow "$WORKFLOW" --event "$event" --limit 10 \
      --json databaseId,createdAt,headSha 2>>"$RUN_LOG" |
      jq -r --arg sha "$sha" --argjson since "$since" \
        '[.[] | select(($sha == "" or .headSha == $sha) and ((.createdAt | fromdateiso8601) >= $since - 60))] | .[0].databaseId // empty' 2>>"$RUN_LOG")
    [[ -n $id ]] && {
      echo "$id"
      return 0
    }
    PHASE="waiting for the $WORKFLOW run to start"
    render_status
    sleep "$(secs 10)"
  done
  return 1
}

# watch_run ID: poll until done, showing the current step. Returns 0 on success. On failure it
# saves the failed log and the failed "job<TAB>step" names next to it.
watch_run() {
  local id=$1 json status conclusion step started unknown=0
  started=$(date +%s)
  log info "Watching deploy run $id: $(gh run view "$id" --json url --jq .url 2>>"$RUN_LOG")"
  while :; do
    json=$(gh run view "$id" --json status,conclusion,jobs 2>>"$RUN_LOG") || json='{}'
    status=$(jq -r '.status // "unknown"' <<<"$json" 2>/dev/null) || status=unknown
    conclusion=$(jq -r '.conclusion // ""' <<<"$json" 2>/dev/null) || conclusion=''
    step=$(jq -r '[.jobs[]?.steps[]? | select(.status == "in_progress") | .name] | first // ""' <<<"$json" 2>/dev/null) || step=''
    PHASE="deploy run $id: $status${step:+ · $step}"
    render_status
    if [[ $status == completed ]]; then
      [[ $conclusion == success ]] && return 0
      gh run view "$id" --log-failed >"$RUN/deploy-$id-failed.log" 2>&1 || true
      jq -r '.jobs[]? | .name as $job | .steps[]? | select(.conclusion == "failure") | "\($job)\t\(.name)"' \
        <<<"$json" >"$RUN/deploy-$id-failed-steps.txt" 2>/dev/null || true
      # Without step data, the log's own "job<TAB>step<TAB>line" prefixes name them.
      [[ -s $RUN/deploy-$id-failed-steps.txt ]] ||
        cut -f1,2 "$RUN/deploy-$id-failed.log" | grep $'\t' | sort -u >"$RUN/deploy-$id-failed-steps.txt" || true
      log err "Deploy run $id ended: $conclusion at $(paste -sd, "$RUN/deploy-$id-failed-steps.txt") (log: $RUN/deploy-$id-failed.log)"
      return 1
    fi
    if [[ $status == unknown ]]; then
      unknown=$((unknown + 1))
      ((unknown < 40)) || die "gh could not read deploy run $id for 10 min; check it by hand"
    else
      unknown=0
    fi
    (($(date +%s) - started < $(secs 5400))) || die "deploy run $id did not finish in 90 min; check it by hand"
    for _ in $(seq 1 "$(secs 15)"); do
      render_status
      sleep 1
    done
  done
}

dispatch_force() {
  local since id
  since=$(date +%s)
  log warn "Live connections blocked the deploy; dispatching with force=true (ends live connections)."
  notify 'Forcing deploy' 'Live connections blocked it; force=true ends live connections'
  gh workflow run "$WORKFLOW" --ref main -f force=true >>"$RUN_LOG" 2>&1 || die "gh workflow run failed"
  id=$(find_run workflow_dispatch "$since") || die "the forced deploy run never appeared"
  RUN_ID=$id
}

[[ -f $REPO/.github/workflows/$WORKFLOW ]] || {
  DEPLOY_STATE="not pushed: .github/workflows/$WORKFLOW is missing ({{DEPLOY_FEATURE}} writes it; gated or unbuilt?)"
  die ".github/workflows/$WORKFLOW is missing, so a push would not deploy; {{DEPLOY_FEATURE}} should have added it"
}
push_main
SHA=$(git rev-parse HEAD)
PUSHED_AT=$(date +%s)
RUN_ID=$(find_run push "$PUSHED_AT" "$SHA") || {
  log warn "No push-triggered deploy run appeared; dispatching one."
  gh workflow run "$WORKFLOW" --ref main >>"$RUN_LOG" 2>&1 || die "gh workflow run failed"
  RUN_ID=$(find_run workflow_dispatch "$PUSHED_AT") || die "no deploy run appeared"
}

# The workflow's own checks and image smoke test (CI_STEPS, at the top) are the code's fault, so
# they get a repair session; anything else (ssh, the runner, the outside smoke check) gets one
# re-run.
REPAIRS=0
RERUNS=0
FORCED=0
until watch_run "$RUN_ID"; do
  failed_log="$RUN/deploy-$RUN_ID-failed.log"
  failed_steps=$(cat "$RUN/deploy-$RUN_ID-failed-steps.txt" 2>/dev/null || true)
  if grep -q 'live connection(s) after 10 min' "$failed_log" && ((FORCED == 0)); then
    FORCED=1
    dispatch_force
  elif grep -qE "$CI_STEPS" <<<"$failed_steps" && ((REPAIRS < 2)); then
    REPAIRS=$((REPAIRS + 1))
    log warn "CI checks failed; repair session $REPAIRS."
    before=$(git rev-parse HEAD)
    repair "repair-ci-$REPAIRS" "The GitHub Actions deploy run failed at: $failed_steps
Its failed-step log ends with:
$(tail -120 "$failed_log")"
    dirty && stash_changes "CI repair $REPAIRS leftovers"
    [[ $(git rev-parse HEAD) != "$before" ]] || die "the CI repair session committed nothing; code is pushed but not live"
    run_gate || die "local checks fail after the CI repair; not pushing again"
    push_main
    SHA=$(git rev-parse HEAD)
    PUSHED_AT=$(date +%s)
    RUN_ID=$(find_run push "$PUSHED_AT" "$SHA") || die "no deploy run appeared after the repair push"
  elif ((RERUNS == 0)); then
    RERUNS=1
    log warn "Deploy failed for another reason; re-running the failed jobs once."
    gh run rerun "$RUN_ID" --failed >>"$RUN_LOG" 2>&1 || die "gh run rerun failed"
    # Until GitHub requeues it, the run still reads completed/failure.
    for _ in $(seq 1 24); do
      [[ $(gh run view "$RUN_ID" --json status --jq .status 2>>"$RUN_LOG") == completed ]] || break
      sleep "$(secs 5)"
    done
  else
    notify 'Deploy failed' "Run $RUN_ID"
    DEPLOY_STATE="failed: deploy run $RUN_ID failed again ($(paste -sd, "$RUN/deploy-$RUN_ID-failed-steps.txt" 2>/dev/null)); code is pushed but not live. Log: $RUN/deploy-$RUN_ID-failed.log"
    die "deploy run $RUN_ID failed again; code is pushed but not live"
  fi
done

DEPLOY_STATE="deployed $(git rev-parse --short HEAD): $(gh run view "$RUN_ID" --json url --jq .url 2>/dev/null || echo "run $RUN_ID") succeeded"
PHASE='checking the live site'
for i in 1 2 3 4 5; do
  if health=$(curl -fsS --max-time 10 "$LIVE_URL$HEALTH_PATH") && [[ $(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$LIVE_URL/") == 200 ]]; then
    LIVE_STATE="$LIVE_URL$HEALTH_PATH answered: $(head -c 200 <<<"$health")"
    log ok "Live: $LIVE_URL$HEALTH_PATH → $health"
    notify "$APP_TITLE is live" "$LIVE_URL · $(kim_checks) Kim checks queued in docs/PROGRESS.md"
    PHASE='done'
    exit 0
  fi
  log warn "Live check $i failed; retrying in 20 s."
  wait_with_status "$(secs 20)" 'live check'
done
LIVE_STATE="FAILED: $LIVE_URL$HEALTH_PATH or $LIVE_URL/ did not answer 200 after the deploy"
die "the deploy succeeded but $LIVE_URL does not answer"
