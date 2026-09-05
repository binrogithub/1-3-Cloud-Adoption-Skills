#!/usr/bin/env bash
# G2 — doctor workspace coverage. --doctor's workspace section must verify
# every shipped skill under supervisor/skills/workspace/*/ (not a hard-coded
# subset): each one's installed SKILL.md must exist and its registration
# count in skills_state.json must be exactly 1. A missing SKILL.md, a count
# other than 1, or a duplicate registration fails and names the skill. A
# missing skills_state.json entirely stays a warn (INV-28/29/30).
#
# The shipped source dir (supervisor/skills/workspace/) is not env-overridable,
# so the doctor always verifies the three real shipped skills (codegraph,
# ui-designer, openspec-author) against AI_DLC_SKILLS_DIR, which we point at
# a fixture we build per case.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# The shipped workspace skills the doctor must verify — taken from the repo
# source so the test tracks whatever ships.
mapfile -t SHIPPED < <(ls "${ROOT}/supervisor/skills/workspace/")
[[ "${#SHIPPED[@]}" -ge 1 ]] || { echo "FAIL: no shipped workspace skills found"; exit 1; }

# Build a fixture workspace dir with the given skills' SKILL.md present and a
# skills_state.json registering the named skills (with possible duplicates).
# Args: <fixture_dir> <state_json|none> <skill1[:count]> <skill2[:count]> ...
# A skill listed in SHIPPED but not in the args gets a SKILL.md only if it
# appears in the extra "allmd" pseudo-arg. To keep this simple, every shipped
# skill gets a SKILL.md by default; pass a skill name prefixed with "nomd:"
# to omit its SKILL.md.
build_fixture() {
  local fx="$1" has_state="$2"; shift 2
  mkdir -p "$fx"
  local nomd=()
  local entries=()
  local regspecs=()
  for tok in "$@"; do
    case "$tok" in
      nomd:*) nomd+=("${tok#nomd:}") ;;
      reg:*)  regspecs+=("${tok#reg:}") ;;
    esac
  done
  # SKILL.md for every shipped skill unless nomd:<skill>
  for s in "${SHIPPED[@]}"; do
    local skip=0
    for n in "${nomd[@]:-}"; do [[ "$n" == "$s" ]] && skip=1; done
    if [[ "$skip" == "0" ]]; then
      mkdir -p "$fx/$s"
      printf -- '---\nname: %s\ndescription: fixture\n---\n# %s fixture\n' "$s" "$s" > "$fx/$s/SKILL.md"
    fi
  done
  # skills_state.json
  if [[ "$has_state" == "yes" ]]; then
    python3.12 - "$fx" "${regspecs[@]:-}" <<'PYEOF'
import datetime, json, os, sys
fx = sys.argv[1]
regspecs = sys.argv[2:]
plug = []
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
for spec in regspecs:
    if ":" in spec:
        name, count = spec.rsplit(":", 1)
    else:
        name, count = spec, "1"
    for _ in range(int(count)):
        plug.append({"name": name, "marketplace": "builtin", "version": "",
                     "commit": "", "source": f"ai-dlc supervisor/skills/workspace/{name}",
                     "installed_at": now})
with open(os.path.join(fx, "skills_state.json"), "w", encoding="utf-8") as f:
    json.dump({"installed_plugins": plug}, f, indent=2)
    f.write("\n")
PYEOF
  fi
}

run_doctor() { AI_DLC_SKILLS_DIR="$1" "$ROOT/install.sh" --doctor 2>&1 || true; }

# ── Case A: every shipped skill registered exactly once → all ok ──
FXA="$T/a"
reg_args=()
for s in "${SHIPPED[@]}"; do reg_args+=("reg:${s}:1"); done
build_fixture "$FXA" yes "${reg_args[@]}"
outA="$(run_doctor "$FXA")"
for s in "${SHIPPED[@]}"; do
  grep -q "workspace: ${s} registered (1 entry, SKILL.md present)" <<<"$outA" \
    || { echo "FAIL A: ${s} not reported as registered-ok"; echo "$outA"; exit 1; }
done
if grep -qE 'workspace skill .* not installed|registration count is' <<<"$outA"; then
  echo "FAIL A: a workspace fail line appeared on the all-registered case"; echo "$outA"; exit 1
fi

# ── Case B: one skill unregistered (count 0) → fail naming it ──
FXB="$T/b"
# register all but the last shipped skill
regB=()
for i in "${!SHIPPED[@]}"; do
  [[ "$i" == "$(( ${#SHIPPED[@]} - 1 ))" ]] && continue
  regB+=("reg:${SHIPPED[$i]}:1")
done
build_fixture "$FXB" yes "${regB[@]}"
UNREG="${SHIPPED[$(( ${#SHIPPED[@]} - 1 ))]}"
outB="$(run_doctor "$FXB")"
grep -q "workspace skill '${UNREG}' registration count is 0, want 1" <<<"$outB" \
  || { echo "FAIL B: unregistered skill ${UNREG} not named with count 0"; echo "$outB"; exit 1; }

# ── Case C: missing SKILL.md → fail naming the missing file ──
FXC="$T/c"
regC=()
for s in "${SHIPPED[@]}"; do regC+=("reg:${s}:1"); done
build_fixture "$FXC" yes "nomd:${UNREG}" "${regC[@]}"
outC="$(run_doctor "$FXC")"
grep -qE "workspace skill '${UNREG}' not installed: SKILL.md missing at .*${UNREG}/SKILL\.md \(expected present, found absent\)" <<<"$outC" \
  || { echo "FAIL C: missing SKILL.md for ${UNREG} not named"; echo "$outC"; exit 1; }

# ── Case D: duplicate registration (count 2) → fail, not silently deduped ──
FXD="$T/d"
regD=()
for i in "${!SHIPPED[@]}"; do
  if [[ "$i" == "$(( ${#SHIPPED[@]} - 1 ))" ]]; then
    regD+=("reg:${SHIPPED[$i]}:2")
  else
    regD+=("reg:${SHIPPED[$i]}:1")
  fi
done
build_fixture "$FXD" yes "${regD[@]}"
outD="$(run_doctor "$FXD")"
grep -q "workspace skill '${UNREG}' registration count is 2, want 1" <<<"$outD" \
  || { echo "FAIL D: duplicate registration of ${UNREG} not flagged as count 2"; echo "$outD"; exit 1; }

# ── Case E: skills_state.json absent → warn, not fail ──
FXE="$T/e"
build_fixture "$FXE" none
outE="$(run_doctor "$FXE")"
grep -qE 'workspace skills_state\.json not found' <<<"$outE" \
  || { echo "FAIL E: missing skills_state.json did not produce a warn"; echo "$outE"; exit 1; }
# It must be a warn (!), not a fail (✗) about skills_state.json
if grep -q '✗.*workspace skills_state.json not found' <<<"$outE"; then
  echo "FAIL E: missing skills_state.json emitted a fail instead of a warn"; echo "$outE"; exit 1
fi
# And no per-skill fail lines should appear (the loop is skipped entirely)
if grep -qE 'workspace skill .* not installed|workspace skill .* registration count' <<<"$outE"; then
  echo "FAIL E: per-skill fail lines appeared even though skills_state.json is absent"; echo "$outE"; exit 1
fi

echo "DOCTOR WORKSPACE COVERAGE: pass (all-registered → ok per skill; unregistered → fail names skill count 0; missing SKILL.md → fail names file; duplicate → fail count 2 not deduped; missing skills_state.json → warn not fail)"
