#!/usr/bin/env bash
# shellcheck disable=SC2016,SC2034 # check() evals its single-quoted test, which reads out, rc and B
# Tests for bin/fiction-autopilot with a fake claude (no real sessions, no network beyond uv's cache).
# Each scenario runs the autopilot in a temp book folder, past its tmux and systemd wrappers, with
# short waits. Ends with shellcheck. Run: bin/tests/fiction-autopilot.sh
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
AUTOPILOT=$HERE/../bin/fiction-autopilot
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/tmux"
pass=0 fail=0
ok() { echo "  ok   $1"; pass=$((pass + 1)); }
bad() { echo "  FAIL $1"; fail=$((fail + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

# --- fakes ---
cat >"$T/bin/notify-send" <<'EOF'
#!/usr/bin/env bash
echo "$*" >>"$FAKE_STATE/notify"
EOF
cat >"$T/bin/claude" <<'EOF'
#!/usr/bin/env bash
# Fake claude -p: finds the stage from the prompt's overrides, does the stage's work (or fails as
# FAKE_<STAGE> says) and prints stream-json events.
prompt=$2
book=$(sed -n 's/.*\$ARGUMENTS = \(.*\), except where.*/\1/p' <<<"$prompt" | head -1)
dir=$(dirname "$book"); c=$dir/companions
case $prompt in
*companions/.split-done*) stage=split ;;
*companions/.epub-done*) stage=epub ;;
*companions/.done*) stage=companions ;;
esac
n=$(($(cat "$FAKE_STATE/$stage.calls" 2>/dev/null || echo 0) + 1))
echo $n >"$FAKE_STATE/$stage.calls"
var=FAKE_${stage^^}; mode=${!var:-ok}
[[ $mode == limit && $n -gt 1 ]] && mode=ok
[[ $mode == weekly && $n -gt 1 ]] && mode=ok
d7=0.30 status=allowed denials='[]'
case $mode in
ok)
  case $stage in
  split)
    mkdir -p "$c/.text"
    printf '{"form":"novel","source_epub":"%s","units":[{"slug":"01-chapter-1"},{"slug":"02-chapter-2"}]}\n' \
      "$(basename "$book")" >"$c/.units.json"
    touch "$c/.text/01-chapter-1.txt" "$c/.text/02-chapter-2.txt"
    echo "split report" >"$c/.split-done" ;;
  companions)
    mkdir -p "$c/src"
    for s in intro 01-chapter-1 02-chapter-2 end; do touch "$c/src/$s.md"; echo "$s" >>"$c/.checked"; done
    echo "companions report" >"$c/.done" ;;
  epub)
    touch "$dir/$(basename "$dir")-companion.epub"
    echo "epub report" >"$c/.epub-done" ;;
  esac ;;
deny) denials='[{"tool_name":"Bash","tool_input":{"command":"curl x"}}]' ;;
limit) status=rejected ;;
weekly) d7=0.95 ;;
fail) ;;
esac
printf '{"type":"assistant","parent_tool_use_id":null,"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/x/%s-notes.txt"}}]}}\n' "$stage"
for ((i = 0; i < ${FAKE_SLEEP:-0} * 5; i++)); do sleep 0.2; done # short sleeps: a kill ends it promptly
printf '{"type":"rate_limit_event","rate_limit_info":{"status":"%s","resetsAt":0,"unifiedWindows":{"five_hour":{"utilization":0.2,"resetsAt":0},"seven_day":{"utilization":%s,"resetsAt":0}}}}\n' "$status" "$d7"
printf '{"type":"result","result":"%s report","duration_ms":60000,"permission_denials":%s}\n' "$stage" "$denials"
EOF
chmod +x "$T/bin/"*

# run_ap <book dir> [env...]: runs the autopilot inside the wrappers' environment; sets out, rc
run_ap() {
  local dir=$1
  shift
  export FAKE_STATE=$dir/.fake
  mkdir -p "$FAKE_STATE"
  out=$(env "$@" PATH="$T/bin:$PATH" CLAUDE_BIN="$T/bin/claude" TMUX=x AUTOPILOT_WRAPPED=1 \
    RETRY_WAIT=1 LIMIT_WAIT=1 TMUX_TMPDIR="$T/tmux" timeout 120 "$AUTOPILOT" "$dir" 2>&1)
  rc=$?
}
newbook() {
  local dir=$T/books/$1
  mkdir -p "$dir"
  touch "$dir/source.epub"
  echo "$dir"
}

echo "1. happy path"
B=$(newbook happy)
run_ap "$B" FAKE_SLEEP=2
check "exit 0" '((rc == 0))'
check "all done files" '[[ -f $B/companions/.split-done && -f $B/companions/.done && -f $B/companions/.epub-done ]]'
check "companion EPUB" '[[ -f $B/happy-companion.epub ]]'
check "one session per stage" '[[ $(cat "$B/.fake/split.calls" "$B/.fake/companions.calls" "$B/.fake/epub.calls" | tr -d "\n") == 111 ]]'
check "reports kept" '[[ $(ls "$B/autopilot-logs/"*.report.md | wc -l) == 3 ]]'
check "summary logged" 'grep -q "all stages done" "$B/autopilot-logs/autopilot.log"'
check "notified" 'grep -q "all stages done" "$B/.fake/notify"'
check "progress shows units" 'grep -q "4/4 units checked" <<<"$out"'
check "activity shown" 'grep -q "last activity [0-9]m0[0-9]s ago · Read split-notes.txt" <<<"$out"'
check "usage shown" 'grep -q "5h usage 20% · 7d usage 30%" <<<"$out"'

echo "2. resume: done stages skipped, own -companion.epub ignored as input"
run_ap "$B"
check "exit 0" '((rc == 0))'
check "no new sessions" '[[ $(ls "$B/autopilot-logs/"*.jsonl | wc -l) == 3 ]]'

echo "3. permission denial stops the run"
B=$(newbook deny)
run_ap "$B" FAKE_COMPANIONS=deny
check "exit 1" '((rc == 1))'
check "STOPPED names the denial" 'grep -q "companions: 1 permission denial(s) (Bash)" "$B/autopilot-logs/STOPPED"'
check "split done, companions not" '[[ -f $B/companions/.split-done && ! -f $B/companions/.done ]]'
check "notified of stop" 'grep -q Stopped "$B/.fake/notify"'

echo "4. an existing STOPPED refuses to start"
run_ap "$B"
check "exit 1 with reason" '((rc == 1)) && grep -q "stopped earlier" <<<"$out"'

echo "5. unfinished stage: 3 tries, then STOPPED"
B=$(newbook fail)
run_ap "$B" FAKE_SPLIT=fail
check "exit 1" '((rc == 1))'
check "three sessions" '[[ $(cat "$B/.fake/split.calls") == 3 ]]'
check "STOPPED says unfinished" 'grep -q "split still unfinished after 3 tries" "$B/autopilot-logs/STOPPED"'

echo "6. usage limit: waits, retries, the wait costs no try"
B=$(newbook limit)
run_ap "$B" FAKE_SPLIT=limit
check "exit 0" '((rc == 0))'
check "waited" 'grep -q "usage limit: waiting" "$B/autopilot-logs/autopilot.log"'
check "both sessions were try 1" '[[ $(grep -c "split: session start (try 1/3" "$B/autopilot-logs/autopilot.log") == 2 ]]'

echo "7. 7-day usage over the cap pauses before the next session"
B=$(newbook weekly)
run_ap "$B" FAKE_SPLIT=weekly
check "exit 0" '((rc == 0))'
check "paused" 'grep -q "7-day usage at 95%: paused" "$B/autopilot-logs/autopilot.log"'

echo "8. input checks"
B=$(newbook two)
touch "$B/other.epub"
run_ap "$B"
check "two source EPUBs refused" '((rc == 1)) && grep -q "exactly one source EPUB" <<<"$out"'
out=$(env -u TMUX TMUX_TMPDIR="$T/tmux" "$AUTOPILOT" attach 2>&1)
rc=$?
check "attach without a session" '((rc == 1)) && grep -q "no fiction autopilot tmux session" <<<"$out"'

echo "9. Ctrl-C ends the claude session too, so a rerun gets the lock"
B=$(newbook int)
export FAKE_STATE=$B/.fake
mkdir -p "$FAKE_STATE"
set -m # job control: a background job would otherwise ignore SIGINT, unlike the autopilot in its tmux pane
env FAKE_SLEEP=30 PATH="$T/bin:$PATH" CLAUDE_BIN="$T/bin/claude" TMUX=x AUTOPILOT_WRAPPED=1 TMUX_TMPDIR="$T/tmux" \
  "$AUTOPILOT" "$B" >"$T/int.out" 2>&1 &
ap=$!
set +m
sleep 3
kill -INT "$ap"
wait "$ap"
rc=$?
check "exit 130" '((rc == 130))'
check "interrupt logged" 'grep -q "interrupted during split" "$B/autopilot-logs/autopilot.log"'
sleep 1
check "no session left running" '! pgrep -f "$B/source.epub" >/dev/null'
run_ap "$B"
check "rerun gets the lock and finishes" '((rc == 0))'

echo "10. shellcheck"
check "fiction-autopilot and this test" 'shellcheck "$AUTOPILOT" "$0"'

echo "$pass passed, $fail failed"
((fail == 0))
