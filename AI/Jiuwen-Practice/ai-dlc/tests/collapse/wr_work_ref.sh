#!/usr/bin/env bash
# wr_work_ref (Y1-Y12): the work-ref resolver and its callers. The country-b
# defect was a branch-name mismatch (task/<task-id> vs task/<change>) that
# silently bypassed every measurement. These gates prove the fix.
#
# S1 gates: Y3 (compliant branch regression), Y5 (recorded branch wins),
#           Y7 (plan.py and report.py agree field-by-field)
# S2 gates: Y1 (mismatch detected), Y2 (planned 0 files hard stop),
#           Y4 (inline 0 files no new block)
# S3 gates: Y6 (design_unmeasured), Y8 (--no-design records)
# S4 gates: Y9 (worktree visible), Y10 (repo mismatch rejected)
# S5 gates: Y11 (foreign service stop = boundary), Y12 (surface hand-edit留痕)
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
REPORT="$ROOT/bin/report.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
"$PY" - "$T" <<'PYEOF'
import sys
open(sys.argv[1] + "/verdict.key", "wb").write(b"\x11" * 32)
PYEOF

# helper: seed a repo with an initial commit on main
seed_repo() {
  local r="$1"
  git -C "$T" init -q "$(basename "$r")"
  git -C "$r" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
}

# ── Y3: compliant branch (task/<change>) — regression ─────────────────
# A planned route with the convention branch name behaves exactly like
# dm_measure_work.sh P1: the task branch is measured, not HEAD.
R3="$T/r-y3"; CHANGE_Y3=y3-ch; TASK3="$R3/.ai-dlc/tasks/y3-m1"
seed_repo "$R3"
"$PY" "$REPORT" init --task-dir "$TASK3" --repo "$R3" \
    --route planned --task-id y3-m1 --change "$CHANGE_Y3" > /dev/null
# init on planned route records branch=task/y3-ch and echoes work_on
"$PY" - "$TASK3" <<'PYEOF'
import json, sys
s = json.load(open(sys.argv[1] + "/state.json"))
assert s.get("branch") == "task/y3-ch", s.get("branch")
assert "repo" in s and "task_dir" in s, s
print("ok Y3a: init recorded branch + repo + task_dir in state.json")
PYEOF
# create the task branch and put work on it
git -C "$R3" branch "task/$CHANGE_Y3"
git -C "$R3" checkout -q "task/$CHANGE_Y3"
printf '<!doctype html><html><body>work</body></html>\n' > "$R3/index.html"
git -C "$R3" add index.html
git -C "$R3" -c user.name=t -c user.email=t commit -q -m page
git -C "$R3" checkout -q main 2>/dev/null || git -C "$R3" checkout -q master 2>/dev/null || true
# deliver measures the task branch, not HEAD
"$PY" "$REPORT" deliver --task-dir "$TASK3" --repo "$R3" \
    --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/y3.json" 2>&1
grep -q '"ref_kind": "task_branch"' "$T/y3.json" \
  || { echo "FAIL Y3: did not measure task branch"; cat "$T/y3.json"; exit 1; }
grep -q '"measured_ref": "refs/heads/task/y3-ch"' "$T/y3.json" \
  || { echo "FAIL Y3: wrong measured_ref"; cat "$T/y3.json"; exit 1; }
grep -q '"landed_files": 1' "$T/y3.json" \
  || { echo "FAIL Y3: wrong landed_files"; cat "$T/y3.json"; exit 1; }
echo "ok Y3: compliant branch — task branch measured, 1 file landed"

# ── Y5: recorded branch wins over convention ──────────────────────────
# state["branch"] is explicitly set to something other than task/<change>;
# resolve_work_ref must use the recorded value, resolved_by == "recorded",
# and no mismatch is reported.
R5="$T/r-y5"; CHANGE_Y5=y5-ch; TASK5="$R5/.ai-dlc/tasks/y5-m1"
seed_repo "$R5"
"$PY" "$REPORT" init --task-dir "$TASK5" --repo "$R5" \
    --route planned --task-id y5-m1 --change "$CHANGE_Y5" > /dev/null
# override the branch name in state.json to a custom name
CUSTOM_BR="task/y5-custom"
"$PY" - "$TASK5" <<'PYEOF'
import json, sys
p = sys.argv[1] + "/state.json"
s = json.load(open(p))
s["branch"] = "task/y5-custom"
json.dump(s, open(p, "w"), indent=2)
PYEOF
# create the custom branch with work
git -C "$R5" branch "$CUSTOM_BR"
git -C "$R5" checkout -q "$CUSTOM_BR"
printf '<!doctype html><html><body>custom</body></html>\n' > "$R5/index.html"
git -C "$R5" add index.html
git -C "$R5" -c user.name=t -c user.email=t commit -q -m custom
git -C "$R5" checkout -q main 2>/dev/null || git -C "$R5" checkout -q master 2>/dev/null || true
"$PY" "$REPORT" deliver --task-dir "$TASK5" --repo "$R5" \
    --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/y5.json" 2>&1
grep -q '"resolved_by": "recorded"' "$T/y5.json" \
  || { echo "FAIL Y5: not resolved by recorded branch"; cat "$T/y5.json"; exit 1; }
grep -q '"refs/heads/task/y5-custom"' "$T/y5.json" \
  || { echo "FAIL Y5: did not measure custom branch"; cat "$T/y5.json"; exit 1; }
# no mismatch when the recorded branch exists
"$PY" - "$T/y5.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
wr = r.get("work_ref", {})
assert wr.get("mismatch") is None, wr.get("mismatch")
print("ok Y5: recorded branch wins, no mismatch")
PYEOF

# ── Y7: plan.py and report.py resolve_work_ref agree ──────────────────
# Z5's execution device: both copies must produce identical results on
# the same repo+state. Tested by importing both and calling directly.
R7="$T/r-y7"; CHANGE_Y7=y7-ch; TASK7="$R7/.ai-dlc/tasks/y7-m1"
seed_repo "$R7"
"$PY" "$REPORT" init --task-dir "$TASK7" --repo "$R7" \
    --route planned --task-id y7-m1 --change "$CHANGE_Y7" > /dev/null
# create a task branch with a different name (the country-b shape)
git -C "$R7" branch "task/y7-m1"  # named after task-id, not change
git -C "$R7" checkout -q "task/y7-m1"
printf '<!doctype html><html><body>country-b</body></html>\n' > "$R7/index.html"
git -C "$R7" add index.html
git -C "$R7" -c user.name=t -c user.email=t commit -q -m work
git -C "$R7" checkout -q main 2>/dev/null || git -C "$R7" checkout -q master 2>/dev/null || true
"$PY" - "$ROOT/bin" "$R7" "$TASK7" <<'PYEOF'
import json, sys
from pathlib import Path
bin_dir = sys.argv[1]
repo = Path(sys.argv[2])
task_dir = Path(sys.argv[3])
state = json.load(open(task_dir / "state.json"))
# import both modules
sys.path.insert(0, bin_dir)
import report
import plan
r_report = report.resolve_work_ref(repo, state)
r_plan = plan.resolve_work_ref(repo, state)
# field-by-field equality
assert r_report == r_plan, (
    "MISMATCH between report.py and plan.py resolve_work_ref:\n"
    f"report: {json.dumps(r_report, indent=2)}\n"
    f"plan:   {json.dumps(r_plan, indent=2)}")
# both should detect the country-b shape: HEAD fallback with mismatch
assert r_report["kind"] == "head", r_report
assert r_report["mismatch"] is not None, r_report
assert "task/y7-m1" in r_report["mismatch"]["found"], r_report["mismatch"]
print("ok Y7: plan.py and report.py agree field-by-field (Z5)")
PYEOF

# ── Y1: mismatch detected — branch task/<task-id> not task/<change> ───
# A planned route where the convention branch task/<change> does not exist
# but a branch named task/<task-id> does and carries a web file. The work
# falls back to HEAD (0 files on HEAD), so the planned 0-files hard stop
# fires. The block output must NOT contain design_not_applicable (design
# validation never runs on a blocked deliver), and route_check.work_ref
# .mismatch must be non-null naming the actual branch.
R1="$T/r-y1"; CHANGE_Y1=y1-ch; TASK1="$R1/.ai-dlc/tasks/y1-m1"
seed_repo "$R1"
"$PY" "$REPORT" init --task-dir "$TASK1" --repo "$R1" \
    --route planned --task-id y1-m1 --change "$CHANGE_Y1" > /dev/null
# create a branch named after task-id, not change (the country-b shape)
git -C "$R1" branch "task/y1-m1"
git -C "$R1" checkout -q "task/y1-m1"
printf '<!doctype html><html><body>y1 work</body></html>\n' > "$R1/index.html"
git -C "$R1" add index.html
git -C "$R1" -c user.name=t -c user.email=t commit -q -m work
git -C "$R1" checkout -q main 2>/dev/null || git -C "$R1" checkout -q master 2>/dev/null || true
set +e
"$PY" "$REPORT" deliver --task-dir "$TASK1" --repo "$R1" \
    --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/y1.json" 2>&1
RC_Y1=$?
set -e
# the deliver must not say design_not_applicable — design validation never runs
if grep -q 'design_not_applicable' "$T/y1.json"; then
  echo "FAIL Y1: design_not_applicable in block output"; cat "$T/y1.json"; exit 1
fi
# work_ref.mismatch must be non-null and name the actual branch
"$PY" - "$T/y1.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
wr = r.get("route_check", {}).get("work_ref", {})
if not wr:
    wr = r.get("work_ref", {})
m = wr.get("mismatch")
assert m is not None, "work_ref.mismatch is null"
assert "task/y1-m1" in str(m.get("found", "")), m
print("ok Y1: mismatch detected, branch task/y1-m1 named, no design_not_applicable")
PYEOF

# ── Y2: planned route, 0 files — route_check blocks (exit 17) ─────────
# A planned route where the measured branch has no files relative to base.
# route_check must hard-stop: exit 17, gate-route.request.json written,
# state stage == ROUTE_STOP.
R2="$T/r-y2"; CHANGE_Y2=y2-ch; TASK2="$R2/.ai-dlc/tasks/y2-m1"
seed_repo "$R2"
"$PY" "$REPORT" init --task-dir "$TASK2" --repo "$R2" \
    --route planned --task-id y2-m1 --change "$CHANGE_Y2" > /dev/null
# create the convention branch but with NO files (empty branch at base)
git -C "$R2" branch "task/$CHANGE_Y2"
git -C "$R2" checkout -q "task/$CHANGE_Y2"
git -C "$R2" checkout -q main 2>/dev/null || git -C "$R2" checkout -q master 2>/dev/null || true
set +e
"$PY" "$REPORT" deliver --task-dir "$TASK2" --repo "$R2" \
    --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/y2.json" 2>&1
RC_Y2=$?
set -e
[[ "$RC_Y2" -eq 17 ]] || { echo "FAIL Y2: planned 0-files deliver exited $RC_Y2, want 17"; cat "$T/y2.json"; exit 1; }
"$PY" - "$TASK2" <<'PYEOF'
import json, sys, os
td = sys.argv[1]
st = json.load(open(f"{td}/state.json"))
assert st["stage"] == "ROUTE_STOP", f"stage={st['stage']}, want ROUTE_STOP"
assert os.path.exists(f"{td}/gates/gate-route.request.json"), "gate-route.request.json not written"
g = json.load(open(f"{td}/gates/gate-route.request.json"))
assert g["measured_files"] == 0, g
print("ok Y2: planned 0-files hard stop — exit 17, ROUTE_STOP, gate request written")
PYEOF

# ── Y4: inline route, 0 files — NO new block (regression) ─────────────
# An inline route with 0 files must NOT trigger the planned-route hard
# stop. Exit code 0, not 17.
R4="$T/r-y4"; TASK4="$R4/.ai-dlc/tasks/y4-m1"
seed_repo "$R4"
"$PY" "$REPORT" init --task-dir "$TASK4" --repo "$R4" \
    --route inline --task-id y4-m1 > /dev/null
set +e
"$PY" "$REPORT" deliver --task-dir "$TASK4" --repo "$R4" \
    --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/y4.json" 2>&1
RC_Y4=$?
set -e
[[ "$RC_Y4" -eq 0 ]] || { echo "FAIL Y4: inline 0-files deliver exited $RC_Y4, want 0"; cat "$T/y4.json"; exit 1; }
if grep -q 'ROUTE_STOP' "$T/y4.json"; then
  echo "FAIL Y4: inline 0-files triggered ROUTE_STOP"; cat "$T/y4.json"; exit 1
fi
echo "ok Y4: inline 0-files — no new block, exit 0 (regression)"


# ── Y6: inline route, empty surface (0 files) → design_unmeasured ─────
# An inline route where HEAD advanced but 0 product files landed (all
# changes were in excluded paths): the measured surface is empty, so
# design_state must be design_unmeasured — NOT design_not_applicable.
# Uses inline route to avoid W4's planned-0-files hard stop.
R6="$T/r-y6"; CHANGE_Y6=y6-ch; TASK6="$R6/.ai-dlc/tasks/y6-m1"
seed_repo "$R6"
"$PY" "$REPORT" init --task-dir "$TASK6" --repo "$R6" \
    --route inline --task-id y6-m1 --change "$CHANGE_Y6" > /dev/null
# commit only an excluded file (.ai-dlc/) so product files = 0 but head advances
mkdir -p "$R6/.ai-dlc/tasks"
printf 'x\n' > "$R6/.ai-dlc/tasks/dummy"
git -C "$R6" add .ai-dlc/tasks/dummy
git -C "$R6" -c user.name=t -c user.email=t commit -q -m bookkeeping
"$PY" "$REPORT" deliver --task-dir "$TASK6" --repo "$R6" \
    --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/y6.json" 2>&1
grep -q '"design_unmeasured"' "$T/y6.json" \
  || { echo "FAIL Y6: expected design_unmeasured, got:"; cat "$T/y6.json"; exit 1; }
if grep -q '"design_not_applicable"' "$T/y6.json"; then
  echo "FAIL Y6: design_not_applicable returned instead of design_unmeasured"; exit 1; fi
echo "ok Y6: empty surface → design_unmeasured (not design_not_applicable)"

# ── Y8: --no-design records design_decision in planning.json ───────────
# deliver with --no-design --no-design-by tester --no-design-why 'gate probe'
# must write design_decision to planning.json with skip=true, decided_by=tester.
# The design_state in the report must be design_declined.
R8="$T/r-y8"; CHANGE_Y8=y8-ch; TASK8="$R8/.ai-dlc/tasks/y8-m1"
seed_repo "$R8"
"$PY" "$REPORT" init --task-dir "$TASK8" --repo "$R8" \
    --route planned --task-id y8-m1 --change "$CHANGE_Y8" > /dev/null
# create the task branch with a web file so the surface is applicable
git -C "$R8" branch "task/$CHANGE_Y8"
git -C "$R8" checkout -q "task/$CHANGE_Y8"
printf '<!doctype html><html><body>y8</body></html>\n' > "$R8/page.html"
git -C "$R8" add page.html
git -C "$R8" -c user.name=t -c user.email=t@t commit -q -m page
git -C "$R8" checkout -q main 2>/dev/null || git -C "$R8" checkout -q master 2>/dev/null || true
"$PY" "$REPORT" deliver --task-dir "$TASK8" --repo "$R8" \
    --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/y8.json" 2>&1
# assert planning.json has design_decision.skip == true, decided_by == tester
"$PY" - "$TASK8" <<'PYEOF'
import json, sys
pl = json.load(open(sys.argv[1] + "/planning.json"))
dd = pl.get("design_decision")
assert dd is not None, "planning.json has no design_decision"
assert dd.get("skip") is True, f"design_decision.skip is {dd.get('skip')}"
assert dd.get("decided_by") == "tester", f"decided_by is {dd.get('decided_by')}"
print("ok Y8a: planning.json recorded design_decision (skip=true, decided_by=tester)")
PYEOF
# assert design_state == design_declined
grep -q '"design_declined"' "$T/y8.json" \
  || { echo "FAIL Y8: expected design_declined, got:"; cat "$T/y8.json"; exit 1; }
echo "ok Y8: --no-design records design_decision → design_declined"


# ── Y11: foreign service stop detected by boundary_scan ───────────────
# Frames contain 'systemctl stop client-x-ai-launch.service'. The boundary
# scan must report foreign_service_stop with the offending command.
R11="$T/r-y11"; CHANGE_Y11=y11-ch; TASK11="$R11/.ai-dlc/tasks/y11-m1"
seed_repo "$R11"
mkdir -p "$TASK11"
# build a frame file with a shell command that stops a foreign service
"$PY" - "$T/y11-frames.jsonl" <<'PYEOF'
import json, sys
frame = {
    "type": "event",
    "event": "chat.tool_call",
    "payload": {
        "tool_name": "bash",
        "arguments": json.dumps({"command": "systemctl stop client-x-ai-launch.service"})
    }
}
open(sys.argv[1], "w").write(json.dumps(frame) + "\n")
PYEOF
# call boundary_scan directly via python import
"$PY" - "$ROOT/bin" "$R11" "$CHANGE_Y11" "$T/y11-frames.jsonl" <<'PYEOF'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import plan
repo = Path(sys.argv[2])
change = sys.argv[3]
frames = Path(sys.argv[4]).read_text().splitlines()
scan = plan.boundary_scan(repo, change, frames=frames)
assert "foreign_service_stop" in scan, f"missing foreign_service_stop: {json.dumps(scan)}"
assert len(scan["foreign_service_stop"]) >= 1, scan
cmd = scan["foreign_service_stop"][0]["command"]
assert "systemctl stop" in cmd, cmd
assert "client-x-ai-launch" in cmd, cmd
print("ok Y11: boundary_scan reports foreign_service_stop")
PYEOF

# ── Y12: surface refusal留痕, then close succeeds with repair mark ────
# Alter the plane surface, run close → G4/G5 refusal writes
# surface-refusal.json. Fix the surface, run close again → succeeds and
# the output carries surface_repaired_by_hand: true.
. "$ROOT/tests/collapse/lib_plane.sh"
R12="$T/r-y12"; CHANGE_Y12=y12-repair; TASK12="$R12/.ai-dlc/tasks/y12-planning"
git -C "$T" init -q r-y12
git -C "$R12" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
BASE12=$(git -C "$R12" symbolic-ref --short HEAD)
(cd "$R12" && openspec init --tools none --language en) >/dev/null 2>&1
# create a valid change in the repo's openspec tree
C12="$R12/openspec/changes/$CHANGE_Y12"
mkdir -p "$C12/specs/cap"
printf '## Why\n\n%s\n\n## What Changes\n\n- One requirement.\n' "$CHANGE_Y12" > "$C12/proposal.md"
printf '## ADDED Requirements\n\n### Requirement: %s\n\nThe system SHALL %s.\n\n#### Scenario: It runs\n\n- **WHEN** it runs\n- **THEN** it %s\n' "$CHANGE_Y12" "$CHANGE_Y12" "$CHANGE_Y12" > "$C12/specs/cap/spec.md"
# task record + merge-gate approval
mkdir -p "$TASK12/gates"
"$PY" - "$TASK12" <<'PYEOF'
import json, sys
td = sys.argv[1]
json.dump({"task_id": "y12-planning", "route": "planned",
           "change_id": "y12-repair", "branch": "task/y12-repair",
           "stage": "Working", "human_state": "Checking"},
          open(td + "/state.json", "w"))
json.dump({"gate_id": "gate-merge", "decision": "approve",
           "approver": "tester", "rationale": "read the diff",
           "ts": "2026-09-01T00:00:00Z"},
          open(td + "/gates/gate-merge.answer.json", "w"))
PYEOF
# migrate the repo into the plane
plane_migrate "$R12"
PROOT12="$(plane_of "$R12")"
# reachability fixtures (same shape as l2_close_tail.sh)
mkdir -p "$T/probe12$T"
ln -s "$R12" "$T/probe12$T/r-y12"
export AI_DLC_GATEWAY_ROOT="$T/probe12"
cat > "$T/gw12.service" <<EOF
[Service]
Environment=JIUWENSWARM_DATA_DIR=$T/data12
PrivateTmp=false
EOF
export AI_DLC_GW_UNIT="$T/gw12.service"
# stub archive client (same shape as l2_close_tail.sh)
cat > "$T/stub-y12" <<'EOF'
#!/usr/bin/env python3
import json, os, subprocess, sys
prompt = sys.argv[2] if len(sys.argv) > 2 else ""
cmds = [l[2:] for l in prompt.splitlines() if l.startswith("- ")]
def frame(ev, payload):
    print(json.dumps({"type": "event", "event": ev,
                      "payload": {"event_type": ev, **payload}}))
for i, cmd in enumerate(cmds):
    cid = f"call_{i}"
    args = json.dumps({"command": cmd})
    frame("chat.tool_call", {"tool_call": {"name": "bash",
                                           "arguments": args,
                                           "tool_call_id": cid}})
    p = subprocess.run(["bash", "-c", cmd], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True)
    content = (p.stdout or "") + (p.stderr or "")
    if p.returncode == 0:
        result = ("success=True data=" + str({"content": content})
                  + " error=None")
    else:
        body = f"Exit code {p.returncode}\n" + content
        result = ("success=False data=" + str({"content": body})
                  + " error=" + repr(body))
    frame("chat.tool_result", {"result": result, "tool_name": "bash",
                               "tool_call_id": cid})
frame("chat.final", {"content": "DONE"})
EOF
chmod +x "$T/stub-y12"
export AI_DLC_CLIENT="$T/stub-y12"
# create a task branch with work
git -C "$R12" checkout -q -b "task/$CHANGE_Y12"
printf 'y12\n' > "$R12/y12.txt"
git -C "$R12" add y12.txt
git -C "$R12" -c user.name=t -c user.email=t commit -qm work
git -C "$R12" checkout -q "$BASE12"
# 1. alter the surface → close refuses and writes surface-refusal.json
chmod 0755 "$PROOT12/openspec"
set +e
"$PY" "$PLAN" close --change "$CHANGE_Y12" --repo "$R12" --task-dir "$TASK12" > "$T/y12-refuse.json" 2>&1
RC12A=$?
set -e
chmod 0750 "$PROOT12/openspec"
[[ "$RC12A" -eq 12 ]] || { echo "FAIL Y12a: altered surface exited $RC12A, want 12"; cat "$T/y12-refuse.json"; exit 1; }
[[ -f "$TASK12/surface-refusal.json" ]] \
  || { echo "FAIL Y12a: surface-refusal.json not written"; cat "$T/y12-refuse.json"; exit 1; }
# 2. fix the surface → close succeeds with surface_repaired_by_hand: true
set +e
"$PY" "$PLAN" close --change "$CHANGE_Y12" --repo "$R12" --task-dir "$TASK12" > "$T/y12-ok.json" 2>&1
RC12B=$?
set -e
[[ "$RC12B" -eq 0 ]] || { echo "FAIL Y12b: close after repair exited $RC12B"; cat "$T/y12-ok.json"; exit 1; }
grep -q '"surface_repaired_by_hand": true' "$T/y12-ok.json" \
  || { echo "FAIL Y12b: surface_repaired_by_hand not in output"; cat "$T/y12-ok.json"; exit 1; }
echo "ok Y12: surface refusal留痕, close after repair marks surface_repaired_by_hand"


# ── Y9: worktree uncommitted files visible to surface measurement ─────
# Work in a linked worktree on the task branch; the uncommitted file
# must appear in change_surface's measurement (W8).
R9="$T/r-y9"; CHANGE_Y9=y9-ch; TASK9="$R9/.ai-dlc/tasks/y9-m1"
seed_repo "$R9"
"$PY" "$REPORT" init --task-dir "$TASK9" --repo "$R9" \
    --route planned --task-id y9-m1 --change "$CHANGE_Y9" > /dev/null
git -C "$R9" branch "task/$CHANGE_Y9"
# create a worktree on the task branch
WT9="$T/wt-y9"
git -C "$R9" worktree add "$WT9" "task/$CHANGE_Y9" 2>/dev/null
# put a committed file on the branch
printf '<!doctype html><html><body>committed</body></html>\n' > "$WT9/index.html"
git -C "$WT9" add index.html
git -C "$WT9" -c user.name=t -c user.email=t commit -q -m page
# put an UNCOMMITTED file in the worktree
printf '<!doctype html><html><body>uncommitted</body></html>\n' > "$WT9/about.html"
# change_surface should see both files
"$PY" - "$ROOT/bin" "$R9" "$TASK9" <<'PYEOF'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import plan
files, meta = plan.change_surface(Path(sys.argv[2]), Path(sys.argv[3]))
assert "index.html" in files, f"committed file missing: {files}"
assert "about.html" in files, f"uncommitted worktree file missing: {files}"
assert meta.get("worktree_paths"), f"no worktree_paths: {meta}"
assert "about.html" in meta["worktree_paths"], meta
print("ok Y9: worktree uncommitted files visible to surface measurement")
PYEOF

# ── Y10: deliver --repo mismatch rejected ─────────────────────────────
# state.json records repo at init; deliver with a different --repo must
# be rejected with both paths printed (W7).
R10="$T/r-y10"; CHANGE_Y10=y10-ch; TASK10="$R10/.ai-dlc/tasks/y10-m1"
seed_repo "$R10"
"$PY" "$REPORT" init --task-dir "$TASK10" --repo "$R10" \
    --route inline --task-id y10-m1 --change "$CHANGE_Y10" > /dev/null
# create a different repo
R10B="$T/r-y10b"
seed_repo "$R10B"
set +e
"$PY" "$REPORT" deliver --task-dir "$TASK10" --repo "$R10B" \
    --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/y10.json" 2>&1
RC10=$?
set -e
[[ "$RC10" -ne 0 ]] || { echo "FAIL Y10: deliver accepted wrong repo"; cat "$T/y10.json"; exit 1; }
grep -q '"refused"' "$T/y10.json" \
  || { echo "FAIL Y10: no refused marker"; cat "$T/y10.json"; exit 1; }
grep -q 'recorded_repo' "$T/y10.json" \
  || { echo "FAIL Y10: recorded_repo not in output"; cat "$T/y10.json"; exit 1; }
grep -q 'actual_repo' "$T/y10.json" \
  || { echo "FAIL Y10: actual_repo not in output"; cat "$T/y10.json"; exit 1; }
echo "ok Y10: deliver --repo mismatch rejected with both paths"

echo "PASS: wr_work_ref (Y1 Y2 Y3 Y4 Y5 Y6 Y7 Y8 Y9 Y10 Y11 Y12)"
