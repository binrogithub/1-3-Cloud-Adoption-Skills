#!/usr/bin/env bash
# D4 tasks 4.3-4.7: the reverse cases of the runtime authorisation record.
# A target under the gateway's private temporary namespace is refused
# before the client is invoked; a run blocked by an interrupt exits
# non-zero naming the tool and its argument even when the final envelope
# claims success; a product-file write outside the change dir aborts the
# task naming the path; a role owning no artifact is rejected; a package
# naming a file count is rejected before any dispatch (nothing written).
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# the plane's records and key live in the test's own world: preflight
# admits a role only against the signed graph record, and the test
# stands in for the graph dispatch that produces it
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
REPO="$T/repo"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
$PY "$RT" graph deny-test --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
C="$REPO/openspec/changes/deny-test"
mkdir -p "$C/specs/x"
cat > "$T/pkg.json" <<EOF
{"requirement": "Write a file named note.md containing the word hello.", "change_id": "deny-test", "capability": "x", "repo": "$REPO"}
EOF

# 1. (4.3/4.5, rewritten by any-directory) a target under /tmp is one the
#    gateway cannot see at all (PrivateTmp) — it is no longer refused: a
#    self-contained copy is staged inside the plane's writable area and
#    the round runs against the copy, never against the /tmp path, and
#    the source gains no bookkeeping
mkdir -p "$T/plane"
export AI_DLC_PLANE_ROOT="$T/plane"
# N6: the write side of every round is the plane's own tree — the
# target's surface is migrated into the test's specs home first
. "$ROOT/tests/collapse/lib_plane.sh"
plane_migrate "$REPO"
# the invisible class is pinned by a fixture, not by the live unit: a
# probe root whose view lacks the repo. At write time the class came
# from the live unit's PrivateTmp; the 2026-09-01 open-sandbox decision
# retired that, and these cases must hold in either regime
mkdir -p "$T/probe"
export AI_DLC_GATEWAY_ROOT="$T/probe"
cat > "$T/stub" <<'STUB'
#!/usr/bin/env bash
cwd=""; prev=""
for a in "$@"; do [ "$prev" = "--cwd" ] && cwd="$a"; prev="$a"; done
printf '%s\n' "$*" >> "${0%/*}/stub-argv.log"
mkdir -p "$cwd/openspec/changes/deny-test"
printf '# Proposal\n\n## Why\n\nstaged round\n' > "$cwd/openspec/changes/deny-test/proposal.md"
printf '{"type":"event","event":"chat.tool_call","payload":{"tool_name":"write_file","arguments":"{\"path\": \"$cwd/openspec/changes/deny-test/proposal.md\"}"}}\n'
printf '{"type":"event","event":"chat.final","payload":{"event_type":"chat.final","content":"proposal written"}}\n'
STUB
chmod +x "$T/stub"
export AI_DLC_CLIENT="$T/stub"
set +e
$PY "$PLAN" dispatch --change deny-test --role proposal --package-file "$T/pkg.json" > "$T/tmp.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: /tmp target exited $RC, want a staged round"; cat "$T/tmp.json"; exit 1; }
grep -q '"kind": "plane"' "$T/tmp.json"
grep -q '"read": "snapshot"' "$T/tmp.json"
grep -q 'private temporary namespace' "$T/tmp.json"
grep -q '"self_contained": true' "$T/tmp.json"
# the client ran with the plane's tree as its working directory and the
# copy granted as the trusted read side — never the /tmp path itself
COPY=$($PY -c 'import json,sys; print(json.load(open(sys.argv[1]))["workspace"]["stage"])' "$T/tmp.json")
[[ "$COPY" == "$T/plane/.ai-dlc/stage/"* ]] || { echo "FAIL: the round did not read a staged copy ($COPY)"; cat "$T/tmp.json"; exit 1; }
grep -q -- "--cwd $PLANE_ROOT" "$T/stub-argv.log" || { echo "FAIL: the client cwd was not the plane tree"; cat "$T/stub-argv.log"; exit 1; }
grep -q -- "--trusted-dir $COPY" "$T/stub-argv.log" || { echo "FAIL: the copy was not granted as the read side"; cat "$T/stub-argv.log"; exit 1; }
# the artifact landed in the plane's tree — the copy stays exactly a copy
[[ -f "$PLANE_TREE/changes/deny-test/proposal.md" ]] || { echo "FAIL: the artifact is not in the plane tree"; exit 1; }
[[ ! -f "$COPY/openspec/changes/deny-test/proposal.md" ]] || { echo "FAIL: the round wrote its artifact into the read-side copy"; exit 1; }
[[ ! -e "$REPO/.ai-dlc" ]] || { echo "FAIL: an invisible-source round wrote task bookkeeping into it"; find "$REPO/.ai-dlc" -type f; exit 1; }
[[ ! -e "$REPO/openspec/changes/deny-test/proposal.md" ]] || { echo "FAIL: the round wrote into the /tmp source"; exit 1; }

# 2. (4.4) a run blocked by an interrupt must exit non-zero and must NOT
#    report success: the frames carry an interrupt naming tool+argument
#    AND a final envelope claiming ok — the envelope never decides alone
cat > "$T/interrupt.jsonl" <<EOF
{"type":"event","event":"chat.delta","payload":{"text":"I will write the note outside the change dir"}}
{"type":"event","event":"chat.ask_user_question","payload":{"event_type":"chat.ask_user_question","request_id":"r9","source":"permission_interrupt","tool_name":"write_file","tool_args":{"path":"$REPO/src/leak.txt"},"questions":[{"question":"requires permission: write_file $REPO/src/leak.txt","header":"Permission","options":["allow","deny"],"multi_select":false}]}}
{"type":"event","event":"chat.processing_status","payload":{"is_processing":false}}
{"type":"event","event":"chat.final","payload":{"ok":true,"status":"ok","content":"note.md written as asked"}}
EOF
set +e
$PY "$PLAN" dispatch --change deny-test --role proposal --package-file "$T/pkg.json" --frames-file "$T/interrupt.jsonl" > "$T/int.json" 2>&1
RC=$?
set -e
[[ "$RC" -ne 0 ]] || { echo "FAIL: an interrupted run exited 0"; cat "$T/int.json"; exit 1; }
[[ "$RC" -eq 7 ]] || { echo "FAIL: interrupted run exited $RC, want 7"; cat "$T/int.json"; exit 1; }
grep -q '"interrupted": true' "$T/int.json"
grep -q '"tool": "write_file"' "$T/int.json"
grep -q 'leak\.txt' "$T/int.json"
grep -q '"final_envelope_claims_ok": true' "$T/int.json"
# the output carries no success verdict of its own
if grep -q '"status": "ok"' "$T/int.json" || grep -q '"accepted": true' "$T/int.json"; then
  echo "FAIL: an interrupted run reported success"; cat "$T/int.json"; exit 1
fi

# 3. (4.5) a role writing a product file outside the change dir aborts
#    the task and names the path: baseline the tree first (pre-existing
#    state is never a role's), then the frames above show the write
#    tool_call to src/leak.txt, the file is really in the tree, and the
#    boundary check refuses to pass the INCREMENT — nothing is cleaned up
mkdir -p "$PLANE_ROOT/src"
$PY "$PLAN" boundary --change deny-test --repo "$REPO" > "$T/bbase.json"
grep -q '"boundary": "baselined"' "$T/bbase.json"
printf 'product surface leak\n' > "$PLANE_ROOT/src/leak.txt"
grep -q 'chat.tool_call\|write_file' "$T/interrupt.jsonl"
set +e
$PY "$PLAN" boundary --change deny-test --repo "$REPO" > "$T/bnd.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 8 ]] || { echo "FAIL: product-file write exited $RC, want 8"; cat "$T/bnd.json"; exit 1; }
grep -q '"boundary": "violated"' "$T/bnd.json"
grep -q '"src/leak.txt"' "$T/bnd.json"
[[ -f "$PLANE_ROOT/src/leak.txt" ]] || { echo "FAIL: boundary cleaned up a path"; exit 1; }

# 4. (4.6) a proposed role owning no artifact is rejected (exit 4) —
#    verifier is not an artifact of the spec-driven schema
set +e
$PY "$PLAN" prompt --change deny-test --role verifier --package-file "$T/pkg.json" > "$T/role.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 4 ]] || { echo "FAIL: role-owns-no-artifact exited $RC, want 4"; cat "$T/role.json"; exit 1; }
grep -q 'role owning no artifact rejected' "$T/role.json"

# 5. (4.7) a package naming a file count is rejected before dispatch:
#    exit 3, the phrase is named, and no evidence/frames file is created
cat > "$T/pkg5.json" <<EOF
{"requirement": "Create 5 files for the note feature under the site tree.", "change_id": "deny-test", "capability": "x", "repo": "$REPO"}
EOF
# (the run's own record lives inside the copy for an invisible target,
# reused across this test's cases — so the assertion is on what the
# shape-rejected dispatch ADDED: nothing. The earlier cases' evidence
# stands; a shape rejection must not add a single file to it)
BEFORE=$(find "$COPY/.ai-dlc" -type f 2>/dev/null | sort; true)
set +e
$PY "$PLAN" dispatch --change deny-test --role proposal --package-file "$T/pkg5.json" > "$T/shape.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 3 ]] || { echo "FAIL: file-count package exited $RC, want 3"; cat "$T/shape.json"; exit 1; }
grep -q '"phrase": "5 files"' "$T/shape.json"
AFTER=$(find "$COPY/.ai-dlc" -type f 2>/dev/null | sort; true)
[[ "$BEFORE" == "$AFTER" ]] || { echo "FAIL: a shape-rejected dispatch added task bookkeeping:"; diff <(echo "$BEFORE") <(echo "$AFTER"); exit 1; }
echo "D4 REVERSE CASES: pass (a /tmp target the gateway cannot see runs against a staged copy, the source untouched; interrupt exits 7 naming tool+argument with no success verdict despite the envelope; product-file write aborts exit 8 naming src/leak.txt; role owning no artifact exit 4; file-count package exit 3 before dispatch, nothing written)"
