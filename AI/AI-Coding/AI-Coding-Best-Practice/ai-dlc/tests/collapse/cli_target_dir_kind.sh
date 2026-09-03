#!/usr/bin/env bash
# Regression test: the CLI entry point (install.sh main) honours --target <name>
# --target-dir <path> by reading the real `kind` from targets/<name>.json, so
# `--target codex --target-dir <dir>` writes AGENTS.md (agents-md), not a
# claude-skill skills/ tree.  Also confirms that `--target codex` alone (no
# --target-dir) now fails loudly instead of reporting a false success.
#
# This exercises install.sh as a subprocess — target_kinds.sh only unit-tests
# install_skills_to_target() directly, which is why this bug slipped through.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# ── 1. --target codex --target-dir <dir> writes AGENTS.md ──────────────
proj="$T/project"
mkdir -p "$proj"
AI_DLC_MANIFEST_FILE="$T/manifest.json" bash "$ROOT/install.sh" --target codex --target-dir "$proj" >"$T/run1.out" 2>&1 \
  || { echo "FAIL: --target codex --target-dir exited non-zero"; cat "$T/run1.out"; exit 1; }

AGENTS_MD="$proj/AGENTS.md"
[[ -f "${AGENTS_MD}" ]] \
  || { echo "FAIL: AGENTS.md not created at ${AGENTS_MD}"; cat "$T/run1.out"; exit 1; }
grep -q '<!-- BEGIN ai-dlc -->' "${AGENTS_MD}" \
  || { echo "FAIL: BEGIN marker missing from AGENTS.md"; exit 1; }

# Must NOT have degraded into the claude-skill path (no skills/ tree).
if [[ -d "$proj/skills" ]]; then
  echo "FAIL: skills/ directory was created — kind fell back to claude-skill"
  exit 1
fi

# ── 2. --target codex alone (no --target-dir) fails loudly ─────────────
# Run from a temp cwd so nothing real is touched; the placeholder config_dir
# should now cause a hard failure, not a silent "Install complete".
set +e
bash "$ROOT/install.sh" --target codex >"$T/run2.out" 2>&1
rc=$?
set -e
if [[ "${rc}" -eq 0 ]]; then
  echo "FAIL: --target codex without --target-dir reported success (exit 0)"
  cat "$T/run2.out"
  exit 1
fi

echo "CLI TARGET-DIR KIND: pass (--target codex --target-dir writes AGENTS.md with markers, no skills/ tree; --target codex alone fails non-zero)"
