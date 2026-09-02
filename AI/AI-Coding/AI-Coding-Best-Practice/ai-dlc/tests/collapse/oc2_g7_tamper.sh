#!/usr/bin/env bash
# G7 (containment PRD §9): a signed record edited after it was written.
# The HMAC no longer covers the edited fields, the record is dropped and
# NAMED as tampering evidence, and the delivery reports spec_unverified —
# not spec_valid (the edit might have flipped rc to 0), not spec_invalid
# (it might have flipped the other way): unverified, with no re-run. A
# good verdict standing BESIDE a tampered one changes nothing — any
# tampering evidence in the set un-verifies it. A tampered status record
# loses its state the same way: the readers see no status at all, never
# the edited one.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT="$ROOT/bin/report.py"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
REPO="$T/repo"; TD="$REPO/.ai-dlc/tasks/t"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
C="$REPO/openspec/changes/add-nav-bar"
mkdir -p "$C"
printf '## Why\n\nThe site has no navigation.\n\n## What Changes\n\n- Add a shared navigation bar.\n' > "$C/proposal.md"
setup_green_delivery() {
  $PY "$REPORT" init --task-dir "$TD" --repo "$REPO" --route inline \
       --task-id t --change add-nav-bar >/dev/null
  mkdir -p "$REPO/src"
  printf '<nav><a href="/">home</a></nav>\n' > "$REPO/src/nav.html"
  git -C "$REPO" add -A
  git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm work
  $PY "$REPORT" gate --task-dir "$TD" --request >/dev/null
  $PY "$REPORT" gate --task-dir "$TD" --decision approve --approver tester \
    --rationale "approved before the tamper" >/dev/null
}

# 1. the plane signed a REJECTING verdict; the caller edits rc to 0 —
#    the one edit that would flip delivery green
$PY "$RT" verdict add-nav-bar --rc 1 \
  --stdout "must include at least one scenario" >/dev/null
$PY - "$T/records/add-nav-bar/verdict-001.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
rec = json.load(open(p))
rec["rc"] = 0                     # the edit a caller would want to make
json.dump(rec, open(p, "w"), indent=2)
PYEOF
setup_green_delivery
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' > "$T/rep1.json"
grep -q '"delivered": false' "$T/rep1.json"
grep -q '"outcome": "spec_unverified"' "$T/rep1.json"
grep -q '"spec_valid": false' "$T/rep1.json"
grep -q 'rejected_records' "$T/rep1.json"
grep -q 'verdict-001.json' "$T/rep1.json" \
  || { echo "FAIL: the tampered record is not named"; cat "$T/rep1.json"; exit 1; }
# unverified is a third state — it must read as neither of the other two
grep -q '"outcome": "spec_invalid"' "$T/rep1.json" \
  && { echo "FAIL: tamper folded into spec_invalid"; exit 1; }

# 2. a good verdict standing beside a tampered one: the set carries
#    tampering evidence, so the newest good record does not verify it
$PY "$RT" verdict add-nav-bar --rc 0 --stdout '{"items":[]}' >/dev/null
rm -rf "$TD"; git -C "$REPO" -c user.name=t -c user.email=t@t commit -q \
  --allow-empty -m round2
setup_green_delivery
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' > "$T/rep2.json"
grep -q '"outcome": "spec_unverified"' "$T/rep2.json"
grep -q '"delivered": false' "$T/rep2.json"

# 3. a tampered STATUS record: the reader sees no status at all — never
#    the edited one, and never a guess
$PY "$RT" graph add-nav-bar --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]}]' >/dev/null
$PY "$RT" status add-nav-bar --artifacts proposal=done --complete false >/dev/null
SP="$T/records/add-nav-bar/status-001.json"
$PY - "$SP" <<'PYEOF'
import json, sys
p = sys.argv[1]
rec = json.load(open(p))
rec["artifacts"] = {"proposal": "done", "specs": "done",
                    "tasks": "done"}          # states nothing reported
rec["is_planning_complete"] = True
json.dump(rec, open(p, "w"), indent=2)
PYEOF
$PY "$PLAN" roles --change add-nav-bar --repo "$REPO" > "$T/roles.json" 2>&1 \
  || { echo "FAIL: roles crashed on a tampered status record"; cat "$T/roles.json"; exit 1; }
grep -q '"status": "unknown"' "$T/roles.json" \
  || { echo "FAIL: a tampered status record leaked states"; cat "$T/roles.json"; exit 1; }
grep -q '"is_planning_complete": false' "$T/roles.json"

echo "OC2 G7: pass (edited verdict → named tampering evidence, spec_unverified, not delivered; a good record beside a tampered one stays unverified; an edited status record reads as no status at all)"
