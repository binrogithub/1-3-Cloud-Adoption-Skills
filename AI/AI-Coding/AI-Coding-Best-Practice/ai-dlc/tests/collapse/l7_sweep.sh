#!/usr/bin/env bash
# L7 (landing tasks 7.4/7.5/7.9, reworked under containment N6): the run
# leaves the target as it found it. sweep judges the PLANE root — the
# tree every dispatch wrote — against the earliest pre-boundary
# baseline: what the run introduced and did not deliver is removed
# (bookkeeping dirs, run-caused tracked modifications restored to HEAD),
# what the plane tree already carried is never touched and the skip is
# recorded, the openspec/ tree stays for a person to commit unless the
# run was voided (--purge-openspec), the repo-side task record goes
# unless --keep-record, and the task worktree and branch go once the
# branch is merged — an unmerged branch holds the only copy of the work
# and is retained with that reason. Without a baseline nothing is
# removed.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
T=$(mktemp -d /root/ai-dlc-l7s-XXXXXX); trap 'rm -rf "$T"' EXIT
export AI_DLC_SPECS="$T/specs"
. "$ROOT/tests/collapse/lib_plane.sh"
REPO="$T/repo"; TD="$REPO/.ai-dlc/tasks/x-planning"

git -C "$T" init -q repo
printf 'base\n' > "$REPO/src.txt"
git -C "$REPO" add src.txt
git -C "$REPO" -c user.name=t -c user.email=t@t commit -qm seed
# N6: the working tree lives in the plane's home — the sweep judges the
# PLANE root, so the pre-existing state, the run's bookkeeping and the
# run-caused modification all stand there (the task record and the task
# worktree/branch stay repo-side, where the caller owns them)
plane_migrate "$REPO"
PROOT="$(plane_of "$REPO")"

# the tree's own pre-existing state (what the baseline will carry —
# untracked dirt the tree already held, exactly what the baseline
# records) and a file the plane tree already tracked when the run
# touched it
mkdir -p "$PROOT/old"; printf 'notes\n' > "$PROOT/old/notes.txt"
printf 'tracked\n' > "$PROOT/src.txt"
git -C "$PROOT" add src.txt
git -C "$PROOT" -c user.name=t -c user.email=t@t commit -qm seed

# the task record with the baseline the first dispatch would have written
mkdir -p "$TD/evidence"
printf '["old/notes.txt"]' > "$TD/evidence/plan-proposal-1.pre-boundary.json"
printf '{}\n' > "$TD/planning.json"

# what the run introduced: gateway bookkeeping, an openspec tree, and a
# run-caused modification of a tracked file
mkdir -p "$PROOT/.agent_history" "$PROOT/coding_memory" "$PROOT/prompt_attachment"
printf 'h\n' > "$PROOT/.agent_history/h.txt"
printf 'm\n' > "$PROOT/coding_memory/m.json"
printf 'p\n' > "$PROOT/prompt_attachment/p.txt"
mkdir -p "$PROOT/openspec/changes/archive/2026-08-30-x"
printf '## Why\n\nRun.\n' > "$PROOT/openspec/changes/archive/2026-08-30-x/proposal.md"
printf 'run touched me\n' > "$PROOT/src.txt"

# the task worktree and branch, holding the only copy of the work
git -C "$REPO" worktree add -q "$T/wt" -b task/x >/dev/null 2>&1
(cd "$T/wt" && printf 'work\n' > work.txt && git add work.txt \
  && git -c user.name=t -c user.email=t@t commit -qm work) >/dev/null 2>&1

# 1. default sweep: run's bookkeeping gone, record kept on request,
#    openspec retained, baseline untouched, unmerged work retained
$PY "$PLAN" sweep --change x --repo "$REPO" --keep-record > "$T/s1.json" 2>&1 \
  || { echo "FAIL: default sweep failed"; cat "$T/s1.json"; exit 1; }
grep -q '"swept": true' "$T/s1.json"
grep -q "\"plane_root\"" "$T/s1.json"
$PY - "$T/s1.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["skipped_baseline"], "baseline skip not recorded"
assert d["skipped_baseline"][0]["component"] == "old", d["skipped_baseline"]
assert any(r["component"] == "openspec" for r in d["retained"]), d["retained"]
assert d["branch"]["removed"] is False and "unmerged" in d["branch"]["reason"], d["branch"]
assert any(w["removed"] is False for w in d["worktrees"]), d["worktrees"]
flat = json.dumps(d["removed"])
assert ".agent_history/" in flat and "coding_memory/" in flat \
    and "prompt_attachment/" in flat, d["removed"]
assert any(r["restored_to_head"] for r in d["restored_to_head"]), d["restored_to_head"]
PYEOF
[[ -f "$PROOT/old/notes.txt" ]] || { echo "FAIL: baseline path removed"; exit 1; }
[[ "$(cat "$PROOT/old/notes.txt")" == "notes" ]] || { echo "FAIL: baseline path altered"; exit 1; }
[[ -d "$PROOT/.agent_history" || -d "$PROOT/coding_memory" || -d "$PROOT/prompt_attachment" ]] \
  && { echo "FAIL: bookkeeping left behind"; ls -a "$PROOT"; exit 1; }
[[ -d "$PROOT/openspec" ]] || { echo "FAIL: openspec purged without the flag"; exit 1; }
[[ -d "$REPO/.ai-dlc" ]] || { echo "FAIL: record removed despite --keep-record"; exit 1; }
[[ "$(cat "$PROOT/src.txt")" == "tracked" ]] \
  || { echo "FAIL: run-caused modification not restored: $(cat "$PROOT/src.txt")"; exit 1; }
git -C "$REPO" rev-parse -q --verify task/x >/dev/null \
  || { echo "FAIL: unmerged branch swept away"; exit 1; }
[[ -d "$T/wt" ]] || { echo "FAIL: unmerged worktree swept away"; exit 1; }

# 2. --purge-openspec: the voided run's openspec tree and record go too
$PY "$PLAN" sweep --change x --repo "$REPO" --purge-openspec > "$T/s2.json" 2>&1 \
  || { echo "FAIL: purge sweep failed"; cat "$T/s2.json"; exit 1; }
[[ ! -d "$PROOT/openspec" ]] || { echo "FAIL: openspec survived --purge-openspec"; exit 1; }
[[ ! -d "$REPO/.ai-dlc" ]] || { echo "FAIL: task record survived"; exit 1; }
[[ -f "$PROOT/old/notes.txt" ]] || { echo "FAIL: baseline path removed on purge"; exit 1; }

# 3. merged branch: the worktree and branch now go
REPO2="$T/repo2"
git -C "$T" init -q repo2
printf 'base\n' > "$REPO2/src.txt"
git -C "$REPO2" add src.txt
git -C "$REPO2" -c user.name=t -c user.email=t@t commit -qm seed
plane_migrate "$REPO2"
TD2="$REPO2/.ai-dlc/tasks/y-planning"
mkdir -p "$TD2/evidence"
printf '[]' > "$TD2/evidence/plan-proposal-1.pre-boundary.json"
git -C "$REPO2" worktree add -q "$T/wt2" -b task/y >/dev/null 2>&1
(cd "$T/wt2" && printf 'work\n' > work.txt && git add work.txt \
  && git -c user.name=t -c user.email=t@t commit -qm work) >/dev/null 2>&1
git -C "$REPO2" merge -q --no-edit task/y >/dev/null 2>&1
$PY "$PLAN" sweep --change y --repo "$REPO2" > "$T/s3.json" 2>&1 \
  || { echo "FAIL: merged sweep failed"; cat "$T/s3.json"; exit 1; }
[[ ! -d "$T/wt2" ]] || { echo "FAIL: merged worktree left behind"; exit 1; }
git -C "$REPO2" rev-parse -q --verify task/y >/dev/null 2>&1 \
  && { echo "FAIL: merged branch left behind"; git -C "$REPO2" branch; exit 1; }
grep -q '"removed": true' "$T/s3.json"

# 4. no baseline -> nothing removed (sweep cannot tell whose paths they are)
REPO3="$T/repo3"
git -C "$T" init -q repo3
printf 'base\n' > "$REPO3/src.txt"
git -C "$REPO3" add src.txt
git -C "$REPO3" -c user.name=t -c user.email=t@t commit -qm seed
plane_migrate "$REPO3"
PROOT3="$(plane_of "$REPO3")"
mkdir -p "$PROOT3/junk"; printf 'j\n' > "$PROOT3/junk/j.txt"
set +e
$PY "$PLAN" sweep --change z --repo "$REPO3" > "$T/s4.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: baseline-less sweep exited $RC, want 1"; cat "$T/s4.json"; exit 1; }
grep -q '"swept": false' "$T/s4.json"
[[ -f "$PROOT3/junk/j.txt" ]] || { echo "FAIL: removed without a baseline"; exit 1; }

echo "L7 SWEEP: pass (the plane root judged against the baseline: bookkeeping gone, baseline path skipped and recorded, openspec retained for a person, --purge-openspec for a voided run, tracked modification restored to HEAD, repo-side record kept on request, unmerged work retained with the reason, merged worktree+branch removed, no baseline -> nothing removed)"
