#!/usr/bin/env bash
# open-plane: the checked boundaries and the scripted runtime.
#
# The author is not the judge — now by inspection, not by withholding:
# a dispatch whose frames show the role running the validator fails
# naming the invocation (13) and the artifact is not accepted on that
# dispatch; a command removing or rewriting a pre-dispatch baseline
# path fails naming the command and the path (14); a role reporting it
# could not run the CLI fails carrying its own account (15). The
# authoring skill gate refuses before the client exists (16). A prompt
# clause naming a constraint the runtime no longer imposes fails the
# surface audit (17). The provisioning mode edits with a backup, names
# the backup when the gateway does not come back, and a second run
# reports no change without a restart.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
INSTALL="$ROOT/install.sh"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export AI_DLC_SPECS="$T/specs"
. "$ROOT/tests/collapse/lib_plane.sh"
# the plane's records and key live in the test's own world: the design
# dispatch in case 5 is admitted against the signed graph record, with
# its dependency (proposal) done in the verdict's statuses
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
REPO="$T/repo"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
$PY "$RT" graph greet --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
mkdir -p "$REPO/openspec/changes/greet/specs/greeting"
cat > "$REPO/openspec/changes/greet/proposal.md" <<'EOF'
## Why

Nothing greets the caller.

## What Changes

- Greet the caller.

## Capabilities

### spec: `greeting`

Greeting behavior.
EOF
# N6: the spec tree moves into the plane's home; every write below
# lands there
plane_migrate "$REPO"
# the repo's class is pinned by a fixture, not by the live unit: a
# probe root whose view lacks the repo (invisible — the staged-copy
# path case 5 exercises). At write time the class came from the live
# unit's PrivateTmp; the 2026-09-01 open-sandbox decision retired
# that, and these cases must hold in either regime
mkdir -p "$T/probe"
export AI_DLC_GATEWAY_ROOT="$T/probe"
C="$PLANE_TREE/changes/greet"
cat > "$T/pkg.json" <<EOF
{"requirement": "The greeter SHALL greet the caller by name.", "change_id": "greet", "capability": "greeting", "repo": "$REPO"}
EOF
$PY "$RT" verdict greet --rc 0 --artifacts proposal=done --complete false >/dev/null

frame() { # frame <tool_call-id> <command>  |  --final <text>
  if [[ "$1" == "--final" ]]; then
    "$PY" -c 'import json,sys; print(json.dumps({"type":"event","event":"chat.final","payload":{"event_type":"chat.final","content":sys.argv[1]}}))' "$2"
  else
    "$PY" -c 'import json,sys; print(json.dumps({"type":"event","event":"chat.tool_call","payload":{"event_type":"chat.tool_call","tool_call":{"name":"bash","arguments":json.dumps({"command":sys.argv[2]}),"tool_call_id":sys.argv[1]}}}))' "$1" "$2"
  fi
}

# 1. (O3.3) a role told to validate its own output fails the dispatch:
#    the frames carry the validator invocation; it is named verbatim
frame c1 "openspec instructions specs --change greet --json" > "$T/v.jsonl"
frame c2 "openspec validate greet --strict" >> "$T/v.jsonl"
frame --final "It validated." >> "$T/v.jsonl"
set +e
$PY "$PLAN" dispatch --change greet --role specs --package-file "$T/pkg.json" --frames-file "$T/v.jsonl" > "$T/v.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 13 ]] || { echo "FAIL: validator reverse exited $RC, want 13"; cat "$T/v.out"; exit 1; }
grep -q 'openspec validate greet --strict' "$T/v.out"
grep -q 'the author judged its own output' "$T/v.out"

# 2. (O3.3, accept side) the artifact of that dispatch is not accepted:
#    accept refuses before the validator runs, naming the role
mkdir -p "$T/task/gates"
cat > "$T/task/planning.json" <<EOF
{"change": "greet", "dispatches": {"specs": {"session_name": "plan-greet-specs", "attempts": 1, "frame_violations": {"validator_invocations": [{"command": "openspec validate greet --strict", "tool": "bash", "tool_call_id": "c2"}]}}}}
EOF
cat > "$C/specs/greeting/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Greet

The greeter SHALL greet.

#### Scenario: Greeting

- **WHEN** the caller arrives
- **THEN** the greeter greets
EOF
set +e
$PY "$PLAN" accept --change greet --repo "$REPO" --task-dir "$T/task" > "$T/acc.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 13 ]] || { echo "FAIL: accept after violation exited $RC, want 13"; cat "$T/acc.out"; exit 1; }
grep -q '"artifact": "specs"' "$T/acc.out"
grep -q 'not accepted on that dispatch' "$T/acc.out"

# 3. (O3.4) a role told to delete a pre-existing file fails the
#    dispatch: the command and the baseline path are both named
frame c1 "openspec instructions specs --change greet --json" > "$T/d.jsonl"
frame c2 "rm -f notes.txt && echo gone" >> "$T/d.jsonl"
frame --final "Deleted." >> "$T/d.jsonl"
echo '["notes.txt", "pkg.json"]' > "$T/baseline.json"
set +e
$PY "$PLAN" dispatch --change greet --role specs --package-file "$T/pkg.json" --frames-file "$T/d.jsonl" --baseline-file "$T/baseline.json" > "$T/d.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 14 ]] || { echo "FAIL: destructive reverse exited $RC, want 14"; cat "$T/d.out"; exit 1; }
grep -q 'rm -f notes.txt' "$T/d.out"
grep -q '"baseline_path": "notes.txt"' "$T/d.out"

# 3b. the same command against a path nothing carried is not a
#     violation: the scan judges against the baseline, not the bin
frame c1 "rm -rf $T/scratch-dir" > "$T/ok.jsonl"
frame --final "Cleaned." >> "$T/ok.jsonl"
set +e
$PY "$PLAN" dispatch --change greet --role specs --package-file "$T/pkg.json" --frames-file "$T/ok.jsonl" --baseline-file "$T/baseline.json" > "$T/ok.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: clean removal outside baseline exited $RC, want 0"; cat "$T/ok.out"; exit 1; }

# 4. (O2.4) a role that reports it could not run the CLI fails the
#    dispatch carrying its own account; no workaround from the caller
frame --final "Stopped.
OPENSPEC_CLI_UNAVAILABLE: bash returned 127 — openspec: command not found" > "$T/u.jsonl"
set +e
$PY "$PLAN" dispatch --change greet --role specs --package-file "$T/pkg.json" --frames-file "$T/u.jsonl" > "$T/u.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 15 ]] || { echo "FAIL: cli-unavailable exited $RC, want 15"; cat "$T/u.out"; exit 1; }
grep -q 'openspec: command not found' "$T/u.out"
grep -q 'role_account' "$T/u.out"

# 5. (O2.5) the authoring skill gate: not installed → refused with the
#    remedy before the client exists (16); installed+registered → the
#    gate passes and the next admission (the /tmp target) answers
mkdir -p "$T/empty-skills"
set +e
AI_DLC_SKILLS_DIR="$T/empty-skills" $PY "$PLAN" dispatch --change greet --role proposal --package-file "$T/pkg.json" > "$T/s1.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 16 ]] || { echo "FAIL: skill gate exited $RC, want 16"; cat "$T/s1.out"; exit 1; }
grep -q 'client was never invoked' "$T/s1.out"
grep -q 'install the openspec-author skill' "$T/s1.out"
mkdir -p "$T/skills/openspec-author"
printf -- '---\nname: openspec-author\ndescription: fixture\n---\n' > "$T/skills/openspec-author/SKILL.md"
printf '{"installed_plugins": [{"name": "openspec-author"}]}' > "$T/skills/skills_state.json"
# installed+registered → the gate passes, and the /tmp target the plane
# cannot see answers by being READ through a staged copy (any-directory
# under N6): the copy sits inside the plane's writable area while the
# round itself writes the plane's own tree
mkdir -p "$T/plane"
cat > "$T/stub" <<'STUB'
#!/usr/bin/env bash
cwd=""; prev=""
for a in "$@"; do [ "$prev" = "--cwd" ] && cwd="$a"; prev="$a"; done
printf '%s\n' "$*" >> "${0%/*}/stub-argv.log"
printf '## Why\n\nThe design.\n' > "$cwd/openspec/changes/greet/design.md"
printf '{"type":"event","event":"chat.tool_call","payload":{"tool_name":"write_file","arguments":"{\"path\": \"$cwd/openspec/changes/greet/design.md\"}"}}\n'
printf '{"type":"event","event":"chat.final","payload":{"event_type":"chat.final","content":"design written"}}\n'
STUB
chmod +x "$T/stub"
set +e
AI_DLC_SKILLS_DIR="$T/skills" AI_DLC_CLIENT="$T/stub" AI_DLC_PLANE_ROOT="$T/plane" \
  $PY "$PLAN" dispatch --change greet --role design --package-file "$T/pkg.json" > "$T/s2.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: skill present but the round failed (exit $RC)"; cat "$T/s2.out"; exit 1; }
grep -q '"kind": "plane"' "$T/s2.out"
grep -q '"read": "snapshot"' "$T/s2.out"
COPY=$($PY -c 'import json,sys; print(json.load(open(sys.argv[1]))["workspace"]["project"])' "$T/s2.out")
[[ "$COPY" == "$T/plane/.ai-dlc/stage/"* ]] || { echo "FAIL: the round did not read through a staged copy ($COPY)"; cat "$T/s2.out"; exit 1; }
grep -q -- "--cwd $(plane_of "$REPO")" "$T/stub-argv.log" || { echo "FAIL: the client cwd was not the plane root"; cat "$T/stub-argv.log"; exit 1; }
grep -q -- "--trusted-dir $COPY" "$T/stub-argv.log" || { echo "FAIL: the copy was not granted for reading"; cat "$T/stub-argv.log"; exit 1; }
[[ ! -e "$REPO/.ai-dlc" ]] || { echo "FAIL: the staged round wrote bookkeeping into the /tmp source"; exit 1; }

# 6. (O4.4) the surface audit: a prompt clause naming a constraint the
#    runtime no longer imposes fails it, naming the clause — and the
#    assembled prompt of this plane carries none
$PY - "$PLAN" <<'PYEOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("plan", sys.argv[1])
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)
retired = ("Treat the bash tool as UNAVAILABLE this round: the round runs "
           "headless, so any permission ask interrupts the whole round. Do "
           "everything with the native file tools (list_files, read_file, "
           "write_file).")
labels = plan.prompt_surface_audit(retired)
assert "shell-unavailable clause" in labels, labels
assert "native-tools-only restriction" in labels, labels
assert plan.prompt_surface_audit(
    "openspec instructions specs --change greet --json via the "
    "openspec-author skill; write boundary: openspec/changes/greet/") == []
print("surface audit discriminates: OK")
PYEOF

# 7. (O1) provisioning on fixtures: the edits carry a backup, the unit
#     narrows to exactly the runtime dir and the project root, and a
#     gateway that does not come back exits non-zero naming the backup
mkdir -p "$T/gw"
cat > "$T/gw/config.yaml" <<'EOF'
a2ui:
  enabled: false
tools:
  bash: {enabled: true}
permissions:
  defaults:
    '*': allow
  enabled: true
  external_directory:
    '*': ask
EOF
cat > "$T/gw/unit.service" <<'EOF'
[Unit]
Description=fixture

[Service]
ExecStart=/bin/sleep 1
ProtectSystem=strict
ReadWritePaths=/root/.jiuwenswarm
ReadWritePaths=/opt/workspace-root-fixture
ReadWritePaths=/opt/extra

[Install]
WantedBy=multi-user.target
EOF
set +e
AI_DLC_GW_CONFIG="$T/gw/config.yaml" AI_DLC_GW_UNIT="$T/gw/unit.service" \
  AI_DLC_GW_SERVICE=dead-fixture-svc AI_DLC_CLIENT="$T/gw/no-client" \
  "$INSTALL" --provision-plane > "$T/p1.out" 2>&1
RC=$?
set -e
[[ "$RC" -ne 0 ]] || { echo "FAIL: dead gateway provisioned successfully"; cat "$T/p1.out"; exit 1; }
grep -q 'restore from:' "$T/p1.out"
ls "$T/gw"/config.yaml.bak.pre-open-plane.* >/dev/null 2>&1
ls "$T/gw"/unit.service.bak.pre-open-plane.* >/dev/null 2>&1
grep -q '^  enabled: false$' "$T/gw/config.yaml"
grep -q 'bash: {enabled: true}' "$T/gw/config.yaml"
[[ "$(grep -c '^ReadWritePaths=' "$T/gw/unit.service")" -eq 2 ]] \
  || { echo "FAIL: unit not narrowed to exactly two grants"; grep ReadWritePaths "$T/gw/unit.service"; exit 1; }
grep -q '/opt/extra' <(grep '^ReadWritePaths=' "$T/gw/unit.service") \
  && { echo "FAIL: the extra writable path survived"; exit 1; } || true

# 8. (O1) a second run against an already-provisioned fixture reports
#     no change and skips the restart (the active real service answers
#     is-active; the stub client answers the probe; nothing restarts)
cat > "$T/gw/stub-client" <<'EOF'
#!/usr/bin/env bash
tok="$(grep -o '[0-9a-f]\{32\}' <<<"$*" | head -1)"
printf '%s\n' "{\"event\":\"chat.final\",\"payload\":{\"content\":\"$(printf '%s' "$tok" | tr 'a-z' 'A-Z')\"}}"
EOF
chmod +x "$T/gw/stub-client"
set +e
AI_DLC_GW_CONFIG="$T/gw/config.yaml" AI_DLC_GW_UNIT="$T/gw/unit.service" \
  AI_DLC_GW_SERVICE=jiuwenswarm-gateway AI_DLC_CLIENT="$T/gw/stub-client" \
  "$INSTALL" --provision-plane > "$T/p2.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: idempotent second run exited $RC"; cat "$T/p2.out"; exit 1; }
grep -q 'no change, no restart' "$T/p2.out"
[[ "$(ls "$T/gw"/config.yaml.bak.pre-open-plane.* 2>/dev/null | wc -l)" -eq 1 ]] \
  || { echo "FAIL: the no-change run took another backup"; ls "$T/gw"; exit 1; }

# 9. (O1.8/O1.9) the health check reports the engine state, the
#     writable grant and the cost — and names a path beyond the project
#     root as a finding
cp "$T/gw/unit.service" "$T/gw/unit-wide.service"
printf 'ReadWritePaths=/opt/extra\n' >> "$T/gw/unit-wide.service"
AI_DLC_GW_CONFIG="$T/gw/config.yaml" AI_DLC_GW_UNIT="$T/gw/unit-wide.service" \
  "$INSTALL" --doctor > "$T/doc.out" 2>&1 || true
grep -q 'permission engine: disabled — the plane is OPEN' "$T/doc.out"
grep -q 'what being open removes' "$T/doc.out"
grep -q 'high-severity shell rules' "$T/doc.out"
grep -q 'only remaining boundary' "$T/doc.out"
grep -q 'finding: writable path beyond the project root — /opt/extra' "$T/doc.out" \
  || { echo "FAIL: the extra writable path was not named as a finding"; cat "$T/doc.out"; exit 1; }

echo "OPEN PLANE: pass (validator invocation 13 + not-accepted; baseline destruction 14 with the clean counterpart; CLI-unavailable 15 with the account; skill gate 16 discriminating; surface audit 17 discriminating; provisioning edits+backup+naming+idempotent; doctor engine/cost/finding)"
