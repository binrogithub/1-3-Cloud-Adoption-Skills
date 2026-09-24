#!/usr/bin/env bash
# any-directory: a project in any directory is read in place, without
# being copied.
#
# The target's class is probed — read and write separately, through the
# gateway's own view of the path — never guessed from a prefix, and the
# probe creates nothing. Since the open-sandbox decision the mounts
# decide first: a mount only the gateway's namespace sees vetoes the
# probe behind it (invisible, whatever the probe reports), and any
# remaining disagreement between the probe and a DECLARED allowlist
# resolves to the most conservative answer, with decision_basis naming
# what decided. A
# writable target dispatches against itself; a readable target is read
# in place through a split workspace (a scratch the round writes to, the
# project granted for reading, guarded before the client exists); only
# an invisible target is copied, and the copy must be self-contained.
# A read-in-place round proves the project byte-for-byte untouched, and
# the return carries the change directory and nothing else. A draft that
# would widen the service unit's writable paths is refused with the
# split workspace named as the remedy.
#
# Under containment N6 the WRITE side is the plane's own tree for every
# class; the class decides the READ side alone (the project in place, or
# a staged copy for a target the plane cannot see at all).
#
# The probe and the plane run on fixtures: AI_DLC_GATEWAY_ROOT stands in
# for /proc/<MainPID>/root (a repo's view is a symlink to the real tree),
# AI_DLC_PROBE_READONLY for the read-only mount a test cannot reproduce
# as root, AI_DLC_GW_MOUNTINFO for the service's own mountinfo (a
# namespace-only mount a test cannot otherwise mount), and
# AI_DLC_PLANE_ROOT for the plane's writable root, so
# nothing here touches the live service unit.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLAN="$ROOT/bin/plan.py"
RT="$ROOT/tests/collapse/records_tool.py"
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
# N6: every round writes the plane's own tree — minted per repo below
export AI_DLC_SPECS="$T/specs"
. "$ROOT/tests/collapse/lib_plane.sh"
# the plane's records and key live in the test's own world: preflight
# admits a role only against the recorded graph, and the statuses a
# validate verdict carries decide what is dispatchable
export AI_DLC_RECORDS="$T/records" AI_DLC_VERDICT_KEY="$T/verdict.key"
$PY "$RT" key

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
# the policy matrix needs two more regimes beside the hardened one:
# grants that AGREE with the probe (the allowlist covers the fixture
# repos), and the OPEN regime (no allowlist declared at all — the
# 2026-09-01 unit form, docs/prd-gateway-open-sandbox.md)
PROJROOT="$T/projroot"
cat > "$T/gw-grants.service" <<EOF
[Service]
Environment=JIUWENSWARM_DATA_DIR=$DATA
PrivateTmp=true
ReadWritePaths=$DATA
ReadWritePaths=$PLANE
ReadWritePaths=$PROJROOT
EOF
cat > "$T/gw-open.service" <<EOF
[Service]
Environment=JIUWENSWARM_DATA_DIR=$DATA
PrivateTmp=false
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
  # the plane's graph for this change, and the verdict reporting the
  # seeded proposal done — the specs and design roles' dependency
  $PY "$RT" graph "ch-$1" --schema spec-driven --artifacts-json \
    '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
  $PY "$RT" verdict "ch-$1" --rc 0 --artifacts proposal=done --complete false >/dev/null
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

# ── Z1: the class is probed, never guessed ──────────────────────────

# 1. the policy matrix, one probe per row: grants that agree with the
#    probe say writable; a mount the unit calls writable but the probe
#    cannot write says readable (the disagreement is a finding, the
#    probe's answer stands); the OPEN regime — no allowlist declared —
#    claims nothing, so a probe-writable path classifies writable with
#    no disagreement; a view that lacks the path says invisible. Each
#    row also pins decision_basis, the evidence that decided.
W=$(mkproj writable-proj)
R=$(mkproj readable-proj)
VIS="$T/projroot/visible-tmp-proj"
mkdir -p "$VIS" && git -C "$VIS" init -q && (cd "$VIS" && openspec init --tools none --language en) >/dev/null 2>&1
printf '{"requirement": "The vis SHALL behave.", "change_id": "ch-visible-tmp-proj", "capability": "cap", "repo": "%s"}\n' "$VIS" > "$T/pkg-vis.json"
mkdir -p "$PROBE$T/projroot" && ln -s "$VIS" "$PROBE$T/projroot/visible-tmp-proj"
I=$(mkproj invisible-proj)
rm "$PROBE$T/projroot/invisible-proj"      # the gateway's view lacks it
export AI_DLC_PROBE_READONLY="$R"
# row: name:repo:unit:class:basis
for spec in "writable-proj:$W:grants:writable:probe" \
            "readable-proj:$R:grants:readable:probe" \
            "visible-tmp-proj:$VIS:open:writable:probe" \
            "invisible-proj:$I:grants:invisible:probe"; do
  name="$(echo "$spec" | cut -d: -f1)"; target="$(echo "$spec" | cut -d: -f2)"
  unit="$(echo "$spec" | cut -d: -f3)"; want="$(echo "$spec" | cut -d: -f4)"; basis="$(echo "$spec" | cut -d: -f5)"
  got=$(AI_DLC_GW_UNIT="$T/gw-$unit.service" "$PY" "$PLAN" classify --repo "$target" 2>/dev/null \
        | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d["class"], d["decision_basis"])')
  [ "$got" = "$want $basis" ] || { echo "FAIL: $name classified '$got', want '$want $basis'"; exit 1; }
done
echo "classify: the policy matrix — grants agreeing, a mount refusing, the open regime, a missing view — OK"

# 1b. the conservative drop: an allowlist that does NOT cover a
#     probe-writable path is a disagreement, and the answer drops to
#     readable until the unit and the filesystem agree (basis grants).
#     Under the hardened fixture unit the fixture repos are beyond the
#     allowlist — exactly this case
got=$(AI_DLC_GW_UNIT="$T/gw.service" "$PY" "$PLAN" classify --repo "$W" 2>/dev/null \
      | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d["class"], d["decision_basis"])')
[ "$got" = "readable grants" ] || { echo "FAIL: beyond-allowlist writable classified '$got', want 'readable grants'"; exit 1; }
echo "classify: a path writable beyond a declared allowlist drops to readable — OK"

# 1c. the mount veto (I2): a mount only the gateway's namespace sees
#     decides invisible WHATEVER the probe reports behind it — the
#     probe's writable is the mount's own residue. The fixture
#     mountinfo carries a /tmp mount with a device the caller's own
#     mountinfo does not have
ROOTDEV=$(awk '$5=="/" {print $3; exit}' /proc/self/mountinfo)
printf '1 0 %s / / rw - rootfs rootfs rw\n2 0 0:999 / /tmp rw - tmpfs private rw\n' "$ROOTDEV" > "$T/gw.mountinfo"
got=$(AI_DLC_GW_UNIT="$T/gw-open.service" AI_DLC_GW_MOUNTINFO="$T/gw.mountinfo" \
      "$PY" "$PLAN" classify --repo "$VIS" 2>/dev/null \
      | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d["class"], d["decision_basis"], bool(d["masked_by"]))')
[ "$got" = "invisible mountinfo True" ] || { echo "FAIL: ns-only /tmp mount classified '$got', want 'invisible mountinfo True'"; exit 1; }
# the same fixture against a repo OUTSIDE the masked point: no veto,
# the probe decides — the mask is a mount comparison, not a prefix
# rule. (The repo sits under /root, which this fixture's "/" mount
# covers exactly as the caller's own does; the test's own $T lives
# under /tmp and would be inside the mask)
OUTSIDE="<tmp>/ad-unmask-check"
rm -rf "$OUTSIDE"; mkdir -p "$OUTSIDE" "$PROBE<tmp>/ad-unmask-check"
got=$(AI_DLC_GW_UNIT="$T/gw-open.service" AI_DLC_GW_MOUNTINFO="$T/gw.mountinfo" \
      "$PY" "$PLAN" classify --repo "$OUTSIDE" 2>/dev/null \
      | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d["class"], d["decision_basis"], bool(d["masked_by"]))')
rm -rf "$OUTSIDE"
[ "$got" = "writable probe False" ] || { echo "FAIL: unmasked path classified '$got', want 'writable probe False'"; exit 1; }
echo "classify: a namespace-only mount vetoes the probe behind it, and only there — OK"

# 1d. the probe creates nothing (I1): a path that never stood classifies
#     invisible with probe_created_paths empty, and still does not
#     stand afterwards — on the caller's side and in the probe view
ABS="$PROJROOT/never-created-proj"
got=$(AI_DLC_GW_UNIT="$T/gw-open.service" "$PY" "$PLAN" classify --repo "$ABS" 2>/dev/null \
      | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d["class"], d["probe_created_paths"])')
[ "$got" = "invisible []" ] || { echo "FAIL: absent path classified '$got', want 'invisible []'"; exit 1; }
[ ! -e "$ABS" ] || { echo "FAIL: the probe left $ABS standing on the caller's side"; exit 1; }
[ ! -e "$PROBE$ABS" ] || { echo "FAIL: the probe left $ABS standing in its own view"; exit 1; }
echo "classify: the probe observes, it never creates — OK"

# 2. (1.4) a writable target still writes the plane's own tree — no
#    scratch, no copy; the project is granted for READING and the
#    client's cwd is the plane root. (The grants-agreeing unit from the
#    matrix stays exported: a genuine writable CLASS is what this case
#    exercises — under the hardened fixture the same repo would be the
#    conservative readable of 1b.)
export AI_DLC_GW_UNIT="$T/gw-grants.service"
"$PY" "$PLAN" dispatch --change ch-writable-proj --role specs \
  --package-file "$T/pkg-writable-proj.json" --timeout 60 > "$T/w.json" 2>&1
grep -q '"kind": "plane"' "$T/w.json"
grep -q '"scratch": null' "$T/w.json"
[ ! -e "$PLANE/.ai-dlc/scratch" ] || { echo "FAIL: a writable target made a scratch"; exit 1; }
calls | grep -q -- "--cwd $(plane_of "$W")" || { echo "FAIL: the client cwd was not the plane root"; calls; exit 1; }
calls | grep -q -- "--trusted-dir $W" || { echo "FAIL: the project was not granted for reading"; calls; exit 1; }
echo "writable target: the round writes the plane tree, project granted for reading — OK"

# ── Z2: the split workspace ─────────────────────────────────────────

# 3. (2.1-2.3, 2.5) a readable target is read IN PLACE: the working
#    directory is the plane root, the project is granted as a trusted
#    location, the prompt names the project as the place to read, and
#    the record states the project was read live
PROOT_R="$(plane_of "$R")"
"$PY" "$PLAN" dispatch --change ch-readable-proj --role specs \
  --package-file "$T/pkg-readable-proj.json" --timeout 60 > "$T/r.json" 2>&1
grep -q '"kind": "plane"' "$T/r.json"
calls | grep -q -- "--cwd $PROOT_R" || { echo "FAIL: the client cwd was not the plane root"; calls; exit 1; }
calls | grep -q -- "--trusted-dir $PROOT_R" || { echo "FAIL: the plane tree was not granted"; calls; exit 1; }
calls | grep -q -- "--trusted-dir $R" || { echo "FAIL: the project was not granted"; calls; exit 1; }
calls | grep -q -- "--project-dir $PROOT_R" || { echo "FAIL: the project identity was not the plane tree"; calls; exit 1; }
calls | grep -q "project you are planning against lives at $R" \
  || { echo "FAIL: the prompt did not name the project"; exit 1; }
grep -q '"read": "live"' "$T/r.json"
grep -q 'read live, not snapshotted' "$R/.ai-dlc/tasks/ch-readable-proj-planning/planning.json"
grep -q '"starting_revision"' "$R/.ai-dlc/tasks/ch-readable-proj-planning/planning.json"
echo "readable target: split round in the plane tree, project granted, read live — OK"

# 4. (2.4/2.6) reverse: only the plane tree granted, the project not —
#    the dispatch fails BEFORE the client is invoked, naming the grant
before=$(calls | wc -l)
set +e
AI_DLC_FAULT=omit-project-trust "$PY" "$PLAN" dispatch --change ch-readable-proj --role design \
  --package-file "$T/pkg-readable-proj.json" --timeout 60 > "$T/fault.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 20 ] || { echo "FAIL: unguarded split dispatch exited $RC, want 20"; cat "$T/fault.json"; exit 1; }
grep -q 'client was never invoked' "$T/fault.json"
grep -q 'project' "$T/fault.json"
after=$(calls | wc -l)
[ "$after" -eq "$before" ] || { echo "FAIL: the client was invoked on a refused dispatch"; exit 1; }
echo "reverse: a round granted no read of the project refused exit 20 before the client — OK"

# ── Z3: the project stays untouched ─────────────────────────────────

# 5. (3.1/3.2) a clean split round leaves the project byte-for-byte as
#    it was found, bookkeeping included
"$PY" "$PLAN" snapshot --tree "$R" --out "$T/r.manifest.json" >/dev/null
"$PY" "$PLAN" dispatch --change ch-readable-proj --role design \
  --package-file "$T/pkg-readable-proj.json" --timeout 60 > "$T/r2.json" 2>&1
set +e
"$PY" "$PLAN" untouched --manifest "$T/r.manifest.json" --tree "$R" > "$T/r.untouched.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 0 ] || { echo "FAIL: a clean round changed the project"; cat "$T/r.untouched.json"; exit 1; }
grep -q '"untouched": true' "$T/r.untouched.json"
for d in .agent_history coding_memory prompt_attachment; do
  [ ! -e "$R/$d" ] || { echo "FAIL: bookkeeping $d left in the project"; exit 1; }
done
echo "project untouched after a clean round — OK"

# 6. (3.3/3.4) reverse: a role whose frames show a write inside the
#    project fails the dispatch naming the path — judged from frames
#    alone, with and without the byte-for-byte manifest
cat > "$T/proj-write.jsonl" <<EOF
{"type":"event","event":"chat.tool_call","payload":{"tool_name":"write_file","arguments":"{\"path\": \"$R/src/inside-project.md\"}"}}
{"type":"event","event":"chat.final","payload":{"event_type":"chat.final","content":"wrote into the project"}}
EOF
set +e
"$PY" "$PLAN" dispatch --change ch-readable-proj --role design --package-file "$T/pkg-readable-proj.json" \
  --frames-file "$T/proj-write.jsonl" --split-project "$R" > "$T/pw.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 8 ] || { echo "FAIL: a write inside the project exited $RC, want 8"; cat "$T/pw.json"; exit 1; }
grep -q 'inside-project.md' "$T/pw.json"
grep -q 'may only read' "$T/pw.json"
set +e
"$PY" "$PLAN" dispatch --change ch-readable-proj --role design --package-file "$T/pkg-readable-proj.json" \
  --frames-file "$T/proj-write.jsonl" --split-project "$R" --project-manifest "$T/r.manifest.json" > "$T/pw2.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 8 ] || { echo "FAIL: frames+manifest project write exited $RC, want 8"; cat "$T/pw2.json"; exit 1; }
# and the byte-for-byte check on the ground: a file that appeared
mkdir -p "$R/src"; printf 'smuggled\n' > "$R/src/smuggled.md"
set +e
"$PY" "$PLAN" untouched --manifest "$T/r.manifest.json" --tree "$R" > "$T/sm.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 8 ] || { echo "FAIL: a smuggled file passed untouched, exited $RC"; cat "$T/sm.json"; exit 1; }
grep -q 'smuggled' "$T/sm.json"
rm -rf "$R/src"
echo "reverse: a write inside the project fails exit 8 naming the path — OK"

# ── Z4: the write-back moved into the close tail ─────────────────────

# 7. (4.1-4.6, containment N2) the return subcommand is gone: a round's
#    work never leaves the plane until the archive dispatch writes the
#    specs and the archived change back through one plane session,
#    judged per command — nothing caller-side may carry it. Those
#    reverse cases live in l2_close_tail.sh; here the surface itself is
#    asserted gone
set +e
"$PY" "$PLAN" return --change ch-gone --workspace "$T" --project "$T" > "$T/ret.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 2 ] || { echo "FAIL: the return surface survived, exited $RC"; cat "$T/ret.json"; exit 1; }
grep -q 'invalid choice' "$T/ret.json"
echo "return: gone — the write-back is the archive dispatch's, judged per command — OK"

# ── Z5: copying only for the invisible class ────────────────────────

# 10. (1.6) reverse: staging a READABLE target is refused — the split
#     workspace named as the remedy, the size the copy would have cost
set +e
"$PY" "$PLAN" stage --change ch-readable-proj --repo "$R" > "$T/stageref.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 20 ] || { echo "FAIL: staging a readable target exited $RC, want 20"; cat "$T/stageref.json"; exit 1; }
grep -q 'split workspace' "$T/stageref.json"
grep -q 'copy_would_have_cost_bytes' "$T/stageref.json"
echo "reverse: copying a readable target refused, the cost named — OK"

# 11. (5.1-5.3) an invisible target is READ through a staged copy: the
#     round still writes the plane tree, the copy carries source, path,
#     time, revision, size and duration, and nothing readable at source
STAGE_I="$PLANE/.ai-dlc/stage/$("$PY" - "$I" <<'PYEOF'
import re, sys
print(re.sub(r"[^A-Za-z0-9._-]+", "-", sys.argv[1].strip("/")).strip("-"))
PYEOF
)--ch-invisible-proj"
"$PY" "$PLAN" dispatch --change ch-invisible-proj --role specs \
  --package-file "$T/pkg-invisible-proj.json" --timeout 60 > "$T/inv.json" 2>&1
grep -q '"kind": "plane"' "$T/inv.json"
grep -q '"class": "invisible"' "$T/inv.json"
grep -q '"read": "snapshot"' "$T/inv.json"
for key in '"source"' '"copy"' '"taken_at"' '"duration_seconds"' '"size_bytes"' '"source_revision"'; do
  grep -q "$key" "$T/inv.json" || { echo "FAIL: the staging record lacks $key"; cat "$T/inv.json"; exit 1; }
done
grep -q 'nothing at the source was readable' "$T/inv.json"
[ -d "$STAGE_I" ] || { echo "FAIL: no staged copy at $STAGE_I"; exit 1; }
calls | grep -q -- "--cwd $(plane_of "$I")" || { echo "FAIL: the client cwd was not the plane root"; calls; exit 1; }
calls | grep -q -- "--trusted-dir $STAGE_I" || { echo "FAIL: the copy was not granted for reading"; calls; exit 1; }
[ ! -e "$I/.ai-dlc" ] || { echo "FAIL: the invisible source gained bookkeeping"; exit 1; }
[ -f "$STAGE_I/README.md" ] || { echo "FAIL: the copy lacks the working tree"; exit 1; }
echo "invisible target: read through a staged copy, cost recorded, source untouched — OK"

# 12. (5.2/5.5) reverse: a copy whose history store points outside the
#     reachable area stops the run before dispatch
MAIN="$T/main-repo"; mkdir -p "$MAIN"; git -C "$MAIN" init -q
git -C "$MAIN" -c user.name=t -c user.email=t@t commit -q --allow-empty -m seed
git -C "$MAIN" worktree add -q "$T/wt-linked" -b wt-branch
(cd "$T/wt-linked" && openspec init --tools none --language en) >/dev/null 2>&1
plane_migrate "$T/wt-linked"
printf '{"requirement": "The wt SHALL behave.", "change_id": "ch-wt", "capability": "cap", "repo": "%s"}\n' "$T/wt-linked" > "$T/pkg-wt.json"
$PY "$RT" graph ch-wt --schema spec-driven --artifacts-json \
  '[{"id":"proposal"},{"id":"specs","requires":["proposal"]},{"id":"design","requires":["proposal"]},{"id":"tasks","requires":["specs","design"]}]' >/dev/null
$PY "$RT" verdict ch-wt --rc 0 --artifacts proposal=done --complete false >/dev/null
rm -rf "$PROBE$T"     # the gateway cannot see this tree at all
before=$(calls | wc -l)
set +e
"$PY" "$PLAN" dispatch --change ch-wt --role specs --package-file "$T/pkg-wt.json" --timeout 60 > "$T/wt.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 20 ] || { echo "FAIL: a non-self-contained copy exited $RC, want 20"; cat "$T/wt.json"; exit 1; }
grep -q 'self-contained' "$T/wt.json"
grep -q 'gitdir' "$T/wt.json"
after=$(calls | wc -l)
[ "$after" -eq "$before" ] || { echo "FAIL: the client ran against a broken copy"; exit 1; }
echo "reverse: a copy pointing outside the reachable area stops exit 20 — OK"

# 13. (5.4) a target that became readable is read in place — an earlier
#     copy exists and is recorded as NOT reused
mkdir -p "$PROBE$T/projroot"
BEC=$(mkproj became-proj)
rm "$PROBE$T/projroot/became-proj"
"$PY" "$PLAN" dispatch --change ch-became-proj --role specs \
  --package-file "$T/pkg-became-proj.json" --timeout 60 >/dev/null 2>&1
ln -s "$BEC" "$PROBE$T/projroot/became-proj"   # the view appears: readable now
export AI_DLC_PROBE_READONLY="$R:$BEC"
"$PY" "$PLAN" dispatch --change ch-became-proj --role design \
  --package-file "$T/pkg-became-proj.json" --timeout 60 > "$T/became.json" 2>&1
grep -q '"kind": "plane"' "$T/became.json"
grep -q '"read": "live"' "$T/became.json"
grep -q '"stage": null' "$T/became.json"
calls | grep -q -- "--cwd $(plane_of "$BEC")" || { echo "FAIL: the readable round did not read in place"; calls; exit 1; }
calls | grep -q -- "--trusted-dir $BEC" || { echo "FAIL: the newly readable project was not granted"; calls; exit 1; }
echo "a target that became readable reads in place, the earlier copy left aside — OK"

# ── Z6: the sandbox stays as it is ──────────────────────────────────

# 14. (6.2) the sandbox report names each writable path and flags one
#     that is a project tree rather than the runtime's own area
mkdir -p "$T/someones-project"
cat > "$T/wide.service" <<EOF
[Service]
Environment=JIUWENSWARM_DATA_DIR=$DATA
PrivateTmp=true
ReadWritePaths=$DATA
ReadWritePaths=$PLANE
ReadWritePaths=$T/someones-project
EOF
"$PY" "$PLAN" sandbox --unit "$T/wide.service" > "$T/sbx.json" 2>&1
grep -q 'someones-project' "$T/sbx.json"
grep -q 'NOT the runtime' "$T/sbx.json"
grep -q 'split workspace' "$T/sbx.json"

# 15. (6.1/6.3) reverse: a draft that widens the unit is refused with
#     the remedy named, nothing applied or restarted
set +e
"$PY" "$PLAN" sandbox --unit "$T/gw.service" --audit-unit "$T/wide.service" > "$T/draft.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 21 ] || { echo "FAIL: a widening draft exited $RC, want 21"; cat "$T/draft.json"; exit 1; }
grep -q 'someones-project' "$T/draft.json"
grep -q 'split workspace' "$T/draft.json"
grep -q 'only boundary left' "$T/draft.json"
grep -q 'not applied' "$T/draft.json"
cat > "$T/same.service" <<EOF
[Service]
Environment=JIUWENSWARM_DATA_DIR=$DATA
ReadWritePaths=$DATA
ReadWritePaths=$PLANE
EOF
set +e
"$PY" "$PLAN" sandbox --unit "$T/gw.service" --audit-unit "$T/same.service" > "$T/same.json" 2>&1
RC=$?
set -e
[ "$RC" -eq 0 ] || { echo "FAIL: an unchanged draft exited $RC"; cat "$T/same.json"; exit 1; }
echo "sandbox: project-tree grants reported, widening refused exit 21 — OK"

echo "AD ANY-DIRECTORY: pass (classify probes with a mount veto and a conservative disagreement policy; every round writes the plane's own tree with the project granted for reading, guarded before the client; the project proves byte-for-byte untouched and a write inside it fails naming the path; the caller-side return surface is gone — the write-back is the archive dispatch's; copying is refused for a readable target and stops for a copy that is not self-contained; a target that became readable is not served from the copy; the sandbox report flags project-tree grants and a widening draft is refused with the remedy named)"
