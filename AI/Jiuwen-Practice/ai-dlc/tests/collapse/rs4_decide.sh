#!/usr/bin/env bash
# R4 (route-and-speed 4.1-4.4): the optional artifact is decided before
# it is dispatched. design carries the upstream instruction's own
# inclusion conditions; a phase with no recorded decision stops for a
# person before the client exists; a claimed condition that is not the
# instruction's own is refused, and so is a skip without a reason. A
# decision naming a real condition dispatches the role and records which
# condition matched; a skip never dispatches it and the reason travels
# into the phase record.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d /root/ai-dlc-rs4-XXXXXX); trap 'rm -rf "$T"' EXIT
# the fixture lives under /root, which the real plane sees read-only
# (ProtectHome) — these cases exercise the writable class, so the probe
# reads this namespace's view of the path. The three classes and the
# split workspace they imply are covered by ad_any_directory.sh.
export AI_DLC_GATEWAY_ROOT=/
# the plane's records and key live in the test's own world: the design
# artifact's inclusion conditions travel in the signed graph record, and
# the statuses a phase's rounds advance by come from verdict records —
# the client stub stands in for the plane and signs one when its role's
# artifact lands (statuses merge across verdicts, newest carries all)
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
# N6: every case's plane tree lives in the test's own specs home
export AI_DLC_SPECS="$T/specs"
export RT PY
$PY "$RT" key


cat > "$T/stub-client" <<'EOF'
#!/usr/bin/env bash
d="${0%/*}"; s=""; prev=""
for a in "$@"; do
  if [ "$prev" = "--session" ]; then s="$a"; fi
  prev="$a"
done
role="${s##*-}"
printf 'start %s\n' "$s" >> "$d/calls.log"
C="$CHANGE_DIR"
case "$role" in
  specs)
    mkdir -p "$C/specs/website"
    printf '## ADDED Requirements\n\n### Requirement: Navigation bar\n\nThe site SHALL show a navigation bar on every page.\n\n#### Scenario: Visitor opens any page\n\n- **WHEN** a visitor opens any page\n- **THEN** the navigation bar is visible\n' > "$C/specs/website/spec.md"
    written="$C/specs/website/spec.md" ;;
  design)
    printf '## Context\n\nA static site.\n\n## Goals / Non-Goals\n\n- Goals: one fragment\n- Non-Goals: dynamic menus\n\n## Decisions\n\n- Build-time injection.\n\n## Risks / Trade-offs\n\n- None measured.\n' > "$C/design.md"
    written="$C/design.md" ;;
  tasks)
    printf '# Tasks\n\n- [ ] 1.1 add the navigation fragment\n' > "$C/tasks.md"
    written="$C/tasks.md" ;;
esac
"$PY" - "$RT" "$C" "$role" <<'PYX' >/dev/null 2>&1
import fcntl, json, os, subprocess, sys
rt, cdir, role = sys.argv[1:4]
change = os.path.basename(cdir.rstrip("/"))
root = os.environ["AI_DLC_RECORDS"]
d = os.path.join(root, change)
# concurrent roles mint at the same moment: the read-merge-write holds
# an exclusive lock so one verdict carries both done states
with open(os.path.join(root, ".mint.lock"), "w") as lf:
    fcntl.flock(lf, fcntl.LOCK_EX)
    states = {"proposal": "done"}
    if os.path.isdir(d):
        for p in sorted(os.listdir(d)):
            if p.startswith("status-"):
                try:
                    rec = json.load(open(os.path.join(d, p)))
                except Exception:
                    continue
                for k, v in (rec.get("artifacts") or {}).items():
                    if v == "done":
                        states[k] = "done"
    states[role] = "done"
    subprocess.run([sys.executable, rt, "verdict", change, "--rc", "0",
                    "--artifacts",
                    ",".join(f"{k}=done" for k in states),
                    "--complete", "false"], check=True, capture_output=True)
PYX
printf '{"type":"event","event":"chat.tool_call","payload":{"tool_name":"write_file","arguments":"{\\"path\\": \\"%s\\"}"}}\n' "$written"
printf '{"event":"chat.final","payload":{"content":"artifact written"}}\n'
EOF
chmod +x "$T/stub-client"
export AI_DLC_CLIENT="$T/stub-client"

. "$ROOT/tests/collapse/lib_plane.sh"

mk_case () {  # a fresh repo + change with proposal done; echoes the repo path
  local name="$1" repo="$T/$1/repo"
  mkdir -p "$T/$name"
  git -C "$T/$name" init -q repo
  git -C "$repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
  (cd "$repo" && openspec init --tools none --language en) >/dev/null 2>&1
  mkdir -p "$repo/openspec/changes/$name"
  printf '## Why\n\nThe site has no navigation.\n\n## What Changes\n\n- Add a shared navigation bar.\n' \
    > "$repo/openspec/changes/$name/proposal.md"
  # N6: the artifacts live in the plane's tree from here on
  plane_migrate "$repo"
  printf '{"requirement": "shared navigation across pages", "change_id": "%s",\n "capability": "website", "repo": "%s"}\n' \
    "$name" "$repo" > "$T/$name/pkg.json"
  # the graph a graph dispatch would have signed: design carries the
  # upstream instruction's own four inclusion conditions, and the
  # verdict marks the proposal that already stands on disk done
  "$PY" "$RT" graph "$name" --schema spec-driven --artifacts-json \
    '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"],"conditional":true,"conditions":["Cross-cutting change (multiple services/modules) or new architectural pattern","New external dependency or significant data model changes","Security, performance, or migration complexity","Ambiguity that benefits from technical decisions before coding"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
  "$PY" "$RT" verdict "$name" --rc 0 --artifacts proposal=done --complete false >/dev/null
  echo "$repo"
}

# 1. (4.1) no decision recorded: the phase stops for a person before the
#    client exists, naming the artifact and the instruction's conditions
REPO_1="$(mk_case rs4a)"
export CHANGE_DIR="$(plane_of "$REPO_1")/openspec/changes/rs4a"
set +e
$PY "$PLAN" phase --change rs4a --repo "$REPO_1" \
  --package-file "$T/rs4a/pkg.json" > "$T/1.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: undecided phase exited $RC, want 1"; cat "$T/1.json"; exit 1; }
grep -q '"waiting_on": "artifact decision"' "$T/1.json"
grep -q 'before dispatch' "$T/1.json"
[[ ! -f "$T/calls.log" ]] \
  || { echo "FAIL: the client ran before the decision existed"; cat "$T/calls.log"; exit 1; }
$PY - "$T/1.json" <<'PYEOF'
import json, sys
out = json.load(open(sys.argv[1]))
u = out["undecided"]
assert [x["artifact"] for x in u] == ["design"], u
assert len(u[0]["conditions"]) == 4, u   # the instruction's own four
assert any("Cross-cutting" in c for c in u[0]["conditions"]), u
PYEOF

# 2. (4.1 reverse) a condition that is not the instruction's own is refused
set +e
$PY "$PLAN" decide --change rs4a --repo "$REPO_1" --artifact design \
  --condition "the executor feels it is small" --decided-by tester \
  > "$T/2.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 4 ]] || { echo "FAIL: foreign condition exited $RC, want 4"; cat "$T/2.json"; exit 1; }
grep -q "not one of the instruction's own" "$T/2.json"

# 3. (4.2 reverse) a skip without a reason is refused
set +e
$PY "$PLAN" decide --change rs4a --repo "$REPO_1" --artifact design \
  --skip --decided-by tester > "$T/3.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 4 ]] || { echo "FAIL: reasonless skip exited $RC, want 4"; cat "$T/3.json"; exit 1; }
grep -q 'unevaluated decision' "$T/3.json"
$PY - "$REPO_1/.ai-dlc/tasks/rs4a-planning/planning.json" <<'PYEOF'
import json, sys, os
p = sys.argv[1]
if os.path.exists(p):
    d = json.load(open(p)).get("artifact_decisions")
    assert not d, d   # a refused decision records nothing
# the file may not exist at all — nothing was dispatched to create it
PYEOF

# 4. (4.4) a change meeting a condition dispatches the role and records
#    which condition matched
REPO_4="$(mk_case rs4b)"
export CHANGE_DIR="$(plane_of "$REPO_4")/openspec/changes/rs4b"
$PY "$PLAN" decide --change rs4b --repo "$REPO_4" --artifact design \
  --condition "Cross-cutting change" --decided-by tester > "$T/4d.json" \
  || { echo "FAIL: valid condition refused"; cat "$T/4d.json"; exit 1; }
set +e
$PY "$PLAN" phase --change rs4b --repo "$REPO_4" \
  --package-file "$T/rs4b/pkg.json" --concurrency 2 > "$T/4.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: dispatch-on-condition phase exited $RC"; cat "$T/4.json"; exit 1; }
grep -q 'plan-rs4b-design' "$T/calls.log" \
  || { echo "FAIL: design not dispatched on a matched condition"; cat "$T/calls.log"; exit 1; }
$PY - "$REPO_4/.ai-dlc/tasks/rs4b-planning/planning.json" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1]))
d = p["artifact_decisions"]["design"]
assert d["dispatch"] is True, d
assert d["condition_matched"].startswith("Cross-cutting change"), d
assert len(d["conditions_considered"]) == 4, d
assert d["decided_by"] == "tester", d
ph = p["phases"][-1]
assert "design" in ph["roles"], sorted(ph["roles"])
assert ph["skipped_by_decision"] == {}, ph["skipped_by_decision"]
PYEOF

# 4b. (stated-authorship 1.3) a decider that is an agent is recorded
#     verbatim, so it cannot read as a person's
REPO_4B="$(mk_case rs4d)"
export CHANGE_DIR="$(plane_of "$REPO_4B")/openspec/changes/rs4d"
$PY "$PLAN" decide --change rs4d --repo "$REPO_4B" --artifact design \
  --condition "Cross-cutting change" \
  --decided-by "rs4 fixture agent (no person asked)" > "$T/4b.json" \
  || { echo "FAIL: an agent decider refused"; cat "$T/4b.json"; exit 1; }
$PY - "$REPO_4B/.ai-dlc/tasks/rs4d-planning/planning.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))["artifact_decisions"]["design"]
assert d["decided_by"] == "rs4 fixture agent (no person asked)", d
PYEOF

# 5. (4.3) a change meeting none of the conditions must not dispatch the
#    role: the skip is recorded with its reason, design never reaches
#    the client, and tasks stays blocked on the artifact it requires
REPO_5="$(mk_case rs4c)"
export CHANGE_DIR="$(plane_of "$REPO_5")/openspec/changes/rs4c"
rm -f "$T/calls.log"
$PY "$PLAN" decide --change rs4c --repo "$REPO_5" --artifact design \
  --skip --reason "one module, no new dependency, no migration" \
  --decided-by tester >/dev/null \
  || { echo "FAIL: reasoned skip refused"; exit 1; }
set +e
$PY "$PLAN" phase --change rs4c --repo "$REPO_5" \
  --package-file "$T/rs4c/pkg.json" --concurrency 2 > "$T/5.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: skip phase exited $RC"; cat "$T/5.json"; exit 1; }
if grep -q 'plan-rs4c-design' "$T/calls.log"; then
  echo "FAIL: design dispatched despite the skip"; cat "$T/calls.log"; exit 1
fi
grep -q 'plan-rs4c-specs' "$T/calls.log" \
  || { echo "FAIL: specs not dispatched alongside the skip"; cat "$T/calls.log"; exit 1; }
$PY - "$REPO_5/.ai-dlc/tasks/rs4c-planning/planning.json" "$T/5.json" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1])); out = json.load(open(sys.argv[2]))
ph = p["phases"][-1]
sk = ph["skipped_by_decision"]["design"]
assert sk["dispatch"] is False, sk
assert sk["reason"] == "one module, no new dependency, no migration", sk
assert "design" not in ph["roles"], sorted(ph["roles"])
assert any(b["artifact"] == "tasks" and "design" in b["waiting_on"]
           for b in ph["blocked"]), ph["blocked"]
assert out["is_planning_complete"] is False
PYEOF

echo "RS4 DECIDE: pass (no decision stops the phase before the client exists naming design and the instruction's four conditions; a foreign condition is refused exit 4; a reasonless skip is refused exit 4 with nothing recorded; a matched condition dispatches design with condition_matched recorded; a reasoned skip never dispatches it, carries the reason, and leaves tasks blocked on design; an agent decider is recorded verbatim)"
