#!/usr/bin/env bash
# D1 negative ① (devteam delivery-criteria): a change whose requirement
# carries no scenario earns a rejecting validate verdict — the delivery
# MUST NOT report delivered, the outcome is spec_invalid, and the
# verdict's validator output is carried verbatim into the report.
# deliver reads the signed verdict record; it never runs the CLI.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT="$ROOT/bin/report.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
REPO="$T/repo"; TD="$REPO/.ai-dlc/tasks/t"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
# the rejected snippet (m3_pos2's negative): a requirement with no scenario
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
EOF
# the test stands in for the validate dispatch: run the normalized
# command once, sign exactly that output as a rejecting verdict
(cd "$REPO" && openspec validate add-nav-bar --strict) > "$T/val.txt" 2>&1 || true
grep -q 'must include at least one scenario' "$T/val.txt" \
  || { echo "FAIL: the scenario-less spec did not reject"; exit 1; }
$PY "$RT" verdict add-nav-bar --rc 1 --stdout "$(cat "$T/val.txt")" >/dev/null
$PY "$REPORT" init --task-dir "$TD" --repo "$REPO" --route inline --task-id t \
     --change add-nav-bar >/dev/null
# everything else is green: work lands, merge approved with a rationale —
# the invalid spec must still block delivery (no cost term exists)
mkdir -p "$REPO/src"
printf '<nav><a href="/">home</a></nav>\n' > "$REPO/src/nav.html"
git -C "$REPO" add -A; git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm work
$PY "$REPORT" gate --task-dir "$TD" --request >/dev/null
$PY "$REPORT" gate --task-dir "$TD" --decision approve --approver tester \
  --rationale "approved before validation ran" >/dev/null
$PY "$REPORT" deliver --task-dir "$TD" --repo "$REPO" --outcome completed --no-design \
  --no-design-by tester --no-design-why 'gate probe' > "$T/rep.json"
grep -q '"delivered": false' "$T/rep.json"
grep -q '"outcome": "spec_invalid"' "$T/rep.json"
grep -q '"spec_valid": false' "$T/rep.json"
# the validator text is carried verbatim (delivery-criteria scenario)
grep -q 'validator_output' "$T/rep.json"
grep -q 'must include at least one scenario' "$T/rep.json"
grep -q '"machine_checked": false' "$T/rep.json"
echo "M1 NEG1: pass (scenario-less requirement → spec_invalid, validator output carried, not delivered)"
