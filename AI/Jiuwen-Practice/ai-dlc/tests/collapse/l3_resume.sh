#!/usr/bin/env bash
# L3 (landing tasks 3.1-3.4): a stopped planning run resumes instead of
# restarting. Roles whose artifact openspec already reports done are
# skipped and recorded — the client is never invoked for them — while
# the remaining role dispatches through the same deterministic session
# name (the client's contract for a named session is reuse, so the
# re-dispatch continues that conversation). Each attempt lands in
# planning.json, so a resume knows what was reached. A validator
# rejection pending on a role cancels its skip: the artifact file
# exists, but the revision dispatch must run.
#
# The client here is a double standing in for the shipped one
# (AI_DLC_CLIENT) — the flags are the contract; it logs its argv and
# emits one round-complete frame. The repo must sit outside the private
# /tmp namespace, which dispatch rejects before any client runs.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d /root/ai-dlc-l3-XXXXXX); trap 'rm -rf "$T"' EXIT
# the plane's records and key: the statuses a validate verdict carries
# are what the resume skip reads now — the artifact files on disk prove
# nothing to the caller. NOTE (bin/plan.py stale_against bug, worked
# around here): the verdict stamp is UTC but is parsed timezone-naive,
# so on this UTC+8 box the guard reads every verdict as 8h older than
# it is and every accept would exit 22 stale. The test backdates the
# artifact files 9h before each accept so the skewed comparison still
# orders correctly; the bug itself is reported, not patched here.
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
# the fixture lives under /root, which the real plane sees read-only
# (ProtectHome) — these cases exercise the writable class, so the probe
# reads this namespace's view of the path. The three classes and the
# split workspace they imply are covered by ad_any_directory.sh.
export AI_DLC_GATEWAY_ROOT=/

REPO="$T/repo"; TD="$REPO/.ai-dlc/tasks/add-nav-bar-planning"

cat > "$T/stub-client" <<'EOF'
#!/usr/bin/env bash
# a double for the shipped gateway client: log the invocation (one marker
# line per call; the full argv separately — the prompt carries newlines),
# close the round with one genuine final frame
d="${0%/*}"
printf 'call\n' >> "$d/client-calls.log"
printf '%s\n' "$*" >> "$d/client-argv.log"
printf '{"event": "chat.final", "payload": {"content": "artifact written"}}\n'
EOF
chmod +x "$T/stub-client"
export AI_DLC_CLIENT="$T/stub-client"

git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
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
cat > "$C/design.md" <<'EOF'
## Context

A static site; one shared template.

## Goals / Non-Goals

- Goals: one navigation fragment reused by every page
- Non-Goals: dynamic menus

## Decisions

- Build-time injection, no runtime script.

## Risks / Trade-offs

- None measured.
EOF
cat > "$T/pkg.json" <<EOF
{"requirement": "shared navigation across pages", "change_id": "add-nav-bar",
 "capability": "website", "repo": "$REPO"}
EOF

# N6: the artifacts above now live in the plane's tree — migrate the
# repo's openspec surface and point C at the plane copy
. "$ROOT/tests/collapse/lib_plane.sh"
plane_migrate "$REPO"
C="$PLANE_TREE/changes/add-nav-bar"
# the graph record, then the verdict that reports three of four done —
# what the plane's latest validate dispatch would have left behind
$PY "$RT" graph add-nav-bar --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
$PY "$RT" verdict add-nav-bar --rc 0 \
  --artifacts proposal=done,specs=done,design=done --complete false >/dev/null

# 0. (3.4) three of four artifacts done -> exactly one role dispatchable
$PY "$PLAN" roles --change add-nav-bar --repo "$REPO" > "$T/roles.json"
$PY - "$T/roles.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["dispatchable_now"] == ["tasks"], d["dispatchable_now"]
PYEOF

# 1. (3.2) a done artifact is skipped: no client call, skip recorded
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role proposal \
  --package-file "$T/pkg.json" > "$T/skip.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: done-artifact dispatch exited $RC"; cat "$T/skip.json"; exit 1; }
grep -q '"skipped": true' "$T/skip.json"
[[ ! -f "$T/client-calls.log" ]] \
  || { echo "FAIL: the client was invoked for a done artifact"; cat "$T/client-argv.log"; exit 1; }
$PY - "$TD/planning.json" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1]))
assert p["skips"]["proposal"]["reason"] == \
    "openspec reports this artifact done", p.get("skips")
PYEOF

# 2. the remaining role dispatches once; the attempt is recorded
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role tasks \
  --package-file "$T/pkg.json" > "$T/d1.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: tasks dispatch exited $RC"; cat "$T/d1.json"; exit 1; }
grep -q '"session_name": "plan-add-nav-bar-tasks"' "$T/d1.json"
$PY - "$TD/planning.json" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1]))
d = p["dispatches"]["tasks"]
assert d["attempts"] == 1, d
assert d["session_name"] == "plan-add-nav-bar-tasks", d
assert d["round_complete"] is True, d
PYEOF
N=$(grep -c "^call$" "$T/client-calls.log")
[[ "$N" -eq 1 ]] || { echo "FAIL: expected 1 client call, got $N"; exit 1; }

# 3. (3.1) a second dispatch of the same role resumes: same session name
#    sent, prior attempt counted — reuse is the client's contract
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role tasks \
  --package-file "$T/pkg.json" > "$T/d2.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: resume dispatch exited $RC"; cat "$T/d2.json"; exit 1; }
grep -q '"prior_attempts": 1' "$T/d2.json"
N=$(grep -c "^call$" "$T/client-calls.log")
[[ "$N" -eq 2 ]] || { echo "FAIL: expected 2 client calls, got $N"; exit 1; }
grep -c -- "--session plan-add-nav-bar-tasks" "$T/client-argv.log" | grep -q '^2$' \
  || { echo "FAIL: session name not identical across attempts"; cat "$T/client-argv.log"; exit 1; }

# 4. a pending validator rejection cancels the skip: the artifact file
#    exists (status says done) but was returned for revision
cat > "$C/specs/website/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Navigation bar

The site SHALL show a navigation bar on every page.
EOF
# the plane's verdict on that text: a rejection naming the spec file —
# minted AFTER the write, so it is the verdict of what now stands
$PY "$RT" verdict add-nav-bar --rc 1 --stdout \
  '[ERROR] specs/website/spec.md: Requirement "Navigation bar" has no scenarios under it. Requirements must have at least one scenario.' \
  --artifacts proposal=done,specs=done,design=done --complete false >/dev/null
set +e
$PY "$PLAN" accept --change add-nav-bar --repo "$REPO" > "$T/acc1.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 9 ]] || { echo "FAIL: scenario-less spec should exit 9, got $RC"; cat "$T/acc1.json"; exit 1; }
grep -q '"revision_pending"' "$TD/planning.json"
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role specs \
  --package-file "$T/pkg.json" > "$T/d3.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: revision dispatch exited $RC"; cat "$T/d3.json"; exit 1; }
grep -q '"skipped"' "$T/d3.json" \
  && { echo "FAIL: revision dispatch was skipped"; cat "$T/d3.json"; exit 1; }
N=$(grep -c "^call$" "$T/client-calls.log")
[[ "$N" -eq 3 ]] || { echo "FAIL: revision dispatch did not reach the client ($N calls)"; exit 1; }

# 5. once the revision validates and accept passes, the skip returns
cat > "$C/specs/website/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Navigation bar

The site SHALL show a navigation bar on every page.

#### Scenario: Visitor opens any page

- **WHEN** a visitor opens any page
- **THEN** the navigation bar is visible with links to all top-level pages
EOF
# the revision validated: a fresh rc-0 verdict minted after the write
# it speaks for
$PY "$RT" verdict add-nav-bar --rc 0 \
  --artifacts proposal=done,specs=done,design=done,tasks=done --complete true >/dev/null
$PY "$PLAN" accept --change add-nav-bar --repo "$REPO" > "$T/acc2.json" 2>&1 \
  || { echo "FAIL: accepted spec still rejected"; cat "$T/acc2.json"; exit 1; }
$PY - "$TD/planning.json" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1]))
assert "revision_pending" not in p, p.get("revision_pending")
PYEOF
$PY "$PLAN" dispatch --change add-nav-bar --role specs \
  --package-file "$T/pkg.json" > "$T/d4.json" 2>&1 \
  || { echo "FAIL: post-accept skip dispatch failed"; cat "$T/d4.json"; exit 1; }
grep -q '"skipped": true' "$T/d4.json"
N=$(grep -c "^call$" "$T/client-calls.log")
[[ "$N" -eq 3 ]] || { echo "FAIL: client called again after acceptance ($N)"; exit 1; }

echo "L3 RESUME: pass (3 of 4 done -> exactly [tasks] dispatchable; done artifact skipped with no client call and the skip recorded; same-role re-dispatch resumes the named session with prior_attempts; a pending validator rejection cancels the skip; after acceptance it returns)"
