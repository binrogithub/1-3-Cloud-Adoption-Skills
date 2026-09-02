#!/usr/bin/env bash
# design-autodispatch: the scheduling gates, hermetic. Scheduling, not
# gating — the auto-dispatch fires once when the surface is applicable
# and no record stands; its成败 never changes `delivered` (J3); it never
# auto-reruns (J2); --no-design and a recorded skip both suppress it
# and say so (J4/J7); the two playbook copies must agree (A8/N7); a
# crash leaves the attempt on file so the next deliver does not re-run
# (A10). All dispatches use a stub client — no real session opens.
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

# ── fixtures: a registered pointer skill, a pinned fixture tree ──────
export AI_DLC_SKILLS_DIR="$T/skills"
mkdir -p "$AI_DLC_SKILLS_DIR/ui-designer"
printf -- '---\nname: ui-designer\ndescription: pointer to the pinned design tree\n---\npick by frontmatter, read the SKILL.md in full\n' \
  > "$AI_DLC_SKILLS_DIR/ui-designer/SKILL.md"
"$PY" - "$AI_DLC_SKILLS_DIR" <<'PYEOF'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1])
(d / "skills_state.json").write_text(json.dumps(
    {"installed_plugins": [{"name": "ui-designer",
                            "source": "fixture"}]}, indent=2) + "\n")
PYEOF

OD="$T/od"; export AI_DLC_OPENDESIGN_ROOT="$OD"
mkdir -p "$OD/skills/web-creator" "$OD/design-templates/editorial" \
         "$OD/design-systems/warm"
printf 'name: web-creator\ncreate pages\n' > "$OD/skills/web-creator/SKILL.md"
printf 'name: editorial\n' > "$OD/design-templates/editorial/SKILL.md"
printf 'name: warm\ntokens\n' > "$OD/design-systems/warm/SKILL.md"
"$PY" "$PLAN" design-pin --root "$OD" --tag fixture --write > /dev/null

# ── the stub client: good (reads upstream, writes page) or d8 (no read)
STUB="$T/stub-design"
cat > "$STUB" <<'STUBEOF'
#!/usr/bin/env python3
import json, os, pathlib, sys
shape = os.environ.get("STUB_SHAPE", "good")
repo = pathlib.Path(os.environ["STUB_REPO"])
od = pathlib.Path(os.environ["AI_DLC_OPENDESIGN_ROOT"])
marker = pathlib.Path(os.environ.get("STUB_MARKER", "/tmp/stub-ran"))
marker.write_text("invoked\n")
def frame(ev, payload):
    print(json.dumps({"type": "event", "event": ev,
                      "payload": {"event_type": ev, **payload}}), flush=True)
page = ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<title>Cabañas</title></head><body>'
        '<h1>Cabañas del Lago</h1><p>Frente al lago.</p>'
        '</body></html>')
cid = 0
def call(name, args):
    global cid; cid += 1; a = json.dumps(args)
    frame("chat.tool_call", {"tool_call": {"name": name, "arguments": a,
                                           "tool_call_id": f"c{cid}"}})
    frame("chat.tool_update", {"tool_name": name, "tool_call_id": f"c{cid}",
                               "arguments": a, "status": "in_progress"})
    frame("chat.tool_result", {"result": "ok", "tool_name": name,
                               "tool_call_id": f"c{cid}"})
if shape == "good":
    call("read_file", {"path": str(od / "design-systems/warm/SKILL.md")})
# N5 call assertion: the stub emits a skill_tool{ui-designer} frame
call("skill_tool", {"skill_name": "ui-designer"})
call("write_file", {"path": str(repo / "index.html"), "content": page})
(repo / "index.html").write_text(page)
frame("chat.final", {"content": "Done."})
STUBEOF
chmod +x "$STUB"
export AI_DLC_CLIENT="$STUB"

# helper: seed a repo with one web file, return via env vars
seed_web_repo() {
  local r="$1" ch="$2" tid="$3"
  git -C "$T" init -q "$(basename "$r")"
  git -C "$r" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
  "$PY" "$REPORT" init --task-dir "$r/.ai-dlc/tasks/$tid" --repo "$r" \
      --route inline --task-id "$tid" --change "$ch" > /dev/null
  printf '<!doctype html><html><body>old</body></html>\n' > "$r/index.html"
  git -C "$r" add index.html
  git -C "$r" -c user.name=t -c user.email=t commit -q -m page
}

# ── A1: pure-code change → zero dispatch, design_not_applicable ──────
R1="$T/r-a1"; CHANGE_A1=a1-ch
git -C "$T" init -q r-a1
git -C "$R1" -c user.name=t -c user.email=t commit -q --allow-empty -m seed
"$PY" "$REPORT" init --task-dir "$R1/.ai-dlc/tasks/a1-m1" --repo "$R1" \
    --route inline --task-id a1-m1 --change "$CHANGE_A1" > /dev/null
printf 'def f():\n    return 1\n' > "$R1/app.py"
git -C "$R1" add app.py
git -C "$R1" -c user.name=t -c user.email=t commit -q -m code
STUB_MARKER="$T/a1-ran" "$PY" "$REPORT" deliver --task-dir "$R1/.ai-dlc/tasks/a1-m1" \
    --repo "$R1" > "$T/a1.json" 2>&1
grep -q '"design_state": "design_not_applicable"' "$T/a1.json"
grep -q '"design_auto_skipped": "not_applicable"' "$T/a1.json"
[[ ! -e "$T/a1-ran" ]] || { echo "FAIL A1: stub ran for pure-code change"; exit 1; }
echo "ok A1: pure-code change — zero dispatch, not_applicable"

# ── A2: web change, no record → auto-dispatch once, design_applied ───
R2="$T/r-a2"; CHANGE_A2=a2-ch; TASK2="$R2/.ai-dlc/tasks/a2-m1"
seed_web_repo "$R2" "$CHANGE_A2" "a2-m1"
STUB_REPO="$R2" STUB_MARKER="$T/a2-ran" \
  "$PY" "$REPORT" deliver --task-dir "$TASK2" --repo "$R2" > "$T/a2.json" 2>&1
grep -q '"design_state": "design_applied"' "$T/a2.json"
[[ -e "$T/a2-ran" ]] || { echo "FAIL A2: stub did not run"; exit 1; }
# design_auto recorded in planning.json
"$PY" - "$TASK2" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1] + "/planning.json"))
da = d["design_auto"]
assert da["rc"] == 0 and da["outcome"] == "design_applied", da
assert da["trigger"] == "deliver" and da["elapsed_seconds"] is not None, da
print("ok A2: auto-dispatched once, design_applied, design_auto recorded")
PYEOF

# ── A3: same change, second deliver → no re-dispatch ─────────────────
rm -f "$T/a2-ran"
STUB_REPO="$R2" STUB_MARKER="$T/a2-ran2" \
  "$PY" "$REPORT" deliver --task-dir "$TASK2" --repo "$R2" > "$T/a3.json" 2>&1
grep -q '"design_auto_skipped": "already_attempted"' "$T/a3.json"
grep -q '"design_state": "design_applied"' "$T/a3.json"
[[ ! -e "$T/a2-ran2" ]] || { echo "FAIL A3: stub ran on second deliver"; exit 1; }
echo "ok A3: second deliver — no re-dispatch (already_attempted)"

# ── A4: design failure (D8) → design_unverified, design_required gates ─
# M6 (design-required): on an applicable surface, design_unverified now
# gates delivery — delivered: false, outcome: design_required. The
# auto-dispatch still runs (J3: its成败 doesn't change exit code), but
# the design state gates the delivery conjunction.
R4="$T/r-a4"; CHANGE_A4=a4-ch; TASK4="$R4/.ai-dlc/tasks/a4-m1"
seed_web_repo "$R4" "$CHANGE_A4" "a4-m1"
# approve the merge gate first so delivered would be true if design gated
"$PY" "$REPORT" gate --task-dir "$TASK4" --decision approve \
    --approver Robin --rationale "looks good" > /dev/null
# also need a spec verdict for delivered to be true
"$PY" "$ROOT/tests/collapse/records_tool.py" verdict "$CHANGE_A4" --rc 0 > /dev/null
STUB_REPO="$R4" STUB_SHAPE=d8 STUB_MARKER="$T/a4-ran" \
  "$PY" "$REPORT" deliver --task-dir "$TASK4" --repo "$R4" > "$T/a4.json" 2>&1
grep -q '"design_state": "design_unverified"' "$T/a4.json"
# M6: design_unverified on an applicable surface gates delivery
grep -q '"delivered": false' "$T/a4.json"
grep -q '"design_required"' "$T/a4.json"
# exit code must be 0 (not changed by design failure — J3)
# (the command above already checked via set -e)
"$PY" - "$TASK4" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1] + "/planning.json"))
da = d["design_auto"]
assert da["rc"] != 0 and da["outcome"] == "design_unverified", da
print("ok A4: design failure — design_unverified, design_required gates (M6), exit 0")
PYEOF

# ── A5: recorded skip → design_declined, no dispatch ─────────────────
R5="$T/r-a5"; CHANGE_A5=a5-ch; TASK5="$R5/.ai-dlc/tasks/a5-m1"
seed_web_repo "$R5" "$CHANGE_A5" "a5-m1"
"$PY" "$PLAN" decide --design skip --change "$CHANGE_A5" --repo "$R5" \
    --task-dir "$TASK5" --decided-by Robin --reason "backend release" > /dev/null
STUB_REPO="$R5" STUB_MARKER="$T/a5-ran" \
  "$PY" "$REPORT" deliver --task-dir "$TASK5" --repo "$R5" > "$T/a5.json" 2>&1
grep -q '"design_state": "design_declined"' "$T/a5.json"
grep -q '"design_auto_skipped": "declined"' "$T/a5.json"
grep -q 'Robin' "$T/a5.json"
[[ ! -e "$T/a5-ran" ]] || { echo "FAIL A5: stub ran despite skip"; exit 1; }
echo "ok A5: recorded skip — design_declined, no dispatch"

# ── A6: --no-design → skipped with why=disabled ──────────────────────
R6="$T/r-a6"; CHANGE_A6=a6-ch; TASK6="$R6/.ai-dlc/tasks/a6-m1"
seed_web_repo "$R6" "$CHANGE_A6" "a6-m1"
STUB_REPO="$R6" STUB_MARKER="$T/a6-ran" \
  "$PY" "$REPORT" deliver --task-dir "$TASK6" --repo "$R6" --no-design --no-design-by Robin --no-design-why "A6 test" > "$T/a6.json" 2>&1
grep -q '"design_auto_skipped": "disabled"' "$T/a6.json"
[[ ! -e "$T/a6-ran" ]] || { echo "FAIL A6: stub ran with --no-design"; exit 1; }
echo "ok A6: --no-design — skipped, why=disabled, no dispatch"

# ── A8: consistency delegated to doctor (K5, prd-install-targets) ────
# The sha256 comparison between repo and deployed copies is now a
# segment of `install.sh --doctor` (N7 segment ②). This test asserts
# doctor's manifest consistency check passes — if the deployed copy
# differs from what the manifest recorded, doctor fails and names it.
REPO_SKILL="$ROOT/supervisor/skills/claude/ai-dlc/SKILL.md"
DEPLOYED_SKILL="/root/.claude-glm/skills/ai-dlc/SKILL.md"
if [[ -f "$DEPLOYED_SKILL" && -f "$ROOT/.ai-dlc/install-manifest.json" ]]; then
  "$ROOT/install.sh" --doctor > "$T/a8-doctor.out" 2>&1 || true
  if grep -q "manifest: claude-glm/ai-dlc" "$T/a8-doctor.out" \
     && ! grep -q "FAIL.*claude-glm/ai-dlc" "$T/a8-doctor.out"; then
    echo "ok A8: doctor manifest consistency passes for claude-glm/ai-dlc (K5)"
  else
    echo "FAIL A8: doctor reports inconsistency for claude-glm/ai-dlc"; cat "$T/a8-doctor.out"; exit 1
  fi
else
  echo "note A8: no deployed playbook or manifest — skipped"
fi

# ── A10: crash leaves incomplete design_auto → next deliver retries (N4)
# N4 (deliver-measures-work): a half-finished attempt (rc=null) is NOT
# a completed attempt. The retry path must not be permanently locked
# by a crash that left the pre-write record standing. The stub runs
# again; the limit is 2 completed attempts, not 1 incomplete one.
R10="$T/r-a10"; CHANGE_A10=a10-ch; TASK10="$R10/.ai-dlc/tasks/a10-m1"
seed_web_repo "$R10" "$CHANGE_A10" "a10-m1"
# simulate a crash: pre-write design_auto with rc=null (as if killed mid-run)
"$PY" - "$TASK10" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1] + "/planning.json")
d = json.loads(p.read_text()) if p.is_file() else {}
d["design_auto"] = {"attempted_at": "2026-09-01T00:00:00Z",
                     "change": "a10-ch", "trigger": "deliver",
                     "rc": None, "outcome": None, "session": None,
                     "elapsed_seconds": None,
                     "attempts": 0, "state": "incomplete"}
p.write_text(json.dumps(d, indent=2) + "\n")
PYEOF
STUB_REPO="$R10" STUB_MARKER="$T/a10-ran" \
  "$PY" "$REPORT" deliver --task-dir "$TASK10" --repo "$R10" > "$T/a10.json" 2>&1
# N4: the stub SHOULD run — an incomplete attempt is retryable
[[ -e "$T/a10-ran" ]] || { echo "FAIL A10: stub did not re-run after incomplete crash (N4)"; exit 1; }
echo "ok A10: incomplete design_auto (rc=null) is retryable (N4)"

# ── A10b: two completed attempts → already_attempted (N4 limit) ──────
R10B="$T/r-a10b"; CHANGE_A10B=a10b-ch; TASK10B="$R10B/.ai-dlc/tasks/a10b-m1"
seed_web_repo "$R10B" "$CHANGE_A10B" "a10b-m1"
# simulate two completed attempts — the limit is 2
"$PY" - "$TASK10B" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1] + "/planning.json")
d = json.loads(p.read_text()) if p.is_file() else {}
d["design_auto"] = {"attempted_at": "2026-09-01T00:00:00Z",
                     "change": "a10b-ch", "trigger": "deliver",
                     "rc": 1, "outcome": "design_unverified",
                     "session": None, "elapsed_seconds": 10.0,
                     "attempts": 2, "state": "complete"}
p.write_text(json.dumps(d, indent=2) + "\n")
PYEOF
STUB_REPO="$R10B" STUB_MARKER="$T/a10b-ran" \
  "$PY" "$REPORT" deliver --task-dir "$TASK10B" --repo "$R10B" > "$T/a10b.json" 2>&1
grep -q '"design_auto_skipped": "already_attempted"' "$T/a10b.json"
[[ ! -e "$T/a10b-ran" ]] || { echo "FAIL A10b: stub ran after 2 completed attempts"; exit 1; }
echo "ok A10b: two completed attempts → already_attempted (N4 limit)"

# ── A11 (D8 negative): stub does NOT read any upstream SKILL.md ──────
# A3: B2 (skill_tool call assertion) is deleted — a page's quality and
# whether it was produced via a specific tool call are two different
# things.  D8 is rewritten: the record must show a SKILL.md read that
# stands on the tree.  This stub writes a valid page but never reads
# any upstream SKILL.md — D8 fails, no signed record, design_unverified.
STUB_NOSKILL="$T/stub-no-skill"
cat > "$STUB_NOSKILL" <<'STUBEOF'
#!/usr/bin/env python3
import json, os, pathlib, sys
repo = pathlib.Path(os.environ["STUB_REPO"])
od = pathlib.Path(os.environ["AI_DLC_OPENDESIGN_ROOT"])
marker = pathlib.Path(os.environ.get("STUB_MARKER", "/tmp/stub-ran"))
marker.write_text("invoked\n")
def frame(ev, payload):
    print(json.dumps({"type": "event", "event": ev,
                      "payload": {"event_type": ev, **payload}}), flush=True)
page = ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<title>Cabañas</title></head><body>'
        '<h1>Cabañas del Lago</h1><p>Frente al lago.</p>'
        '</body></html>')
cid = 0
def call(name, args):
    global cid; cid += 1; a = json.dumps(args)
    frame("chat.tool_call", {"tool_call": {"name": name, "arguments": a,
                                           "tool_call_id": f"c{cid}"}})
    frame("chat.tool_update", {"tool_name": name, "tool_call_id": f"c{cid}",
                               "arguments": a, "status": "in_progress"})
    frame("chat.tool_result", {"result": "ok", "tool_name": name,
                               "tool_call_id": f"c{cid}"})
# does NOT read any upstream SKILL.md — D8 fails
call("write_file", {"path": str(repo / "index.html"), "content": page})
(repo / "index.html").write_text(page)
frame("chat.final", {"content": "Done."})
STUBEOF
chmod +x "$STUB_NOSKILL"
R11="$T/r-a11"; CHANGE_A11=a11-ch; TASK11="$R11/.ai-dlc/tasks/a11-m1"
seed_web_repo "$R11" "$CHANGE_A11" "a11-m1"
AI_DLC_CLIENT="$STUB_NOSKILL" STUB_REPO="$R11" STUB_MARKER="$T/a11-ran" \
  "$PY" "$REPORT" deliver --task-dir "$TASK11" --repo "$R11" > "$T/a11.json" 2>&1
grep -q '"design_state": "design_unverified"' "$T/a11.json" \
  || { echo "FAIL A11: stub without upstream SKILL.md read produced a signed record"; cat "$T/a11.json"; exit 1; }
echo "ok A11: stub without upstream SKILL.md read → design_unverified (D8 negative)"

# ── N5: the three new extensions are measured as web ─────────────────
"$PY" - "$ROOT/bin" <<'PYEOF'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from report import design_file_classes, DESIGN_WEB_EXTS
d = Path(tempfile.mkdtemp())
for ext in (".less", ".styl", ".sass"):
    assert ext in DESIGN_WEB_EXTS, f"{ext} missing from DESIGN_WEB_EXTS"
    assert design_file_classes(f"style{ext}", d) == ["web"], ext
print("ok N5: .less .styl .sass measured as web")
PYEOF

# ── J6: events.jsonl carries the dispatch/skip events ────────────────
EVENTS="$TASK2/events.jsonl"
grep -q 'DESIGN_AUTO_DISPATCHED' "$EVENTS" || { echo "FAIL J6: no DISPATCHED event"; exit 1; }
grep -q 'DESIGN_AUTO_SKIPPED' "$TASK5/events.jsonl" || { echo "FAIL J6: no SKIPPED event"; exit 1; }
echo "ok J6: events.jsonl carries dispatch and skip events"

echo "PASS: ud_autodispatch_gates (A1 A2 A3 A4 A5 A6 A8 A10 A10b A11 N5 J6)"
