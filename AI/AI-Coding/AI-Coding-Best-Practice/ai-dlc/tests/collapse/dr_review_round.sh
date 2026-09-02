#!/usr/bin/env bash
# DR (design-review): the adversarial round over the design artifact.
# V1 — the roster: axes are the named list in the configuration; an
# off-list axis, a reasonless choice, an empty choice and a choice over
# the configured maximum are refused, and two personas sharing a stance
# fail the roster check before anything is paid. V2 — the round: it
# runs only when the design artifact ran (a recorded skip is carried as
# the reason it did not), reviewers go through the per-role dispatch
# with own session/frame/baseline, a second finding, a write outside
# the reviewer's own path (an edit of the design included) and silence
# in place of an explicit nothing-found all fail the dispatch. V3 — the
# revision: the author is dispatched once more with every finding,
# answers each on the record, and an unanswered finding blocks the
# phase from reporting complete while the delivery criteria stay
# untouched — the round travels into the delivery report as advice.
# V4 — team mode is refused with the three recorded reasons and by
# reference to the team-mode record; an unresolved finding never blocks
# delivery. V5 — the synthesis (review-synthesis): after the reviewers
# and before the author is dispatched, the caller groups the findings,
# names every opposing pair and cites each concern to its finding — no
# session is opened for it; an uncited concern, an unfiled citation,
# an omitted finding, a side-taking passage, a silent no-pairs and a
# one-directional pair all fail the round; the revision carries every
# finding in full with the synthesis alongside and the answers owed to
# the findings — answering the synthesis alone blocks as unanswered;
# the synthesis travels into the delivery report as advice.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
REPORT="$ROOT/bin/report.py"
T=$(mktemp -d /root/ai-dlc-dr-XXXXXX); trap 'rm -rf "$T"' EXIT
# N6: every round writes the plane's own tree — minted per repo in mk_case
export AI_DLC_SPECS="$T/specs"
. "$ROOT/tests/collapse/lib_plane.sh"
# the fixture lives under /root, which the real plane sees read-only
# (ProtectHome) — these cases exercise the writable class, so the probe
# reads this namespace's view of the path. The three classes and the
# split workspace they imply are covered by ad_any_directory.sh.
export AI_DLC_GATEWAY_ROOT=/
# the plane's records and key live in the test's own world: the round
# runs only when the design artifact stands done, and that state is
# read from the plane's signed records — the caller no longer looks at
# the tree. mk_case signs the graph (design carries the upstream
# instruction's own inclusion conditions, so a skip stays decidable)
# and a verdict marking every artifact done and the phase complete,
# minted after the last artifact write so accept never sees it stale
RT="$ROOT/tests/collapse/records_tool.py"
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key


cat > "$T/stub-client" <<'EOF'
#!/usr/bin/env bash
# one dispatch: a reviewer (one finding to its own path) or the author
# revising (answers to the review record). What it writes is steered by
# STUB_MODE / STUB_REV so the reverse cases are provable without a
# live plane. Emits the event frames the judge reads.
s=""; prev=""
for a in "$@"; do
  if [ "$prev" = "--session" ]; then s="$a"; fi
  prev="$a"
done
prompt="$2"
d="${0%/*}"
printf 'start %s\n' "$s" >> "$d/calls.log"
mkdir -p "$d/prompts"
printf '%s\n' "$prompt" > "$d/prompts/$s.prompt"
axis="$(printf '%s\n' "$prompt" | sed -n 's/^You are the \([a-z]*\) reviewer.*/\1/p')"
emit_write () {  # $1 = path
  printf '{"type":"event","event":"chat.tool_call","payload":{"tool_name":"write_file","arguments":"{\\"path\\": \\"%s\\"}"}}\n' "$1"
}
if [ -n "$axis" ]; then
  path="$(printf '%s\n' "$prompt" | sed -n 's/^Write exactly one file, this path and no other: //p')"
  mode="${STUB_MODE:-ok}"
  case " ${STUB_NOTHING_AXES:-} " in
    *" $axis "*) mode=nothing ;;
  esac
  case "$mode" in
    ok)
      { printf 'Axis: %s\n\n## Finding\n\n' "$axis"
        printf 'Where: the concurrency section.\nConcern: on the %s axis.\nChange: name a ceiling.\n' "$axis"; } > "$path"
      emit_write "$path" ;;
    two)
      { printf 'Axis: %s\n\n## Finding\n\nfirst\n\n## Finding\n\nsecond\n' "$axis"; } > "$path"
      emit_write "$path" ;;
    stray)
      { printf 'Axis: %s\n\n## Finding\n\none finding, but hands elsewhere\n' "$axis"; } > "$path"
      emit_write "$path"
      dm="$(echo openspec/changes/*/design.md)"
      printf 'design edited by a reviewer\n' > "$dm"
      emit_write "$dm" ;;
    silent) : ;;
    nothing)
      { printf 'Axis: %s\n\n## Nothing found\n\n## Examined\n\n- the whole design on the %s axis\n' "$axis" "$axis"; } > "$path"
      emit_write "$path" ;;
    bare-nothing)
      printf 'Axis: %s\n\n## Nothing found\n\n' "$axis" > "$path"
      emit_write "$path" ;;
  esac
else
  apath="$(printf '%s\n' "$prompt" | sed -n 's/^- write your answers to \([^ ]*\).*/\1/p')"
  mkdir -p "$(dirname "$apath")"
  case "${STUB_REV:-full}" in
    full)
      { printf '### security\n\naccepted: yes\nnamed a ceiling in the design\n'
        printf '\n### performance\n\naccepted: no\nthe ceiling belongs to the gateway\n'; } > "$apath" ;;
    partial)
      printf '### security\n\naccepted: yes\nnamed a ceiling in the design\n' > "$apath" ;;
    synthesis)
      printf '### synthesis\n\naccepted: yes\nanswered the synthesis as one blob\n' > "$apath" ;;
  esac
  emit_write "$apath"
fi
printf '{"event":"chat.final","payload":{"content":"done"}}\n'
EOF
chmod +x "$T/stub-client"
export AI_DLC_CLIENT="$T/stub-client"

mk_case () {  # a repo whose change is complete: proposal, specs, tasks,
              # design — the design artifact stands done. Echoes the repo.
  local name="$1" repo="$T/$1/repo"
  mkdir -p "$T/$name"
  git -C "$T/$name" init -q repo
  git -C "$repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
  (cd "$repo" && openspec init --tools none --language en) >/dev/null 2>&1
  mkdir -p "$repo/openspec/changes/$name/specs/website"
  printf '## Why\n\nThe site has no navigation.\n\n## What Changes\n\n- Add a shared navigation bar.\n' \
    > "$repo/openspec/changes/$name/proposal.md"
  printf '## ADDED Requirements\n\n### Requirement: Navigation bar\n\nThe site SHALL show a navigation bar on every page.\n\n#### Scenario: Visitor opens any page\n\n- **WHEN** a visitor opens any page\n- **THEN** the navigation bar is visible\n' \
    > "$repo/openspec/changes/$name/specs/website/spec.md"
  printf '## Context\n\nA static site.\n\n## Decisions\n\n- Build-time injection.\n\n## Risks / Trade-offs\n\n- None measured.\n' \
    > "$repo/openspec/changes/$name/design.md"
  printf '# Tasks\n\n- [ ] 1.1 add the navigation fragment\n' \
    > "$repo/openspec/changes/$name/tasks.md"
  plane_migrate "$repo"
  "$PY" "$RT" graph "$name" --schema spec-driven --artifacts-json \
    '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"],"conditional":true,"conditions":["Cross-cutting change (multiple services/modules) or new architectural pattern","New external dependency or significant data model changes","Security, performance, or migration complexity","Ambiguity that benefits from technical decisions before coding"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
  "$PY" "$RT" verdict "$name" --rc 0 \
    --artifacts proposal=done,specs=done,design=done,tasks=done \
    --complete true >/dev/null
  echo "$repo"
}

AXES3="security: concurrency runs beside a permission engine that is off, operability: the shared record is written by separate invocations, performance: no concurrency ceiling is named"

# 1. (V1.4) an axis off the named list is refused — adding one means
#    amending the list first
R="$(mk_case dr1)"
set +e
$PY "$PLAN" review --change dr1 --repo "$R" --axes "aesthetic: it looks wrong" > "$T/1.json" 2>&1
RC=$?
set -e
[[ "$RC" -eq 4 ]] || { echo "FAIL: off-list axis exited $RC, want 4"; cat "$T/1.json"; exit 1; }
grep -q "not on the named list" "$T/1.json"
grep -q "security" "$T/1.json"

# 2. (V2.2) no axes named, and a reasonless choice, are both refused
set +e
$PY "$PLAN" review --change dr1 --repo "$R" > "$T/2a.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 4 ]] || { echo "FAIL: empty axes exited $RC"; cat "$T/2a.json"; exit 1; }
grep -q "named with a reason each" "$T/2a.json"
set +e
$PY "$PLAN" review --change dr1 --repo "$R" --axes "security:" > "$T/2b.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 4 ]] || { echo "FAIL: reasonless axis exited $RC"; cat "$T/2b.json"; exit 1; }
grep -q "chosen without a reason" "$T/2b.json"

# 3. (V1.5 reverse) two personas sharing a stance fail the roster
#    check before any dispatch is paid
sed 's/axis.operability.stance: suspicious of anything that holds only while a single process stays alive/axis.operability.stance: suspicious of anything that widens who can act or what a process can reach without a named owner/' \
  "$ROOT/config/collapsed.config.yaml" > "$T/clash.config.yaml"
AI_DLC_CONFIG="$T/clash.config.yaml" $PY "$PLAN" review --change dr1 --repo "$R" \
  --axes "$AXES3" > "$T/3.json" 2>&1 \
  && { echo "FAIL: stance clash accepted"; cat "$T/3.json"; exit 1; } || true
grep -q "share a stance" "$T/3.json"
grep -q '"rejected": "reviewer roster"' "$T/3.json"

# 4. (V1.1) more axes than the configured maximum are refused, not
#    truncated
sed 's/max_axes: 3/max_axes: 2/' "$ROOT/config/collapsed.config.yaml" > "$T/small.config.yaml"
set +e
AI_DLC_CONFIG="$T/small.config.yaml" $PY "$PLAN" review --change dr1 --repo "$R" \
  --axes "$AXES3" > "$T/4.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 4 ]] || { echo "FAIL: over-max axes exited $RC"; cat "$T/4.json"; exit 1; }
grep -q "refuses rather than truncate" "$T/4.json"

# 5. (V4.3/RS 4.5) team mode is refused with the three recorded
#    reasons, by reference to the record — no experiment runs
set +e
$PY "$PLAN" review --change dr1 --repo "$R" --mode team --axes "$AXES3" > "$T/5.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 4 ]] || { echo "FAIL: team mode exited $RC"; cat "$T/5.json"; exit 1; }
grep -q "order of magnitude longer" "$T/5.json"
grep -q "invisible until it ends" "$T/5.json"
grep -q "docs/team-mode-record.md" "$T/5.json"
grep -q "no new experiment" "$T/5.json"
$PY - "$R/.ai-dlc/tasks/dr1-planning/planning.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))["review"]
assert len(r["rejected_team_mode"]["reasons"]) == 3, r
assert r["rejected_team_mode"]["record"] == "docs/team-mode-record.md", r
PYEOF

# 6. (V2.1) the design artifact skipped by decision: the round does not
#    run and the skip is carried as the reason
R6="$(mk_case dr6)"
$PY "$PLAN" decide --change dr6 --repo "$R6" --artifact design \
  --skip --reason "one module, no new dependency, no migration" \
  --decided-by tester >/dev/null
$PY "$PLAN" review --change dr6 --repo "$R6" --axes "$AXES3" > "$T/6.json" 2>&1 \
  || { echo "FAIL: skipped round exited non-zero"; cat "$T/6.json"; exit 1; }
grep -q '"review": "skipped"' "$T/6.json"
grep -q "one module, no new dependency" "$T/6.json"

# 7. (V2.3/2.4/2.6) the round: reviewers through the per-role dispatch,
#    one finding each, an explicit nothing-found where nothing was found
R7="$(mk_case dr7)"
STUB_NOTHING_AXES=operability $PY "$PLAN" review --change dr7 --repo "$R7" \
  --axes "$AXES3" --concurrency 3 --stage reviewers > "$T/7.json" 2>&1 \
  || { echo "FAIL: reviewers stage exited non-zero"; cat "$T/7.json"; exit 1; }
$PY - "$R7" "$(plane_of "$R7")" "$T/7.json" <<'PYEOF'
import json, sys
repo, plane, out = sys.argv[1], sys.argv[2], json.load(open(sys.argv[3]))
p = json.load(open(f"{repo}/.ai-dlc/tasks/dr7-planning/planning.json"))
r = p["review"]
assert [c["axis"] for c in r["axes_chosen"]] == \
    ["security", "operability", "performance"], r["axes_chosen"]
assert all(c["reason"] for c in r["axes_chosen"]), r["axes_chosen"]
assert r["axes_not_chosen"] == [], r["axes_not_chosen"]
assert r["failures"] == [], r["failures"]
kinds = {a: v["kind"] for a, v in r["reviewers"].items()}
assert kinds == {"security": "finding", "operability": "nothing",
                 "performance": "finding"}, kinds
for a, v in r["reviewers"].items():
    assert v["session_name"] == f"plan-dr7-review-{a}", v
    assert v["outcome"] == 0, v
    f = open(f"{plane}/{v['finding']}").read()
    assert f"Axis: {a}" in f, f
assert r["complete"] is False, r
PYEOF
for a in security operability performance; do
  grep -q "plan-dr7-review-$a" "$T/calls.log"
done
# the findings live on the plane's own review surface, never repo-side
[[ -f "$(plane_of "$R7")/.ai-dlc/review/dr7/operability/finding.md" ]]
[[ ! -e "$R7/.ai-dlc/tasks/dr7-planning/review/operability" ]]

# 8. (V2.5 reverse) a reviewer that files two findings fails the
#    dispatch, and nothing of the round is reported complete
R8="$(mk_case dr8)"
rm -f "$T/calls.log"
set +e
STUB_MODE=two $PY "$PLAN" review --change dr8 --repo "$R8" \
  --axes "$AXES3" > "$T/8.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: two findings exited $RC, want 18"; cat "$T/8.json"; exit 1; }
grep -q "findings are filed" "$T/8.json"

# 9. (V2.5/V4.4 reverse) a reviewer that edits the design fails the
#    dispatch — its write left its own path
R9="$(mk_case dr9)"
set +e
STUB_MODE=stray $PY "$PLAN" review --change dr9 --repo "$R9" \
  --axes "security: the permission engine is off under concurrency" > "$T/9.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: stray write exited $RC, want 18"; cat "$T/9.json"; exit 1; }
grep -q "outside its own path" "$T/9.json"

# 10. (V2.6 reverse) silence is not a nothing-found record
R10="$(mk_case dr10)"
set +e
STUB_MODE=silent $PY "$PLAN" review --change dr10 --repo "$R10" \
  --axes "security: the permission engine is off under concurrency" > "$T/10.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: silent reviewer exited $RC, want 18"; cat "$T/10.json"; exit 1; }
grep -q "finding file was not written" "$T/10.json"

# 11. (V2.6 reverse) a nothing-found without a record of what was
#     examined is refused too
R11="$(mk_case dr11)"
set +e
STUB_MODE=bare-nothing $PY "$PLAN" review --change dr11 --repo "$R11" \
  --axes "security: the permission engine is off under concurrency" > "$T/11.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: bare nothing exited $RC, want 18"; cat "$T/11.json"; exit 1; }
grep -q "no record of what was examined" "$T/11.json"

# 12. (RS 1.1) after the reviewers, a revision without the synthesis
#     waits for it — the caller writes it, and no dispatch is opened
rm -f "$T/calls.log"
rm -rf "$T/prompts"
set +e
STUB_REV=full $PY "$PLAN" review --change dr7 --repo "$R7" \
  --axes "$AXES3" --stage revision > "$T/12.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: revision without a synthesis exited $RC, want 1"; cat "$T/12.json"; exit 1; }
grep -q '"waiting_on": "the synthesis"' "$T/12.json"
grep -q "no dispatch can produce the synthesis" "$T/12.json"
[[ ! -e "$T/calls.log" ]] || { echo "FAIL: a session was opened for the synthesis"; cat "$T/calls.log"; exit 1; }
# the composed round stops at the same gate: --stage all will not skip
# the caller's step by dispatching the author past it
set +e
STUB_REV=full $PY "$PLAN" review --change dr7 --repo "$R7" \
  --axes "$AXES3" > "$T/12b.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: stage all skipped the synthesis (rc $RC)"; cat "$T/12b.json"; exit 1; }
grep -q '"waiting_on": "the synthesis"' "$T/12b.json"

# the syntheses the reverse cases break: two filed axes (dr7's
# operability recorded nothing found) and three
write_synth () {  # $1 = task record dir, $2 = two|three
  local td="$1"
  mkdir -p "$td/review"    # the caller's own write, its own directory
  { printf '# Synthesis\n\nGroups ordered by where each lands in the design.\n\n'
    printf '## Group — Decisions (build-time injection)\n'
    printf -- '- [security] the injection runs with no containment named\n'
    printf -- '- [performance] the injection names no ceiling on concurrent work\n'
    if [ "$2" = three ]; then
      printf '\n## Group — Risks (the shared record)\n'
      printf -- '- [operability] the record is written by separate invocations with no lock\n'
    fi
    printf '\n## Opposing — [security] against [performance]\n'
    printf -- '- lands: the injection decision\n'
    printf -- '- [security] increases: isolation cost — a narrower blast radius is a slower path\n'
    printf -- '- [performance] reduces: that same speed — a ceiling spent on containment\n'
  } > "$td/review/synthesis.md"
}

# 13. (RS 1.1–1.6) the caller writes the synthesis; the stage checks it
#     and records it — zero sessions, zero dispatches
TD7="$R7/.ai-dlc/tasks/dr7-planning"
write_synth "$TD7" two
$PY "$PLAN" review --change dr7 --repo "$R7" \
  --axes "$AXES3" --stage synthesis > "$T/13.json" 2>&1 \
  || { echo "FAIL: synthesis stage exited non-zero"; cat "$T/13.json"; exit 1; }
[[ ! -e "$T/calls.log" ]] || { echo "FAIL: the synthesis stage opened a session"; cat "$T/calls.log"; exit 1; }
$PY - "$TD7/planning.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))["review"]
s = r["synthesis"]
assert s["produced_by"] == "caller" and s["sessions_opened"] == 0, s
assert s["ok"] is True, s
assert s["path"] == ".ai-dlc/tasks/dr7-planning/review/synthesis.md", s
assert [g["cites"] for g in s["groups"]] == \
    [["security", "performance"]], s
assert s["opposing_pairs"] == \
    [{"axes": ["security", "performance"]}], s
assert s["no_opposing_pairs"] is False, s
PYEOF

# 14. (RS 3.1/3.2) the revision: every original finding in full, the
#     synthesis alongside, and the answers owed to the findings
rm -f "$T/calls.log"
STUB_REV=full $PY "$PLAN" review --change dr7 --repo "$R7" \
  --axes "$AXES3" --stage revision > "$T/14.json" 2>&1 \
  || { echo "FAIL: revision stage exited non-zero"; cat "$T/14.json"; exit 1; }
grep -q "plan-dr7-design" "$T/calls.log" \
  || { echo "FAIL: the author was not re-dispatched"; cat "$T/calls.log"; exit 1; }
P="$T/prompts/plan-dr7-design.prompt"
grep -q "Every finding follows, verbatim" "$P"
grep -q "on the security axis" "$P"      # the finding itself, verbatim
grep -q "reading aid that groups them" "$P"
grep -q "answers are owed to the findings" "$P"
grep -q "not a thing to answer" "$P"
grep -q "## Opposing" "$P"               # the synthesis travels along
$PY - "$R7" "$T/14.json" <<'PYEOF'
import json, sys
repo, out = sys.argv[1], json.load(open(sys.argv[2]))
r = json.load(open(f"{repo}/.ai-dlc/tasks/dr7-planning/planning.json"))["review"]
rev = r["revision"]
assert rev["dispatched"] is True, rev
# operability recorded nothing found — it carries no finding to answer
assert rev["answers"] == {"security": True, "performance": False}, rev
assert rev["unanswered"] == [], rev
assert r["complete"] is True, r
PYEOF

# 15. (V3.3) with the round complete the phase may report complete;
#     with a design dispatched and no round it may not
$PY "$PLAN" accept --change dr7 --repo "$R7" > "$T/15a.json" 2>&1 \
  || { echo "FAIL: accept after a complete round"; cat "$T/15a.json"; exit 1; }
grep -q '"phase_complete": true' "$T/15a.json"
R15="$(mk_case dr15)"
mkdir -p "$R15/.ai-dlc/tasks/dr15-planning"
printf '{"change": "dr15", "dispatches": {"design": {"attempts": 1}}}\n' \
  > "$R15/.ai-dlc/tasks/dr15-planning/planning.json"
$PY "$PLAN" accept --change dr15 --repo "$R15" \
  --task-dir "$R15/.ai-dlc/tasks/dr15-planning" > "$T/15b.json" 2>&1 \
  || { echo "FAIL: accept without a round"; cat "$T/15b.json"; exit 1; }
grep -q '"phase_complete": false' "$T/15b.json"
grep -q "no review round is recorded" "$T/15b.json"

# 16. (V3.5 reverse) a revision that leaves a finding unanswered blocks
#     the phase and names the finding
R16="$(mk_case dr16)"
STUB_REV=partial $PY "$PLAN" review --change dr16 --repo "$R16" \
  --axes "$AXES3" --stage reviewers >/dev/null 2>&1
write_synth "$R16/.ai-dlc/tasks/dr16-planning" three
set +e
STUB_REV=partial $PY "$PLAN" review --change dr16 --repo "$R16" \
  --axes "$AXES3" --stage revision > "$T/16.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 19 ]] || { echo "FAIL: unanswered finding exited $RC, want 19"; cat "$T/16.json"; exit 1; }
grep -q '"unanswered_findings"' "$T/16.json"
grep -q "performance" "$T/16.json"
$PY "$PLAN" accept --change dr16 --repo "$R16" > "$T/16b.json" 2>&1 \
  || { echo "FAIL: accept after an unanswered finding"; cat "$T/16b.json"; exit 1; }
grep -q '"phase_complete": false' "$T/16b.json"
$PY - "$T/16b.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
assert r["review"]["unanswered_findings"] == \
    ["operability", "performance"], r["review"]
PYEOF

# 17. (RS 2.5 reverse) a synthesis carrying an uncited concern fails
#     the round, the passage named
R17="$(mk_case dr17)"
STUB_REV=full $PY "$PLAN" review --change dr17 --repo "$R17" \
  --axes "$AXES3" --stage reviewers >/dev/null 2>&1
TD17="$R17/.ai-dlc/tasks/dr17-planning"
write_synth "$TD17" three
sed -i 's/^- \[security\] the injection runs with no containment named$/- containment is simply missing/' \
  "$TD17/review/synthesis.md"
set +e
$PY "$PLAN" review --change dr17 --repo "$R17" \
  --axes "$AXES3" --stage synthesis > "$T/17.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: uncited concern exited $RC, want 18"; cat "$T/17.json"; exit 1; }
grep -q "cites no finding" "$T/17.json"
grep -q "containment is simply missing" "$T/17.json"

# 18. (RS 2.5 reverse) a concern citing a finding no reviewer filed
#     fails the round, the finding named
R18="$(mk_case dr18)"
STUB_REV=full $PY "$PLAN" review --change dr18 --repo "$R18" \
  --axes "$AXES3" --stage reviewers >/dev/null 2>&1
TD18="$R18/.ai-dlc/tasks/dr18-planning"
write_synth "$TD18" three
sed -i 's/^- \[security\]/- [aesthetic]/' "$TD18/review/synthesis.md"
set +e
$PY "$PLAN" review --change dr18 --repo "$R18" \
  --axes "$AXES3" --stage synthesis > "$T/18.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: unfiled citation exited $RC, want 18"; cat "$T/18.json"; exit 1; }
grep -q "no reviewer filed" "$T/18.json"
grep -q "aesthetic" "$T/18.json"

# 19. (RS 2.6 reverse) a synthesis omitting a filed finding fails the
#     round, the finding named
R19="$(mk_case dr19)"
STUB_REV=full $PY "$PLAN" review --change dr19 --repo "$R19" \
  --axes "$AXES3" --stage reviewers >/dev/null 2>&1
TD19="$R19/.ai-dlc/tasks/dr19-planning"
write_synth "$TD19" three
sed -i '/^- \[performance\] the injection names no ceiling/d' \
  "$TD19/review/synthesis.md"
set +e
$PY "$PLAN" review --change dr19 --repo "$R19" \
  --axes "$AXES3" --stage synthesis > "$T/19.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: omitted finding exited $RC, want 18"; cat "$T/19.json"; exit 1; }
grep -q "appears in no group" "$T/19.json"
grep -q '"finding": "performance"' "$T/19.json"

# 20. (RS 2.7 reverse) a synthesis that recommends between findings
#     fails the round, the passage named
R20="$(mk_case dr20)"
STUB_REV=full $PY "$PLAN" review --change dr20 --repo "$R20" \
  --axes "$AXES3" --stage reviewers >/dev/null 2>&1
TD20="$R20/.ai-dlc/tasks/dr20-planning"
write_synth "$TD20" three
printf -- '- the security finding should win — act on it first\n' \
  >> "$TD20/review/synthesis.md"
set +e
$PY "$PLAN" review --change dr20 --repo "$R20" \
  --axes "$AXES3" --stage synthesis > "$T/20.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: side-taking synthesis exited $RC, want 18"; cat "$T/20.json"; exit 1; }
grep -q "picks a side" "$T/20.json"
grep -q "should win" "$T/20.json"

# 21. (RS 1.5 reverse) no opposing pair and no statement that none
#     oppose — silence does not stand in for the statement; stated, it
#     passes
R21="$(mk_case dr21)"
STUB_REV=full $PY "$PLAN" review --change dr21 --repo "$R21" \
  --axes "$AXES3" --stage reviewers >/dev/null 2>&1
TD21="$R21/.ai-dlc/tasks/dr21-planning"
write_synth "$TD21" three
sed -i '/^## Opposing/,$d' "$TD21/review/synthesis.md"
set +e
$PY "$PLAN" review --change dr21 --repo "$R21" \
  --axes "$AXES3" --stage synthesis > "$T/21.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: silent no-pairs exited $RC, want 18"; cat "$T/21.json"; exit 1; }
grep -q "silence does not stand in" "$T/21.json"
printf '\n## No opposing pairs\n\nNo two findings pull against each other.\n' \
  >> "$TD21/review/synthesis.md"
$PY "$PLAN" review --change dr21 --repo "$R21" \
  --axes "$AXES3" --stage synthesis > "$T/21b.json" 2>&1 \
  || { echo "FAIL: explicit no-pairs refused"; cat "$T/21b.json"; exit 1; }
grep -q '"no_opposing_pairs": true' "$T/21b.json"

# 22. (RS pair contract) an opposing pair that states one direction
#     only is incomplete — both directions or it is not a relationship
R22="$(mk_case dr22)"
STUB_REV=full $PY "$PLAN" review --change dr22 --repo "$R22" \
  --axes "$AXES3" --stage reviewers >/dev/null 2>&1
TD22="$R22/.ai-dlc/tasks/dr22-planning"
write_synth "$TD22" three
sed -i '/^- \[performance\] reduces:/d' "$TD22/review/synthesis.md"
set +e
$PY "$PLAN" review --change dr22 --repo "$R22" \
  --axes "$AXES3" --stage synthesis > "$T/22.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 18 ]] || { echo "FAIL: one-directional pair exited $RC, want 18"; cat "$T/22.json"; exit 1; }
grep -q "both directions" "$T/22.json"

# 23. (RS 3.5 reverse) a revision answering the synthesis instead of
#     each finding blocks the phase, the findings named
R23="$(mk_case dr23)"
STUB_REV=full $PY "$PLAN" review --change dr23 --repo "$R23" \
  --axes "$AXES3" --stage reviewers >/dev/null 2>&1
write_synth "$R23/.ai-dlc/tasks/dr23-planning" three
set +e
STUB_REV=synthesis $PY "$PLAN" review --change dr23 --repo "$R23" \
  --axes "$AXES3" --stage revision > "$T/23.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 19 ]] || { echo "FAIL: synthesis-only answers exited $RC, want 19"; cat "$T/23.json"; exit 1; }
$PY - "$T/23.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
assert r["unanswered_findings"] == \
    ["operability", "performance", "security"], r["unanswered_findings"]
PYEOF

# 24. (RS 2.4) a roster role named for synthesis or leadership is
#     refused with the recorded reason
sed 's/^  axis.security.stance:/  axis.synthesis.stance: brings the findings together as a summariser\n  axis.synthesis.accepts: grouping what the reviewers said\n  axis.synthesis.refuses: leaving findings unrelated\n  axis.security.stance:/' \
  "$ROOT/config/collapsed.config.yaml" > "$T/synth-role.config.yaml"
R24="$(mk_case dr24)"
set +e
AI_DLC_CONFIG="$T/synth-role.config.yaml" $PY "$PLAN" review \
  --change dr24 --repo "$R24" --axes "$AXES3" > "$T/24.json" 2>&1; RC=$?
set -e
[[ "$RC" -eq 17 ]] || { echo "FAIL: synthesis roster role exited $RC, want 17"; cat "$T/24.json"; exit 1; }
grep -q "equal by construction" "$T/24.json"
grep -q "docs/team-mode-record.md" "$T/24.json"
$PY - "$R24/.ai-dlc/tasks/dr24-planning/planning.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))["review"]
assert r["rejected_roster_role"]["axes"] == ["synthesis"], r
assert "caller" in r["rejected_roster_role"]["reason"], r
PYEOF

# 25. (RS 3.4) the synthesis travels into the delivery report as advice
#     and takes no part in the decision: an unanswered finding beside
#     green criteria delivers, synthesis and all
R25="$(mk_case dr25)"
STUB_REV=partial $PY "$PLAN" review --change dr25 --repo "$R25" \
  --axes "$AXES3" --stage reviewers >/dev/null 2>&1
write_synth "$R25/.ai-dlc/tasks/dr25-planning" three
STUB_REV=partial $PY "$PLAN" review --change dr25 --repo "$R25" \
  --axes "$AXES3" --stage revision >/dev/null 2>&1 || true
TD="$R25/.ai-dlc/tasks/dr25-impl"
/usr/bin/python3.9 "$REPORT" init --task-dir "$TD" --repo "$R25" \
  --route planned --task-id dr25-impl --change dr25 >/dev/null
printf 'print("navigation")\n' > "$R25/nav.py"
git -C "$R25" add nav.py
git -C "$R25" -c user.name=t -c user.email=t@t commit -qm "nav"
mkdir -p "$TD/gates"
printf '{"gate_id": "gate-merge", "decision": "approve", "approver": "user", "rationale": "read it", "ts": "2026-08-31T00:00:00Z"}\n' \
  > "$TD/gates/gate-merge.answer.json"
/usr/bin/python3.9 "$REPORT" deliver --task-dir "$TD" --repo "$R25" --no-design \
  --no-design-by tester --no-design-why 'gate probe' \
  --outcome completed > "$T/25.json" 2>&1 \
  || { echo "FAIL: deliver exited non-zero"; cat "$T/25.json"; exit 1; }
$PY - "$T/25.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
assert r["delivered"] is True, r
assert r["outcome"] == "completed", r
adv = r["review_advice"]
assert adv["unanswered"] == ["operability", "performance"], adv
syn = adv["synthesis"]
assert syn["produced_by"] == "caller", syn
assert syn["opposing_pairs"] == [["security", "performance"]], syn
assert syn["ok"] is True, syn
assert "never a delivery criterion" in adv["record"], adv
assert "by anything the synthesis says" in adv["record"], adv
PYEOF

echo "DR REVIEW ROUND: pass (off-list, reasonless, over-max and team-mode choices refused with the reasons recorded and the record cited; a stance clash and a synthesis/leader roster role fail the roster; a skipped design carries its reason; reviewers run one finding per axis through the per-role dispatch with sessions and frames of their own; two findings, an edit of the design, silence and a bare nothing-found all fail the dispatch; the caller synthesises with zero sessions — an uncited concern, an unfiled citation, an omitted finding, a side-taking passage, a silent no-pairs and a one-directional pair all fail the round; the author answers every finding with the synthesis alongside and owed to the findings — answering the synthesis alone blocks as unanswered; an unanswered finding blocks the phase report and never blocks delivery — the round and the synthesis travel as advice)"
