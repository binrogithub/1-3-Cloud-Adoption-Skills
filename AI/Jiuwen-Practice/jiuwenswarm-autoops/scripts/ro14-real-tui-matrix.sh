#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
CASES_FILE="${RO14_CASES_FILE:-${ROOT_DIR}/config/acceptance/ro-14-tui-scenarios-v1.json}"
EVIDENCE_FILE="${RO14_EVIDENCE_FILE:-${ROOT_DIR}/docs/evidence/ro-14-real-tui-matrix-20260914.json}"
RUN_PREFIX="${RO14_RUN_PREFIX:-ro14-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
START_AT="${RO14_START_AT:-1}"
COUNT="${RO14_COUNT:-12}"
REPEATS="${RO14_REPEATS:-3}"
REPEAT_START="${RO14_REPEAT_START:-1}"
TIMEOUT="${RO14_TIMEOUT:-180}"

[[ -f "$CASES_FILE" ]] || { echo "cases file not found: $CASES_FILE" >&2; exit 2; }
command -v jiuwenswarm-tui >/dev/null || { echo "missing jiuwenswarm-tui" >&2; exit 2; }
command -v expect >/dev/null || { echo "missing expect" >&2; exit 2; }
[[ "$START_AT" =~ ^[0-9]+$ && "$COUNT" =~ ^[0-9]+$ && "$REPEATS" =~ ^[0-9]+$ && "$REPEAT_START" =~ ^[0-9]+$ ]] || exit 2

mkdir -p "$(dirname -- "$EVIDENCE_FILE")" "$ROOT_DIR/.runtime/ro14-matrix"
RESULTS_FILE="$ROOT_DIR/.runtime/ro14-matrix/${RUN_PREFIX}.tsv"
printf 'scenario_id\tclass\trepetition\tresult\tsession\thistory\tdriver_log\n' >"$RESULTS_FILE"

write_evidence() {
  python3 - "$RESULTS_FILE" "$EVIDENCE_FILE" <<'PY'
import json, sys
path, output = sys.argv[1:]
merged = {}
try:
    with open(output, encoding='utf-8') as stream:
        previous = json.load(stream)
    for row in previous.get('scenarios', []):
        if isinstance(row, dict) and row.get('scenario_id'):
            merged[str(row['scenario_id'])] = row
except (OSError, json.JSONDecodeError, TypeError):
    pass
with open(path, encoding='utf-8') as stream:
    for line in stream:
        if line.startswith('scenario_id'):
            continue
        scenario, cls, repetition, result, session, history, driver = line.rstrip('\n').split('\t')
        merged[f'{scenario}-r{repetition}'] = {
            "acceptance_scope":"RO-14-02", "evidence_level":"real-tui",
            "scenario_id":f"{scenario}-r{repetition}", "scenario_class":cls,
            "run_id":session, "result":result, "history":history,
            "driver_log":driver}
with open(output, 'w', encoding='utf-8') as out:
    json.dump({"schema_version":1, "suite":"RO-14-02",
               "scenarios":list(merged.values())}, out, ensure_ascii=False, indent=2)
    out.write('\n')
print(json.dumps({"status":"RECORDED", "runs":len(merged), "evidence":output}, ensure_ascii=False))
PY
}
trap write_evidence EXIT

mapfile -t CASE_ROWS < <(python3 - "$CASES_FILE" "$START_AT" "$COUNT" <<'PY'
import json, sys
cases=json.load(open(sys.argv[1], encoding='utf-8'))['scenarios']
start=int(sys.argv[2]); count=int(sys.argv[3])
for case in cases[start-1:start-1+count]:
    print(json.dumps(case, ensure_ascii=False))
PY
)
[[ "${#CASE_ROWS[@]}" -gt 0 ]] || { echo "no cases selected" >&2; exit 2; }

for row in "${CASE_ROWS[@]}"; do
  eval "$(python3 - "$row" <<'PY'
import json, shlex, sys
c=json.loads(sys.argv[1])
for key in ('scenario_id','class','expected_role','prompt'):
    print(f'{key.upper()}={shlex.quote(str(c.get(key,"")))}')
PY
  )"
  for repetition in $(seq "$REPEAT_START" "$((REPEAT_START + REPEATS - 1))"); do
    session="${RUN_PREFIX}-${SCENARIO_ID}-r${repetition}"
    driver_log="$ROOT_DIR/.runtime/ro14-matrix/${session}.log"
    history="/root/.jiuwenswarm/agent/sessions/${session}/history.jsonl"
    echo "START ${SCENARIO_ID} repetition=${repetition} session=${session}"
    if "$SCRIPT_DIR/tui-autoops-e2e.sh" --prompt "$PROMPT" --session "$session" \
        --expected-role "$EXPECTED_ROLE" --timeout "$TIMEOUT" >"$driver_log" 2>&1; then
      result=PASS
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$SCENARIO_ID" "$CLASS" "$repetition" "$result" "$session" "$history" "$driver_log" >>"$RESULTS_FILE"
      echo "PASS ${SCENARIO_ID} repetition=${repetition}"
    else
      result=FAIL
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$SCENARIO_ID" "$CLASS" "$repetition" "$result" "$session" "$history" "$driver_log" >>"$RESULTS_FILE"
      tail -n 60 "$driver_log" >&2 || true
      echo "STOP after ${SCENARIO_ID} repetition=${repetition}; repair before continuing" >&2
      exit 1
    fi
  done
done
