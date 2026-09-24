#!/usr/bin/env bash
# any-directory: a project in any directory is read in place, without
# being copied.
#
# The target's class is probed — read and write separately, through the
# gateway's own view of the path — never guessed from a prefix. A
# writable target dispatches against itself; a readable target is read
# in place through a split workspace (a scratch the round writes to, the
# project granted for reading, guarded before the client exists); only
# an invisible target is copied, and the copy must be self-contained.
# A read-in-place round proves the project byte-for-byte untouched, and
# the return carries the change directory and nothing else. A draft that
# would widen the service unit's writable paths is refused with the
# split workspace named as the remedy.
#
# The probe and the plane run on fixtures: AI_DLC_GATEWAY_ROOT stands in
# for /proc/<MainPID>/root (a repo's view is a symlink to the real tree),
# AI_DLC_PROBE_READONLY for the read-only mount a test cannot reproduce
# as root, and AI_DLC_PLANE_ROOT for the plane's writable root, so
# nothing here touches the live service unit.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
# N6: every dispatch writes the plane's own tree — mint it per repo
export AI_DLC_SPECS="$T/specs"
. "$ROOT/tests/collapse/lib_plane.sh"
# the plane's records and key live in the test's own world: preflight
# admits a role only against the signed graph record, with dependencies
# done in the verdict's statuses. In the base tree records_tool.py does
# not exist and the old code reads openspec directly, so the minting is
# conditional on the tool being there.
if [ -f "$RT" ]; then
  export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
  $PY "$RT" key
fi
mkrecords() {  # <change>: the graph a graph dispatch signs, proposal done
  [ -f "$RT" ] || return 0
  $PY "$RT" graph "$1" --schema spec-driven --artifacts-json \
    '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
  $PY "$RT" verdict "$1" --rc 0 --artifacts proposal=done --complete false >/dev/null
}

# the fixture plane: its writable root, its data dir, its unit file
PLANE="$T/plane"; DATA="$T/data"
mkdir -p "$PLANE" "$DATA" "$T/projroot"
cat > "$T/gw.service" <<EOF
[Service]
Environment=JIUWENSWARM_DATA_DIR=$DATA
PrivateTmp=true
ReadWritePaths=$DATA
ReadWritePaths=$PLANE
EOF
export AI_DLC_GW_UNIT="$T/gw.service"
export AI_DLC_PLANE_ROOT="$PLANE"

# the fixture probe root: the gateway's own view of the filesystem.
# A repo's view is a symlink to the real tree, so read and write probe
# the real thing; removing the symlink makes the path invisible.
PROBE="$T/probe"
mkdir -p "$PROBE"
export AI_DLC_GATEWAY_ROOT="$PROBE"

# mkproj <name> — a real repo under $T/projroot with an openspec
# scaffold and a seeded proposal (so the specs and design roles are
# dispatchable), a package file beside it, a visible probe view
mkproj() {
  local repo="$T/projroot/$1"
  mkdir -p "$repo/openspec/changes/ch-$1/specs/cap"
  git -C "$repo" init -q
  git -C "$repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
  (cd "$repo" && openspec init --tools none --language en) >/dev/null 2>&1
  printf 'fixture content for %s\n' "$1" > "$repo/README.md"
  printf '# Proposal\n\n## Why\n\n%s needs behavior.\n\n## What Changes\n\n- Behave.\n' "$1" \
    > "$repo/openspec/changes/ch-$1/proposal.md"
  printf '{"requirement": "The %s SHALL behave.", "change_id": "ch-%s", "capability": "cap", "repo": "%s"}\n' \
    "$1" "$1" "$repo" > "$T/pkg-$1.json"
  mkdir -p "$PROBE$T/projroot"
  ln -s "$repo" "$PROBE$T/projroot/$1"
  plane_migrate "$repo"
  mkrecords "ch-$1"
  echo "$repo"
}

# the stub client: logs its full argv and its cwd, writes the role's
# artifact into the cwd the dispatch set, emits the frames the judge
# reads. STUB_WRITE_EXTRA names an extra path it writes (the reverse
# cases); STUB_SILENT emits no write at all.
cat > "$T/stub" <<'EOF'
#!/usr/bin/env bash
d="${0%/*}"
printf '%s\n' "$*" >> "$d/calls.log"
prompt="$2"; s=""; cwd=""
prev=""
for a in "$@"; do
  if [ "$prev" = "--session" ]; then s="$a"; fi
  if [ "$prev" = "--cwd" ]; then cwd="$a"; fi
  prev="$a"
done
[ -n "$cwd" ] || cwd="$PWD"
mkdir -p "$d/cwd"; printf '%s\n' "$cwd" > "$d/cwd/$s"
emit_write() {
  printf '{"type":"event","event":"chat.tool_call","payload":{"tool_name":"write_file","arguments":"{\\"path\\": \\"%s\\"}"}}\n' "$1"
}
emit_final() {
  printf '{"type":"event","event":"chat.final","payload":{"event_type":"chat.final","content":"done"}}\n'
}
change="${s#plan-}"; change="${change%-*}"; role="${s##*-}"
art="proposal.md"
case "$role" in
  specs) art="specs/cap/spec.md" ;;
  design) art="design.md" ;;
  tasks) art="tasks.md" ;;
esac
if [ -z "${STUB_SILENT:-}" ]; then
  target="$cwd/openspec/changes/$change/$art"
  mkdir -p "$(dirname "$target")"
  printf 'fixture artifact\n' > "$target"
  emit_write "$target"
  if [ -n "${STUB_WRITE_EXTRA:-}" ]; then
    mkdir -p "$(dirname "$STUB_WRITE_EXTRA")"
    printf 'extra\n' > "$STUB_WRITE_EXTRA"
    emit_write "$STUB_WRITE_EXTRA"
  fi
fi
emit_final
EOF
chmod +x "$T/stub"
export AI_DLC_CLIENT="$T/stub"
mkdir -p "$T/skills/openspec-author"
printf -- '---\nname: openspec-author\ndescription: fixture\n---\n' > "$T/skills/openspec-author/SKILL.md"
printf '{"installed_plugins": [{"name": "openspec-author"}]}' > "$T/skills/skills_state.json"
export AI_DLC_SKILLS_DIR="$T/skills"

calls() { cat "$T/calls.log" 2>/dev/null || true; }


# ── red-first harness ───────────────────────────────────────────────
# The same script runs from two trees: the pre-change snapshot (ROOT is
# /tmp/ad-base) and this change. In the base tree every case must go
# RED — the old code does not refuse; in the changed tree every case
# must hold. A case that cannot go red pins nothing.
BASE=0; [ "$ROOT" = "/tmp/ad-base" ] && BASE=1
R=$(mkproj readable-proj)
export AI_DLC_PROBE_READONLY="$R"      # a read-only mount, faked for the probe
I=$(mkproj invisible-proj); rm "$PROBE$T/projroot/invisible-proj" || true
red=0; held=0
rr() { out=$1; shift; set +e; "$@" > "$out" 2>&1; RC=$?; set -e; return 0; }
verdict() { if [ "$2" -eq 1 ]; then held=$((held+1)); else red=$((red+1)); echo "  wrongly held: $3"; fi; return 0; }

# R1 (2.4/2.6) a split dispatch granting only the scratch
before=$(calls | wc -l)
rr "$T/red1.json" env AI_DLC_FAULT=omit-project-trust "$PY" "$PLAN" dispatch --change ch-readable-proj --role design \
  --package-file "$T/pkg-readable-proj.json" --timeout 60
after=$(calls | wc -l)
echo "R1 unguarded split dispatch: exit $RC, client calls $before->$after, wrote into the project: $([ -f "$R/openspec/changes/ch-readable-proj/design.md" ] && echo yes || echo no)"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -ne 20 ]; then verdict R1 1 "old exits $RC"; else verdict R1 0 ""; fi
else
  if [ "$RC" -eq 20 ] && [ "$after" -eq "$before" ] && grep -q 'client was never invoked' "$T/red1.json"; then verdict R1 1 ""; else verdict R1 0 "exit $RC"; fi
fi

# R2 (1.6) staging a readable target
rr "$T/red2.json" "$PY" "$PLAN" stage --change ch-readable-proj --repo "$R"
echo "R2 copy of a readable target: exit $RC — $(head -c 110 "$T/red2.json" | tr '\n' ' ')"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -ne 20 ]; then verdict R2 1 "old exits $RC"; else verdict R2 0 ""; fi
else
  if [ "$RC" -eq 20 ] && grep -q 'split workspace' "$T/red2.json" && grep -q 'copy_would_have_cost_bytes' "$T/red2.json"; then verdict R2 1 ""; else verdict R2 0 "exit $RC"; fi
fi

# R3 (3.3/3.4) frames show a write inside the project
cat > "$T/red3.jsonl" <<EOF
{"type":"event","event":"chat.tool_call","payload":{"tool_name":"write_file","arguments":"{\"path\": \"$R/src/inside-project.md\"}"}}
{"type":"event","event":"chat.final","payload":{"event_type":"chat.final","content":"wrote"}}
EOF
rr "$T/red3.json" "$PY" "$PLAN" dispatch --change ch-readable-proj --role design --package-file "$T/pkg-readable-proj.json" \
  --frames-file "$T/red3.jsonl" --split-project "$R"; RC_SPLIT=$RC
rr "$T/red3b.json" "$PY" "$PLAN" dispatch --change ch-readable-proj --role design --package-file "$T/pkg-readable-proj.json" \
  --frames-file "$T/red3.jsonl"; RC_NOSPLIT=$RC
echo "R3 write inside the project: split-judged exit $RC_SPLIT; the same frames with no split declared exit $RC_NOSPLIT"
RC=$RC_SPLIT
if [ "$BASE" -eq 1 ]; then
  # the old code cannot declare a split at all; the red fact is that the
  # same frames — a write inside the project — are judged clean
  if [ "$RC_NOSPLIT" -eq 0 ]; then verdict R3 1 ""; else verdict R3 0 "old exits $RC_NOSPLIT"; fi
else
  if [ "$RC" -eq 8 ] && grep -q 'inside-project.md' "$T/red3.json"; then verdict R3 1 ""; else verdict R3 0 "exit $RC"; fi
fi

# R4 (4.2/4.6) the write-back surface is never guessed: with the plane
#    already holding a tree, a repo that has grown its own openspec/
#    back stops the one-time move — both named, a person decides which
#    is real. The old return's rule (only the change dir travels) lives
#    in the archive dispatch now, so this is the same never-guess pin
mkdir -p "$R/openspec/changes/ch-readable-proj"
printf '# Handwritten\n' > "$R/openspec/changes/ch-readable-proj/proposal.md"
rr "$T/red4.json" "$PY" "$PLAN" migrate --repo "$R"
echo "R4 both trees standing: exit $RC — $(head -c 110 "$T/red4.json" | tr '\n' ' ')"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -ne 20 ]; then verdict R4 1 "old exits $RC"; else verdict R4 0 ""; fi
else
  if grep -q 'both trees exist' "$T/red4.json" && grep -q '"plane_tree"' "$T/red4.json" && grep -q '"repo_tree"' "$T/red4.json"; then verdict R4 1 ""; else verdict R4 0 "exit $RC"; fi
fi

# R5 (5.2/5.5) a copy that is not self-contained
MAIN="$T/red-main"; mkdir -p "$MAIN"; git -C "$MAIN" init -q
git -C "$MAIN" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
git -C "$MAIN" worktree add -q "$T/red-wt" -b red-branch
(cd "$T/red-wt" && openspec init --tools none --language en) >/dev/null 2>&1
plane_migrate "$T/red-wt"
printf '{"requirement": "The wt SHALL behave.", "change_id": "ch-redwt", "capability": "cap", "repo": "%s"}\n' "$T/red-wt" > "$T/pkg-redwt.json"
mkrecords ch-redwt
before=$(calls | wc -l)
rr "$T/red5.json" "$PY" "$PLAN" dispatch --change ch-redwt --role specs --package-file "$T/pkg-redwt.json" --timeout 60
after=$(calls | wc -l)
echo "R5 non-self-contained copy: exit $RC, client calls $before->$after"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -ne 20 ]; then verdict R5 1 "old exits $RC"; else verdict R5 0 ""; fi
else
  if [ "$RC" -eq 20 ] && grep -q 'self-contained' "$T/red5.json" && [ "$after" -eq "$before" ]; then verdict R5 1 ""; else verdict R5 0 "exit $RC"; fi
fi

# R6 (6.1/6.3) a draft widening the unit
cat > "$T/red-wide.service" <<EOF
[Service]
Environment=JIUWENSWARM_DATA_DIR=$DATA
PrivateTmp=true
ReadWritePaths=$DATA
ReadWritePaths=$PLANE
ReadWritePaths=$T/someones-tree
EOF
rr "$T/red6.json" "$PY" "$PLAN" sandbox --unit "$T/gw.service" --audit-unit "$T/red-wide.service"
echo "R6 widening draft: exit $RC — $(head -c 110 "$T/red6.json" | tr '\n' ' ')"
if [ "$BASE" -eq 1 ]; then
  if [ "$RC" -ne 21 ]; then verdict R6 1 "old exits $RC"; else verdict R6 0 ""; fi
else
  if [ "$RC" -eq 21 ] && grep -q 'split workspace' "$T/red6.json" && grep -q 'not applied' "$T/red6.json"; then verdict R6 1 ""; else verdict R6 0 "exit $RC"; fi
fi

# in the base tree "held" counts the cases that went red (the old code
# failed to refuse); in the changed tree it counts the cases that hold
if [ "$BASE" -eq 1 ]; then
  echo "RED-FIRST (pre-change tree): $held of $((red+held)) cases went red"
  if [ "$red" -eq 0 ] && [ "$held" -gt 0 ]; then echo "RED-FIRST base: pass"; else echo "FAIL: $red case(s) wrongly held against the old code"; exit 1; fi
else
  echo "RED-FIRST (this change): $held of $((red+held)) cases hold"
  if [ "$red" -eq 0 ] && [ "$held" -eq 6 ]; then echo "RED-FIRST change: pass"; else exit 1; fi
fi
