#!/usr/bin/env bash
# Anti-drift test: the committed root SKILL.md must stay in sync with the
# canonical source (supervisor/skills/claude/*/SKILL.md bodies). If someone
# edits a SKILL.md but forgets to re-run ./install.sh --gen-root-skill, this
# test fails. Mirrors the glue_surface.sh philosophy of catching missed
# synchronisations.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# Source install.sh without the final main "$@" call so we can call
# gen_root_skill directly. Fix SCRIPT_DIR to the real repo root.
grep -vxF 'main "$@"' "$ROOT/install.sh" > "$T/install_funcs.sh"
sed -i 's|^SCRIPT_DIR=.*|SCRIPT_DIR="'"$ROOT"'"|' "$T/install_funcs.sh"

# ── 1. Assert the committed root SKILL.md exists with valid frontmatter ──
ROOT_SKILL="$ROOT/SKILL.md"
[[ -f "${ROOT_SKILL}" ]] \
  || { echo "FAIL: repo root SKILL.md does not exist — run ./install.sh --gen-root-skill"; exit 1; }

# Must have a YAML frontmatter block with name: ai-dlc and a non-empty description
head -1 "${ROOT_SKILL}" | grep -qx -- '---' \
  || { echo "FAIL: root SKILL.md missing opening --- frontmatter delimiter"; exit 1; }
grep -q '^name: ai-dlc$' "${ROOT_SKILL}" \
  || { echo "FAIL: root SKILL.md missing 'name: ai-dlc' in frontmatter"; exit 1; }
# description: line must exist and have non-empty content on the same line
grep -q '^description: .\+' "${ROOT_SKILL}" \
  || { echo "FAIL: root SKILL.md missing non-empty 'description:' field"; exit 1; }

# ── 2. Generate into a temp file (do NOT touch the real repo file) ──
(
  # shellcheck disable=SC1090
  source "$T/install_funcs.sh"
  MANIFEST_FILE="$T/test-manifest.json"
  gen_root_skill "$T/generated-SKILL.md"
) > "$T/gen.out" 2>&1 || { echo "FAIL: gen_root_skill errored"; cat "$T/gen.out"; exit 1; }

[[ -f "$T/generated-SKILL.md" ]] \
  || { echo "FAIL: gen_root_skill did not write output file"; cat "$T/gen.out"; exit 1; }

# ── 3. diff generated vs committed — must be identical ──
if ! diff -q "$T/generated-SKILL.md" "${ROOT_SKILL}" >/dev/null 2>&1; then
  echo "FAIL: root SKILL.md is out of sync with the canonical skill sources."
  echo "       Re-run: ./install.sh --gen-root-skill"
  echo "       diff (generated vs committed):"
  diff "$T/generated-SKILL.md" "${ROOT_SKILL}" || true
  exit 1
fi

echo "ROOT SKILL SYNC: pass (committed SKILL.md matches generated output, frontmatter valid)"
