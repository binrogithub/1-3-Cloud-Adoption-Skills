#!/usr/bin/env bash
# R3 (route-and-speed 3.1-3.6): independent roles dispatch together.
# specs and design both depend only on proposal, so round one dispatches
# both at once (the calls log proves the overlap); each keeps its own
# session, evidence file and boundary baseline. When one role fails the
# others already running finish and every outcome is reported before the
# phase stops; tasks (depending on both) is blocked, not dispatched.
# A write outside the change dir aborts the phase naming the role whose
# frames carry it; a path written from more than one role's frames
# breaks the disjointness the frame proof rests on and aborts too.
#
# The client is a double standing in for the shipped one (AI_DLC_CLIENT);
# it sleeps so overlap is measurable, logs start/end per session, writes
# its role's artifact, and emits a write frame plus the final frame.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d /root/ai-dlc-rs3-XXXXXX); trap 'rm -rf "$T"' EXIT
# the fixture lives under /root, which the real plane sees read-only
# (ProtectHome) — these cases exercise the writable class, so the probe
# reads this namespace's view of the path. The three classes and the
# split workspace they imply are covered by ad_any_directory.sh.
export AI_DLC_GATEWAY_ROOT=/
# the plane's records and key live in the test's own world: a phase's
# rounds advance by verdict statuses, so the client stub stands in for
# the plane and signs a cumulative verdict when its role's artifact
# lands (each verdict carries every done state, newest wins)
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
# N6: every case's plane tree lives in the test's own specs home
export AI_DLC_SPECS="$T/specs"
export RT PY
$PY "$RT" key

STUB="$T/stub-client"

cat > "$STUB" <<'EOF'
#!/usr/bin/env bash
d="${0%/*}"; s=""; prev=""
for a in "$@"; do
  if [ "$prev" = "--session" ]; then s="$a"; fi
  prev="$a"
done
role="${s##*-}"
printf 'start %s %s\n' "$s" "$(date +%s.%N)" >> "$d/calls.log"
if [ -n "${FAIL_ROLE:-}" ] && [ "$role" = "$FAIL_ROLE" ]; then
  exit 0
fi
if [ -n "${NO_WRITE:-}" ]; then
  printf '{"event":"chat.final","payload":{"content":"nothing written"}}\n'
  printf 'end %s %s\n' "$s" "$(date +%s.%N)" >> "$d/calls.log"
  exit 0
fi
sleep "${SLEEP:-1.2}"
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
"$PY" - "$RT" "$C" "$role" <<'PYX' >/dev/null 2>&1 || true
import fcntl, json, os, subprocess, sys
rt, cdir, role = sys.argv[1:4]
change = os.path.basename(cdir.rstrip("/"))
root = os.environ["AI_DLC_RECORDS"]
d = os.path.join(root, change)
# concurrent roles mint at the same moment: the read-merge-write holds
# an exclusive lock so one verdict carries both done states
with open(os.path.join(root, ".mint.lock"), "w") as lf:
    fcntl.flock(lf, fcntl.LOCK_EX)
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
frames=''
emit () { frames="$frames$1\n"; }
if [ -n "${LEAK_ROLE:-}" ] && [ "$role" = "$LEAK_ROLE" ]; then
  mkdir -p "$REPO_ROOT/src"
  printf 'leak\n' > "$REPO_ROOT/src/leak.txt"
  emit "{\"type\":\"event\",\"event\":\"chat.tool_call\",\"payload\":{\"tool_name\":\"write_file\",\"arguments\":\"{\\\"path\\\": \\\"$REPO_ROOT/src/leak.txt\\\"}\"}}"
fi
for cr in ${CLASH_ROLES:-}; do
  if [ "$role" = "$cr" ]; then
    emit "{\"type\":\"event\",\"event\":\"chat.tool_call\",\"payload\":{\"tool_name\":\"write_file\",\"arguments\":\"{\\\"path\\\": \\\"$C/proposal.md\\\"}\"}}"
  fi
done
printf '{"type":"event","event":"chat.tool_call","payload":{"tool_name":"write_file","arguments":"{\\"path\\": \\"%s\\"}"}}\n' "$written"
printf '%b' "$frames"
printf '{"event":"chat.final","payload":{"content":"artifact written"}}\n'
printf 'end %s %s\n' "$s" "$(date +%s.%N)" >> "$d/calls.log"
EOF
chmod +x "$STUB"
export AI_DLC_CLIENT="$STUB"

# N6: the shared plane fixture — every case's repo migrates into the
# test's own specs home
. "$ROOT/tests/collapse/lib_plane.sh"

mk_case () {  # a fresh repo + change with proposal done; echoes the repo path
  local name="$1" repo="$T/$1/repo"
  mkdir -p "$T/$name"
  git -C "$T/$name" init -q repo
  git -C "$repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
  (cd "$repo" && openspec init --tools none --language en) >/dev/null 2>&1
  mkdir -p "$repo/openspec/changes/$name"
  printf '## Why\n\nThe site has no navigation.\n\n## What Changes\n\n- Add a shared navigation bar.\n' \
    > "$repo/openspec/changes/$name/proposal.md"
  # N6: the artifacts live in the plane's tree — migrate this repo's
  # surface before anything dispatches against it
  plane_migrate "$repo"
  printf '{"requirement": "shared navigation across pages", "change_id": "%s",\n "capability": "website", "repo": "%s"}\n' \
    "$name" "$repo" > "$T/$name/pkg.json"
  # the graph a graph dispatch would have signed: design carries the
  # upstream instruction's own four inclusion conditions, and the
  # verdict marks the proposal that already stands on disk done
  "$PY" "$RT" graph "$name" --schema spec-driven --artifacts-json \
    '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"],"conditional":true,"conditions":["Cross-cutting change (multiple services/modules) or new architectural pattern","New external dependency or significant data model changes","Security, performance, or migration complexity","Ambiguity that benefits from technical decisions before coding"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
  "$PY" "$RT" verdict "$name" --rc 0 --artifacts proposal=done --complete false >/dev/null
  CHANGE_DIR="$PLANE_TREE/changes/$name" \
    $PY "$PLAN" decide --change "$name" --repo "$repo" --artifact design \
    --condition "Cross-cutting change" --decided-by tester >/dev/null
  echo "$repo"
}

# ── A. (3.1/3.2/3.4/3.5) both independent roles dispatch together ──
unset FAIL_ROLE LEAK_ROLE CLASH_ROLES NO_WRITE
REPO_A="$(mk_case rs3a)"
export CHANGE_DIR="$(plane_of "$REPO_A")/openspec/changes/rs3a"
export REPO_ROOT="$REPO_A"
TD_A="$REPO_A/.ai-dlc/tasks/rs3a-planning"; rm -f "$T/calls.log"
set +e
$PY "$PLAN" phase --change rs3a --repo "$REPO_A" \
  --package-file "$T/rs3a/pkg.json" --concurrency 2 > "$T/a.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: concurrent phase exited $RC"; cat "$T/a.json"; exit 1; }
$PY - "$T/calls.log" "$TD_A" "$T/a.json" <<'PYEOF'
import json, sys, os
log = [l.split() for l in open(sys.argv[1])]
span = {}
for parts in log:
    span.setdefault(parts[1], {})[parts[0]] = float(parts[2])
td, out = sys.argv[2], json.load(open(sys.argv[3]))
ph = out["phase"]
# (3.1) specs and design ran at the same moment — the intervals overlap
s, d = span["plan-rs3a-specs"], span["plan-rs3a-design"]
assert s["start"] < d["end"] and d["start"] < s["end"], (s, d)
# round two dispatched tasks alone, after both landed
assert ph["rounds"] == 2, ph["rounds"]
assert sorted(ph["roles"]) == ["design", "specs", "tasks"], sorted(ph["roles"])
# (3.2) own session, own evidence, own baseline per role
dis = ph["disjointness"]
assert dis["sessions_pairwise_distinct"] is True, dis
ev = sorted(os.listdir(f"{td}/evidence"))
assert len([e for e in ev if e.endswith(".jsonl")]) == 3, ev
assert len([e for e in ev if e.endswith(".pre-boundary.json")]) == 3, ev
# (3.4/3.5) each written path sits in exactly one role's frames
w = dis["artifact_writers"]
for path, roles in w.items():
    assert roles == ["specs"] or roles == ["design"] or roles == ["tasks"], (path, roles)
assert dis["multi_written"] == {}, dis
PYEOF

# ── B. (3.3) one fails fast; the other finishes; every outcome reported ──
REPO_B="$(mk_case rs3b)"
export CHANGE_DIR="$(plane_of "$REPO_B")/openspec/changes/rs3b"
export REPO_ROOT="$REPO_B"
TD_B="$REPO_B/.ai-dlc/tasks/rs3b-planning"; rm -f "$T/calls.log"
set +e
FAIL_ROLE=specs \
  $PY "$PLAN" phase --change rs3b --repo "$REPO_B" \
  --package-file "$T/rs3b/pkg.json" --concurrency 2 > "$T/b.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: one-failure phase exited $RC, want 1"; cat "$T/b.json"; exit 1; }
$PY - "$T/calls.log" "$T/b.json" <<'PYEOF'
import json, sys
log = [l.split() for l in open(sys.argv[1])]
out = json.load(open(sys.argv[2])); ph = out["phase"]
called = {parts[1] for parts in log}
# both round-one roles reached the client; tasks never did
assert "plan-rs3b-specs" in called and "plan-rs3b-design" in called, called
assert "plan-rs3b-tasks" not in called, called
# the failing role failed; the running one FINISHED and is reported
assert ph["roles"]["specs"]["outcome"] == 1, ph["roles"]["specs"]
assert ph["roles"]["design"]["outcome"] == 0, ph["roles"]["design"]
assert isinstance(ph["roles"]["specs"]["elapsed_seconds"], (int, float))
assert ph["failures"] == ["specs"], ph["failures"]
assert any(b["artifact"] == "tasks" and b["waiting_on"] for b in ph["blocked"]), ph["blocked"]
PYEOF

# ── C. (3.6) a write outside the change dir aborts, naming the role ──
REPO_C="$(mk_case rs3c)"
export CHANGE_DIR="$(plane_of "$REPO_C")/openspec/changes/rs3c"
export REPO_ROOT="$REPO_C"
set +e
LEAK_ROLE=design \
  $PY "$PLAN" phase --change rs3c --repo "$REPO_C" \
  --package-file "$T/rs3c/pkg.json" --concurrency 2 > "$T/c.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 8 ]] || { echo "FAIL: leaking phase exited $RC, want 8"; cat "$T/c.json"; exit 1; }
grep -q '"src/leak.txt"' "$T/c.json"
grep -q '"frames_carry": \[' "$T/c.json"
$PY - "$T/c.json" <<'PYEOF'
import json, sys
out = json.load(open(sys.argv[1]))
o = out["offenders"][0]
assert o["path"] == "src/leak.txt", o
assert o["frames_carry"] == ["design"], o   # the role whose frames carry it
PYEOF
[[ -f "$REPO_C/src/leak.txt" ]] || { echo "FAIL: the leak was cleaned up"; exit 1; }

# ── D. (3.5 reverse) one path, two roles' frames: disjointness broken ──
REPO_D="$(mk_case rs3d)"
export CHANGE_DIR="$(plane_of "$REPO_D")/openspec/changes/rs3d"
export REPO_ROOT="$REPO_D"
set +e
CLASH_ROLES="specs design" \
  $PY "$PLAN" phase --change rs3d --repo "$REPO_D" \
  --package-file "$T/rs3d/pkg.json" --concurrency 2 > "$T/d.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 8 ]] || { echo "FAIL: clash phase exited $RC, want 8"; cat "$T/d.json"; exit 1; }
grep -q 'more than one role' "$T/d.json"
$PY - "$REPO_D/.ai-dlc/tasks/rs3d-planning/planning.json" <<'PYEOF'
import json, sys
ph = json.load(open(sys.argv[1]))["phases"][-1]
mw = ph["disjointness"]["multi_written"]
assert any("proposal.md" in p for p in mw), mw
assert set(mw["openspec/changes/rs3d/proposal.md"]) == {"design", "specs"}, mw
PYEOF

# ── E. a round that lands no artifact stops the phase — the runner
#    never re-dispatches the same roles forever (each is a real payment) ──
REPO_E="$(mk_case rs3e)"
export CHANGE_DIR="$(plane_of "$REPO_E")/openspec/changes/rs3e"
export REPO_ROOT="$REPO_E"; rm -f "$T/calls.log"
set +e
NO_WRITE=1 SLEEP=0 \
  $PY "$PLAN" phase --change rs3e --repo "$REPO_E" \
  --package-file "$T/rs3e/pkg.json" --concurrency 2 > "$T/e.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: no-progress phase exited $RC, want 1"; cat "$T/e.json"; exit 1; }
grep -q 'landed no artifact' "$T/e.json"
N=$(grep -c '^start ' "$T/calls.log")
[[ "$N" -eq 2 ]] || { echo "FAIL: no-progress phase re-dispatched ($N client starts, want 2)"; cat "$T/calls.log"; exit 1; }
$PY - "$REPO_E/.ai-dlc/tasks/rs3e-planning/planning.json" <<'PYEOF'
import json, sys
ph = json.load(open(sys.argv[1]))["phases"][-1]
assert ph["rounds"] == 1, ph["rounds"]
assert ph["no_progress"] == ["design", "specs"], ph["no_progress"]
PYEOF

echo "RS3 CONCURRENCY: pass (specs and design overlap in the calls log, round two alone runs tasks; own session/evidence/baseline per role; one failure lets the running role finish with every outcome reported and tasks blocked; src/leak.txt aborts exit 8 with frames_carry [design] and nothing cleaned up; one path in two roles' frames aborts exit 8 — disjointness held and broken; a round landing no artifact stops after one round instead of re-paying forever)"
