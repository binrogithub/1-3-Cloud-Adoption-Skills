#!/usr/bin/env bash
# D3 task 3.1: the role set is read from the change's signed graph
# record — exactly proposal/specs/design/tasks with the dependency edges
# the graph declares, dispatchable_now follows the statuses verdict
# records carry, and the phase-complete verdict is the plane's own
# (never asserted by us, never computed caller-side).
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world: the caller
# reads only what these hold
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
GRAPH='[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"]},{"id":"tasks","requires":["specs","design"]}]'
$PY "$RT" key
REPO="$T/repo"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
# the plane produces the graph once; the test stands in for that
# dispatch and signs the record it would have written
$PY "$RT" graph add-nav-bar --schema spec-driven --artifacts-json "$GRAPH" >/dev/null
C="$REPO/openspec/changes/add-nav-bar"
mkdir -p "$C/specs/website"

# 1. a fresh change: exactly the four roles, the declared edges, only
#    proposal dispatchable, phase incomplete
$PY "$PLAN" roles --change add-nav-bar --repo "$REPO" > "$T/r1.json"
grep -q '"schema": "spec-driven"' "$T/r1.json"
$PY - "$T/r1.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
ids = [r["artifact"] for r in d["roles"]]
assert ids == ["proposal", "specs", "design", "tasks"], ids
edges = {r["artifact"]: r["requires"] for r in d["roles"]}
assert edges == {"proposal": [], "specs": ["proposal"],
                 "design": ["proposal"], "tasks": ["specs", "design"]}, edges
assert d["dispatchable_now"] == ["proposal"], d["dispatchable_now"]
assert d["is_planning_complete"] is False
PYEOF

# 2. proposal lands -> specs and design unlock; tasks still blocked.
# The caller never looks at the file: the unlock is a verdict status.
printf '## Why\n\nThe site has no navigation.\n\n## What Changes\n\n- Add a shared navigation bar.\n' > "$C/proposal.md"
$PY "$RT" verdict add-nav-bar --rc 0 --artifacts proposal=done --complete false >/dev/null
$PY "$PLAN" roles --change add-nav-bar --repo "$REPO" > "$T/r2.json"
$PY - "$T/r2.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["dispatchable_now"] == ["specs", "design"], d["dispatchable_now"]
assert d["is_planning_complete"] is False
PYEOF

# 3. complete only when the plane's verdict says so — files on disk
# prove nothing to the caller anymore
cat > "$C/specs/website/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Navigation bar

The site SHALL show a navigation bar on every page.

#### Scenario: Visitor opens any page

- **WHEN** a visitor opens any page
- **THEN** the navigation bar is visible with links to all top-level pages
EOF
printf '## Context\n\nA small static site.\n\n## Decisions\n\n- Server-side include over client script.\n' > "$C/design.md"
printf '# Tasks\n\n- [ ] 1.1 Add the shared navigation bar\n' > "$C/tasks.md"
$PY "$RT" verdict add-nav-bar --rc 0 --artifacts proposal=done,specs=done,design=done,tasks=done --complete true >/dev/null
$PY "$PLAN" roles --change add-nav-bar --repo "$REPO" > "$T/r3.json"
grep -q '"is_planning_complete": true' "$T/r3.json"
$PY - "$T/r3.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["dispatchable_now"] == [], d["dispatchable_now"]
assert all(r["status"] == "done" for r in d["roles"])
PYEOF
echo "D3 PLAN ROLES: pass (four roles from the signed graph record, edges honored, dispatchable_now follows verdict statuses, phase-complete is the plane's verdict)"
