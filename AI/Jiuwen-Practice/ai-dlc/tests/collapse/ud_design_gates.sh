#!/usr/bin/env bash
# uidesigner-opendesign: the design surface gates, hermetic. The three
# stops that fire before any session opens (skill 25 / pin 26 / surface
# 24 — each proved by the stub client never running), the facts
# contract (a session whose frames show no upstream read writes NO
# record however loudly it claims the work — D8), the heredoc strip
# that keeps a page's own markup out of the write facts, deliver's four
# design states (unverified → applied → tampered-back-to-unverified →
# a person's recorded skip outranking the record), and the two standing
# regressions: bin/ spawns no od/open-design process (I1), and the CC
# runtime shell cannot see the tree when it stands (D2/D3 — live,
# skipped with a note when the host carries no tree).
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
"$PY" "$PLAN" design-pin --root "$OD" --tag fixture --write > "$T/pin.json"
grep -q '"tree_sha256"' "$T/pin.json"

# ── the repo: seed → task record → one web file lands after base ────
REPO="$T/repo"; CHANGE=ud-ch; TASK="$REPO/.ai-dlc/tasks/ud-m1"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
"$PY" "$REPORT" init --task-dir "$TASK" --repo "$REPO" --route inline \
    --task-id ud-m1 --change "$CHANGE" > /dev/null
printf '<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Cabañas</title></head><body><main>Viejo</main></body></html>\n' \
  > "$REPO/index.html"
git -C "$REPO" add index.html
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q -m "the cabin page"

# ── the stub client: marks itself invoked, then shows the session ───
# STUB_SHAPE: good (reads the upstream, writes the page) | d8 (claims
# the work, writes the page, reads nothing upstream)
STUB="$T/stub-design"
cat > "$STUB" <<EOF
#!/usr/bin/env python3
import json, os, pathlib, sys
shape = os.environ.get("STUB_SHAPE", "good")
marker = pathlib.Path("$T/client-invoked")
marker.write_text("invoked\n")
repo = pathlib.Path("$REPO")
od = pathlib.Path("$OD")

def frame(ev, payload):
    print(json.dumps({"type": "event", "event": ev,
                      "payload": {"event_type": ev, **payload}}), flush=True)

page = ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
        # a connection hint: present in the page, never fetched — the
        # asset fact must skip it (fonts.googleapis.com's root 404s to
        # everything; a hint href is not a resource)
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<title>Cabañas del Lago</title></head><body>'
        '<h1>Cabañas del Lago</h1><p>Frente al lago, con chimenea.</p>'
        '</body></html>')
cid = 0
def call(name, args):
    global cid
    cid += 1
    a = json.dumps(args)
    frame("chat.tool_call", {"tool_call": {"name": name, "arguments": a,
                                           "tool_call_id": f"c{cid}"}})
    frame("chat.tool_update", {"tool_name": name,
                               "tool_call_id": f"c{cid}", "arguments": a,
                               "status": "in_progress"})
    frame("chat.tool_result", {"result": "success=True data={} error=None",
                               "tool_name": name,
                               "tool_call_id": f"c{cid}"})

if shape == "good":
    # a probe for a SKILL.md that never stood (the shipped tree keeps
    # none under design-systems/): its name appears in the frames and
    # must not back the template — only a read that landed does
    call("read_file", {"path": str(od / "design-systems/absent/SKILL.md")})
    call("read_file", {"path": str(od / "design-systems/warm/SKILL.md")})
# N5 call assertion: the stub emits a skill_tool{ui-designer} frame
call("skill_tool", {"skill_name": "ui-designer"})
if shape == "good":
    # a truncated write: partial arguments that parse as nothing — the
    # payload must never read as shell text (live round-2 finding)
    partial = json.dumps({"file_path": str(repo / "index.html"),
                          "content": page})[:60]
    frame("chat.tool_call", {"tool_call": {"name": "write_file",
                                           "arguments": partial,
                                           "tool_call_id": "c99"}})
(repo / "index.html").write_text(page)
call("write_file", {"path": str(repo / "index.html"), "content": page})
final = ("I beautified the cabin page with the warm design system."
         if shape == "d8" else "Done.")
frame("chat.final", {"content": final})
EOF
chmod +x "$STUB"
export AI_DLC_CLIENT="$STUB"

# ── 1. the applicability classes (report.design_file_classes) ───────
"$PY" - "$ROOT/bin" <<'PYEOF'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from report import design_file_classes
d = Path(tempfile.mkdtemp())
for rel, want in {
        "index.html": ["web"], "style.scss": ["web"], "App.jsx": ["web"],
        # an html under slides/ is a deck AND a web file — both classes
        "slides/intro.html": ["web", "deck"],
        "deck/a.html": ["web", "deck"],
        "deck.pptx": ["deck"]}.items():
    got = design_file_classes(rel, d)
    assert got == want, (rel, got)
(d / "notes.md").write_text("---\ndeck: true\n---\n# dia\n")
assert design_file_classes("notes.md", d) == ["deck"]
(d / "plain.md").write_text("# plano\n")
assert design_file_classes("plain.md", d) == []
assert design_file_classes("app.py", d) == []
print("ok: web/deck classes measured, backend and plain md ask nothing")
PYEOF

# ── 2. exit 24: a backend change buys no beautifying ────────────────
R2="$T/repo2"
git -C "$T" init -q repo2
git -C "$R2" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
"$PY" "$REPORT" init --task-dir "$R2/.ai-dlc/tasks/ud-m2" --repo "$R2" \
    --route inline --task-id ud-m2 --change "$CHANGE" > /dev/null
printf 'def add(a, b):\n    return a + b\n' > "$R2/app.py"
git -C "$R2" add app.py
git -C "$R2" -c user.name=t -c user.email=t@t commit -q -m backend
rc=0; "$PY" "$PLAN" design --change "$CHANGE" --repo "$R2" \
    --task-dir "$R2/.ai-dlc/tasks/ud-m2" > "$T/o24.json" 2>&1 || rc=$?
[[ $rc -eq 24 ]] || { echo "FAIL: backend surface exit $rc (want 24)"; cat "$T/o24.json"; exit 1; }
grep -q '"applicable": false' "$T/o24.json"
grep -q 'measured_surface' "$T/o24.json"
[[ ! -e "$T/client-invoked" ]] || { echo "FAIL: the stub ran for a refused surface"; exit 1; }
rm -f "$T/client-invoked"

# ── 3. exit 25: the pointer skill missing, nothing self-installs ────
rc=0
AI_DLC_SKILLS_DIR="$T/empty-skills" \
  "$PY" "$PLAN" design --change "$CHANGE" --repo "$REPO" --task-dir "$TASK" \
  > "$T/o25.json" 2>&1 || rc=$?
[[ $rc -eq 25 ]] || { echo "FAIL: missing skill exit $rc (want 25)"; cat "$T/o25.json"; exit 1; }
grep -q 'install-opendesign.sh' "$T/o25.json"
[[ ! -e "$T/client-invoked" ]] || { echo "FAIL: the stub ran without the skill"; exit 1; }
rm -f "$T/client-invoked"

# ── 4. exit 26: the tree moved off the pin (I3's detection half) ────
SK="$OD/design-systems/warm/SKILL.md"; cp "$SK" "$T/sk.orig"
printf 'local edit\n' >> "$SK"
rc=0; "$PY" "$PLAN" design --change "$CHANGE" --repo "$REPO" --task-dir "$TASK" \
  > "$T/o26.json" 2>&1 || rc=$?
[[ $rc -eq 26 ]] || { echo "FAIL: off-pin tree exit $rc (want 26)"; cat "$T/o26.json"; exit 1; }
grep -q 'measured_tree_sha256' "$T/o26.json"
[[ ! -e "$T/client-invoked" ]] || { echo "FAIL: the stub ran off-pin"; exit 1; }
cp "$T/sk.orig" "$SK"; rm -f "$T/client-invoked"

# ── 5. D8: claims without reads — no record, deliver says so ────────
rc=0
STUB_SHAPE=d8 "$PY" "$PLAN" design --change "$CHANGE" --repo "$REPO" \
    --task-dir "$TASK" > "$T/od8.json" 2>&1 || rc=$?
[[ $rc -eq 1 ]] || { echo "FAIL: d8 exit $rc (want 1)"; cat "$T/od8.json"; exit 1; }
grep -q '"record": null' "$T/od8.json"
grep -q '(D8)' "$T/od8.json"
[[ -z "$(ls "$T/records/$CHANGE" 2>/dev/null)" ]] || { echo "FAIL: a record stands for a frame-contradicted session"; exit 1; }
rm -rf "$TASK/gates"
# pre-record design_auto to prevent auto-dispatch (W6: --no-design would
# write design_decision and mask the unverified state we are testing)
"$PY" - "$TASK/planning.json" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text()) if p.is_file() else {}
d["design_auto"] = {"attempted_at": "2026-09-01T00:00:00Z", "rc": 1,
                    "outcome": "design_unverified", "attempts": 1,
                    "state": "complete", "trigger": "deliver"}
p.write_text(json.dumps(d, indent=2) + "\n")
PYEOF
"$PY" "$REPORT" deliver --task-dir "$TASK" --repo "$REPO" > "$T/dd8.json" 2>&1
grep -q '"design_state": "design_unverified"' "$T/dd8.json"

# ── 6. the positive control: five facts hold, record signed ─────────
rc=0
STUB_SHAPE=good "$PY" "$PLAN" design --change "$CHANGE" --repo "$REPO" \
    --task-dir "$TASK" > "$T/ogood.json" 2>&1 || rc=$?
[[ $rc -eq 0 ]] || { echo "FAIL: positive dispatch exit $rc"; cat "$T/ogood.json"; exit 1; }
grep -q '"failed": \[\]' "$T/ogood.json"
RECORD=$(grep -o '"record": "[^"]*"' "$T/ogood.json" | head -1 | cut -d'"' -f4)
[[ -f "$RECORD" ]] || { echo "FAIL: no record file at $RECORD"; exit 1; }
rm -rf "$TASK/gates"
# pre-record design_auto to prevent auto-dispatch without recording a skip
"$PY" - "$TASK/planning.json" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text()) if p.is_file() else {}
d["design_auto"] = {"attempted_at": "2026-09-01T00:00:00Z", "rc": 0,
                    "outcome": "design_applied", "attempts": 1,
                    "state": "complete", "trigger": "deliver"}
p.write_text(json.dumps(d, indent=2) + "\n")
PYEOF
"$PY" "$REPORT" deliver --task-dir "$TASK" --repo "$REPO" > "$T/dgood.json" 2>&1
grep -q '"design_state": "design_applied"' "$T/dgood.json"
"$PY" - "$ROOT/bin" "$T/records" <<'PYEOF'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import os
os.environ["AI_DLC_RECORDS"] = sys.argv[2]
from report import signed_records
recs, rejected = signed_records("ud-ch", "design")
assert not rejected, rejected
assert len(recs) == 1 and recs[0]["verb"] == "design"
r = recs[0]
assert r["template"]["path"].endswith("design-systems/warm/SKILL.md")
assert r["template"]["sha256"] and len(r["template"]["sha256"]) == 64
f = r["files"][0]
assert f["path"] == "index.html" and f["bytes"] > 0 and f["sha256"]
# the truncated write and the hint href leave no phantom file, and no
# ref was ever checked against the network (the hint was skipped)
assert len(r["files"]) == 1, r["files"]
assert r["assets"]["refs_checked"] == 0, r["assets"]
assert r["assets"]["remote_unreachable"] == []
assert r["render"][0]["status"] == 200 and r["render"][0]["dom_nodes"] > 0
assert r["placeholders"] == []
print("ok: the design record is signed and carries the five facts")
PYEOF

# ── 7. D7: a tampered record is tampering evidence, not a record ────
"$PY" - "$RECORD" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text())
d["files"][0]["path"] = "evil.html"   # the payload moves, the signature stays
p.write_text(json.dumps(d, indent=2, ensure_ascii=False))
PYEOF
rm -rf "$TASK/gates"
# pre-record design_auto to prevent auto-dispatch without recording a skip
"$PY" - "$TASK/planning.json" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text()) if p.is_file() else {}
d["design_auto"] = {"attempted_at": "2026-09-01T00:00:00Z", "rc": 1,
                    "outcome": "design_unverified", "attempts": 1,
                    "state": "complete", "trigger": "deliver"}
p.write_text(json.dumps(d, indent=2) + "\n")
PYEOF
"$PY" "$REPORT" deliver --task-dir "$TASK" --repo "$REPO" > "$T/dtamp.json" 2>&1
grep -q '"design_state": "design_unverified"' "$T/dtamp.json"
grep -q 'tampering' "$T/dtamp.json"

# ── 8. a person's recorded skip outranks the record ─────────────────
rc=0; "$PY" "$PLAN" decide --design skip --change "$CHANGE" --repo "$REPO" \
    --task-dir "$TASK" --decided-by user --reason "backend release" \
    > "$T/dec1.json" 2>&1 || rc=$?
[[ $rc -eq 4 ]] || { echo "FAIL: class-word decider accepted (exit $rc)"; cat "$T/dec1.json"; exit 1; }
"$PY" "$PLAN" decide --design skip --change "$CHANGE" --repo "$REPO" \
    --task-dir "$TASK" --decided-by Robin --reason "backend release" > /dev/null
rm -rf "$TASK/gates"
"$PY" "$REPORT" deliver --task-dir "$TASK" --repo "$REPO" --no-design --no-design-by Robin --no-design-why "decline test" > "$T/ddec.json"
grep -q '"design_state": "design_declined"' "$T/ddec.json"
grep -q 'Robin' "$T/ddec.json"

# ── 9. the heredoc strip: payload markup is not a write target ──────
"$PY" - "$ROOT/bin" <<'PYEOF'
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location(
    "planmod", str(Path(sys.argv[1]) / "plan.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
cmd = ("cat > index.html <<'EOF'\n<h1>Cabañas del Lago</h1>\n"
       "<a href=\"c.html\">Ver</a>\nEOF")
stripped = m._strip_heredocs(cmd)
assert "Cabañas" not in stripped and "> index.html" in stripped
lines = [json.dumps({"type": "event", "event": "chat.tool_call",
                     "payload": {"event_type": "chat.tool_call",
                                 "tool_call": {"name": "bash",
                                               "arguments": json.dumps({"command": cmd}),
                                               "tool_call_id": "c1"}}})]
writes = m.frame_write_abs(lines, Path("/r"))
assert writes == ["/r/index.html"], writes
print("ok: heredoc writes resolve to the page, never to payload text")
PYEOF

# ── 10. I1/D1: bin/ spawns no od / open-design process, ever ────────
"$PY" - "$ROOT/bin" <<'PYEOF'
import ast, sys
from pathlib import Path
BINS = {"subprocess.run", "subprocess.Popen", "subprocess.call",
        "subprocess.check_call", "subprocess.check_output",
        "subprocess.run", "os.system", "os.popen", "os.execv",
        "os.execve", "os.spawnv"}
BAD = ('"od"', "'od'", "/opt/open-design", "opendesign")
hits = []
for f in Path(sys.argv[1]).glob("*.py"):
    tree = ast.parse(f.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        d = node.func
        if isinstance(d, ast.Attribute):
            name = f"{getattr(d.value, 'id', '?')}.{d.attr}"
        else:
            name = getattr(d, "id", "")
        if name in BINS or (isinstance(d, ast.Attribute)
                            and d.attr in {"system", "popen", "execv",
                                           "spawnv"}):
            src = ast.unparse(node)
            if any(b in src for b in BAD):
                hits.append(f"{f.name}: {src[:90]}")
assert not hits, "process calls naming od/open-design:\n" + "\n".join(hits)
print("ok: no od/open-design process call stands in bin/")
PYEOF

# ── 11. D2/D3 live: the CC runtime shell cannot see the tree ────────
if [[ -d /opt/open-design ]]; then
  MASK=$("$ROOT/bin/aidlc-shell" --print-mask)
  grep -qx "/opt/open-design" <<< "$MASK" || { echo "FAIL: tree absent from the mask"; exit 1; }
  if "$ROOT/bin/aidlc-shell" -- cat /opt/open-design/.aidlc-pin.json > /dev/null 2>&1; then
    echo "FAIL: the CC shell read the pinned tree (D2)"; exit 1
  fi
  cat /opt/open-design/.aidlc-pin.json > /dev/null   # the control: it stands
  if "$ROOT/bin/aidlc-shell" -- od --version > /dev/null 2>&1; then
    echo "FAIL: od ran inside the CC shell (D3)"; exit 1
  fi
  command -v od > /dev/null   # od exists outside — masked by name, not absent
  echo "ok: tree and od invisible inside the CC shell, visible outside"
else
  echo "note: no tree at /opt/open-design — D2/D3 shell checks skipped"
fi

echo "PASS: ud_design_gates (surface 24 / skill 25 / pin 26 / D8 / D7 / four states / I1 / heredoc strip / design-required C1-C14)"
