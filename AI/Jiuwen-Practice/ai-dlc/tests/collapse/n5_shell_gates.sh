#!/usr/bin/env bash
# N5 (PRD §7): the CC runtime shell. G2-G5 run in the REAL aidlc-shell
# — a systemd transient unit with NoNewPrivileges, an empty
# CapabilityBoundingSet and InaccessiblePaths over every openspec
# entry on PATH, the node module tree behind it, and the plane's specs
# home. No fixture stands in for the unit: every probe goes through
# bin/aidlc-shell itself. The positive controls matter as much as the
# gates (G9's lesson — a shut system is not a contained one): the
# caller's own surface keeps working inside the shell, and the
# plane-sight CLIs stop HONESTLY, naming the mask, instead of judging
# blind or prescribing a migrate that cannot run.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
SHELL_BIN="$ROOT/bin/aidlc-shell"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d /root/ai-dlc-n5-XXXXXX)
# the caller's records and key live in the test's own world; the specs
# home is deliberately NOT overridden — the gates must bite on the
# plane's real home
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
mkdir -p "$AI_DLC_RECORDS"
$PY "$RT" key
cleanup() { command rm -rf "$T"; }
trap cleanup EXIT

insh() {  # run one shell command inside the REAL unit, output cleaned
  "$SHELL_BIN" -- /bin/sh -c "$1" 2>&1 \
    | grep -Ev '^Running as unit|^Finished with|^Main processes|^Service runtime' \
    || true
}

# 1. the mask names the three surfaces: the CLI entry, the module tree
#    behind it, the plane's specs home
"$SHELL_BIN" --print-mask > "$T/mask.txt"
grep -qx "/usr/local/bin/openspec" "$T/mask.txt" \
  || { echo "FAIL: the CLI entry is not masked"; cat "$T/mask.txt"; exit 1; }
MOD=$(grep -v "^/usr/local/bin/openspec\$" "$T/mask.txt" \
  | grep "/openspec\$" | head -1)
[[ -n "$MOD" ]] \
  || { echo "FAIL: the module tree is not masked"; cat "$T/mask.txt"; exit 1; }
grep -qx "/var/lib/aidlc/specs" "$T/mask.txt" \
  || { echo "FAIL: the specs home is not masked"; cat "$T/mask.txt"; exit 1; }

# 2. (G2) the tool itself: no version, no execution
O=$(insh 'openspec --version 2>&1; echo rc=$?')
[[ "$O" == *"rc=127"* || "$O" == *"rc=126"* ]] \
  || { echo "FAIL: G2 — openspec ran inside the shell: $O"; exit 1; }
if grep -qE 'openspec [0-9]+\.[0-9]+' <<<"$O"; then
  echo "FAIL: G2 — a version string escaped the mask: $O"; exit 1; fi

# 3. (G3) the direct node route to the module: equally closed
O=$(insh "node $MOD/bin/openspec.js --version 2>&1; echo rc=\$?")
if grep -qE 'openspec [0-9]+\.[0-9]+' <<<"$O"; then
  echo "FAIL: G3 — the module answered: $O"; exit 1; fi
grep -q "rc=0" <<<"$O" \
  && { echo "FAIL: G3 — the direct node call succeeded: $O"; exit 1; }

# a probe repo with a real change, migrated into the plane's REAL home
REPO="$T/repo"
git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
C="$REPO/openspec/changes/n5-probe"
mkdir -p "$C/specs/probe"
printf '## Why\n\nShell gate probe.\n\n## What Changes\n\n- One requirement.\n' > "$C/proposal.md"
printf '## ADDED Requirements\n\n### Requirement: Probe\n\nThe system SHALL pass.\n\n#### Scenario: It runs\n\n- **WHEN** it runs\n- **THEN** it passes\n' > "$C/specs/probe/spec.md"
$PY "$PLAN" migrate --repo "$REPO" >/dev/null
# repo_id: the absolute path with separators doubled away
PROOT="/var/lib/aidlc/specs/root--$(basename "$T")--repo"
[[ -d "$PROOT/openspec" ]] \
  || { echo "FAIL: the probe's plane root did not stand at $PROOT"; exit 1; }
cleanup() { command rm -rf "$T" "${PROOT:-}"; }

# 4. (G4) the plane's tree is not readable from inside the shell
O=$(insh "cat $PROOT/openspec/config.yaml 2>&1; echo rc=\$?")
grep -q "rc=0" <<<"$O" \
  && { echo "FAIL: G4 — the plane tree was read inside the shell: $O"; exit 1; }

# 5. (G5) and not writable either
O=$(insh "touch $PROOT/forbidden 2>&1; echo rc=\$?")
grep -q "rc=0" <<<"$O" \
  && { echo "FAIL: G5 — the plane tree was written inside the shell: $O"; exit 1; }
grep -qi "denied\|not found\|permission" <<<"$O" \
  || { echo "note: G5 refused without a diagnostic: $O"; }
[[ ! -e "$PROOT/forbidden" ]] || { echo "FAIL: G5 left a file behind"; exit 1; }

# 6. the positive controls: the caller's own surface works in-shell —
#    HOME forwarded, git live, the verdict key readable, the records
#    store writable (the caller signs what it judges, N2/N4)
O=$(insh "echo HOME=\$HOME; git --version; head -c4 $AI_DLC_VERDICT_KEY >/dev/null 2>&1 && echo KEY-OK; touch $AI_DLC_RECORDS/probe 2>/dev/null && echo REC-OK; cat $REPO/.git/HEAD >/dev/null 2>&1 && echo REPO-OK")
grep -q "HOME=/root" <<<"$O" || { echo "FAIL: HOME did not travel in: $O"; exit 1; }
grep -q "git version" <<<"$O" || { echo "FAIL: git is dead inside the shell: $O"; exit 1; }
grep -q "KEY-OK" <<<"$O" || { echo "FAIL: the verdict key is unreadable in-shell: $O"; exit 1; }
grep -q "REC-OK" <<<"$O" || { echo "FAIL: the records store is unwritable in-shell: $O"; exit 1; }
grep -q "REPO-OK" <<<"$O" || { echo "FAIL: the repo is unreadable in-shell: $O"; exit 1; }

# 7. the plane-sight CLIs stop HONESTLY inside the shell: the mask is
#    named, never mistaken for a missing tree (a migrate remedy that
#    cannot run), never judged blind
O=$(insh "$PY $PLAN boundary --change n5-probe --repo $REPO 2>&1; echo rc=\$?")
grep -q "rc=12" <<<"$O" || { echo "FAIL: boundary inside the shell exited differently: $O"; exit 1; }
grep -q "aidlc-shell" <<<"$O" \
  || { echo "FAIL: the refusal does not name the mask: $O"; exit 1; }
if grep -q "migrate --repo" <<<"$O"; then
  echo "FAIL: the masked refusal prescribes a migrate: $O"; exit 1; fi
O=$(insh "$PY $PLAN validate --change n5-probe --repo $REPO 2>&1; echo rc=\$?")
grep -q "rc=12" <<<"$O" || { echo "FAIL: validate inside the shell exited differently: $O"; exit 1; }
grep -q "aidlc-shell" <<<"$O" \
  || { echo "FAIL: the validate refusal does not name the mask: $O"; exit 1; }

# 8. and the caller's read side still works in-shell: deliver reads the
#    SIGNED record (minted outside, by the plane's own stand-in) and
#    reports spec_valid — the agent implements, delivers and reads
#    verdicts inside the shell; it never needs the plane's sight
(cd "$PROOT" && openspec validate n5-probe --strict) >/dev/null 2>&1
$PY "$RT" verdict n5-probe --rc 0 --artifacts proposal=done,specs=done --complete false >/dev/null
TD="$REPO/.ai-dlc/tasks/n5-probe-planning"
mkdir -p "$TD/gates"
BASE=$(git -C "$REPO" rev-parse HEAD)
printf '{"task_id": "n5-probe-planning", "route": "inline", "change_id": "n5-probe",\n "base_sha": "%s", "stage": "Working", "human_state": "Checking"}\n' "$BASE" > "$TD/state.json"
O=$(insh "$PY $ROOT/bin/report.py deliver --task-dir $TD --repo $REPO --no-design --no-design-by tester --no-design-why 'shell-gate probe' 2>&1; echo rc=\$?")
grep -q "rc=0" <<<"$O" || { echo "FAIL: deliver did not run in-shell: $O"; exit 1; }
grep -q '"spec_valid": true' <<<"$O" \
  || { echo "FAIL: the signed verdict did not read as valid in-shell: $O"; exit 1; }
[[ -f "$TD/report.json" ]] || { echo "FAIL: no delivery report written in-shell"; exit 1; }

echo "N5 SHELL GATES: pass (the real systemd unit masks the CLI entry, its module tree and the specs home — G2 no execution, G3 no direct node route, G4/G5 no read and no write of the plane's tree; the caller's own surface works inside — HOME, git, repo, the verdict key and the records store; the plane-sight CLIs stop honestly naming aidlc-shell; deliver reads the signed verdict in-shell)"
