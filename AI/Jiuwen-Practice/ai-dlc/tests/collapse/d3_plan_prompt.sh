#!/usr/bin/env bash
# D3 task 3.2/3.3 (open-plane O2): the prompt carries the handoff
# package, the artifact identity, the write boundary and the instruction
# to obtain the authoring guidance from the CLI through the authoring
# skill — the guidance itself is NOT copied in and no clause states the
# shell is unavailable — and a handoff package naming a file count, a
# module count or a directory layout is rejected BEFORE any dispatch, as
# is a role owning no artifact and a package missing a key.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world; the caller
# (plan.py) reads only what these hold. The openspec calls this test
# still makes are the TEST standing in for the plane — the guidance the
# CLI returns is the data the not-copied-in assertion compares against.
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
REPO="$T/repo"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
# the graph dispatch's record, plus the statuses a validate verdict
# carries: proposal done, so the specs role's dependency is satisfied
$PY "$RT" graph add-nav-bar --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
$PY "$RT" verdict add-nav-bar --rc 0 --artifacts proposal=done --complete false >/dev/null
C="$REPO/openspec/changes/add-nav-bar"
mkdir -p "$C/specs/website"
cat > "$C/proposal.md" <<'EOF'
## Why

The site has no navigation; visitors cannot move between pages.

## What Changes

- Add a shared navigation bar to every page.

## Capabilities

### spec: `website`

Navigation behavior of the public site.
EOF
cat > "$T/pkg.json" <<EOF
{"requirement": "Visitors cannot move between pages; the site needs navigation on every page.", "change_id": "add-nav-bar", "capability": "website", "repo": "$REPO"}
EOF

# 1. assembly (open-plane): the requirement verbatim, the artifact
#    identity and write boundary, the CLI instruction for THIS artifact,
#    the language — and NOT a copy of the guidance the CLI returns
$PY "$PLAN" prompt --change add-nav-bar --role specs --package-file "$T/pkg.json" > "$T/p.json"
$PY - "$T/p.json" "$REPO" <<'PYEOF'
import json, subprocess, sys
d = json.load(open(sys.argv[1]))
repo, prompt = sys.argv[2], d["prompt"]
up = json.loads(subprocess.run(
    ["openspec", "instructions", "specs", "--change", "add-nav-bar", "--json"],
    cwd=repo, capture_output=True, text=True).stdout)
assert d["package"]["requirement"] in prompt
# the guidance is deliberately NOT copied in: the role fetches it itself
assert up["instruction"] not in prompt, "authoring guidance copied into the prompt"
assert up["template"] not in prompt, "template copied into the prompt"
assert up["outputPath"] not in prompt
# the instruction to fetch it, named for this artifact and change
assert "openspec instructions specs --change add-nav-bar --json" in prompt
assert "openspec-author" in prompt
assert "artifact: specs" in prompt
assert "write boundary: openspec/changes/add-nav-bar/" in prompt
# the CLI-unavailable contract the role reports against
assert "OPENSPEC_CLI_UNAVAILABLE:" in prompt
# no clause describes the retired closed runtime
assert "Treat the bash tool as UNAVAILABLE" not in prompt
assert "native file tools" not in prompt
assert "Write your artifact in English." in prompt
assert d["prompt_bytes"] == len(prompt.encode("utf-8"))
PYEOF

# 2. shape rejection before dispatch: a file count names structure, not
#    behaviour; the error names the offending phrase
cat > "$T/pkg5.json" <<EOF
{"requirement": "Create 5 files and 3 modules under the site tree.", "change_id": "add-nav-bar", "capability": "website", "repo": "$REPO"}
EOF
set +e
$PY "$PLAN" prompt --change add-nav-bar --role specs --package-file "$T/pkg5.json" > "$T/shape.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 3 ]] || { echo "FAIL: shape rejection exited $RC, want 3"; exit 1; }
grep -q '"phrase": "5 files"' "$T/shape.json"

# 3. a role owning no artifact is rejected (verifier is not an artifact
#    of the spec-driven schema — no verification role exists)
set +e
$PY "$PLAN" prompt --change add-nav-bar --role verifier --package-file "$T/pkg.json" > "$T/role.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 4 ]] || { echo "FAIL: role rejection exited $RC, want 4"; exit 1; }
grep -q 'role owning no artifact rejected' "$T/role.json"

# 4. a package missing a key is rejected naming the key
cat > "$T/pkgmiss.json" <<EOF
{"requirement": "Add navigation.", "change_id": "add-nav-bar", "repo": "$REPO"}
EOF
set +e
$PY "$PLAN" prompt --change add-nav-bar --role specs --package-file "$T/pkgmiss.json" > "$T/miss.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 5 ]] || { echo "FAIL: missing-key rejection exited $RC, want 5"; exit 1; }
grep -q '"missing_key": "capability"' "$T/miss.json"

# 5. (landing L1.9) a package carrying a budget key is rejected, naming
#    the key — budgeting is not provided upstream, and no token figure
#    is computed, capped or reported anywhere in the plane
cat > "$T/pkgbud.json" <<EOF
{"requirement": "Add navigation.", "change_id": "add-nav-bar", "capability": "website", "repo": "$REPO", "budget": 250000}
EOF
set +e
$PY "$PLAN" prompt --change add-nav-bar --role specs --package-file "$T/pkgbud.json" > "$T/bud.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 5 ]] || { echo "FAIL: budget-key rejection exited $RC, want 5"; exit 1; }
grep -q '"missing_key": "budget"' "$T/bud.json"
grep -q 'not provided upstream' "$T/bud.json"
# and no budget line appears in an assembled prompt (checked via case 1's
# prompt, which carries no budget key at all)
if grep -qi 'budget' "$T/p.json"; then
  echo "FAIL: an assembled role prompt mentions budget"; exit 1; fi
echo "D3 PLAN PROMPT: pass (handoff + artifact identity + write boundary + CLI fetch instruction + language, guidance NOT copied in, no retired-constraint clause; file-count shape, role-owns-no-artifact, missing-key and budget-key all rejected before dispatch; no budget line in the prompt)"
