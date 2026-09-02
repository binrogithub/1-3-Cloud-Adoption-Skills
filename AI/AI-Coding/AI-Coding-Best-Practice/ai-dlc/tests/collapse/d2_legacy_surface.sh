#!/usr/bin/env bash
# D2 legacy surface (devteam task 2.7): the retired worker-plane surface
# is gone — no swarm skill anywhere, no openjiuwen/sdd-proposed vocabulary,
# route values are inline|planned, a stale route stops a live record for
# the human, and a closed record keeps its historical value.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT="$ROOT/bin/report.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# 1. the swarm skill is gone — tracked source and .claude mirror
[[ ! -e "$ROOT/supervisor/skills/claude/ai-dlc-swarm" ]] || { echo "FAIL: supervisor/skills/claude/ai-dlc-swarm still exists"; exit 1; }
[[ ! -e "$ROOT/.claude/skills/ai-dlc-swarm" ]] || { echo "FAIL: .claude/skills/ai-dlc-swarm still exists"; exit 1; }

# 2. nothing names the retired route vocabulary
if grep -rq 'delegate_dispatch\|sdd-proposed\|"worker"' \
     "$ROOT/supervisor/skills/claude" "$ROOT/bin" "$ROOT/config"; then
  echo "FAIL: retired route vocabulary still present"; exit 1; fi
if grep -q 'sdd-proposed' "$REPORT"; then
  echo "FAIL: report.py still knows sdd-proposed"; exit 1; fi

# 3. the routing table names the planning plane, not a worker
SKILL="$ROOT/supervisor/skills/claude/ai-dlc/SKILL.md"
grep -q 'planning plane' "$SKILL" || { echo "FAIL: routing table names no planning plane"; exit 1; }
if grep -q 'via `delegate`' "$SKILL"; then
  echo "FAIL: routing table still sends work via delegate"; exit 1; fi
# README's routing section too (historical retirement prose is allowed)
if grep -q 'PROPOSE SDD\|Size alone never selects SDD' "$ROOT/README.md"; then
  echo "FAIL: README routing still proposes SDD"; exit 1; fi

# 4. init rejects retired values; planned is accepted
REPO="$T/repo"; TD="$REPO/.ai-dlc/tasks/t"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
set +e
$PY "$REPORT" init --task-dir "$TD" --repo "$REPO" --route worker --task-id t \
  > "$T/rej.json" 2>&1
RC=$?
set -e
[[ $RC -ne 0 ]] || { echo "FAIL: init accepted retired route 'worker'"; exit 1; }
$PY "$REPORT" init --task-dir "$TD" --repo "$REPO" --route planned --task-id t \
  | grep -q '"route": "planned"' || { echo "FAIL: init rejected route planned"; exit 1; }

# 5. a stale route stops a live record; a closed record keeps its history
$PY - "$TD/state.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["route"] = "worker"          # a route naming no existing plane
json.dump(d, open(p, "w"), indent=2)
PYEOF
set +e
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --no-design \
  --no-design-by tester --no-design-why 'gate probe' \
  > "$T/stopped.json" 2>&1
RC=$?
set -e
[[ $RC -eq 17 ]] || { echo "FAIL: stale route did not stop bill (rc=$RC)"; exit 1; }
grep -q '"stale_route": true' "$T/stopped.json" || { echo "FAIL: stale-route stop prints no marker"; exit 1; }
# history is allowed on a closed record
$PY - "$TD/state.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["stage"] = "DONE"
json.dump(d, open(p, "w"), indent=2)
PYEOF
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --no-design \
  --no-design-by tester --no-design-why 'gate probe' >/dev/null \
  || { echo "FAIL: closed record with historical route blocked"; exit 1; }

# 6. config: inline default, no openjiuwen_dispatch
grep -q 'route_default: inline' "$ROOT/config/collapsed.config.yaml" \
  || { echo "FAIL: route_default is not inline"; exit 1; }
if grep -q delegate_dispatch "$ROOT/config/collapsed.config.yaml"; then
  echo "FAIL: delegate_dispatch still configured"; exit 1; fi

echo "D2 LEGACY SURFACE: pass (swarm skill gone; inline|planned only; a stale route stops the run)"
