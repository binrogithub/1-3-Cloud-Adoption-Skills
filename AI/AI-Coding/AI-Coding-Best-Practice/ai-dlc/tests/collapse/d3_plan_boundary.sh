#!/usr/bin/env bash
# D3 task 3.9 (reworked after the baseline defect): the boundary check
# judges the INCREMENT a run causes, never the working tree's
# pre-existing state. The first call on an unprepared, already-dirty
# tree records a baseline and claims no violation; after a baseline,
# new paths must sit inside the change dir or the three gateway
# bookkeeping dirs (.agent_history/, coding_memory/, prompt_attachment/).
# A stray new path aborts naming it; nothing is cleaned up.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export AI_DLC_SPECS="$T/specs"
. "$ROOT/tests/collapse/lib_plane.sh"
REPO="$T/repo"
git -C "$T" init -q repo
mkdir -p "$REPO/src"
printf 'legacy\n' > "$REPO/src/legacy.txt"
git -C "$REPO" add src/legacy.txt
git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm seed
# the caller's pre-existing state: an untracked note no role ever wrote
printf 'dev notes\n' > "$REPO/NOTES.md"
C="$REPO/openspec/changes/add-nav-bar"
mkdir -p "$C/specs/website"
cat > "$C/proposal.md" <<'EOF'
## Why

The site has no navigation.

## What Changes

- Add a shared navigation bar to every page.
EOF
cat > "$C/specs/website/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Navigation bar

The site SHALL show a navigation bar on every page.

#### Scenario: Visitor opens any page

- **WHEN** a visitor opens any page
- **THEN** the navigation bar is visible
EOF
# N6: the tree moves into the plane's home and the boundary judges the
# PLANE root from here on — so the pre-existing dirt, the bookkeeping
# dirs and the strays are all planted inside it
plane_migrate "$REPO"
C="$PLANE_TREE/changes/add-nav-bar"
mkdir -p "$PLANE_ROOT/src"
printf 'legacy\n' > "$PLANE_ROOT/src/legacy.txt"
git -C "$PLANE_ROOT" add src/legacy.txt
git -C "$PLANE_ROOT" -c user.name=t -c user.email=t@t commit -qm seed
printf 'dev notes\n' > "$PLANE_ROOT/NOTES.md"
mkdir -p "$PLANE_ROOT/.agent_history" "$PLANE_ROOT/coding_memory/proj" "$PLANE_ROOT/prompt_attachment"
printf 'attachment\n' > "$PLANE_ROOT/prompt_attachment/blob.bin"

# 1. the discriminating test (the defect report): a repo holding only a
#    pre-existing NOTES.md, no role ever dispatched — the boundary gate
#    must NOT claim a violation. First call records the baseline.
$PY "$PLAN" boundary --change add-nav-bar --repo "$REPO" > "$T/base.json"
grep -q '"boundary": "baselined"' "$T/base.json"
grep -q '"NOTES.md"' "$T/base.json" || true   # count-only output; the
grep -q '"baseline_paths": [1-9]' "$T/base.json"
if grep -q '"boundary": "violated"' "$T/base.json"; then
  echo "FAIL: pre-existing dirt flagged with no run having happened"; exit 1; fi

# 2. after the baseline: a NEW path inside the change dir (a role's
#    artifact landing) and bookkeeping paths -> clean, exercising the
#    allowed-root rule itself, not the baseline
printf '## Context\n' > "$C/design.md"
printf '{"actions":[]}\n' > "$PLANE_ROOT/.agent_history/file_ops_plan-add-nav-bar-specs.json"
printf 'sqlite\n' > "$PLANE_ROOT/coding_memory/proj/memory.db"
$PY "$PLAN" boundary --change add-nav-bar --repo "$REPO" > "$T/clean.json"
grep -q '"boundary": "clean"' "$T/clean.json"
grep -q '\.agent_history/file_ops_plan-add-nav-bar-specs\.json' "$T/clean.json"

# 3. a NEW stray path after the baseline -> exit 8 naming it, and the
#    file is still on disk (nothing is cleaned up)
printf 'legacy, tampered\n' >> "$PLANE_ROOT/src/legacy.txt"
set +e
$PY "$PLAN" boundary --change add-nav-bar --repo "$REPO" > "$T/dirty.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 8 ]] || { echo "FAIL: newly-modified tracked file exited $RC, want 8"; cat "$T/dirty.json"; exit 1; }
grep -q '"boundary": "violated"' "$T/dirty.json"
grep -q '"src/legacy.txt"' "$T/dirty.json"
[[ -f "$PLANE_ROOT/src/legacy.txt" ]] || { echo "FAIL: boundary cleaned up a path"; exit 1; }

# 4. an untracked stray added after the baseline is equally refused —
#    while the pre-existing NOTES.md never counts against the run
git -C "$PLANE_ROOT" checkout -q -- src/legacy.txt
printf 'stray\n' > "$PLANE_ROOT/stray-plugin.txt"
set +e
$PY "$PLAN" boundary --change add-nav-bar --repo "$REPO" > "$T/dirty2.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 8 ]] || { echo "FAIL: untracked stray exited $RC, want 8"; cat "$T/dirty2.json"; exit 1; }
grep -q '"stray-plugin.txt"' "$T/dirty2.json"
if grep -q '"NOTES.md"' "$T/dirty2.json"; then
  echo "FAIL: a pre-existing baseline path was named as offending"; exit 1; fi
command rm -f "$PLANE_ROOT/stray-plugin.txt"
$PY "$PLAN" boundary --change add-nav-bar --repo "$REPO" > "$T/clean2.json"
grep -q '"boundary": "clean"' "$T/clean2.json"
echo "D3 PLAN BOUNDARY: pass (pre-existing dirt baselined, never a violation; post-baseline bookkeeping + change-dir clean; new modified and new untracked strays abort naming the path; nothing cleaned up)"
