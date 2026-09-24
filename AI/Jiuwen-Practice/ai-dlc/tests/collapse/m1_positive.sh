#!/usr/bin/env bash
# D1 positive (devteam tasks 1.2/1.3, landing L1): the delivered path
# with no verification role and no budget term — a temp git repo, a
# strictly valid change (a passing signed verdict), init --change, merge
# approval with a rationale → delivered true, and the report states
# plainly that no machine checked correctness. With no verdict at all
# the report says spec_unverified — never a failure verdict, never a
# re-run.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT="$ROOT/bin/report.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world: deliver
# reads the spec state from these, never from a CLI run
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
REPO="$T/repo"; TD="$REPO/.ai-dlc/tasks/t"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
# the repo owns its own spec tree (--tools none)
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
[[ -f "$REPO/openspec/config.yaml" ]] || { echo "FAIL: openspec init wrote nothing"; exit 1; }
# author a minimal valid change (the AI writes the markdown; the CLI validates)
C="$REPO/openspec/changes/add-nav-bar"
mkdir -p "$C/specs/website"
cat > "$C/proposal.md" <<'EOF'
## Why

The site has no navigation; visitors cannot move between pages.

## What Changes

- Add a shared navigation bar to every page.
EOF
cat > "$C/specs/website/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Navigation bar

The site SHALL show a navigation bar on every page.

#### Scenario: Visitor opens any page

- **WHEN** a visitor opens any page
- **THEN** the navigation bar is visible with links to all top-level pages
EOF
# init stamps base BEFORE work lands; --change wires spec validity into deliver
$PY "$REPORT" init --task-dir "$TD" --repo "$REPO" --route inline --task-id t \
     --change add-nav-bar | grep -q '"change_id": "add-nav-bar"'
# the work lands in the repo (a product file, committed)
mkdir -p "$REPO/src"
printf '<nav><a href="/">home</a></nav>\n' > "$REPO/src/nav.html"
git -C "$REPO" add -A; git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm work
# no verdict exists yet: the report says spec_unverified — its own
# state, not folded into spec_invalid, and nothing re-runs the
# validator on the report's behalf
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/unv.json"
grep -q '"delivered": false' "$T/unv.json"
grep -q '"outcome": "spec_unverified"' "$T/unv.json"
grep -q '"spec_valid": false' "$T/unv.json"
grep -q '"spec_state": "spec_unverified"' "$T/unv.json"
if grep -q '"spec_state": "spec_invalid"' "$T/unv.json"; then
  echo "FAIL: a missing verdict was reported as spec_invalid"; exit 1; fi

# the validate dispatch's verdict: the test runs the normalized command
# once and signs its passing output
(cd "$REPO" && openspec validate add-nav-bar --strict) > "$T/val.txt" 2>&1
grep -q 'valid' "$T/val.txt" || { echo "FAIL: the valid change rejected"; cat "$T/val.txt"; exit 1; }
$PY "$RT" verdict add-nav-bar --rc 0 --stdout "$(cat "$T/val.txt")" >/dev/null

# no cost step exists (landing L1): the report carries no cost verdict
# delivery before the human answers: merge pending, nothing merged
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/pre.json"
grep -q '"delivered": false' "$T/pre.json"
grep -q '"outcome": "merge_pending"' "$T/pre.json"
$PY "$REPORT" gate --task-dir "$TD" --request >/dev/null
# an approval without a rationale is refused
if $PY "$REPORT" gate --task-dir "$TD" --decision approve --approver tester \
     --rationale "" 2>/dev/null; then
  echo "FAIL: rationale-less approval accepted"; exit 1; fi
$PY "$REPORT" gate --task-dir "$TD" --decision approve --approver tester \
  --rationale "read the diff: the nav bar matches the accepted spec" >/dev/null
# delivered after approval — spec valid, and correctness disclaimed
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --outcome completed --no-design --no-design-by tester --no-design-why 'gate probe' > "$T/rep.json"
grep -q '"delivered": true' "$T/rep.json"
grep -q '"human_state": "Ready"' "$T/rep.json"
grep -q '"spec_valid": true' "$T/rep.json"
grep -q '"machine_checked": false' "$T/rep.json"
if grep -q 'cost_gate\|cost_over\|input_equivalent\|"cap"' "$T/rep.json"; then
  echo "FAIL: the delivery report carries a cost verdict"; exit 1; fi
echo "M1 POSITIVE: pass (valid change → merge approved → delivered, no cost term; not-machine-checked stated)"
