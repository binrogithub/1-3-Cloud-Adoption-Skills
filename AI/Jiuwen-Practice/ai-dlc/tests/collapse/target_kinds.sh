#!/usr/bin/env bash
# Test target kind dispatch: agents-md, cursor-rules, copilot-instructions.
# Verifies that install_skills_to_target with kind=agents-md produces an
# AGENTS.md with BEGIN/END markers and SKILL.md body, and that re-running
# is idempotent (content does not duplicate).  Also checks cursor-rules
# and copilot-instructions kinds.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# Source install.sh without the final main "$@" call so we can call
# individual functions directly.  Fix SCRIPT_DIR to point at the real
# install.sh location (sourcing from a temp copy would otherwise set it
# to the temp dir).
grep -vxF 'main "$@"' "$ROOT/install.sh" > "$T/install_funcs.sh"
sed -i 's|^SCRIPT_DIR=.*|SCRIPT_DIR="'"$ROOT"'"|' "$T/install_funcs.sh"

# Helper: source install funcs and override MANIFEST_FILE to a temp path
# so the test never pollutes the real install manifest.
source_funcs() {
  # shellcheck disable=SC1090
  source "$T/install_funcs.sh"
  MANIFEST_FILE="$T/test-manifest.json"
}

# ── 1. kind=agents-md ─────────────────────────────────────────
mkdir -p "$T/project"
(
  source_funcs
  install_skills_to_target "test-agents-md" "$T/project" "agents-md"
) > "$T/agents.out" 2>&1 || true

AGENTS_MD="$T/project/AGENTS.md"
[[ -f "${AGENTS_MD}" ]] || { echo "FAIL: AGENTS.md not created"; cat "$T/agents.out"; exit 1; }
grep -q '<!-- BEGIN ai-dlc -->' "${AGENTS_MD}" \
  || { echo "FAIL: BEGIN marker missing from AGENTS.md"; exit 1; }
grep -q '<!-- END ai-dlc -->' "${AGENTS_MD}" \
  || { echo "FAIL: END marker missing from AGENTS.md"; exit 1; }
# The body should contain content from SKILL.md (not just markers)
line_count=$(wc -l < "${AGENTS_MD}")
[[ "${line_count}" -gt 5 ]] \
  || { echo "FAIL: AGENTS.md too short (${line_count} lines) — body not written"; exit 1; }

# Idempotency: re-run and content must be identical
sha1=$("python3.12" -c "import hashlib; print(hashlib.sha256(open('${AGENTS_MD}','rb').read()).hexdigest())")
(
  source_funcs
  install_skills_to_target "test-agents-md" "$T/project" "agents-md"
) > "$T/agents2.out" 2>&1 || true
sha2=$("python3.12" -c "import hashlib; print(hashlib.sha256(open('${AGENTS_MD}','rb').read()).hexdigest())")
[[ "${sha1}" == "${sha2}" ]] \
  || { echo "FAIL: AGENTS.md not idempotent — sha changed on re-run"; exit 1; }

# Append-prevention: if a user has pre-existing content, it is preserved
mkdir -p "$T/project2"
printf '# My Project\n\nSome existing docs.\n' > "$T/project2/AGENTS.md"
(
  source_funcs
  install_skills_to_target "test-agents-md2" "$T/project2" "agents-md"
) > "$T/agents3.out" 2>&1 || true
grep -q '# My Project' "$T/project2/AGENTS.md" \
  || { echo "FAIL: pre-existing AGENTS.md content was overwritten"; exit 1; }
grep -q '<!-- BEGIN ai-dlc -->' "$T/project2/AGENTS.md" \
  || { echo "FAIL: BEGIN marker not appended to existing AGENTS.md"; exit 1; }

# ── 2. kind=cursor-rules ──────────────────────────────────────
mkdir -p "$T/cursorproj/.cursor/rules"
(
  source_funcs
  install_skills_to_target "test-cursor" "$T/cursorproj/.cursor/rules" "cursor-rules"
) > "$T/cursor.out" 2>&1 || true

MDC="$T/cursorproj/.cursor/rules/ai-dlc.mdc"
[[ -f "${MDC}" ]] || { echo "FAIL: ai-dlc.mdc not created"; cat "$T/cursor.out"; exit 1; }
grep -q '^description: AI-DLC spec-driven coding flow' "${MDC}" \
  || { echo "FAIL: Cursor frontmatter description missing"; exit 1; }
grep -q '^alwaysApply: false' "${MDC}" \
  || { echo "FAIL: Cursor frontmatter alwaysApply missing"; exit 1; }

# ── 3. kind=copilot-instructions ──────────────────────────────
mkdir -p "$T/copilotproj/.github"
(
  source_funcs
  install_skills_to_target "test-copilot" "$T/copilotproj/.github" "copilot-instructions"
) > "$T/copilot.out" 2>&1 || true

COPILOT="$T/copilotproj/.github/copilot-instructions.md"
[[ -f "${COPILOT}" ]] || { echo "FAIL: copilot-instructions.md not created"; cat "$T/copilot.out"; exit 1; }
grep -q '<!-- BEGIN ai-dlc -->' "${COPILOT}" \
  || { echo "FAIL: BEGIN marker missing from copilot-instructions.md"; exit 1; }
grep -q '<!-- END ai-dlc -->' "${COPILOT}" \
  || { echo "FAIL: END marker missing from copilot-instructions.md"; exit 1; }

# Idempotency for copilot
sha1c=$("python3.12" -c "import hashlib; print(hashlib.sha256(open('${COPILOT}','rb').read()).hexdigest())")
(
  source_funcs
  install_skills_to_target "test-copilot" "$T/copilotproj/.github" "copilot-instructions"
) > "$T/copilot2.out" 2>&1 || true
sha2c=$("python3.12" -c "import hashlib; print(hashlib.sha256(open('${COPILOT}','rb').read()).hexdigest())")
[[ "${sha1c}" == "${sha2c}" ]] \
  || { echo "FAIL: copilot-instructions.md not idempotent"; exit 1; }

echo "TARGET KINDS: pass (agents-md creates AGENTS.md with markers + body, idempotent, preserves existing content; cursor-rules creates .mdc with frontmatter; copilot-instructions creates .md with markers, idempotent)"
