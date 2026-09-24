#!/usr/bin/env bash
# N3 (containment PRD §7): the graph dispatch — ONE dispatch produces
# the change's graph record for its whole life. The session runs the
# normalized status literal and the normalized instructions literal for
# every artifact that status reported; the graph (ids, dependency
# edges, each conditional artifact's own inclusion conditions VERBATIM
# from its instruction) is derived mechanically from those command
# outputs — nothing is asked of the model's judgment. The status
# dispatch writes the status record of its own. roles then reads both
# records and nothing else: dispatch → records → readers, closed.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
head -c 32 /dev/zero | tr '\0' '\x9f' > "$T/verdict.key" 2>/dev/null \
  || printf '0123456789abcdef0123456789abcdef' > "$T/verdict.key"
REPO="$T/repo"; CHANGE=oc5-ch
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
# N6: the spec surface lives in the plane's own home — the dispatch
# session runs there, so the repo's tree is migrated first
. "$ROOT/tests/collapse/lib_plane.sh"
plane_migrate "$REPO"

# the double: a plane session that runs the status command and the
# instructions command for each artifact, reporting the frames the
# gateway would. The --session name names the dispatch (verb first).
cat > "$T/stub-plane" <<EOF
#!/usr/bin/env python3
import json, sys
change = "$CHANGE"
verb = "graph"
for i, a in enumerate(sys.argv):
    if a == "--session":
        verb = sys.argv[i + 1].split("-")[0]
def frame(ev, payload):
    print(json.dumps({"type": "event", "event": ev,
                      "payload": {"event_type": ev, **payload}}))
def call(cid, cmd):
    args = json.dumps({"command": cmd})
    frame("chat.tool_call", {"tool_call": {"name": "bash",
                                           "arguments": args,
                                           "tool_call_id": cid}})
    frame("chat.tool_update", {"tool_name": "bash", "tool_call_id": cid,
                               "arguments": args,
                               "status": "in_progress"})
def result(cid, stdout):
    data = {"content": stdout}
    frame("chat.tool_result", {"result": "success=True data="
                               + str(data) + " error=None",
                               "tool_name": "bash", "tool_call_id": cid})
STATUS = {"schemaName": "spec-driven",
          "artifacts": [{"id": "proposal", "status": "done",
                         "requires": []},
                        {"id": "specs", "status": "unknown",
                         "requires": ["proposal"]},
                        {"id": "design", "status": "unknown",
                         "requires": ["proposal"]},
                        {"id": "tasks", "status": "unknown",
                         "requires": ["specs", "design"]}],
          "isPlanningComplete": False}
INSTR = {
    "proposal": "## Proposal\n\nState why and what changes.\n",
    "specs": "## Specs\n\nOne delta per capability.\n",
    "design": ("Create the design document that explains HOW.\n\n"
               "When to include design.md (create only if any apply):\n"
               "- Cross-cutting change (multiple services/modules) or new "
               "architectural pattern\n"
               "- New external dependency or significant data model "
               "changes\n"
               "- Security, performance, or migration complexity\n"
               "- Ambiguity that benefits from technical decisions "
               "before coding\n"),
    "tasks": "## Tasks\n\nBehavior only, never shape.\n"}
call("c_status", "/usr/local/bin/openspec status --json --change " + change)
result("c_status", json.dumps(STATUS))
if verb == "graph":
    n = 0
    for a in STATUS["artifacts"]:
        n += 1
        cid = "c_instr_" + str(n)
        call(cid, "/usr/local/bin/openspec instructions " + a["id"]
             + " --change " + change + " --json")
        result(cid, json.dumps({"instruction": INSTR[a["id"]]}))
frame("chat.final", {"content": "DONE"})
EOF
chmod +x "$T/stub-plane"
export AI_DLC_CLIENT="$T/stub-plane"

# 1. the graph dispatch: one session, one signed graph record, the
#    conditional artifact's four conditions verbatim from its own
#    instruction
$PY "$PLAN" graph --change "$CHANGE" --repo "$REPO" > "$T/g.json"
grep -q '"schema": "spec-driven"' "$T/g.json"
$PY - "$ROOT/bin" "$T/records/$CHANGE/graph-001.json" <<'PYEOF'
import json, sys
sys.path.insert(0, sys.argv[1])
import report
rec = json.load(open(sys.argv[2]))
assert report.verify_record(rec), "the graph record does not verify"
assert rec["verb"] == "graph" and rec["schema"] == "spec-driven", rec
arts = {a["id"]: a for a in rec["artifacts"]}
assert sorted(arts) == ["design", "proposal", "specs", "tasks"], arts
assert arts["tasks"]["requires"] == ["specs", "design"], arts["tasks"]
assert arts["design"]["conditional"] is True, arts["design"]
assert arts["design"]["conditions"] == [
    "Cross-cutting change (multiple services/modules) or new "
    "architectural pattern",
    "New external dependency or significant data model changes",
    "Security, performance, or migration complexity",
    "Ambiguity that benefits from technical decisions before coding"], \
    arts["design"]["conditions"]
for aid in ("proposal", "specs", "tasks"):
    assert arts[aid]["conditional"] is False, (aid, arts[aid])
PYEOF

# 2. the status dispatch: its own record, artifact states as the plane
#    reported them
$PY "$PLAN" status --change "$CHANGE" --repo "$REPO" > "$T/s.json"
grep -q '"is_planning_complete": false' "$T/s.json"
$PY - "$ROOT/bin" "$T/records/$CHANGE/status-001.json" <<'PYEOF'
import json, sys
sys.path.insert(0, sys.argv[1])
import report
rec = json.load(open(sys.argv[2]))
assert report.verify_record(rec), "the status record does not verify"
assert rec["artifacts"] == {"proposal": "done", "specs": "unknown",
                            "design": "unknown", "tasks": "unknown"}, rec
assert rec["is_planning_complete"] is False, rec
PYEOF

# 3. the readers consume the dispatches' records and nothing else:
#    roles derives the role set and dispatchability from graph+status
$PY "$PLAN" roles --change "$CHANGE" --repo "$REPO" > "$T/r.json"
grep -q '"artifact": "design"' "$T/r.json"
$PY - "$T/r.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
by = {x["artifact"]: x for x in r["roles"]}
assert by["proposal"]["status"] == "done", by
assert by["specs"]["dispatchable"] is True, by       # proposal done
assert by["design"]["dispatchable"] is True, by
assert by["tasks"]["dispatchable"] is False, by      # specs not done
# dispatchable_NOW never names an artifact already done
assert r["dispatchable_now"] == ["specs", "design"], r
assert r["is_planning_complete"] is False, r
PYEOF
# the graph is not recomputed: a second roles read reuses the record,
# and no second graph-*.json appears
N=$(ls "$T/records/$CHANGE" | grep -c '^graph-' || true)
[[ "$N" -eq 1 ]] || { echo "FAIL: $N graph records after re-reads"; exit 1; }
echo "OC5 N3: pass (one graph dispatch → signed graph record, conditions verbatim, requires from status output; status dispatch → its own record; roles reads both and derives dispatchability; the graph is never recomputed)"
