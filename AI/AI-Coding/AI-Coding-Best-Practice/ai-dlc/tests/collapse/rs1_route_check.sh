#!/usr/bin/env bash
# R2 (route-and-speed 2.1-2.8): the recorded route is checked against the
# measured change. A 14-file change recorded inline stops the task (exit
# 17, ROUTE_STOP, the gate request names count, threshold and route, the
# two options); a 2-file change passes silently; the measurement excludes
# task records, evidence, gateway bookkeeping and the openspec tree and
# lists the exclusions beside the count; a recorded exception with its
# author travels into the delivery report, and one without a reason is
# refused; a configuration carrying no threshold stops rather than
# assuming one; a planned route over the same 14 files passes.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT="$ROOT/bin/report.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
REPO="$T/repo"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed

commit_n () {  # n product files, one commit
  local n="$1"
  for ((i=1;i<=n;i++)); do printf 'product %s\n' "$i" > "$REPO/src$i.txt"; done
  git -C "$REPO" add -A && git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm "n$n"
}

# 1. (2.7) a 14-file change recorded inline stops the task: exit 17,
#    stage ROUTE_STOP, the request names count, threshold and route.
#    Both task records are stamped at the seed commit so base..HEAD
#    spans the change for each
$PY "$REPORT" init --task-dir "$T/task14" --repo "$REPO" --route inline \
  --task-id rs14 >/dev/null
$PY "$REPORT" init --task-dir "$T/task14p" --repo "$REPO" --route planned \
  --task-id rs14p >/dev/null
commit_n 14
set +e
$PY "$REPORT" deliver --task-dir "$T/task14" --repo "$REPO" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' \
  > "$T/d14.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 17 ]] || { echo "FAIL: 14-file inline deliver exited $RC, want 17"; cat "$T/d14.json"; exit 1; }
grep -q '"measured_files": 14' "$T/d14.json"
grep -q '"threshold": 4' "$T/d14.json"
grep -q '"route": "inline"' "$T/d14.json"
grep -q 'rerun_through_plane' "$T/d14.json"
grep -q 'record_exception' "$T/d14.json"
$PY - "$T/task14" <<'PYEOF'
import json, sys
td = sys.argv[1]
st = json.load(open(f"{td}/state.json"))
assert st["stage"] == "ROUTE_STOP", st
assert st["human_state"] == "Needs your decision", st
g = json.load(open(f"{td}/gates/gate-route.request.json"))
assert g["gate_id"] == "gate-route", g
assert g["measured_files"] == 14 and g["threshold"] == 4, g
assert g["options"] == ["rerun_through_plane", "record_exception", "cancel"], g
assert g["excluded_patterns"], "excluded patterns must be listed beside the count"
ev = [json.loads(l) for l in open(f"{td}/events.jsonl")]
assert any(e.get("event") == "ROUTE_STOP" for e in ev), ev
PYEOF

# 2. (2.4) an exception without a reason is refused: exit 1, nothing written
set +e
$PY "$REPORT" exception --task-dir "$T/task14" --reason "" --author nobody \
  > "$T/ex.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: reasonless exception exited $RC, want 1"; cat "$T/ex.json"; exit 1; }
grep -q 'without a reason' "$T/ex.json"
[[ ! -f "$T/task14/gates/gate-route.answer.json" ]] \
  || { echo "FAIL: a refused exception wrote the answer file"; exit 1; }

# 3. (2.5) a recorded exception travels into the delivery report
$PY "$REPORT" exception --task-dir "$T/task14" \
  --reason "single mechanical change despite the file count" --author tester >/dev/null
set +e
$PY "$REPORT" deliver --task-dir "$T/task14" --repo "$REPO" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' \
  > "$T/d14b.json" 2>&1
RC=$?
set -e
[[ "$RC" -ne 17 ]] || { echo "FAIL: deliver still route-stopped after the exception"; cat "$T/d14b.json"; exit 1; }
$PY - "$T/task14" <<'PYEOF'
import json, sys
td = sys.argv[1]
r = json.load(open(f"{td}/report.json"))
ex = r.get("route_exception")
assert ex and ex["reason"] == "single mechanical change despite the file count", ex
assert ex["author"] == "tester", ex
assert "exception" in r["route_check"], r["route_check"].keys()
assert json.load(open(f"{td}/state.json"))["stage"] != "ROUTE_STOP"
PYEOF

# 3b. (stated-authorship 2.3) an exception authored by an agent is
#     recorded verbatim, so it cannot read as a person's
$PY "$REPORT" exception --task-dir "$T/task14" \
  --reason "single mechanical change despite the file count" \
  --author "rs1 fixture agent (no person asked)" >/dev/null
$PY - "$T/task14" <<'PYEOF'
import json, sys
td = sys.argv[1]
a = json.load(open(f"{td}/gates/gate-route.answer.json"))
assert a["author"] == "rs1 fixture agent (no person asked)", a
PYEOF

# 4. (2.8) a 2-file change recorded inline passes silently
REPO2="$T/repo2"
git -C "$T" init -q repo2
git -C "$REPO2" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
$PY "$REPORT" init --task-dir "$T/task2" --repo "$REPO2" --route inline \
  --task-id rs2 >/dev/null
for i in 1 2; do printf 'small %s\n' "$i" > "$REPO2/s$i.txt"; done
git -C "$REPO2" add -A && git -C "$REPO2" -c user.name=t -c user.email=t@t commit -qm two
set +e
$PY "$REPORT" deliver --task-dir "$T/task2" --repo "$REPO2" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' \
  > "$T/d2.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: 2-file inline deliver exited $RC"; cat "$T/d2.json"; exit 1; }
$PY - "$T/task2" <<'PYEOF'
import json, sys
td = sys.argv[1]
r = json.load(open(f"{td}/report.json"))
assert r["route_check"]["measured_files"] == 2, r["route_check"]
assert "exception" not in r["route_check"], r["route_check"]
assert "route_exception" not in r, list(r)
import os
assert not os.path.exists(f"{td}/gates/gate-route.request.json"), "a passing check wrote a gate request"
PYEOF

# 5. (2.2) the measurement counts the deliverable, not the bookkeeping:
#    openspec tree + task records excluded, exclusions listed
REPO3="$T/repo3"
git -C "$T" init -q repo3
git -C "$REPO3" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
mkdir -p "$REPO3/openspec/changes/x" "$REPO3/.ai-dlc/tasks/x/evidence"
$PY "$REPORT" init --task-dir "$T/task3" --repo "$REPO3" --route inline \
  --task-id rs3 >/dev/null
printf '## Why\n\nx\n' > "$REPO3/openspec/changes/x/proposal.md"
printf '{"dispatches": {}}\n' > "$REPO3/.ai-dlc/tasks/x/planning.json"
for i in 1 2 3; do printf 'p %s\n' "$i" > "$REPO3/p$i.txt"; done
git -C "$REPO3" add -A && git -C "$REPO3" -c user.name=t -c user.email=t@t commit -qm mix
set +e
$PY "$REPORT" deliver --task-dir "$T/task3" --repo "$REPO3" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' \
  > "$T/d3.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: 3-product-file deliver exited $RC"; cat "$T/d3.json"; exit 1; }
$PY - "$T/task3" <<'PYEOF'
import json, sys
r = json.load(open(f"{sys.argv[1]}/report.json"))
m = r["route_check"]
assert m["measured_files"] == 3, m
assert m["excluded_count"] == 2, m
assert "openspec/**" in m["excluded_patterns"] and ".ai-dlc/**" in m["excluded_patterns"], m
PYEOF

# 6. (2.6) a configuration carrying no threshold stops rather than
#    assuming one — the tool tree is copied with the line removed, so
#    CONFIG_PATH (__file__-relative) reads the stripped copy
TOOL="$T/tool-nothresh"; mkdir -p "$TOOL/bin" "$TOOL/config"
cp "$ROOT/bin/report.py" "$TOOL/bin/"
grep -v 'planning_threshold_files' "$ROOT/config/collapsed.config.yaml" \
  > "$TOOL/config/collapsed.config.yaml"
$PY "$TOOL/bin/report.py" init --task-dir "$T/task6" --repo "$REPO" \
  --route inline --task-id rs6 >/dev/null
set +e
$PY "$TOOL/bin/report.py" deliver --task-dir "$T/task6" --repo "$REPO" --no-design \
  --no-design-by tester --no-design-why 'gate probe' \
  --outcome completed > "$T/d6.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 17 ]] || { echo "FAIL: absent threshold exited $RC, want 17"; cat "$T/d6.json"; exit 1; }
grep -q 'no route threshold is configured' "$T/d6.json"
grep -q '"threshold": null' "$T/d6.json"

# 7. the same 14 files on the planned route pass the check
set +e
$PY "$REPORT" deliver --task-dir "$T/task14p" --repo "$REPO" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' \
  > "$T/d14p.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: planned-route deliver exited $RC"; cat "$T/d14p.json"; exit 1; }
grep -q '"route": "planned"' "$T/d14p.json"
grep -q '"measured_files": 14' "$T/d14p.json"
if grep -q 'ROUTE_STOP' "$T/d14p.json"; then
  echo "FAIL: a planned route over 14 files stopped"; cat "$T/d14p.json"; exit 1
fi

# 8. (2.1) the skill states the same number the check reads
grep -q 'planning_threshold_files' "$ROOT/supervisor/skills/claude/ai-dlc/SKILL.md"
grep -q '\*\*4\*\*' "$ROOT/supervisor/skills/claude/ai-dlc/SKILL.md" \
  || { echo "FAIL: the skill does not state the number 4"; exit 1; }
CFG_N=$(grep -oE 'planning_threshold_files: *[0-9]+' "$ROOT/config/collapsed.config.yaml" | grep -oE '[0-9]+')
[[ "$CFG_N" -eq 4 ]] || { echo "FAIL: config threshold is $CFG_N, want 4"; exit 1; }

echo "RS1 ROUTE CHECK: pass (14-file inline stops exit 17 naming count/threshold/route with both options; reasonless exception refused; a recorded exception with its author travels into the report; 2 files pass silently; openspec and task records excluded with patterns listed; absent threshold stops rather than assumes; planned over the same 14 files passes; skill and config state the same number)"
