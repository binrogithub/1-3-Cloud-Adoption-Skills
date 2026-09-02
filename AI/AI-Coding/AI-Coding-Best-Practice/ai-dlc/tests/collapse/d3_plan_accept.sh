#!/usr/bin/env bash
# D3 task 3.7/3.8/3.10: acceptance reads the plane's signed validate
# verdict — on a rejecting verdict the validator text is returned VERBATIM
# to the role owning the failing artifact with a revision prompt; with no
# verdict at all accept stops (exit 22) rather than judging; on a passing
# verdict a revision that changed requirement or scenario counts unbidden
# is rejected again until a human approves, and the phase gate reports
# the verdict's own completeness (never asserted by us).
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world: the caller
# reads only what these hold, and never executes openspec itself
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
REPO="$T/repo"
TD="$T/td"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
# N6: the artifacts live in the plane's own tree — the test's stand-in
# validate dispatch runs there too
. "$ROOT/tests/collapse/lib_plane.sh"
plane_migrate "$REPO"
# the graph dispatch's record: the four artifacts, their edges, and
# design's own inclusion conditions (upstream states them; the graph
# carries them verbatim so the caller never fetches the instruction)
GRAPH='[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"],"conditional":true,"conditions":["Security, performance, or migration complexity"]},{"id":"tasks","requires":["specs","design"]}]'
$PY "$RT" graph add-nav-bar --schema spec-driven --artifacts-json "$GRAPH" >/dev/null
C="$PLANE_TREE/changes/add-nav-bar"
mkdir -p "$C/specs/website"
cat > "$C/proposal.md" <<'EOF'
## Why

The site has no navigation; visitors cannot move between pages.

## What Changes

- Add a shared navigation bar to every page.
EOF
# a requirement with no scenario: the validator must reject it. The
# test stands in for the validate dispatch: it runs the normalized
# command once and signs exactly that output into a verdict record.
cat > "$C/specs/website/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Navigation bar

The site SHALL show a navigation bar on every page.
EOF
(cd "$PLANE_ROOT" && openspec validate add-nav-bar --strict) > "$T/val.txt" 2>&1 || true

# 0. no verdict at all: accept refuses to judge — exit 22, the stop
#    names the missing record and its dispatch remedy, never the CLI
set +e
$PY "$PLAN" accept --change add-nav-bar --repo "$REPO" --task-dir "$TD" > "$T/a0.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 22 ]] || { echo "FAIL: verdict-less accept exited $RC, want 22"; cat "$T/a0.json"; exit 1; }
grep -q '"needs": \[' "$T/a0.json"
grep -q '"validate"' "$T/a0.json"
grep -q 'plan.py validate --change <id>' "$T/a0.json"
[[ ! -f "$TD/planning.json" ]] || { echo "FAIL: a verdict-less accept wrote a planning snapshot"; exit 1; }

# 1. rejection: exit 9, validator output carried verbatim from the
#    verdict record, the specs role owns the revision, the revision
#    prompt carries the text
$PY "$RT" verdict add-nav-bar --rc 1 --stdout "$(cat "$T/val.txt")" >/dev/null
set +e
$PY "$PLAN" accept --change add-nav-bar --repo "$REPO" --task-dir "$TD" > "$T/a1.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 9 ]] || { echo "FAIL: rejection exited $RC, want 9"; cat "$T/a1.json"; exit 1; }
$PY - "$T/a1.json" "$T/val.txt" <<'PYEOF'
import json, sys
d, direct = json.load(open(sys.argv[1])), open(sys.argv[2]).read().strip()
assert d["accepted"] is False and d["validator_rc"] != 0
assert d["validator_output"] == direct, "validator output not verbatim"
assert d["owning_artifact"] == "specs", d["owning_artifact"]
assert d["revision_prompt"]["validator_output"] == direct
assert "revise only your artifact" in d["revision_prompt"]["clause"]
assert "do not change requirement or scenario counts" in d["revision_prompt"]["clause"]
p = json.load(open(sys.argv[1].replace("a1.json", "td/planning.json")))
assert p["revision_pending"]["validator_output"] == direct[:2000]
PYEOF

# 1b. a verdict that predates the tree it speaks for is not the verdict
#     of what stands: write an artifact after the verdict — past the
#     one-second grace the stamp's whole seconds earn — and accept
#     refuses to judge with it, the offending path named (exit 22)
sleep 1.2
touch "$C/proposal.md"
set +e
$PY "$PLAN" accept --change add-nav-bar --repo "$REPO" --task-dir "$TD" > "$T/a1b.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 22 ]] || { echo "FAIL: stale verdict exited $RC, want 22"; cat "$T/a1b.json"; exit 1; }
grep -q '"stale_against"' "$T/a1b.json"
grep -q 'proposal.md' "$T/a1b.json"

# 2. the spec gains its scenario -> a passing verdict: the plane's
#    validate dispatch would report rc 0 with proposal and specs done
cat > "$C/specs/website/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Navigation bar

The site SHALL show a navigation bar on every page.

#### Scenario: Visitor opens any page

- **WHEN** a visitor opens any page
- **THEN** the navigation bar is visible with links to all top-level pages
EOF
# the tasks artifact with the executable entries the implementation
# reads — the N7 handoff carries these verbatim and nothing of the
# spec surface that produced them
cat > "$C/tasks.md" <<'EOF'
## Tasks

- [ ] 1. Render the shared navigation bar on every page
- [ ] 2. Keep the link list driven by one place
- [x] 3. Name the top-level pages

Some prose that is not an entry and must not travel.
EOF
# a fresh verdict: minted after the last write, inside its own second —
# the grace window trusts it, the phase proceeds
$PY "$RT" verdict add-nav-bar --rc 0 --artifacts proposal=done,specs=done --complete false >/dev/null
$PY "$PLAN" accept --change add-nav-bar --repo "$REPO" --task-dir "$TD" > "$T/a2.json"
grep -q '"accepted": true' "$T/a2.json"
[[ -f "$TD/planning.json" ]] || { echo "FAIL: no accepted snapshot written"; exit 1; }
# 2b. (N7) the accepted change's executable entries land in the plane's
#     records store the moment the change is accepted — behavior only
grep -q '"handoff"' "$T/a2.json"
HO="$AI_DLC_RECORDS/add-nav-bar/handoff.md"
[[ -f "$HO" ]] || { echo "FAIL: no handoff written for the accepted change"; exit 1; }
grep -q '1. - \[ \] 1. Render the shared navigation bar on every page' "$HO"
grep -q '3. - \[x\] 3. Name the top-level pages' "$HO"
if grep -q 'Some prose that is not an entry' "$HO"; then
  echo "FAIL: the handoff carries non-entry prose"; exit 1; fi
if grep -qi 'openspec\|--strict' "$HO"; then
  echo "FAIL: the handoff names the spec tooling"; cat "$HO"; exit 1; fi
# the phase gate is honest: the verdict says design and tasks are not
# done, so the phase is NOT complete even though the change validates
grep -q '"is_planning_complete": false' "$T/a2.json"
grep -q '"phase_complete": false' "$T/a2.json"
grep -q '"artifact": "design"' "$T/a2.json"

# 3. count drift: hand-lower the accepted snapshot -> the counts now
#    differ from the last accepted ones -> rejected again (exit 10)
$PY - "$TD/planning.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["accepted_counts"]["requirements"] = 0
json.dump(d, open(p, "w"))
PYEOF
set +e
$PY "$PLAN" accept --change add-nav-bar --repo "$REPO" --task-dir "$TD" > "$T/a3.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 10 ]] || { echo "FAIL: count drift exited $RC, want 10"; cat "$T/a3.json"; exit 1; }
grep -q '"accepted": false' "$T/a3.json"
grep -q '"requirements": 1' "$T/a3.json"
grep -q '"requirements": 0' "$T/a3.json"

# 4. a human approves the count change -> accepted, new snapshot written
$PY "$PLAN" accept --change add-nav-bar --repo "$REPO" --task-dir "$TD" --counts-approved > "$T/a4.json"
grep -q '"accepted": true' "$T/a4.json"
grep -q '"counts_approved": true' "$T/a4.json"
echo "D3 PLAN ACCEPT: pass (no verdict → exit 22 stop, verbatim rejection from the record to the owning artifact, revision prompt, count-drift rejection without approval, phase gate from the verdict's completeness; N7: the accepted change's executable entries land in records/<change>/handoff.md verbatim — behavior only, no spec tooling)"
