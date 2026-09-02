#!/usr/bin/env bash
# stated-authorship: a recorded decision names who made it — stated by
# the caller, never assumed.
#
# A decision recorded without a stated decider is refused, and so is an
# exception without an author, a gate answer without an approver, and any
# of the three whose stated value claims a human without naming one (the
# residue of the removed default). The request path of the gate asks a
# question and carries no approver; it is not refused for lacking one.
# The last case is the sweep itself: no flag either executable defines
# silently defaults to a human identity.
#
# The same script runs from two trees: the pre-change snapshot (ROOT is
# /tmp/ha-base) and this change. In the base tree every case must go RED
# — the old code records the default and exits 0; in the changed tree
# every case must hold. A case that cannot go red pins nothing.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
REPORT="$ROOT/bin/report.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d /root/ai-dlc-ha-XXXXXX)
trap 'rm -rf "$T"' EXIT
# the fixture repo lives under /root, which the real plane sees read-only
# (ProtectHome); these cases record decisions, they dispatch nothing, so
# the probe reads this namespace's view of the path (the rs4 pattern)
export AI_DLC_GATEWAY_ROOT=/
# N6: the spec tree lives plane-side — mint it so the decide cases are
# judged on their own merits, not on a missing plane root
export AI_DLC_SPECS="$T/specs"
. "$ROOT/tests/collapse/lib_plane.sh"
# the plane's records and key live in the test's own world. In the base
# tree records_tool.py does not exist and the old code reads openspec
# directly, so the minting is conditional on the tool being there.
if [ -f "$RT" ]; then
  export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
  $PY "$RT" key
fi

BASE=0; [ "$ROOT" = "/tmp/ha-base" ] && BASE=1
red=0; held=0
rr() { out=$1; shift; set +e; "$@" > "$out" 2>&1; RC=$?; set -e; return 0; }
verdict() { if [ "$2" -eq 1 ]; then held=$((held+1)); else red=$((red+1)); echo "  wrongly held: $3"; fi; return 0; }

# the decide fixture: a scaffolded repo whose design artifact carries
# the upstream instruction's own inclusion conditions — under the
# records contract those conditions travel in the signed graph record
# (rs4's mk_case pattern)
REPO="$T/repo"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
[ -f "$RT" ] && $PY "$RT" graph ha-red --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"],"conditional":true,"conditions":["Cross-cutting change (multiple services/modules) or new architectural pattern","New external dependency or significant data model changes","Security, performance, or migration complexity","Ambiguity that benefits from technical decisions before coding"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
mkdir -p "$REPO/openspec/changes/ha-red"
printf '## Why\n\nThe site has no navigation.\n\n## What Changes\n\n- Add a shared navigation bar.\n' \
  > "$REPO/openspec/changes/ha-red/proposal.md"
plane_migrate "$REPO"
PLANNING="$REPO/.ai-dlc/tasks/ha-red-planning/planning.json"
nodecision() {  # nothing was recorded: no planning.json, or no decision in it
  if [ -f "$PLANNING" ]; then
    $PY -c 'import json,sys; d=json.load(open(sys.argv[1])).get("artifact_decisions"); sys.exit(0 if d else 1)' \
      "$PLANNING"
  else
    return 0
  fi
}

# R1 (1.1) a decision recorded without a stated decider
rr "$T/r1.json" "$PY" "$PLAN" decide --change ha-red --repo "$REPO" --artifact design \
  --condition "Cross-cutting change"
echo "R1 decide with no decider stated: exit $RC — $(head -c 90 "$T/r1.json" | tr '\n' ' ')"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -eq 0 ]; then verdict R1 1 ""; else verdict R1 0 "old exits $RC"; fi
else
  if [ "$RC" -ne 0 ] && nodecision; then verdict R1 1 ""; else verdict R1 0 "exit $RC"; fi
fi

# R2 (1.2) a decider that claims a human without naming one
rr "$T/r2.json" "$PY" "$PLAN" decide --change ha-red --repo "$REPO" --artifact design \
  --condition "Cross-cutting change" --decided-by user
echo "R2 decide with the class word 'user': exit $RC — $(head -c 90 "$T/r2.json" | tr '\n' ' ')"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -eq 0 ]; then verdict R2 1 ""; else verdict R2 0 "old exits $RC"; fi
else
  if [ "$RC" -eq 4 ] && grep -q 'never assumed' "$T/r2.json" && nodecision; then verdict R2 1 ""; else verdict R2 0 "exit $RC"; fi
fi

# R3 (2.1) an exception recorded without a stated author
TD="$T/task-ex"; mkdir -p "$TD"
rr "$T/r3.json" "$PY" "$REPORT" exception --task-dir "$TD" \
  --reason "single mechanical change despite the file count"
echo "R3 exception with no author stated: exit $RC — $(head -c 90 "$T/r3.json" | tr '\n' ' ')"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -eq 0 ] && grep -q '"author": "user"' "$TD/gates/gate-route.answer.json"; then verdict R3 1 ""; else verdict R3 0 "old exits $RC"; fi
else
  if [ "$RC" -ne 0 ] && [ ! -f "$TD/gates/gate-route.answer.json" ]; then verdict R3 1 ""; else verdict R3 0 "exit $RC"; fi
fi

# R4 (2.2) an author that claims a human without naming one
rr "$T/r4.json" "$PY" "$REPORT" exception --task-dir "$TD" \
  --reason "single mechanical change despite the file count" --author user
echo "R4 exception authored 'user': exit $RC — $(head -c 90 "$T/r4.json" | tr '\n' ' ')"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -eq 0 ]; then verdict R4 1 ""; else verdict R4 0 "old exits $RC"; fi
else
  if [ "$RC" -eq 1 ] && grep -q 'without naming' "$T/r4.json" && [ ! -f "$TD/gates/gate-route.answer.json" ]; then verdict R4 1 ""; else verdict R4 0 "exit $RC"; fi
fi

# R5 (3.1) a gate answer recorded without a stated approver
TDG="$T/task-gate"; mkdir -p "$TDG"
rr "$T/r5.json" "$PY" "$REPORT" gate --task-dir "$TDG" --decision approve \
  --rationale "read the diff; it matches the accepted spec"
echo "R5 gate answer with no approver stated: exit $RC — $(head -c 90 "$T/r5.json" | tr '\n' ' ')"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -eq 0 ] && grep -q '"approver": "user"' "$TDG/gates/gate-merge.answer.json"; then verdict R5 1 ""; else verdict R5 0 "old exits $RC"; fi
else
  if [ "$RC" -eq 1 ] && [ ! -f "$TDG/gates/gate-merge.answer.json" ]; then verdict R5 1 ""; else verdict R5 0 "exit $RC"; fi
fi

# R6 (3.2) an approver that claims a human without naming one
rr "$T/r6.json" "$PY" "$REPORT" gate --task-dir "$TDG" --decision approve \
  --rationale "read the diff; it matches the accepted spec" --approver user
echo "R6 gate answer approver 'user': exit $RC — $(head -c 90 "$T/r6.json" | tr '\n' ' ')"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -eq 0 ]; then verdict R6 1 ""; else verdict R6 0 "old exits $RC"; fi
else
  if [ "$RC" -eq 1 ] && grep -q 'without naming' "$T/r6.json" && [ ! -f "$TDG/gates/gate-merge.answer.json" ]; then verdict R6 1 ""; else verdict R6 0 "exit $RC"; fi
fi

# R7 (4.1) the sweep: no flag either executable defines silently defaults
# to a human identity
HITS=0
for f in "$ROOT/bin/plan.py" "$ROOT/bin/report.py"; do
  n=$(grep -cE 'add_argument\([^)]*default=["'"'"'](user|human|person)["'"'"']' "$f" || true)
  HITS=$((HITS + n))
done
echo "R7 identity-defaulting flags in the two executables: $HITS"
if [ "$BASE" -eq 1 ]; then
  if [ "$HITS" -ge 1 ]; then verdict R7 1 ""; else verdict R7 0 "no default found in base"; fi
else
  if [ "$HITS" -eq 0 ]; then verdict R7 1 ""; else verdict R7 0 "$HITS default(s) survive"; fi
fi

# in the base tree "held" counts the cases that went red (the old code
# failed to refuse); in the changed tree it counts the cases that hold
if [ "$BASE" -eq 1 ]; then
  echo "RED-FIRST (pre-change tree): $held of $((red+held)) cases went red"
  if [ "$red" -eq 0 ] && [ "$held" -gt 0 ]; then echo "RED-FIRST base: pass"; else echo "FAIL: $red case(s) wrongly held against the old code"; exit 1; fi
else
  echo "RED-FIRST (this change): $held of $((red+held)) cases hold"
  if [ "$red" -eq 0 ] && [ "$held" -eq 7 ]; then echo "RED-FIRST change: pass"; else exit 1; fi
fi
