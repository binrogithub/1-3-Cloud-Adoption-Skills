#!/usr/bin/env bash
# G8 (containment PRD §9): no verdict record exists when deliver runs.
# The report says spec_unverified, carries the remedy that names the
# validate DISPATCH (never a caller-side run), and no validator rc or
# output appears anywhere in the report — the only way one could appear
# is the caller running the validator itself, which is the thing the
# containment PRD deletes. Nothing re-runs on its own: a second deliver
# reports the same state from the same absence.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT="$ROOT/bin/report.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world — a graph
# and a status record exist, a verdict record does not
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
$PY "$RT" graph add-nav-bar --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"tasks","requires":["specs"]}]' >/dev/null
$PY "$RT" status add-nav-bar --artifacts proposal=done --complete false >/dev/null
REPO="$T/repo"; TD="$REPO/.ai-dlc/tasks/t"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
C="$REPO/openspec/changes/add-nav-bar"
mkdir -p "$C"
printf '## Why\n\nThe site has no navigation.\n\n## What Changes\n\n- Add a shared navigation bar.\n' > "$C/proposal.md"
$PY "$REPORT" init --task-dir "$TD" --repo "$REPO" --route inline \
     --task-id t --change add-nav-bar >/dev/null
mkdir -p "$REPO/src"
printf '<nav><a href="/">home</a></nav>\n' > "$REPO/src/nav.html"
git -C "$REPO" add -A
git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm work
$PY "$REPORT" gate --task-dir "$TD" --request >/dev/null
$PY "$REPORT" gate --task-dir "$TD" --decision approve --approver tester \
  --rationale "approved; the verdict was never requested" >/dev/null
# everything else is green — the missing verdict is the only blocker
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' > "$T/rep.json"
grep -q '"delivered": false' "$T/rep.json"
grep -q '"outcome": "spec_unverified"' "$T/rep.json"
grep -q '"spec_valid": false' "$T/rep.json"
# the remedy names the dispatch, not a caller-side run
grep -q 'plan.py validate' "$T/rep.json"
# no validator rc/output exists to report — proof the caller ran nothing
if grep -q 'validator_rc\|validator_output' "$T/rep.json"; then
  echo "FAIL: a validator result appears with no verdict record"; cat "$T/rep.json"; exit 1
fi
# nothing re-runs by itself: the same absence reports the same state
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' > "$T/rep2.json"
grep -q '"outcome": "spec_unverified"' "$T/rep2.json"
N=$(ls "$T/records/add-nav-bar" | grep -c '^verdict-' || true)
[[ "$N" -eq 0 ]] \
  || { echo "FAIL: deliver minted a verdict record ($N) — it ran the validator"; exit 1; }
echo "OC3 G8: pass (no verdict → spec_unverified, remedy names the dispatch, no validator rc/output anywhere, nothing auto-ran)"
