#!/usr/bin/env bash
# R1 (route-and-speed 1.1-1.3, 1.5): the dispatch records its own
# duration. Every dispatch carries start, end and elapsed seconds beside
# its outcome in the output and in planning.json — a dispatch that fails
# fast records its duration AND its failure and never reads as a fast
# success. The phase record reports each role's duration, the sum of
# role durations and the wall-clock span, with serial made visible.
#
# The client is a double standing in for the shipped one (AI_DLC_CLIENT)
# — the flags are the contract; it writes its role's artifact into the
# change dir and closes the round with a write frame plus one final
# frame. The repo sits outside the private /tmp namespace.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d /root/ai-dlc-rs2-XXXXXX); trap 'rm -rf "$T"' EXIT
# the fixture lives under /root, which the real plane sees read-only
# (ProtectHome) — these cases exercise the writable class, so the probe
# reads this namespace's view of the path. The three classes and the
# split workspace they imply are covered by ad_any_directory.sh.
export AI_DLC_GATEWAY_ROOT=/
# the plane's records and key live in the test's own world: statuses
# advance by verdict records, and the stub signs one when its role's
# artifact lands
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
export PY RT
$PY "$RT" key

REPO="$T/repo"; C="$REPO/openspec/changes/time-it"; TD="$REPO/.ai-dlc/tasks/time-it-planning"

# the double: parse --session, write the role's artifact, emit the write
# frame and the final frame. FAIL_ROLE dies instantly with no frames at
# all — a fail-fast dispatch
cat > "$T/stub-client" <<'EOF'
#!/usr/bin/env bash
d="${0%/*}"; s=""; prev=""
for a in "$@"; do
  if [ "$prev" = "--session" ]; then s="$a"; fi
  prev="$a"
done
role="${s##*-}"
if [ -n "${FAIL_ROLE:-}" ] && [ "$role" = "$FAIL_ROLE" ]; then
  exit 0
fi
C="$CHANGE_DIR"
case "$role" in
  specs)
    mkdir -p "$C/specs/website"
    printf '## ADDED Requirements\n\n### Requirement: Navigation bar\n\nThe site SHALL show a navigation bar on every page.\n\n#### Scenario: Visitor opens any page\n\n- **WHEN** a visitor opens any page\n- **THEN** the navigation bar is visible\n' > "$C/specs/website/spec.md"
    written="$C/specs/website/spec.md" ;;
  design)
    printf '## Context\n\nA static site.\n\n## Goals / Non-Goals\n\n- Goals: one fragment\n- Non-Goals: dynamic menus\n\n## Decisions\n\n- Build-time injection.\n\n## Risks / Trade-offs\n\n- None measured.\n' > "$C/design.md"
    written="$C/design.md" ;;
  tasks)
    printf '# Tasks\n\n- [ ] 1.1 add the navigation fragment\n' > "$C/tasks.md"
    written="$C/tasks.md" ;;
esac
# the plane's verdict on what just landed: a signed record marking the
# role's artifact done (cumulative — merges every done state so one
# verdict carries the round's whole truth)
"$PY" - "$RT" "$C" "$role" <<'PYX' >/dev/null 2>&1 || true
import json, os, subprocess, sys
rt, cdir, role = sys.argv[1:4]
change = os.path.basename(cdir.rstrip("/"))
d = os.path.join(os.environ["AI_DLC_RECORDS"], change)
states = {"proposal": "done"}
if os.path.isdir(d):
    for p in sorted(os.listdir(d)):
        if p.startswith("status-"):
            try:
                rec = json.load(open(os.path.join(d, p)))
            except Exception:
                continue
            for k, v in (rec.get("artifacts") or {}).items():
                if v == "done":
                    states[k] = "done"
states[role] = "done"
subprocess.run([sys.executable, rt, "verdict", change, "--rc", "0",
                "--artifacts",
                ",".join(f"{k}=done" for k in states),
                "--complete", "false"], check=True, capture_output=True)
PYX
printf '{"type":"event","event":"chat.tool_call","payload":{"tool_name":"write_file","arguments":"{\\"path\\": \\"%s\\"}"}}\n' "$written"
printf '{"event":"chat.final","payload":{"content":"artifact written"}}\n'
EOF
chmod +x "$T/stub-client"
export AI_DLC_CLIENT="$T/stub-client"
export CHANGE_DIR="$C"

git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
mkdir -p "$C"
printf '## Why\n\nThe site has no navigation.\n\n## What Changes\n\n- Add a shared navigation bar.\n' > "$C/proposal.md"
cat > "$T/pkg.json" <<EOF
{"requirement": "shared navigation across pages", "change_id": "time-it",
 "capability": "website", "repo": "$REPO"}
EOF
# the graph a graph dispatch would have signed: design carries the
# upstream instruction's own four inclusion conditions, and the verdict
# marks the proposal that already stands on disk done
# N6: the artifacts live in the plane's tree from here on
. "$ROOT/tests/collapse/lib_plane.sh"
plane_migrate "$REPO"
C="$PLANE_TREE/changes/time-it"; export CHANGE_DIR="$C"

$PY "$RT" graph time-it --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"],"conditional":true,"conditions":["Cross-cutting change (multiple services/modules) or new architectural pattern","New external dependency or significant data model changes","Security, performance, or migration complexity","Ambiguity that benefits from technical decisions before coding"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
$PY "$RT" verdict time-it --rc 0 --artifacts proposal=done --complete false >/dev/null

# the design artifact is conditional upstream: record the decision so the
# phase may dispatch it (the decision surface itself is rs4's subject)
$PY "$PLAN" decide --change time-it --repo "$REPO" --artifact design \
  --condition "Cross-cutting change" --decided-by tester >/dev/null

# 1. (1.1) a dispatch carries start, end and elapsed seconds beside its
#    outcome — in the output and in planning.json
set +e
$PY "$PLAN" dispatch --change time-it --role specs \
  --package-file "$T/pkg.json" > "$T/d1.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: specs dispatch exited $RC"; cat "$T/d1.json"; exit 1; }
$PY - "$TD/planning.json" "$T/d1.json" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1])); out = json.load(open(sys.argv[2]))
d = p["dispatches"]["specs"]
for rec, where in ((d, "planning.json"), (out, "dispatch output")):
    for k in ("started_at", "ended_at", "elapsed_seconds"):
        assert k in rec, f"{where} lacks {k}: {sorted(rec)}"
    assert isinstance(rec["elapsed_seconds"], (int, float)) and rec["elapsed_seconds"] >= 0
assert d["outcome"] == 0, d
PYEOF

# 2. (1.5) a fail-fast dispatch records its duration AND its failure —
#    never a fast success
set +e
FAIL_ROLE=design $PY "$PLAN" dispatch --change time-it --role design \
  --package-file "$T/pkg.json" > "$T/d2.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: fail-fast dispatch exited $RC, want 1"; cat "$T/d2.json"; exit 1; }
grep -q '"round_complete": false' "$T/d2.json"
if grep -q '"accepted": true\|"status": "ok"' "$T/d2.json"; then
  echo "FAIL: a fail-fast dispatch read as a success"; cat "$T/d2.json"; exit 1
fi
$PY - "$TD/planning.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))["dispatches"]["design"]
assert d["outcome"] == 1, d
assert "elapsed_seconds" in d and d["elapsed_seconds"] >= 0, d
assert "started_at" in d and "ended_at" in d, d
assert d["round_complete"] is False, d
PYEOF

# 3. (1.2/1.3) the phase record reports each role's duration, the sum of
#    role durations and the wall-clock span; --concurrency 1 is serial
set +e
$PY "$PLAN" phase --change time-it --repo "$REPO" \
  --package-file "$T/pkg.json" --concurrency 1 > "$T/ph.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: serial phase exited $RC"; cat "$T/ph.json"; exit 1; }
$PY - "$TD/planning.json" "$T/ph.json" <<'PYEOF'
import json, sys
p = json.load(open(sys.argv[1])); out = json.load(open(sys.argv[2]))
ph = p["phases"][-1]
assert ph["serial"] is True and ph["concurrency"] == 1, ph
assert ph["rounds"] >= 1, ph
# specs is already done (dispatched in step 1) — never-pay-twice: the
# phase dispatches only design and tasks, each with its duration
assert sorted(ph["roles"]) == ["design", "tasks"], sorted(ph["roles"])
for role, r in ph["roles"].items():
    assert isinstance(r.get("elapsed_seconds"), (int, float)), r
for k in ("wall_seconds", "sum_role_seconds", "started_at", "ended_at"):
    assert isinstance(ph.get(k), (int, float)) or k.endswith("_at"), (k, ph.get(k))
assert isinstance(ph["wall_seconds"], (int, float)) and ph["wall_seconds"] >= 0
assert isinstance(ph["sum_role_seconds"], (int, float))
# serial: the span cannot be shorter than the roles took together
assert ph["wall_seconds"] + 0.05 >= ph["sum_role_seconds"], ph
assert "sum_role_seconds" in out["note"] or "wall_seconds" in out["note"]
PYEOF

echo "RS2 TIMING: pass (dispatch output and planning.json carry start/end/elapsed beside the outcome; a fail-fast dispatch records its duration and its outcome 1, never a success; the phase record carries each role's duration, sum_role_seconds and wall_seconds with serial visible)"
