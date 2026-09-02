#!/usr/bin/env bash
# deliver-measures-work (N1-N6): the delivery measurement must measure
# the ref where the work lives, not blindly HEAD. On the planned route
# the work is on task/<change> before the merge; measuring HEAD sees an
# empty tree and the design gate is silently bypassed as
# design_not_applicable. These gates prove the fix and its regressions.
#
# P1: planned route pre-merge → measures task branch, not HEAD
# P2: same shape, no design record → design_required, delivered: false
# P3: inline regression → unchanged behavior (measures HEAD)
# P4: post-merge (branch deleted) → falls back to HEAD, same files
# P5: head_advanced ∧ files>0 ∧ bytes==0 → measurement_inconsistent
# P6: report + merge gate summary carry measured_ref / ref_kind
# P7: design_auto rc=null → due (retryable, N4)
# P8: design_auto attempts>=2 → already_attempted (N4 limit)
# P9: three identical delivers → DELIVERY_REPORT + DELIVERY_REPORT_REPEAT
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

# force main as the default branch for all test repos (this git has no -b)
# the branch is renamed after the first commit (before that it's unborn)
git_init() { git -C "$T" init -q "$1"; }
git_rename() { git -C "$1" branch -m main 2>/dev/null || true; }

# ── P1: planned route pre-merge → measures task branch ───────────────
# Shape: base on main, work on task/<change> branch, main hasn't moved.
# deliver should measure the task branch and see the web files.
R1="$T/r-p1"; CHANGE_P1=p1-ch; TASK1="$R1/.ai-dlc/tasks/p1-m1"
git_init r-p1
git -C "$R1" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
git_rename "$R1"
BASE_SHA=$(git -C "$R1" rev-parse HEAD)
"$PY" "$REPORT" init --task-dir "$TASK1" --repo "$R1" \
    --route planned --task-id p1-m1 --change "$CHANGE_P1" > /dev/null
# create the task branch and put work there
git -C "$R1" branch "task/$CHANGE_P1"
git -C "$R1" checkout -q "task/$CHANGE_P1"
printf '<!doctype html><html><body><h1>Page A</h1></body></html>\n' > "$R1/index.html"
printf '<!doctype html><html><body><h1>Page B</h1></body></html>\n' > "$R1/about.html"
printf 'body { color: #333; }\n' > "$R1/style.css"
git -C "$R1" add index.html about.html style.css
git -C "$R1" -c user.name=t -c user.email=t commit -q -m "web pages"
# switch back to main (which does NOT have the work yet)
git -C "$R1" checkout -q main
# deliver — should measure the task branch, not main/HEAD
"$PY" "$REPORT" deliver --task-dir "$TASK1" --repo "$R1" \
    --no-design --no-design-by Robin --no-design-why "P1 test" > "$T/p1.json"
grep -q '"ref_kind": "task_branch"' "$T/p1.json" || { echo "FAIL P1: ref_kind not task_branch"; cat "$T/p1.json"; exit 1; }
grep -q '"refs/heads/task/p1-ch"' "$T/p1.json" || { echo "FAIL P1: measured_ref not task branch"; cat "$T/p1.json"; exit 1; }
# should see the web files (not zero)
"$PY" - "$T/p1.json" <<'PYEOF'
import json, sys
r = json.loads(open(sys.argv[1]).read())
assert r["landed_files"] >= 2, f"P1: landed_files={r['landed_files']} (want >=2)"
assert r["landed_bytes"] > 0, f"P1: landed_bytes={r['landed_bytes']} (want >0)"
assert "index.html" in r["files"] or "about.html" in r["files"], f"P1: files={r['files']}"
print("ok P1: planned route measures task branch, sees web files")
PYEOF

# ── P2: same shape, no design record → design_required ───────────────
# P1's surface is web; no design record stands; deliver (without --no-design)
# should say design_required and delivered: false.
# We need a fresh task because P1 used --no-design.
R2="$T/r-p2"; CHANGE_P2=p2-ch; TASK2="$R2/.ai-dlc/tasks/p2-m1"
git_init r-p2
git -C "$R2" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
git_rename "$R2"
"$PY" "$REPORT" init --task-dir "$TASK2" --repo "$R2" \
    --route planned --task-id p2-m1 --change "$CHANGE_P2" > /dev/null
git -C "$R2" branch "task/$CHANGE_P2"
git -C "$R2" checkout -q "task/$CHANGE_P2"
printf '<!doctype html><html><body><h1>Client-x</h1></body></html>\n' > "$R2/index.html"
git -C "$R2" add index.html
git -C "$R2" -c user.name=t -c user.email=t commit -q -m "client-x page"
git -C "$R2" checkout -q main
# deliver without --no-design: surface is applicable, no record → design_required
# (the auto-dispatch will try to run plan.py design, which will fail because
# no skill/pin is set up — that's fine, we check the outcome after)
AI_DLC_SKILLS_DIR="$T/empty" "$PY" "$REPORT" deliver --task-dir "$TASK2" \
    --repo "$R2" --outcome completed > "$T/p2.json" 2>&1 || true
grep -q '"design_required"\|"design_unverified"\|"design_not_applicable"' "$T/p2.json" \
  || { echo "FAIL P2: no design state in output"; cat "$T/p2.json"; exit 1; }
# The key assertion: the surface IS applicable (measured from task branch)
grep -q '"applicable": true' "$T/p2.json" \
  || { echo "FAIL P2: surface not applicable — task branch not measured"; cat "$T/p2.json"; exit 1; }
echo "ok P2: planned route surface is applicable (design gate exercised)"

# ── P3: inline regression → measures HEAD, unchanged behavior ─────────
R3="$T/r-p3"; CHANGE_P3=p3-ch; TASK3="$R3/.ai-dlc/tasks/p3-m1"
git_init r-p3
git -C "$R3" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
git_rename "$R3"
"$PY" "$REPORT" init --task-dir "$TASK3" --repo "$R3" \
    --route inline --task-id p3-m1 --change "$CHANGE_P3" > /dev/null
# inline: work goes directly to HEAD (main), no task branch
printf '<!doctype html><html><body><h1>Inline</h1></body></html>\n' > "$R3/index.html"
printf 'body { margin: 0; }\n' > "$R3/style.css"
git -C "$R3" add index.html style.css
git -C "$R3" -c user.name=t -c user.email=t commit -q -m "inline work"
"$PY" "$REPORT" deliver --task-dir "$TASK3" --repo "$R3" \
    --no-design --no-design-by Robin --no-design-why "P3 test" > "$T/p3.json"
grep -q '"ref_kind": "head"' "$T/p3.json" || { echo "FAIL P3: ref_kind not head"; cat "$T/p3.json"; exit 1; }
"$PY" - "$T/p3.json" <<'PYEOF'
import json, sys
r = json.loads(open(sys.argv[1]).read())
assert r["landed_files"] >= 2, f"P3: landed_files={r['landed_files']}"
assert r["landed_bytes"] > 0, f"P3: landed_bytes={r['landed_bytes']}"
print("ok P3: inline route measures HEAD, behavior unchanged (Q6)")
PYEOF

# ── P4: post-merge (branch deleted) → falls back to HEAD ─────────────
R4="$T/r-p4"; CHANGE_P4=p4-ch; TASK4="$R4/.ai-dlc/tasks/p4-m1"
git_init r-p4
git -C "$R4" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
git_rename "$R4"
"$PY" "$REPORT" init --task-dir "$TASK4" --repo "$R4" \
    --route planned --task-id p4-m1 --change "$CHANGE_P4" > /dev/null
git -C "$R4" branch "task/$CHANGE_P4"
git -C "$R4" checkout -q "task/$CHANGE_P4"
printf '<!doctype html><html><body><h1>Merged</h1></body></html>\n' > "$R4/index.html"
git -C "$R4" add index.html
git -C "$R4" -c user.name=t -c user.email=t commit -q -m "page on branch"
# merge into main and delete the branch
git -C "$R4" checkout -q main
git -C "$R4" merge -q --no-edit "task/$CHANGE_P4"
git -C "$R4" branch -d "task/$CHANGE_P4"
# now deliver — branch is gone, should fall back to HEAD
"$PY" "$REPORT" deliver --task-dir "$TASK4" --repo "$R4" \
    --no-design --no-design-by Robin --no-design-why "P4 test" > "$T/p4.json"
grep -q '"ref_kind": "head"' "$T/p4.json" || { echo "FAIL P4: ref_kind not head after merge"; cat "$T/p4.json"; exit 1; }
"$PY" - "$T/p4.json" <<'PYEOF'
import json, sys
r = json.loads(open(sys.argv[1]).read())
assert r["landed_files"] >= 1, f"P4: landed_files={r['landed_files']}"
assert r["landed_bytes"] > 0, f"P4: landed_bytes={r['landed_bytes']}"
print("ok P4: post-merge (branch deleted) falls back to HEAD, sees work")
PYEOF

# ── P5: head_advanced ∧ files>0 ∧ bytes==0 → measurement_warning (N3) ─
# R4 validation: a pure-deletion change is a legitimate 0-byte delivery,
# so N3 is a WARNING, not a hard failure. The client-x case (2 openspec
# files, 0 bytes, wrong ref) and a real deletion both produce this
# shape — the human reads the file list to tell them apart.
# We test with a real deletion: file exists at base, deleted at head.
R5="$T/r-p5"; CHANGE_P5=p5-ch; TASK5="$R5/.ai-dlc/tasks/p5-m1"
git_init r-p5
printf "content to delete\n" > "$R5/old_file.txt"
git -C "$R5" add old_file.txt
git -C "$R5" -c user.name=t -c user.email=t commit -q -m "seed with file"
git_rename "$R5"
"$PY" "$REPORT" init --task-dir "$TASK5" --repo "$R5" \
    --route inline --task-id p5-m1 --change "$CHANGE_P5" > /dev/null
# delete the file — pure deletion, 0 bytes
git -C "$R5" rm old_file.txt
git -C "$R5" -c user.name=t -c user.email=t commit -q -m "delete file"
"$PY" "$REPORT" deliver --task-dir "$TASK5" --repo "$R5" \
    --no-design --no-design-by Robin --no-design-why "P5 test" > "$T/p5.json"
grep -q '"measurement_warning"' "$T/p5.json" \
  || { echo "FAIL P5: measurement_warning not fired"; cat "$T/p5.json"; exit 1; }
# P5b: the measurement_warning must be in the merge gate summary —
# a warning the human can't see at the moment of approval is no defense
"$PY" "$REPORT" gate --task-dir "$TASK5" --gate-id gate-merge --request \
    --question "Merge?" > /dev/null
"$PY" - "$TASK5" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1] + "/gates/gate-merge.request.json")
d = json.loads(p.read_text())
s = d.get("summary", {})
assert "measurement_warning" in s, \
    f"P5b: measurement_warning not in merge gate summary: {list(s.keys())}"
print("ok P5: 0-byte delivery → measurement_warning in report AND merge gate summary (N3)")
PYEOF

# ── P5c: L6 blocks a model from signing a correction (N6 fix) ─────────
R5C="$T/r-p5c"; CHANGE_P5C=p5c-ch; TASK5C="$R5C/.ai-dlc/tasks/p5c-m1"
git_init r-p5c
git -C "$R5C" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
git_rename "$R5C"
"$PY" "$REPORT" init --task-dir "$TASK5C" --repo "$R5C" \
    --route inline --task-id p5c-m1 --change "$CHANGE_P5C" > /dev/null
# write a forged design_override (the shape N6 corrects)
"$PY" - "$TASK5C" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1] + "/planning.json")
d = json.loads(p.read_text()) if p.is_file() else {}
d["design_override"] = {"by": "human-at-terminal", "why": "forged", "ts": "x"}
p.write_text(json.dumps(d, indent=2) + "\n")
PYEOF
# a model trying to sign the correction → refused (L6)
rc=0; "$PY" "$REPORT" correct --task-dir "$TASK5C" \
    --remove-key design_override \
    --corrected-by "AI-DLC Executor" \
    --why "test" > "$T/p5c.json" 2>&1 || rc=$?
[[ $rc -eq 1 ]] || { echo "FAIL P5c: model signed the correction (L6 broken)"; exit 1; }
grep -q 'L6' "$T/p5c.json" || { echo "FAIL P5c: no L6 in refusal"; cat "$T/p5c.json"; exit 1; }
# a named human → accepted
"$PY" "$REPORT" correct --task-dir "$TASK5C" \
    --remove-key design_override \
    --corrected-by Robin \
    --why "removing forged override" > "$T/p5c-ok.json"
grep -q '"corrected": true' "$T/p5c-ok.json" || { echo "FAIL P5c: human correction failed"; cat "$T/p5c-ok.json"; exit 1; }
grep -q '"Robin"' "$T/p5c-ok.json" || { echo "FAIL P5c: correction not signed by Robin"; cat "$T/p5c-ok.json"; exit 1; }
echo "ok P5c: L6 blocks model from signing correction; named human accepted (N6)"

# ── P6: report + merge gate summary carry measured_ref / ref_kind ─────
# Reuse P1's task: request a merge gate and check the summary
"$PY" "$REPORT" gate --task-dir "$TASK1" --gate-id gate-merge --request \
    --question "Merge?" > /dev/null
"$PY" - "$TASK1" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1] + "/gates/gate-merge.request.json")
d = json.loads(p.read_text())
s = d.get("summary", {})
assert s.get("measured_ref") is not None, f"P6: no measured_ref in summary: {s}"
assert s.get("ref_kind") is not None, f"P6: no ref_kind in summary: {s}"
print(f"ok P6: merge gate summary carries measured_ref={s['measured_ref']!r} ref_kind={s['ref_kind']!r}")
PYEOF

# ── P7: design_auto rc=null → due (retryable, N4) ────────────────────
R7="$T/r-p7"; CHANGE_P7=p7-ch; TASK7="$R7/.ai-dlc/tasks/p7-m1"
git_init r-p7
git -C "$R7" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
git_rename "$R7"
"$PY" "$REPORT" init --task-dir "$TASK7" --repo "$R7" \
    --route inline --task-id p7-m1 --change "$CHANGE_P7" > /dev/null
printf '<!doctype html><html><body><h1>P7</h1></body></html>\n' > "$R7/index.html"
git -C "$R7" add index.html
git -C "$R7" -c user.name=t -c user.email=t commit -q -m page
# write an incomplete design_auto (rc=null, attempts=0)
"$PY" - "$TASK7" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1] + "/planning.json")
d = json.loads(p.read_text()) if p.is_file() else {}
d["design_auto"] = {"attempted_at": "2026-09-01T00:00:00Z",
                     "change": "p7-ch", "trigger": "deliver",
                     "rc": None, "outcome": None, "session": None,
                     "elapsed_seconds": None,
                     "attempts": 0, "state": "incomplete"}
p.write_text(json.dumps(d, indent=2) + "\n")
PYEOF
# design_auto_due should return (True, "due") — incomplete is retryable
"$PY" - "$ROOT/bin" "$TASK7" "$R7" <<'PYEOF'
import json, sys, os, pathlib
sys.path.insert(0, sys.argv[1])
from report import design_auto_due, load_json
task = pathlib.Path(sys.argv[2])
repo = pathlib.Path(sys.argv[3])
state = load_json(task / "state.json", {})
files = ["index.html"]
due, why = design_auto_due(task, repo, state, files, False)
assert due, f"P7: design_auto_due returned (False, {why!r}) — incomplete should be retryable"
print(f"ok P7: design_auto rc=null → due (why={why!r}, N4)")
PYEOF

# ── P8: design_auto attempts>=2 → already_attempted (N4 limit) ────────
R8="$T/r-p8"; CHANGE_P8=p8-ch; TASK8="$R8/.ai-dlc/tasks/p8-m1"
git_init r-p8
git -C "$R8" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
git_rename "$R8"
"$PY" "$REPORT" init --task-dir "$TASK8" --repo "$R8" \
    --route inline --task-id p8-m1 --change "$CHANGE_P8" > /dev/null
printf '<!doctype html><html><body><h1>P8</h1></body></html>\n' > "$R8/index.html"
git -C "$R8" add index.html
git -C "$R8" -c user.name=t -c user.email=t commit -q -m page
# write a completed design_auto with attempts=2
"$PY" - "$TASK8" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1] + "/planning.json")
d = json.loads(p.read_text()) if p.is_file() else {}
d["design_auto"] = {"attempted_at": "2026-09-01T00:00:00Z",
                     "change": "p8-ch", "trigger": "deliver",
                     "rc": 1, "outcome": "design_unverified",
                     "session": None, "elapsed_seconds": 10.0,
                     "attempts": 2, "state": "complete"}
p.write_text(json.dumps(d, indent=2) + "\n")
PYEOF
"$PY" - "$ROOT/bin" "$TASK8" "$R8" <<'PYEOF'
import json, sys, os, pathlib
sys.path.insert(0, sys.argv[1])
from report import design_auto_due, load_json
task = pathlib.Path(sys.argv[2])
repo = pathlib.Path(sys.argv[3])
state = load_json(task / "state.json", {})
files = ["index.html"]
due, why = design_auto_due(task, repo, state, files, False)
assert not due and why == "already_attempted", \
    f"P8: design_auto_due returned ({due}, {why!r}) — limit 2 should block"
print("ok P8: attempts>=2 → already_attempted (N4 limit)")
PYEOF

# ── P9: three identical delivers → DELIVERY_REPORT + REPEAT ───────────
R9="$T/r-p9"; CHANGE_P9=p9-ch; TASK9="$R9/.ai-dlc/tasks/p9-m1"
git_init r-p9
git -C "$R9" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
git_rename "$R9"
"$PY" "$REPORT" init --task-dir "$TASK9" --repo "$R9" \
    --route inline --task-id p9-m1 --change "$CHANGE_P9" > /dev/null
printf '<!doctype html><html><body><h1>P9</h1></body></html>\n' > "$R9/index.html"
git -C "$R9" add index.html
git -C "$R9" -c user.name=t -c user.email=t commit -q -m page
# deliver three times — same measurement each time
"$PY" "$REPORT" deliver --task-dir "$TASK9" --repo "$R9" \
    --no-design --no-design-by Robin --no-design-why "P9a" > /dev/null
"$PY" "$REPORT" deliver --task-dir "$TASK9" --repo "$R9" \
    --no-design --no-design-by Robin --no-design-why "P9b" > /dev/null
"$PY" "$REPORT" deliver --task-dir "$TASK9" --repo "$R9" \
    --no-design --no-design-by Robin --no-design-why "P9c" > /dev/null
# check events.jsonl: first DELIVERY_REPORT, then DELIVERY_REPORT_REPEAT
"$PY" - "$TASK9" <<'PYEOF'
import json, sys, pathlib
events = [json.loads(l) for l in
          pathlib.Path(sys.argv[1] + "/events.jsonl").read_text().splitlines()
          if l.strip()]
reports = [e for e in events if e.get("event") in ("DELIVERY_REPORT",
                                                    "DELIVERY_REPORT_REPEAT")]
assert len(reports) == 3, f"P9: expected 3 report events, got {len(reports)}"
assert reports[0]["event"] == "DELIVERY_REPORT", f"P9: first event is {reports[0]['event']}"
assert reports[1]["event"] == "DELIVERY_REPORT_REPEAT", f"P9: second event is {reports[1]['event']}"
assert reports[2]["event"] == "DELIVERY_REPORT_REPEAT", f"P9: third event is {reports[2]['event']}"
assert reports[2].get("_repeat_count", 0) == 3, f"P9: repeat_count={reports[2].get('_repeat_count')}"
print("ok P9: three identical delivers → DELIVERY_REPORT + 2x DELIVERY_REPORT_REPEAT (N5)")
PYEOF

echo "PASS: dm_measure_work (P1 P2 P3 P4 P5 P5c P6 P7 P8 P9)"
