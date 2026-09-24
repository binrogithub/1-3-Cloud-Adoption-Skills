#!/usr/bin/env bash
# L2 (landing tasks 2.1-2.6, reworked under containment N2/N6): the tail
# runs after approval and only after approval. Without an approval
# carrying a rationale, close does nothing and reports waiting on a
# person — neither merge nor archive runs. With one: the task branch
# merges caller-side, then ONE plane session archives the change and
# writes the result back — the normalized archive literal, the
# write-back literals (specs, the archived change dir, git add, git
# commit) — each judged from the frames and then checked against the
# filesystem, because a dispatch's report is never its proof. G6 stands
# at the archive door: a change dir that stands only repo-side, a
# surface altered by hand, or foreign-owned content under the change
# dir refuses before any session exists. A session that skips a
# normalized literal fails exit 23 with no record written; a command
# that exits non-zero fails exit 11 carrying its output verbatim.
# The reachability pre-check (I3, the open-sandbox PRD) stops the
# close before the plane's tree is touched when the repo is not
# writable through the gateway's own view; a tree whose shape says the
# archive already ran resumes at the write-back alone (I4) and signs
# the resume into the record.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export AI_DLC_SPECS="$T/specs"
. "$ROOT/tests/collapse/lib_plane.sh"
# the plane's records and key live in the test's own world: the signed
# archive record is written through the same path the plane's own
# records take
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key
REPO="$T/repo"; TD="$REPO/.ai-dlc/tasks/x-planning"

mkchange() {  # a strictly valid change named $1 in the repo's tree
  local C="$REPO/openspec/changes/$1"
  mkdir -p "$C/specs/cap"
  printf '## Why\n\n%s\n\n## What Changes\n\n- One requirement.\n' "$1" > "$C/proposal.md"
  printf '## ADDED Requirements\n\n### Requirement: %s\n\nThe system SHALL %s.\n\n#### Scenario: It runs\n\n- **WHEN** it runs\n- **THEN** it %s\n' "$1" "$1" "$1" > "$C/specs/cap/spec.md"
}

git -C "$T" init -q repo
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
BASE=$(git -C "$REPO" symbolic-ref --short HEAD)
(cd "$REPO" && openspec init --tools none --language en) >/dev/null 2>&1
mkchange add-nav-bar
mkchange keep-me
mkchange refuse-me
mkdir -p "$TD/gates"
printf '{"task_id": "x-planning", "route": "planned", "change_id": "add-nav-bar",\n "stage": "Working", "human_state": "Checking"}\n' > "$TD/state.json"
# N6: the tree moves into the plane's home before any close — the
# archive session runs there and G6 judges what stands there
plane_migrate "$REPO"
PROOT="$(plane_of "$REPO")"
# close's I3 pre-check classifies the repo before the plane's tree is
# touched: the class is pinned by fixtures — a probe view holding the
# repo and a unit declaring no allowlist (the open regime) — so the
# suite sees writable whatever regime the LIVE unit is in
mkdir -p "$T/probe$T"
ln -s "$REPO" "$T/probe$T/repo"
export AI_DLC_GATEWAY_ROOT="$T/probe"
cat > "$T/gw-open.service" <<EOF
[Service]
Environment=JIUWENSWARM_DATA_DIR=$T/data
PrivateTmp=false
EOF
export AI_DLC_GW_UNIT="$T/gw-open.service"

approve() {  # write a merge-gate approval carrying a rationale
  $PY - "$1" <<'PYEOF'
import json, sys
json.dump({"gate_id": "gate-merge", "decision": "approve",
           "approver": "tester", "rationale": "read the diff; it matches",
           "ts": "2026-08-30T00:00:00Z"},
          open(sys.argv[1] + "/gates/gate-merge.answer.json", "w"))
PYEOF
}

# the stub plane: runs EXACTLY the commands the prompt lists, reports
# each with the frames the gateway reports (the oc4 double), replies
# DONE. STUB_SKIP drops every command matching the substring — the
# exit-23 case; STUB_FAIL reports rc 1 for a matching command without
# running it — the exit-11 case
cat > "$T/stub-archive" <<'EOF'
#!/usr/bin/env python3
import json, os, subprocess, sys
prompt = sys.argv[2] if len(sys.argv) > 2 else ""
cmds = [l[2:] for l in prompt.splitlines() if l.startswith("- ")]
def frame(ev, payload):
    print(json.dumps({"type": "event", "event": ev,
                      "payload": {"event_type": ev, **payload}}))
for i, cmd in enumerate(cmds):
    if os.environ.get("STUB_SKIP", "") and os.environ["STUB_SKIP"] in cmd:
        continue
    cid = f"call_{i}"
    args = json.dumps({"command": cmd})
    frame("chat.tool_call", {"tool_call": {"name": "bash",
                                           "arguments": args,
                                           "tool_call_id": cid}})
    if os.environ.get("STUB_FAIL", "") and os.environ["STUB_FAIL"] in cmd:
        body = "Exit code 1\nthe stub was told to fail this command"
        result = ("success=False data=" + str({"content": body})
                  + " error=" + repr(body))
    else:
        p = subprocess.run(["bash", "-c", cmd], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True)
        content = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0:
            result = ("success=True data=" + str({"content": content})
                      + " error=None")
        else:
            body = f"Exit code {p.returncode}\n" + content
            result = ("success=False data=" + str({"content": body})
                      + " error=" + repr(body))
    frame("chat.tool_result", {"result": result, "tool_name": "bash",
                               "tool_call_id": cid})
frame("chat.final", {"content": "DONE"})
EOF
chmod +x "$T/stub-archive"
export AI_DLC_CLIENT="$T/stub-archive"

# a task branch carrying one commit the target does not have
git -C "$REPO" checkout -q -b task/add-nav-bar
printf 'nav\n' > "$REPO/nav.html"
git -C "$REPO" add nav.html
git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm work
git -C "$REPO" checkout -q "$BASE"

# 1. (2.5) no approval at all -> nothing runs, waiting on a person
set +e
$PY "$PLAN" close --change add-nav-bar --repo "$REPO" --task-dir "$TD" > "$T/w1.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: no-approval close exited $RC, want 1"; cat "$T/w1.json"; exit 1; }
grep -q '"closed": false' "$T/w1.json"
grep -q '"waiting_on": "merge_gate"' "$T/w1.json"
git -C "$REPO" merge-base --is-ancestor task/add-nav-bar "$BASE" 2>/dev/null \
  && { echo "FAIL: merged without an approval"; exit 1; }
[[ -d "$PROOT/openspec/changes/add-nav-bar" ]] \
  || { echo "FAIL: the plane's change dir went missing without an approval"; exit 1; }
[[ ! -d "$REPO/openspec" ]] \
  || { echo "FAIL: something wrote the repo's openspec surface back without an approval"; exit 1; }

# 2. (2.5) an approval WITHOUT a rationale is no approval
$PY - "$TD" <<'PYEOF'
import json, sys
json.dump({"gate_id": "gate-merge", "decision": "approve",
           "approver": "tester", "rationale": "  ", "ts": "x"},
          open(sys.argv[1] + "/gates/gate-merge.answer.json", "w"))
PYEOF
set +e
$PY "$PLAN" close --change add-nav-bar --repo "$REPO" --task-dir "$TD" > "$T/w2.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: rationale-less approval closed (rc=$RC)"; cat "$T/w2.json"; exit 1; }
grep -q '"waiting_on": "merge_gate"' "$T/w2.json"

# 3. (2.1-2.4, N2) with an approval the merge runs caller-side and the
#    archive runs as ONE plane session: every normalized literal judged
#    from the frames, then checked against the filesystem, the record
#    signed, the task closed and the run's worktree/branch removed
approve "$TD"
BEFORE=$(git -C "$REPO" rev-parse "$BASE")
TASKSHA=$(git -C "$REPO" rev-parse task/add-nav-bar)
git -C "$REPO" worktree add -q "$T/wt" task/add-nav-bar >/dev/null 2>&1
NAME="$(date +%Y-%m-%d)-add-nav-bar"
$PY "$PLAN" close --change add-nav-bar --repo "$REPO" --task-dir "$TD" > "$T/ok.json" 2>&1 \
  || { echo "FAIL: approved close failed"; cat "$T/ok.json"; exit 1; }
grep -q '"closed": true' "$T/ok.json"
grep -q '"status": "merged"' "$T/ok.json"
grep -q '"archive": "dispatched"' "$T/ok.json"
# the merge advanced the target with the task's work
AFTER=$(git -C "$REPO" rev-parse "$BASE")
[[ "$BEFORE" != "$AFTER" ]] || { echo "FAIL: target head did not advance"; exit 1; }
git -C "$REPO" merge-base --is-ancestor "$TASKSHA" "$BASE"
# the filesystem truth the frames were checked against
[[ ! -d "$PROOT/openspec/changes/add-nav-bar" ]] \
  || { echo "FAIL: the plane's change dir was not moved"; exit 1; }
[[ -d "$PROOT/openspec/changes/archive/$NAME" ]] \
  || { echo "FAIL: no archive dir in the plane tree"; ls "$PROOT/openspec/changes/"; exit 1; }
[[ -d "$REPO/openspec/changes/archive/$NAME" ]] \
  || { echo "FAIL: the archived change was not written back"; ls "$REPO/openspec/changes/"; exit 1; }
[[ -f "$REPO/openspec/specs/cap/spec.md" ]] \
  || { echo "FAIL: the specs were not written back"; find "$REPO/openspec"; exit 1; }
SUBJ=$(git -C "$REPO" log -1 --format=%s)
[[ "$SUBJ" == "openspec: archive add-nav-bar" ]] \
  || { echo "FAIL: the write-back commit subject is '$SUBJ'"; exit 1; }
AUTHOR=$(git -C "$REPO" log -1 --format=%an)
[[ "$AUTHOR" == "ai-dlc-plane" ]] \
  || { echo "FAIL: the write-back commit is authored '$AUTHOR'"; exit 1; }
# the signed archive record: verb, argv, rc, stdout digest
$PY - "$T/records/add-nav-bar/archive-001.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
assert r["verb"] == "archive", r
assert r["argv"][-3:] == ["--yes", "--json"] or r["argv"][-2:] == ["--yes", "--json"], r
assert r["rc"] == 0, r
assert r["writeback"]["predicted_name"].endswith("add-nav-bar"), r
assert r["hmac"], r
PYEOF
# the task record closed and the run's own tree cleaned up
grep -q '"stage": "DONE"' "$TD/state.json"
[[ ! -d "$T/wt" ]] || { echo "FAIL: the task worktree survived the close"; exit 1; }
git -C "$REPO" rev-parse -q --verify task/add-nav-bar >/dev/null 2>&1 \
  && { echo "FAIL: the merged task branch survived the close"; exit 1; }

# 3b. --keep-task-branch records the retention instead of removing
TD3="$REPO/.ai-dlc/tasks/keep-planning"; mkdir -p "$TD3/gates"
approve "$TD3"
git -C "$REPO" checkout -q -b task/keep-me
printf 'keep\n' > "$REPO/keep.txt"
git -C "$REPO" add keep.txt
git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm keep
git -C "$REPO" checkout -q "$BASE"
$PY "$PLAN" close --change keep-me --repo "$REPO" --task-dir "$TD3" \
  --keep-task-branch > "$T/keep.json" 2>&1 \
  || { echo "FAIL: keep-branch close failed"; cat "$T/keep.json"; exit 1; }
grep -q '"retention"' "$T/keep.json"
grep -q 'kept by request' "$T/keep.json"
git -C "$REPO" rev-parse -q --verify task/keep-me >/dev/null \
  || { echo "FAIL: --keep-task-branch removed the branch anyway"; exit 1; }
git -C "$REPO" branch -q -D task/keep-me

# 3c. (I3) a repo the gateway cannot write stops the close BEFORE the
#     plane's tree is touched: no archive session, no record, the
#     change dir still standing — the split state this order exists to
#     make impossible. The text points at the unit's sandbox or the
#     path, never at a second way out
UC="$PROOT/openspec/changes/unreachable"
mkdir -p "$UC/specs/cap"
printf '## Why\n\nunreachable.\n\n## What Changes\n\n- One requirement.\n' > "$UC/proposal.md"
printf '## ADDED Requirements\n\n### Requirement: unreachable\n\nThe system SHALL unreachable.\n\n#### Scenario: It runs\n\n- **WHEN** it runs\n- **THEN** it unreachable\n' > "$UC/specs/cap/spec.md"
TDU="$REPO/.ai-dlc/tasks/unreach-planning"; mkdir -p "$TDU/gates"
approve "$TDU"
rm -f "$T/probe$T/repo"      # the gateway's view loses the repo: invisible
set +e
$PY "$PLAN" close --change unreachable --repo "$REPO" --task-dir "$TDU" > "$T/i3.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 11 ]] || { echo "FAIL: unreachable-repo close exited $RC, want 11"; cat "$T/i3.json"; exit 1; }
grep -q '"closed": false' "$T/i3.json"
grep -q '"class": "invisible"' "$T/i3.json"
grep -q "the plane's tree was not touched" "$T/i3.json"
[[ -d "$UC" ]] || { echo "FAIL: a stopped close moved the plane's change dir"; exit 1; }
[[ ! -e "$T/records/unreachable" ]] || { echo "FAIL: a stopped close wrote an archive record"; exit 1; }
ln -s "$REPO" "$T/probe$T/repo"   # the view returns for what follows
echo "I3: an unreachable repo stops the close before the plane's tree is touched — OK"

# 3d. (I4) the split state resumes at the write-back: a tree whose
#     SHAPE says the archive already ran (the change dir gone, an
#     archive standing — what a failed first close leaves) does not
#     re-run the archive literal; the session runs the write-back
#     alone, against the archive directory that actually stands (an
#     earlier date than today's prediction), and the record says it
#     resumed
SC="$PROOT/openspec/changes/split-change"
mkdir -p "$SC/specs/cap"
printf '## Why\n\nsplit.\n\n## What Changes\n\n- One requirement.\n' > "$SC/proposal.md"
printf '## ADDED Requirements\n\n### Requirement: split-change\n\nThe system SHALL split.\n\n#### Scenario: It runs\n\n- **WHEN** it runs\n- **THEN** it split\n' > "$SC/specs/cap/spec.md"
mkdir -p "$PROOT/openspec/changes/archive"
mv "$SC" "$PROOT/openspec/changes/archive/2020-01-01-split-change"
TDS="$REPO/.ai-dlc/tasks/split-planning"; mkdir -p "$TDS/gates"
approve "$TDS"
set +e
$PY "$PLAN" close --change split-change --repo "$REPO" --task-dir "$TDS" > "$T/i4.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 0 ]] || { echo "FAIL: resume close exited $RC"; cat "$T/i4.json"; exit 1; }
grep -q '"closed": true' "$T/i4.json"
grep -q '"resumed_from": "write-back"' "$T/i4.json"
grep -q 'resumed at the write-back' "$T/i4.json"
# the write-back landed against the STANDING archive name, not today's
[[ -d "$REPO/openspec/changes/archive/2020-01-01-split-change" ]] \
  || { echo "FAIL: the resume did not write back the standing archive"; ls "$REPO/openspec/changes/archive/"; exit 1; }
SUBJ=$(git -C "$REPO" log -1 --format=%s)
[[ "$SUBJ" == "openspec: archive split-change" ]] \
  || { echo "FAIL: the resume commit subject is '$SUBJ'"; exit 1; }
AUTHOR=$(git -C "$REPO" log -1 --format=%an)
[[ "$AUTHOR" == "ai-dlc-plane" ]] \
  || { echo "FAIL: the resume commit is authored '$AUTHOR'"; exit 1; }
# exactly one archived split-change plane-side — the archive literal
# was not re-run against a tree that no longer held the change
N=$(ls -1 "$PROOT/openspec/changes/archive" | grep -c 'split-change$')
[[ "$N" -eq 1 ]] || { echo "FAIL: $N split-change archives stand, want 1"; ls "$PROOT/openspec/changes/archive/"; exit 1; }
# the signed record says the session resumed and carries no rc for a
# command that did not run
$PY - "$T/records/split-change/archive-001.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
assert r["verb"] == "archive", r
assert r.get("resumed") is True, r
assert r["argv"] is None and r["rc"] is None, r
assert r["hmac"], r
PYEOF
echo "I4: a split state resumes at the write-back, the standing archive named — OK"

# 4. (G6, path) a change dir that stands only REPO-side is not the
#    plane's work: the archive door refuses before any session exists
mkdir -p "$REPO/openspec/changes/hand-written"
printf '## Why\n\nhand-written.\n' > "$REPO/openspec/changes/hand-written/proposal.md"
TD4="$REPO/.ai-dlc/tasks/hand-planning"; mkdir -p "$TD4/gates"
approve "$TD4"
set +e
$PY "$PLAN" close --change hand-written --repo "$REPO" --task-dir "$TD4" > "$T/g6a.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 12 ]] || { echo "FAIL: repo-side change exited $RC, want 12"; cat "$T/g6a.json"; exit 1; }
grep -q "does not stand in the PLANE" "$T/g6a.json"
grep -q '"closed": false' "$T/g6a.json"
[[ ! -e "$T/records/hand-written" ]] \
  || { echo "FAIL: a refused archive wrote a record"; exit 1; }
command rm -rf "$REPO/openspec/changes/hand-written"

# 5. (G6, surface) a surface altered by hand is refused, not repaired
chmod 0755 "$PROOT/openspec"
set +e
$PY "$PLAN" close --change refuse-me --repo "$REPO" --task-dir "$TD" > "$T/g6b.json" 2>&1
RC=$?
set -e
chmod 0750 "$PROOT/openspec"
[[ "$RC" -eq 12 ]] || { echo "FAIL: altered surface exited $RC, want 12"; cat "$T/g6b.json"; exit 1; }
grep -q 'altered by hand' "$T/g6b.json"
[[ -d "$PROOT/openspec/changes/refuse-me" ]] \
  || { echo "FAIL: the refused archive moved the change anyway"; exit 1; }

# 6. (G6, ownership) foreign-owned content under the change dir refuses
chown 1234 "$PROOT/openspec/changes/refuse-me/proposal.md"
set +e
$PY "$PLAN" close --change refuse-me --repo "$REPO" --task-dir "$TD" > "$T/g6c.json" 2>&1
RC=$?
set -e
chown 0 "$PROOT/openspec/changes/refuse-me/proposal.md"
[[ "$RC" -eq 12 ]] || { echo "FAIL: foreign ownership exited $RC, want 12"; cat "$T/g6c.json"; exit 1; }
grep -q 'foreign' "$T/g6c.json"

# 7. (N1/N2 gates) a session that skips a normalized literal fails
#    exit 23 with no record written — and the run's tail survives
TD7="$REPO/.ai-dlc/tasks/skip-planning"; mkdir -p "$TD7/gates"
approve "$TD7"
git -C "$REPO" checkout -q -b task/refuse-me
printf 'r\n' > "$REPO/r.txt"
git -C "$REPO" add r.txt
git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm r
git -C "$REPO" checkout -q "$BASE"
set +e
STUB_SKIP="git " $PY "$PLAN" close --change refuse-me --repo "$REPO" --task-dir "$TD7" > "$T/skip.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 23 ]] || { echo "FAIL: skipped literal exited $RC, want 23"; cat "$T/skip.json"; exit 1; }
grep -q 'no normalized call' "$T/skip.json"
grep -q '"closed": false' "$T/skip.json"
[[ ! -e "$T/records/refuse-me/archive-001.json" ]] \
  || { echo "FAIL: a record was written for an unjudged archive"; exit 1; }
if grep -q '"stage": "DONE"' "$TD7/state.json" 2>/dev/null; then
  echo "FAIL: the task record closed behind an unjudged archive"; exit 1; fi
git -C "$REPO" rev-parse -q --verify task/refuse-me >/dev/null \
  || { echo "FAIL: a failed archive removed the task branch"; exit 1; }
git -C "$REPO" branch -q -D task/refuse-me

# 8. (N2) a command that exits non-zero fails the close carrying its
#    output verbatim; nothing is reported archived — on its OWN change,
#    one the skip case above did not already archive
mkplane() {  # a strictly valid change named $1 in the PLANE's tree
  local C="$PROOT/openspec/changes/$1"
  mkdir -p "$C/specs/cap"
  printf '## Why\n\n%s\n\n## What Changes\n\n- One requirement.\n' "$1" > "$C/proposal.md"
  printf '## ADDED Requirements\n\n### Requirement: %s\n\nThe system SHALL %s.\n\n#### Scenario: It runs\n\n- **WHEN** it runs\n- **THEN** it %s\n' "$1" "$1" "$1" > "$C/specs/cap/spec.md"
}
mkplane fail-me
TD8="$REPO/.ai-dlc/tasks/fail-planning"; mkdir -p "$TD8/gates"
approve "$TD8"
git -C "$REPO" checkout -q -b task/fail-me
printf 'f\n' > "$REPO/f.txt"
git -C "$REPO" add f.txt
git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm f
git -C "$REPO" checkout -q "$BASE"
set +e
STUB_FAIL="openspec archive" $PY "$PLAN" close --change fail-me --repo "$REPO" --task-dir "$TD8" > "$T/fail.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 11 ]] || { echo "FAIL: failing command exited $RC, want 11"; cat "$T/fail.json"; exit 1; }
grep -q '"archive": "failed"' "$T/fail.json"
grep -q 'the stub was told to fail this command' "$T/fail.json"
grep -q '"closed": false' "$T/fail.json"
[[ ! -e "$T/records/fail-me/archive-001.json" ]] \
  || { echo "FAIL: a failed archive wrote a record"; exit 1; }
[[ -d "$PROOT/openspec/changes/fail-me" ]] \
  || { echo "FAIL: a failed archive moved the change"; exit 1; }
git -C "$REPO" branch -q -D task/fail-me

echo "L2 CLOSE TAIL: pass (no approval and no rationale wait on the person, neither merge nor archive; an approved close classifies the repo first — an unreachable repo stops exit 11 with the plane's tree untouched; the merge runs caller-side then archives through ONE plane session — every normalized literal judged from the frames and checked against the filesystem, the archived change and specs written back under a plane-authored commit, the record signed, the task closed and the run's worktree/branch removed, or their retention recorded; a split state resumes at the write-back alone against the archive that stands, the resume signed into the record; a repo-side change dir, an altered surface and foreign-owned content refuse at the door; a skipped literal fails exit 23 with no record; a failing command fails exit 11 carrying its output)"
