#!/usr/bin/env bash
# setup-review-axes.sh — interactively pick review axes for a target's
# collapsed.config.yaml.
#
# The design-review round (bin/plan.py review_axes()) reads
# review.axis.<name>.{stance,accepts,refuses} from the config file and
# dispatches one independent reviewer per axis. This script prompts the
# user to pick up to max_axes axes from presets (or write custom ones),
# then writes them back atomically — only the review.axis.* lines change,
# every other top-level key is preserved byte-for-byte.
#
# Skips re-prompting when the file's review.axis.* already differs from
# the shipped factory default (security/operability/performance with the
# exact factory text). --force always re-prompts.
#
# Usage:
#   ./scripts/setup-review-axes.sh --config-file <path/to/collapsed.config.yaml> [--force]
set -euo pipefail

PY="$(command -v python3.12 || command -v python3 || echo ${HOME}/.local/bin/python3.12)"

CONFIG_FILE=""
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config-file)    CONFIG_FILE="$2"; shift 2 ;;
    --config-file=*)  CONFIG_FILE="${1#--config-file=}"; shift ;;
    --force)          FORCE=1; shift ;;
    --help|-h)
      cat <<'USAGE'
setup-review-axes.sh — interactively pick review axes for a target's config

Options:
  --config-file <path>  target collapsed.config.yaml (required)
  --force               re-prompt even if axes already differ from factory default
USAGE
      exit 0 ;;
    *) shift ;;
  esac
done

[[ -n "${CONFIG_FILE}" ]] || { echo "setup-review-axes: --config-file <path> is required" >&2; exit 1; }
[[ -f "${CONFIG_FILE}" ]] || { echo "setup-review-axes: config file not found: ${CONFIG_FILE}" >&2; exit 1; }

# ── Presets ────────────────────────────────────────────────────
# The first three (security, operability, performance) are the factory
# defaults shipped in config/collapsed.config.yaml. The next three are
# additional presets offered at install time. Each preset carries a
# stance, what it accepts as a trade, and what it refuses.
PRESET_NAMES=(security operability performance correctness spec-completeness maintainability)

preset_stance() {
  case "$1" in
    security)          printf '%s' "suspicious of anything that widens who can act or what a process can reach without a named owner" ;;
    operability)       printf '%s' "suspicious of anything that holds only while a single process stays alive" ;;
    performance)       printf '%s' "suspicious of any cost that grows without a named ceiling" ;;
    correctness)       printf '%s' "suspicious of anything that reads right but is not" ;;
    spec-completeness) printf '%s' "suspicious of anything that ships without covering a stated requirement" ;;
    maintainability)   printf '%s' "suspicious of anything that makes the next change harder" ;;
    *) return 1 ;;
  esac
}

preset_accepts() {
  case "$1" in
    security)          printf '%s' "paying convenience for containment, a slower path with a narrower blast radius" ;;
    operability)       printf '%s' "a rougher tool whose state survives restarts, concurrent runs and partial failure" ;;
    performance)       printf '%s' "paying memory or duplication to keep the critical path short" ;;
    correctness)       printf '%s' "tests that pin behavior over implementation detail" ;;
    spec-completeness) printf '%s' "gaps named explicitly as out of scope with a reason" ;;
    maintainability)   printf '%s' "a little more structure now for less friction later" ;;
    *) return 1 ;;
  esac
}

preset_refuses() {
  case "$1" in
    security)          printf '%s' "unattended agents holding unrestricted shells side by side in one tree" ;;
    operability)       printf '%s' "shared state two separate invocations can corrupt and no operator can see" ;;
    performance)       printf '%s' "unbounded concurrency and unmeasured claims of speed" ;;
    correctness)       printf '%s' "untested changes and assumptions about behavior not checked" ;;
    spec-completeness) printf '%s' "requirements silently dropped or quietly reinterpreted" ;;
    maintainability)   printf '%s' "special cases that accrete and code only the author can follow" ;;
    *) return 1 ;;
  esac
}

is_preset_name() {
  local n
  for n in "${PRESET_NAMES[@]}"; do
    [[ "$1" == "$n" ]] && return 0
  done
  return 1
}

# ── Factory default check ──────────────────────────────────────
# Returns 0 (true) when the file's review.axis.* exactly matches the
# shipped factory default (security/operability/performance with the
# exact factory text). Returns 1 otherwise.
is_factory_default() {
  "$PY" - "${CONFIG_FILE}" <<'PYEOF'
import re, sys

config_file = sys.argv[1]
lines = open(config_file, encoding="utf-8").read().splitlines()

factory = {
    "security": {
        "stance": "suspicious of anything that widens who can act or what a process can reach without a named owner",
        "accepts": "paying convenience for containment, a slower path with a narrower blast radius",
        "refuses": "unattended agents holding unrestricted shells side by side in one tree",
    },
    "operability": {
        "stance": "suspicious of anything that holds only while a single process stays alive",
        "accepts": "a rougher tool whose state survives restarts, concurrent runs and partial failure",
        "refuses": "shared state two separate invocations can corrupt and no operator can see",
    },
    "performance": {
        "stance": "suspicious of any cost that grows without a named ceiling",
        "accepts": "paying memory or duplication to keep the critical path short",
        "refuses": "unbounded concurrency and unmeasured claims of speed",
    },
}

axes = {}
section = None
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    if not line[0].isspace():
        section = stripped.split(":", 1)[0].strip()
        continue
    if section != "review":
        continue
    m = re.match(r"axis\.([\w-]+)\.(stance|accepts|refuses):\s*(.+)$", stripped)
    if m:
        val = m.group(3).split("#", 1)[0].strip()
        axes.setdefault(m.group(1), {})[m.group(2)] = val

if set(axes.keys()) != set(factory.keys()):
    sys.exit(1)

for name, persona in factory.items():
    for field, expected in persona.items():
        if axes.get(name, {}).get(field, "") != expected:
            sys.exit(1)

sys.exit(0)
PYEOF
}

# ── Read max_axes from the config file ─────────────────────────
read_max_axes() {
  "$PY" - "${CONFIG_FILE}" <<'PYEOF'
import sys
config_file = sys.argv[1]
lines = open(config_file, encoding="utf-8").read().splitlines()
section = None
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    if not line[0].isspace():
        section = stripped.split(":", 1)[0].strip()
        continue
    if section == "review" and stripped.startswith("max_axes:"):
        val = stripped.split(":", 1)[1].split("#", 1)[0].strip()
        print(int(val) if val.isdigit() else 3)
        sys.exit(0)
print(3)
PYEOF
}

# ── Skip if already configured (and not --force) ───────────────
if [[ "${FORCE}" == "0" ]] && ! is_factory_default; then
  echo "setup-review-axes: ${CONFIG_FILE} already has custom review axes — skipping (use --force to re-prompt)"
  exit 0
fi

# ── Interactive prompt ─────────────────────────────────────────
# Works with both a terminal and piped stdin (for testing/CI). The
# caller (install.sh configure_review_axes) decides when to skip.
MAX_AXES="$(read_max_axes)"

echo ""
echo "Review axes configuration"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "The design-review round dispatches up to ${MAX_AXES} independent reviewers."
echo "Each reviewer holds one axis with a stance, what it accepts, and what it refuses."
echo ""
echo "Available presets:"
local_i=1
for preset_name in "${PRESET_NAMES[@]}"; do
  printf '  %d. %-18s — %s\n' "${local_i}" "${preset_name}" "$(preset_stance "${preset_name}")"
  local_i=$((local_i + 1))
done
echo ""
echo "You can pick a preset by number, or type a custom axis name."
echo ""

# Collect axes
AXIS_NAMES=()
AXIS_STANCES=()
AXIS_ACCEPTS=()
AXIS_REFUSES=()

# Ask how many axes
while true; do
  printf 'How many axes do you want (1-%d)? [%s]: ' "${MAX_AXES}" "${MAX_AXES}"
  read -r num_axes
  num_axes="${num_axes:-${MAX_AXES}}"
  if [[ "${num_axes}" =~ ^[0-9]+$ ]] && (( num_axes >= 1 && num_axes <= MAX_AXES )); then
    break
  fi
  echo "  Please enter a number between 1 and ${MAX_AXES}."
done

for (( ax_idx = 1; ax_idx <= num_axes; ax_idx++ )); do
  echo ""
  echo "── Axis ${ax_idx}/${num_axes} ──"

  while true; do
    printf 'Pick a preset (1-%d) or type a custom axis name: ' "${#PRESET_NAMES[@]}"
    read -r choice

    # Check if it's a number (preset selection)
    if [[ "${choice}" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#PRESET_NAMES[@]} )); then
      preset_name="${PRESET_NAMES[$((choice - 1))]}"
      # Check for duplicate axis name
      local_dup=0
      for existing in "${AXIS_NAMES[@]:-}"; do
        [[ "${existing}" == "${preset_name}" ]] && local_dup=1
      done
      if [[ "${local_dup}" == "1" ]]; then
        echo "  Axis '${preset_name}' already selected — pick a different one."
        continue
      fi

      p_stance="$(preset_stance "${preset_name}")"
      p_accepts="$(preset_accepts "${preset_name}")"
      p_refuses="$(preset_refuses "${preset_name}")"

      echo "  Preset: ${preset_name}"
      echo "    stance:  ${p_stance}"
      echo "    accepts: ${p_accepts}"
      echo "    refuses: ${p_refuses}"

      printf '  Use preset text as-is? [Y/n]: '
      read -r use_preset
      if [[ "${use_preset}" != "n" && "${use_preset}" != "N" ]]; then
        AXIS_NAMES+=("${preset_name}")
        AXIS_STANCES+=("${p_stance}")
        AXIS_ACCEPTS+=("${p_accepts}")
        AXIS_REFUSES+=("${p_refuses}")
        break
      fi

      # Customize the three fields
      printf '  Enter stance:  '
      read -r c_stance
      printf '  Enter accepts: '
      read -r c_accepts
      printf '  Enter refuses:  '
      read -r c_refuses

      if [[ -z "${c_stance}" || -z "${c_accepts}" || -z "${c_refuses}" ]]; then
        echo "  All three fields must be non-empty — re-picking this axis."
        continue
      fi

      AXIS_NAMES+=("${preset_name}")
      AXIS_STANCES+=("${c_stance}")
      AXIS_ACCEPTS+=("${c_accepts}")
      AXIS_REFUSES+=("${c_refuses}")
      break

    # Custom axis name
    elif [[ -n "${choice}" ]]; then
      # Check for duplicate
      local_dup=0
      for existing in "${AXIS_NAMES[@]:-}"; do
        [[ "${existing}" == "${choice}" ]] && local_dup=1
      done
      if [[ "${local_dup}" == "1" ]]; then
        echo "  Axis '${choice}' already selected — pick a different name."
        continue
      fi

      echo "  Custom axis: ${choice}"
      printf '  Enter stance:  '
      read -r c_stance
      printf '  Enter accepts: '
      read -r c_accepts
      printf '  Enter refuses:  '
      read -r c_refuses

      if [[ -z "${c_stance}" || -z "${c_accepts}" || -z "${c_refuses}" ]]; then
        echo "  All three fields must be non-empty — re-picking this axis."
        continue
      fi

      AXIS_NAMES+=("${choice}")
      AXIS_STANCES+=("${c_stance}")
      AXIS_ACCEPTS+=("${c_accepts}")
      AXIS_REFUSES+=("${c_refuses}")
      break

    else
      echo "  Please pick a preset number or type a custom axis name."
    fi
  done
done

# ── Validate: no two axes share a stance ───────────────────────
stance_collision=""
for (( i = 0; i < ${#AXIS_STANCES[@]}; i++ )); do
  for (( j = i + 1; j < ${#AXIS_STANCES[@]}; j++ )); do
    if [[ "${AXIS_STANCES[$i]}" == "${AXIS_STANCES[$j]}" ]]; then
      stance_collision="${AXIS_NAMES[$i]} / ${AXIS_NAMES[$j]}"
    fi
  done
done
if [[ -n "${stance_collision}" ]]; then
  echo ""
  echo "setup-review-axes: two axes (${stance_collision}) share the same stance —"
  echo "the review round exists to prevent convergence, so each reviewer must pull"
  echo "a different way. Please re-run with different stances." >&2
  exit 1
fi

echo ""
echo "Validation:"
echo "  ✓ ${#AXIS_NAMES[@]} axes, all with stance/accepts/refuses"
echo "  ✓ all axis names unique"
echo "  ✓ all stances distinct"

# ── Write back atomically ──────────────────────────────────────
# Only the review.axis.* lines change. Every other line — including
# all other top-level keys and the review.max_axes line — is preserved
# byte-for-byte. Atomic write via mktemp same-dir + chmod + mv,
# matching the discipline in setup-maas-key.sh.

AXIS_TMP="$(mktemp)"
chmod 600 "${AXIS_TMP}"
for (( i = 0; i < ${#AXIS_NAMES[@]}; i++ )); do
  printf '%s\tstance\t%s\n'  "${AXIS_NAMES[$i]}" "${AXIS_STANCES[$i]}"  >> "${AXIS_TMP}"
  printf '%s\taccepts\t%s\n' "${AXIS_NAMES[$i]}" "${AXIS_ACCEPTS[$i]}" >> "${AXIS_TMP}"
  printf '%s\trefuses\t%s\n'  "${AXIS_NAMES[$i]}" "${AXIS_REFUSES[$i]}"  >> "${AXIS_TMP}"
done
trap 'rm -f "${AXIS_TMP}"' EXIT

"${PY}" - "${CONFIG_FILE}" "${AXIS_TMP}" <<'PYEOF'
import os, sys, tempfile

config_file = sys.argv[1]
axis_file = sys.argv[2]

# Read axis data (tab-separated: name \t field \t value)
axis_data = []
for line in open(axis_file, encoding="utf-8").read().splitlines():
    parts = line.split("\t", 2)
    if len(parts) == 3:
        axis_data.append(parts)

# Read existing lines
lines = open(config_file, encoding="utf-8").read().splitlines()

# Find the review: section and identify all axis.* lines within it
in_review = False
axis_indices = set()
first_axis_idx = None

for i, ln in enumerate(lines):
    stripped = ln.strip()
    if not stripped or stripped.startswith("#"):
        continue
    if not ln[0].isspace():
        section = stripped.split(":", 1)[0].strip()
        in_review = (section == "review")
        continue
    if in_review and stripped.startswith("axis."):
        axis_indices.add(i)
        if first_axis_idx is None:
            first_axis_idx = i

# Build new lines without the old axis lines
new_lines = [ln for i, ln in enumerate(lines) if i not in axis_indices]

# Determine where to insert the new axis lines:
#  - if there were axis lines before, insert where the first one was
#  - otherwise, insert at the end of the review: section
if first_axis_idx is not None:
    insert_at = first_axis_idx - sum(1 for idx in axis_indices if idx < first_axis_idx)
else:
    insert_at = len(new_lines)
    in_rev = False
    for i, ln in enumerate(new_lines):
        stripped = ln.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not ln[0].isspace():
            section = stripped.split(":", 1)[0].strip()
            if section == "review":
                in_rev = True
            elif in_rev:
                insert_at = i
                break

# Build the new axis lines (2-space indent, matching the file's style)
new_axis_lines = [f"  axis.{name}.{field}: {value}"
                  for name, field, value in axis_data]

# Insert
result = new_lines[:insert_at] + new_axis_lines + new_lines[insert_at:]
result_text = "\n".join(result) + "\n"

# Atomic write: mktemp in same dir, preserve permissions, mv
d = os.path.dirname(config_file) or "."
mode = os.stat(config_file).st_mode & 0o777
fd, tmp = tempfile.mkstemp(dir=d)
os.write(fd, result_text.encode("utf-8"))
os.close(fd)
os.chmod(tmp, mode)
os.rename(tmp, config_file)
PYEOF

rm -f "${AXIS_TMP}"
trap - EXIT

echo ""
echo "setup-review-axes: review axes written to ${CONFIG_FILE}"
for (( i = 0; i < ${#AXIS_NAMES[@]}; i++ )); do
  echo "  ${AXIS_NAMES[$i]}: ${AXIS_STANCES[$i]}"
done
