#!/usr/bin/env bash
# N1 (containment PRD §7): the validate dispatch. plan.py opens a FRESH
# plane session whose only business is the normalized validator literal
# (absolute path, --strict, --json, nothing else), reads rc and stdout
# from the frames' own tool result — never the model's conclusion — and
# writes the signed verdict record. A session that paraphrases the
# command (relative path, a pipe, a redirect) fails with exit 23 and
# writes NO record: a verdict exists only for a command the frames show
# the plane running exactly as normalized.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY - "$T" <<'PYEOF'
import os, sys
k = os.path.join(sys.argv[1], "verdict.key")
open(k, "wb").write(b"\x11" * 32)
PYEOF
REPO="$T/repo"; CHANGE=oc4-ch
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
# N6: the spec surface lives in the plane's own home — the dispatch
# session runs there, so the repo's tree is migrated first
. "$ROOT/tests/collapse/lib_plane.sh"
plane_migrate "$REPO"

# the double: a session that runs one bash command and reports exactly
# the frames the gateway reports (measured on this host — probe sessions
# aidlc-rc-probe / aidlc-rc2-probe). STUB_MODE picks what it runs:
# normalized | relative | piped | redirected
cat > "$T/stub-validate" <<EOF
#!/usr/bin/env python3
import json, os
mode = os.environ.get("STUB_MODE", "normalized")
change = "$CHANGE"
cid = "call_v1"
def frame(ev, payload):
    print(json.dumps({"type": "event", "event": ev,
                      "payload": {"event_type": ev, **payload}}))
cmd = "/usr/local/bin/openspec validate " + change + " --strict --json"
if mode == "relative":
    cmd = "openspec validate " + change + " --strict --json"
elif mode == "piped":
    cmd += " | jq ."
elif mode == "redirected":
    cmd += " > /tmp/verdict.json"
args = json.dumps({"command": cmd, "description": "validate"})
frame("chat.tool_call", {"tool_call": {"name": "bash", "arguments": args,
                                       "tool_call_id": cid}})
frame("chat.tool_update", {"tool_name": "bash", "tool_call_id": cid,
                           "arguments": args, "status": "in_progress"})
rc = os.environ.get("STUB_RC", "0")
content = os.environ.get("STUB_CONTENT", '{"items":[]}\n')
if mode == "normalized" and rc != "0":
    body = "Exit code " + rc + "\n" + content
    data = {"content": body}
    result = "success=False data=" + str(data) + " error=" + repr(body)
else:
    data = {"content": content}
    result = "success=True data=" + str(data) + " error=None"
frame("chat.tool_result", {"result": result, "tool_name": "bash",
                           "tool_call_id": cid})
frame("chat.final", {"content": "DONE"})
EOF
chmod +x "$T/stub-validate"
export AI_DLC_CLIENT="$T/stub-validate"

# 1. a rejecting verdict: rc 1 with issue text — read from the frame,
#    carried verbatim into a signed record
STUB_MODE=normalized STUB_RC=1 STUB_CONTENT='must include at least one scenario' \
  $PY "$PLAN" validate --change "$CHANGE" --repo "$REPO" > "$T/v1.json"
grep -q '"rc": 1' "$T/v1.json"
grep -q '"spec_state": "spec_invalid"' "$T/v1.json"
grep -q 'must include at least one scenario' "$T/v1.json"
$PY - "$ROOT/bin" "$T/records/$CHANGE/verdict-001.json" <<'PYEOF'
import json, sys
sys.path.insert(0, sys.argv[1])
import report
rec = json.load(open(sys.argv[2]))
assert report.verify_record(rec), "the verdict record does not verify"
assert rec["verb"] == "validate", rec
assert rec["rc"] == 1, rec
assert rec["stdout"] == "must include at least one scenario", rec
assert rec["argv"] == ["/usr/local/bin/openspec", "validate", "oc4-ch",
                       "--strict", "--json"], rec
assert rec["session"].startswith("validate-oc4-ch-"), rec
import hashlib
assert rec["sha256"] == hashlib.sha256(
    rec["stdout"].encode()).hexdigest(), rec
PYEOF

# 2. an accepting verdict: rc 0
STUB_MODE=normalized STUB_RC=0 \
  $PY "$PLAN" validate --change "$CHANGE" --repo "$REPO" > "$T/v2.json"
grep -q '"spec_state": "spec_valid"' "$T/v2.json"
grep -q '"rc": 0' "$T/v2.json"

# 3-5. the paraphrases: each fails with exit 23, names the literal it
#      owed, carries what the session ran instead, writes no record
NV=$(ls "$T/records/$CHANGE" | grep -c '^verdict-' || true)
for mode in relative piped redirected; do
  set +e
  STUB_MODE=$mode $PY "$PLAN" validate --change "$CHANGE" --repo "$REPO" \
    > "$T/f_$mode.json" 2>&1
  RC=$?
  set -e
  [[ "$RC" -eq 23 ]] || { echo "FAIL: $mode paraphrase exited $RC, want 23"; cat "$T/f_$mode.json"; exit 1; }
  grep -q '"rejected": "plane dispatch"' "$T/f_$mode.json"
  grep -q "normalized_literals" "$T/f_$mode.json"
  grep -q 'commands_seen' "$T/f_$mode.json"
done
# no record was written by any failed dispatch — count unchanged
N2=$(ls "$T/records/$CHANGE" | grep -c '^verdict-' || true)
[[ "$N2" -eq "$NV" ]] \
  || { echo "FAIL: a failed dispatch wrote a record ($NV -> $N2)"; exit 1; }

# 6. the session names and the planning record: a fresh session per
#    dispatch, the attempt recorded beside its duration
$PY - "$REPO/.ai-dlc/tasks/$CHANGE-planning/planning.json" "$T/v1.json" "$T/v2.json" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1]))
a, b = json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
d = p["plane_dispatches"]["validate"]
assert d["attempts"] >= 3, d
for k in ("started_at", "ended_at", "elapsed_seconds", "session_name"):
    assert k in d, d
assert a["session_name"] != b["session_name"], "sessions were not fresh"
import os
assert os.path.basename(a["evidence"]).startswith("plan-validate-"), a
PYEOF
echo "OC4 N1: pass (fresh session, normalized literal judged from frames, rc/stdout verbatim into a signed record; relative/piped/redirected paraphrases exit 23 and write nothing)"
