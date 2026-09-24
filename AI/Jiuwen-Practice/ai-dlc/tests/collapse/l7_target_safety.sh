#!/usr/bin/env bash
# L7 (landing tasks 7.1/7.2/7.6/7.8): the chain refuses a target it must
# never write into, and reports a view narrower than the repository
# before the first dispatch. A tree holding source of a dependency this
# project may not modify stops the run BEFORE the client exists, naming
# the paths — while the root-level openspec/ data dir the upstream CLI
# itself creates is expected and never trips the rule. A working tree
# showing fewer files than its head commit (sparse checkout) waits for
# a human to accept the narrower view; --accept-partial-view records
# that acceptance and a resume does not ask again.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d /tmp/ai-dlc-l7t-XXXXXX); trap 'rm -rf "$T"' EXIT
export AI_DLC_SPECS="$T/specs"
. "$ROOT/tests/collapse/lib_plane.sh"
# the plane's records and key live in the test's own world: the task
# role is admitted against the signed graph record and its dependencies
# come from the verdict's statuses, both minted as the plane would
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
# the fixture lives under /root, which the real plane sees read-only
# (ProtectHome) — these cases exercise the writable class, so the probe
# reads this namespace's view of the path. The three classes and the
# split workspace they imply are covered by ad_any_directory.sh.
export AI_DLC_GATEWAY_ROOT=/

REPO="$T/repo"

cat > "$T/stub-client" <<'EOF'
#!/usr/bin/env bash
d="${0%/*}"
printf 'call\n' >> "$d/client-calls.log"
printf '%s\n' "$*" >> "$d/client-argv.log"
printf '{"event": "chat.final", "payload": {"content": "artifact written"}}\n'
EOF
chmod +x "$T/stub-client"
export AI_DLC_CLIENT="$T/stub-client"

git -C "$T" init -q repo
printf 'root\n' > "$REPO/a.txt"
mkdir -p "$REPO/dir"; printf 'b\n' > "$REPO/dir/b.txt"
git -C "$REPO" add -A
git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
C="$REPO/openspec/changes/add-nav-bar"
mkdir -p "$C/specs/website"
$PY "$RT" graph add-nav-bar --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
# the fixture change already carries proposal/specs/design on disk; the
# verdict says the same, so tasks is the dispatchable role (minted after
# the file writes so the verdict is never stale against them)
printf '## Why\n\nNo navigation.\n\n## What Changes\n\n- Add a bar.\n' > "$C/proposal.md"
printf '## ADDED Requirements\n\n### Requirement: Navigation bar\n\nThe site SHALL show one.\n\n#### Scenario: Visitor opens a page\n\n- **WHEN** they do\n- **THEN** the bar is visible\n' > "$C/specs/website/spec.md"
printf '## Context\n\nStatic site.\n\n## Goals / Non-Goals\n\n- Goals: one fragment\n\n## Decisions\n\n- Build-time.\n\n## Risks / Trade-offs\n\n- None.\n' > "$C/design.md"
# N6: the spec tree moves into the plane's home before any dispatch —
# the rounds read and write it there, never in the repo
plane_migrate "$REPO"
$PY "$RT" verdict add-nav-bar --rc 0 \
  --artifacts proposal=done,specs=done,design=done --complete false >/dev/null
cat > "$T/pkg.json" <<EOF
{"requirement": "shared navigation across pages", "change_id": "add-nav-bar",
 "capability": "website", "repo": "$REPO"}
EOF

# 1. (7.1/7.2/7.8) dependency source in the tree stops the run before
#    the client exists, naming the paths; the root-level openspec/ data
#    dir the CLI created does NOT trip the rule
mkdir -p "$REPO/vendor/claude-code-oauth-delegate-router"
printf 'src\n' > "$REPO/vendor/claude-code-oauth-delegate-router/mod.py"
mkdir -p "$REPO/node_modules/@fission-ai/openspec"
printf '{}\n' > "$REPO/node_modules/@fission-ai/openspec/package.json"
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role tasks \
  --package-file "$T/pkg.json" > "$T/f.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 12 ]] || { echo "FAIL: forbidden target exited $RC, want 12"; cat "$T/f.json"; exit 1; }
grep -q '"stopped": "before dispatch' "$T/f.json"
grep -q 'claude-code-oauth-delegate-router' "$T/f.json"
grep -q '@fission-ai/openspec' "$T/f.json"
grep -q 'openspec/changes' "$T/f.json" \
  && { echo "FAIL: the root openspec/ data dir tripped the rule"; cat "$T/f.json"; exit 1; }
[[ ! -f "$T/client-calls.log" ]] \
  || { echo "FAIL: the client ran against a forbidden tree"; cat "$T/client-argv.log"; exit 1; }
[[ ! -d "$REPO/.ai-dlc" ]] \
  || { echo "FAIL: a refused run left a task record behind"; find "$REPO/.ai-dlc"; exit 1; }

# 2. the same tree without the dependency source dispatches (the
#    openspec/ data dir alone is fine; the view is complete and passes
#    silently)
command rm -rf "$REPO/vendor" "$REPO/node_modules"
$PY "$PLAN" dispatch --change add-nav-bar --role tasks \
  --package-file "$T/pkg.json" > "$T/d1.json" 2>&1 \
  || { echo "FAIL: clean dispatch failed"; cat "$T/d1.json"; exit 1; }
grep -q '"round_complete": true' "$T/d1.json"
grep -q '"waiting_on"' "$T/d1.json" \
  && { echo "FAIL: a complete view did not pass silently"; cat "$T/d1.json"; exit 1; }
[[ "$(grep -c '^call$' "$T/client-calls.log")" -eq 1 ]]

# 3. (7.6) a sparse working tree is a partial view: reported before the
#    first dispatch of the change, stating what the roles will and will
#    not see; the run waits for a human
git -C "$REPO" sparse-checkout init --cone
git -C "$REPO" sparse-checkout set onlyroot >/dev/null 2>&1
[[ -f "$REPO/dir/b.txt" ]] && { echo "FAIL: fixture is not sparse"; exit 1; }
set +e
$PY "$PLAN" dispatch --change add-nav-bar --role tasks \
  --package-file "$T/pkg.json" > "$T/v1.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: partial view exited $RC, want 1"; cat "$T/v1.json"; exit 1; }
grep -q '"waiting_on": "human view acceptance"' "$T/v1.json"
grep -q '"state": "partial"' "$T/v1.json"
grep -q '"dir/b.txt"' "$T/v1.json"
grep -q 'roles_will_not_see' "$T/v1.json"
[[ "$(grep -c '^call$' "$T/client-calls.log")" -eq 1 ]] \
  || { echo "FAIL: dispatched a partial view without acceptance"; exit 1; }

# 4. --accept-partial-view records the acceptance and proceeds; a
#    resume does not ask again
$PY "$PLAN" dispatch --change add-nav-bar --role tasks \
  --package-file "$T/pkg.json" --accept-partial-view > "$T/v2.json" 2>&1 \
  || { echo "FAIL: accepted-view dispatch failed"; cat "$T/v2.json"; exit 1; }
grep -q '"view"' "$T/v2.json"
[[ "$(grep -c '^call$' "$T/client-calls.log")" -eq 2 ]]
$PY - "$REPO/.ai-dlc/tasks/add-nav-bar-planning/planning.json" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1]))
assert p["view"]["accepted"] is True, p.get("view")
assert p["view"]["state"] == "partial", p["view"]
PYEOF
$PY "$PLAN" dispatch --change add-nav-bar --role tasks \
  --package-file "$T/pkg.json" > "$T/v3.json" 2>&1 \
  || { echo "FAIL: resume after acceptance asked again"; cat "$T/v3.json"; exit 1; }
grep -q '"waiting_on"' "$T/v3.json" \
  && { echo "FAIL: a resume re-asked for view acceptance"; cat "$T/v3.json"; exit 1; }
[[ "$(grep -c '^call$' "$T/client-calls.log")" -eq 3 ]]

echo "L7 TARGET SAFETY: pass (dependency source -> exit 12 before the client, paths named, openspec/ data dir exempt, nothing recorded; clean tree dispatches; sparse view waits on a human naming what the roles will not see; --accept-partial-view records and proceeds; a resume does not re-ask)"
