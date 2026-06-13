#!/usr/bin/env bash
# Concurrent Top-30 production test batch for claude-glm.
# See tests/PRODUCTION-TEST-PLAN.md for the full matrix; this script runs the [C] cases.
set -u

GLM_BIN="${GLM_BIN:-claude-glm}"
ROUTER_URL="${ROUTER_URL:-http://127.0.0.1:3456}"
ROUTER_KEY="${CLAUDE_GLM_ROUTER_KEY:-claude-glm-local}"
CASE_TIMEOUT="${CASE_TIMEOUT:-300}"
RESULTS="${RESULTS:-/tmp/claude-glm-top30-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$RESULTS"

# --- helpers -----------------------------------------------------------------

# run claude-glm in the case workdir; $1=case id, rest = args (last is prompt)
glm() {
  local id="$1"; shift
  local wd="$RESULTS/$id/work"
  mkdir -p "$wd"
  ( cd "$wd" && timeout "$CASE_TIMEOUT" "$GLM_BIN" "$@" \
      > "$RESULTS/$id/stdout" 2> "$RESULTS/$id/stderr" )
  echo $? > "$RESULTS/$id/rc"
}

rc_of() { cat "$RESULTS/$1/rc" 2>/dev/null || echo 999; }
out_of() { cat "$RESULTS/$1/stdout" 2>/dev/null; }

# assert_json <id> <python-bool-expr over d (parsed stdout JSON)>
assert_json() {
  local id="$1" expr="$2"
  python3 - "$RESULTS/$id/stdout" "$expr" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print(f"json-parse-failed: {e}"); sys.exit(1)
try:
    ok = bool(eval(sys.argv[2], {"d": d}))
except Exception as e:
    print(f"expr-error: {e}"); sys.exit(1)
sys.exit(0 if ok else 1)
PY
}

pass() { echo PASS > "$RESULTS/$1.status"; echo "${2:-}" > "$RESULTS/$1.note"; }
fail() { echo FAIL > "$RESULTS/$1.status"; echo "${2:-}" > "$RESULTS/$1.note"; }

# --- cases -------------------------------------------------------------------

case_A1() { # minimal conversation
  glm A1 --print 'Reply with OK only'
  [[ "$(rc_of A1)" == 0 ]] && out_of A1 | grep -q 'OK' \
    && pass A1 "OK returned" || fail A1 "rc=$(rc_of A1) out=$(out_of A1 | head -c 120)"
}

case_A2() { # json output protocol
  glm A2 --print --output-format json 'Reply with OK only'
  assert_json A2 'd["subtype"]=="success" and d["is_error"]==False and "OK" in d["result"]' \
    && pass A2 || fail A2 "$(out_of A2 | head -c 200)"
}

case_A3() { # stream-json protocol
  glm A3 --print --verbose --output-format stream-json 'Reply with OK only'
  python3 - "$RESULTS/A3/stdout" <<'PY' && pass A3 || fail A3 "stream lines invalid"
import json, sys
lines = [l for l in open(sys.argv[1]) if l.strip()]
assert len(lines) >= 2, "too few events"
objs = [json.loads(l) for l in lines]
assert any(o.get("type") == "result" for o in objs), "no result event"
sys.exit(0)
PY
}

case_A4() { # exit code semantics: success=0, invalid flag value !=0
  glm A4 --print 'Reply with OK only'
  local rc_ok; rc_ok="$(rc_of A4)"
  mkdir -p "$RESULTS/A4b"; cp -r "$RESULTS/A4" "$RESULTS/A4b" 2>/dev/null || true
  ( cd "$RESULTS/A4/work" && timeout 60 "$GLM_BIN" --print --output-format bogus 'x' \
      >/dev/null 2>&1 ); local rc_bad=$?
  [[ "$rc_ok" == 0 && "$rc_bad" != 0 ]] \
    && pass A4 "ok=0 bad=$rc_bad" || fail A4 "ok=$rc_ok bad=$rc_bad"
}

case_A5() { # stderr cleanliness
  glm A5 --print 'Reply with OK only'
  if [[ "$(rc_of A5)" == 0 ]] && ! grep -qiE 'error|exception|traceback' "$RESULTS/A5/stderr"; then
    pass A5
  else
    fail A5 "stderr: $(head -c 200 "$RESULTS/A5/stderr")"
  fi
}

case_A6() { # --version passthrough
  glm A6 --version
  out_of A6 | grep -qE '[0-9]+\.[0-9]+\.[0-9]+' \
    && pass A6 "$(out_of A6 | head -1)" || fail A6 "$(out_of A6 | head -c 120)"
}

case_A7() { # stop_reason semantics
  glm A7 --print --output-format json 'Reply with OK only'
  assert_json A7 'd["stop_reason"]=="end_turn" and d.get("terminal_reason")=="completed"' \
    && pass A7 || fail A7 "$(out_of A7 | head -c 200)"
}

case_B1() { # modelUsage present
  glm B1 --print --output-format json 'Reply with OK only'
  assert_json B1 'len(d["modelUsage"])>0' \
    && pass B1 "model=$(python3 -c 'import json,sys;print(list(json.load(open(sys.argv[1]))["modelUsage"]))' "$RESULTS/B1/stdout")" \
    || fail B1 "$(out_of B1 | head -c 200)"
}

case_B2() { # auto-compact window must be configured below the MaaS hard input
  # limit (196608). Claude Code's declared contextWindow cannot be overridden,
  # so the production-relevant property is the compact trigger point.
  local wrapper window
  wrapper="$(command -v "$GLM_BIN")"
  window="$(grep -oE 'CLAUDE_CODE_AUTO_COMPACT_WINDOW="[^"]*:-([0-9]+)' "$wrapper" 2>/dev/null | grep -oE '[0-9]+$' | head -1)"
  mkdir -p "$RESULTS/B2"
  if [[ -n "$window" && "$window" -le 190000 ]]; then
    glm B2 --print --output-format json 'Reply with OK only'
    assert_json B2 'd["is_error"]==False' \
      && pass B2 "auto-compact window=$window (< 196608 hard limit)" \
      || fail B2 "window=$window but request failed"
  else
    fail B2 "wrapper auto-compact window missing or too high: '${window:-unset}'"
  fi
}

case_B6() { # explicit --model passthrough
  glm B6 --model claude-opus-4-6 --print --output-format json 'Reply with OK only'
  assert_json B6 'd["is_error"]==False and "OK" in d["result"]' \
    && pass B6 || fail B6 "rc=$(rc_of B6) $(out_of B6 | head -c 200)"
}

case_C1() { # Bash tool
  local mk="MARK-C1-$RANDOM"
  glm C1 --print --allowedTools Bash --output-format json \
    "Use the Bash tool to run exactly this command: echo $mk . Then reply with only the command output."
  assert_json C1 "\"$mk\" in d[\"result\"]" \
    && pass C1 || fail C1 "$(out_of C1 | head -c 300)"
}

case_C2() { # Read tool
  local mk="SECRET-C2-$RANDOM"
  mkdir -p "$RESULTS/C2/work"; echo "$mk" > "$RESULTS/C2/work/note.txt"
  glm C2 --print --allowedTools Read --output-format json \
    'Read the file note.txt in the current directory and reply with only its contents.'
  assert_json C2 "\"$mk\" in d[\"result\"]" \
    && pass C2 || fail C2 "$(out_of C2 | head -c 300)"
}

case_C3() { # Write tool
  local mk="CONTENT-C3-$RANDOM"
  glm C3 --print --permission-mode acceptEdits --allowedTools Write --output-format json \
    "Create a file named out.txt in the current directory with exactly this content: $mk"
  grep -q "$mk" "$RESULTS/C3/work/out.txt" 2>/dev/null \
    && pass C3 || fail C3 "file missing or wrong: $(cat "$RESULTS/C3/work/out.txt" 2>/dev/null | head -c 120)"
}

case_C4() { # Edit tool
  mkdir -p "$RESULTS/C4/work"
  printf 'alpha beta gamma\n' > "$RESULTS/C4/work/data.txt"
  glm C4 --print --permission-mode acceptEdits --allowedTools Read,Edit --output-format json \
    'In data.txt in the current directory, replace the word beta with DELTA. Change nothing else.'
  grep -q 'alpha DELTA gamma' "$RESULTS/C4/work/data.txt" 2>/dev/null \
    && pass C4 || fail C4 "data.txt: $(cat "$RESULTS/C4/work/data.txt" 2>/dev/null)"
}

case_C5() { # Glob/Grep tools
  local mk="NEEDLE-C5-$RANDOM"
  mkdir -p "$RESULTS/C5/work/a/b"
  echo "filler" > "$RESULTS/C5/work/a/x.txt"
  echo "$mk" > "$RESULTS/C5/work/a/b/target.txt"
  glm C5 --print --allowedTools Glob,Grep --output-format json \
    "Search the current directory tree for the file containing the string $mk and reply with only that file's name."
  assert_json C5 '"target.txt" in d["result"]' \
    && pass C5 || fail C5 "$(out_of C5 | head -c 300)"
}

case_C6() { # multi-tool agentic chain
  local mk="CHAIN-C6-$RANDOM"
  glm C6 --print --permission-mode acceptEdits --allowedTools Write,Read --output-format json \
    "Step 1: use the Write tool to create chain.txt containing exactly: $mk . Step 2: use the Read tool to read chain.txt back. Step 3: reply with only the file content."
  assert_json C6 "\"$mk\" in d[\"result\"] and d[\"num_turns\"]>=2" \
    && pass C6 "turns=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["num_turns"])' "$RESULTS/C6/stdout" 2>/dev/null)" \
    || fail C6 "$(out_of C6 | head -c 300)"
}

case_C7() { # tool args with special characters
  local mk='he said "hi" 中文 100%'
  glm C7 --print --permission-mode acceptEdits --allowedTools Write --output-format json \
    "Use the Write tool to create special.txt with exactly this content (preserve quotes and Chinese): $mk"
  grep -qF "$mk" "$RESULTS/C7/work/special.txt" 2>/dev/null \
    && pass C7 || fail C7 "special.txt: $(cat "$RESULTS/C7/work/special.txt" 2>/dev/null | head -c 120)"
}

case_D1() { # session id + JSONL persisted
  glm D1 --print --output-format json 'Reply with OK only'
  local sid
  sid="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["session_id"])' "$RESULTS/D1/stdout" 2>/dev/null)"
  if [[ "$sid" =~ ^[0-9a-f-]{36}$ ]] && \
     compgen -G "$HOME/.claude*/projects/*/${sid}.jsonl" > /dev/null; then
    pass D1 "sid=$sid"
  else
    fail D1 "sid=$sid jsonl-not-found"
  fi
}

case_D2() { # --resume memory
  local mk="MEMO-D2-$RANDOM"
  glm D2 --print --output-format json "Remember the secret word: $mk . Reply with OK only."
  local sid
  sid="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["session_id"])' "$RESULTS/D2/stdout" 2>/dev/null)"
  [[ -n "$sid" ]] || { fail D2 "no session id"; return; }
  ( cd "$RESULTS/D2/work" && timeout "$CASE_TIMEOUT" "$GLM_BIN" --print --resume "$sid" \
      --output-format json 'What is the secret word? Reply with only the secret word.' \
      > "$RESULTS/D2/stdout2" 2>> "$RESULTS/D2/stderr" )
  grep -q "$mk" "$RESULTS/D2/stdout2" \
    && pass D2 || fail D2 "resume answer: $(head -c 200 "$RESULTS/D2/stdout2" 2>/dev/null)"
}

case_E1() { # usage tokens must be non-zero (cost + auto-compact foundation)
  glm E1 --print --output-format json 'Reply with OK only'
  assert_json E1 'd["usage"]["input_tokens"]>0 and d["usage"]["output_tokens"]>0' \
    && pass E1 \
    || fail E1 "usage=$(python3 -c 'import json,sys;u=json.load(open(sys.argv[1]))["usage"];print(u["input_tokens"],u["output_tokens"])' "$RESULTS/E1/stdout" 2>/dev/null)"
}

case_E2() { # ~30k char input
  local filler prompt
  filler="$(python3 -c 'print(("lorem ipsum dolor sit amet "*8 + "\n")*140)')"
  prompt="The text below is filler. Ignore it and reply with only the word ACK.
$filler"
  glm E2 --print --output-format json "$prompt"
  assert_json E2 'd["is_error"]==False and "ACK" in d["result"]' \
    && pass E2 "input_chars=${#prompt}" || fail E2 "rc=$(rc_of E2) $(out_of E2 | head -c 200)"
}

case_E3() { # large output
  glm E3 --print 'Output the numbers 1 to 100, one number per line, with no other text.'
  local n
  n="$(out_of E3 | grep -cE '^[0-9]+$')"
  [[ "$n" -ge 80 ]] && pass E3 "lines=$n" || fail E3 "numeric lines=$n"
}

case_E5() { # latency SLO under concurrency
  glm E5 --print --output-format json 'Reply with OK only'
  assert_json E5 'd["duration_ms"]<120000' \
    && pass E5 "$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["duration_ms"],"ms")' "$RESULTS/E5/stdout" 2>/dev/null)" \
    || fail E5 "duration too high or request failed"
}

case_G2() { # session isolation
  local mk="ISOLATE-G2-$RANDOM"
  glm G2 --print --output-format json "Remember the secret word: $mk . Reply with OK only."
  ( cd "$RESULTS/G2/work" && timeout "$CASE_TIMEOUT" "$GLM_BIN" --print --output-format json \
      'Did I tell you a secret word earlier in this conversation? If you do not know one, reply with exactly NO-SECRET.' \
      > "$RESULTS/G2/stdout2" 2>> "$RESULTS/G2/stderr" )
  if grep -q "$mk" "$RESULTS/G2/stdout2"; then
    fail G2 "secret leaked across sessions"
  elif grep -q 'NO-SECRET' "$RESULTS/G2/stdout2"; then
    pass G2
  else
    fail G2 "unexpected answer: $(head -c 200 "$RESULTS/G2/stdout2" 2>/dev/null)"
  fi
}

case_G3() { # router stays healthy under load: probe for 120s
  local fails=0 total=0
  for _ in $(seq 1 40); do
    total=$((total+1))
    curl -fsS -m 3 -H "Authorization: Bearer $ROUTER_KEY" "$ROUTER_URL/" >/dev/null 2>&1 \
      || fails=$((fails+1))
    sleep 3
  done
  mkdir -p "$RESULTS/G3"; echo "probes=$total fails=$fails" > "$RESULTS/G3/probe"
  [[ "$fails" == 0 ]] && pass G3 "40/40 probes ok" || fail G3 "$fails/$total probes failed"
}

case_H1() { # Chinese Q&A
  glm H1 --print '用中文回答：1+1等于几？只回答数字，不要其他内容。'
  out_of H1 | grep -qE '2|二' && pass H1 || fail H1 "$(out_of H1 | head -c 120)"
}

case_H2() { # emoji / unicode round-trip
  glm H2 --print 'Reply with exactly this string and nothing else: 🚀火箭🎯'
  out_of H2 | grep -q '🚀火箭🎯' && pass H2 || fail H2 "$(out_of H2 | head -c 120)"
}

case_H3() { # shell special characters survive
  glm H3 --print 'Reply with only this token, exactly as written: A$B"C\D'
  out_of H3 | grep -qF 'A$B"C\D' && pass H3 || fail H3 "$(out_of H3 | head -c 120)"
}

case_H4() { # whitespace-only prompt: must exit, not hang
  ( cd "$RESULTS" && mkdir -p H4/work && cd H4/work && \
    timeout 90 "$GLM_BIN" --print '   ' > "$RESULTS/H4/stdout" 2> "$RESULTS/H4/stderr" )
  local rc=$?
  [[ "$rc" != 124 ]] && pass H4 "rc=$rc (no hang)" || fail H4 "timed out (hang)"
}

case_H5() { # strict JSON output fidelity
  glm H5 --print 'Output exactly this JSON object and nothing else: {"a":1,"b":"x"}'
  python3 - "$RESULTS/H5/stdout" <<'PY' && pass H5 || fail H5 "$(out_of H5 | head -c 120)"
import json, sys, re
raw = open(sys.argv[1]).read().strip()
m = re.search(r'\{.*\}', raw, re.S)
assert m, "no json found"
assert json.loads(m.group(0)) == {"a": 1, "b": "x"}
PY
}

case_I1() { # default permissions block writes in headless mode
  glm I1 --print --output-format json \
    'Create a file named forbidden.txt in the current directory containing the word blocked. If you are unable to, reply with exactly CANNOT.'
  if [[ -f "$RESULTS/I1/work/forbidden.txt" ]]; then
    fail I1 "file was written despite default permissions"
  else
    pass I1 "write blocked"
  fi
}

# --- run ---------------------------------------------------------------------

CASES=(A1 A2 A3 A4 A5 A6 A7 B1 B2 B6 C1 C2 C3 C4 C5 C6 C7 D1 D2 E1 E2 E3 E5 G2 G3 H1 H2 H3 H4 H5 I1)

echo "results dir: $RESULTS"
echo "launching ${#CASES[@]} cases concurrently..."
start_ts=$(date +%s)
declare -A PIDS
for c in "${CASES[@]}"; do
  mkdir -p "$RESULTS/$c"
  ( "case_$c" ) &
  PIDS[$c]=$!
done
for c in "${CASES[@]}"; do
  wait "${PIDS[$c]}" 2>/dev/null
done
elapsed=$(( $(date +%s) - start_ts ))

# --- report ------------------------------------------------------------------

passn=0; failn=0
for c in "${CASES[@]}"; do
  [[ "$(cat "$RESULTS/$c.status" 2>/dev/null)" == PASS ]] && passn=$((passn+1)) || failn=$((failn+1))
done
{
  echo "# claude-glm Top-30 concurrent batch — $(date -Iseconds)"
  echo
  echo "wall time: ${elapsed}s, concurrency: ${#CASES[@]}"
  echo
  printf "| %-4s | %-6s | %s |\n" "case" "status" "note"
  echo "|------|--------|------|"
  for c in "${CASES[@]}"; do
    s="$(cat "$RESULTS/$c.status" 2>/dev/null || echo MISSING)"
    n="$(head -c 160 "$RESULTS/$c.note" 2>/dev/null | tr '\n' ' ')"
    printf "| %-4s | %-6s | %s |\n" "$c" "$s" "$n"
  done
  echo
  echo "PASS=$passn FAIL=$failn"
} | tee "$RESULTS/report.md"

exit $(( failn > 0 ? 1 : 0 ))
