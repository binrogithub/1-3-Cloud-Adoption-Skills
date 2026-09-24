#!/usr/bin/env bash
# Regression test: kind=codex-native-skill copies the whole toolkit (not
# just SKILL.md — bin/, config/, openspec/, supervisor/) into
# <config_dir>/ai-dlc/ and generates a fresh SKILL.md there, mirroring
# what Codex CLI's own remote skill-installer produces when it clones
# this repo's GitHub tree wholesale. A user who already has a local
# checkout can register it as a Codex skill this way, without depending
# on Codex's own network fetch path.
#
# This exists because a real user ran plain `./install.sh` (the default
# Claude-only target) then asked "why is there no ai-dlc skill in
# Codex" — there was no install.sh path that did this locally; Codex
# had to be told to `install <url>` (network-dependent, and separately
# found to be broken by a stale local daemon on one host) or a user had
# to manually cp -r the checkout themselves.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

grep -vxF 'main "$@"' "$ROOT/install.sh" > "$T/install_funcs.sh"
sed -i 's|^SCRIPT_DIR=.*|SCRIPT_DIR="'"$ROOT"'"|' "$T/install_funcs.sh"

source_funcs() {
  # shellcheck disable=SC1090
  source "$T/install_funcs.sh"
  MANIFEST_FILE="$T/test-manifest.json"
}

# ── 1. install: whole toolkit lands, SKILL.md generated, exclusions honored
skills_root="$T/codex-skills-root"
mkdir -p "$skills_root"
(
  source_funcs
  install_skills_to_target "codex-native-test" "$skills_root" "codex-native-skill"
) > "$T/install.out" 2>&1 || { echo "FAIL: install_skills_to_target (codex-native-skill) failed"; cat "$T/install.out"; exit 1; }

dest="$skills_root/ai-dlc"
[[ -f "$dest/SKILL.md" ]] || { echo "FAIL: SKILL.md not created at $dest"; exit 1; }
grep -q '^name: ai-dlc' "$dest/SKILL.md" || { echo "FAIL: generated SKILL.md missing name frontmatter"; exit 1; }
[[ -f "$dest/bin/plan.py" ]] || { echo "FAIL: bin/plan.py did not travel with the toolkit copy"; exit 1; }
[[ -f "$dest/config/collapsed.config.yaml" ]] || { echo "FAIL: config/ did not travel with the toolkit copy"; exit 1; }
[[ -d "$dest/openspec" ]] || { echo "FAIL: openspec/ did not travel with the toolkit copy"; exit 1; }

[[ ! -e "$dest/.git" ]] || { echo "FAIL: .git was copied — must be excluded"; exit 1; }
[[ ! -e "$dest/.ai-dlc" ]] || { echo "FAIL: .ai-dlc (install-state) was copied — must be excluded"; exit 1; }
[[ ! -e "$dest/PUBLISH_NOTES.md" ]] || { echo "FAIL: PUBLISH_NOTES.md was copied — must be excluded"; exit 1; }

# ── 2. idempotent re-install: same sha on a clean re-run ───────────────
sha1=$(python3 -c "import hashlib; print(hashlib.sha256(open('$dest/SKILL.md','rb').read()).hexdigest())")
(
  source_funcs
  install_skills_to_target "codex-native-test" "$skills_root" "codex-native-skill"
) > "$T/install2.out" 2>&1 || { echo "FAIL: second install_skills_to_target run failed"; cat "$T/install2.out"; exit 1; }
sha2=$(python3 -c "import hashlib; print(hashlib.sha256(open('$dest/SKILL.md','rb').read()).hexdigest())")
[[ "$sha1" == "$sha2" ]] || { echo "FAIL: re-install produced a different SKILL.md sha"; exit 1; }

# ── 3. uninstall removes the whole directory, not just SKILL.md ────────
(
  source_funcs
  MANIFEST_FILE="$T/test-manifest.json"
  uninstall_target "codex-native-test"
) > "$T/uninstall.out" 2>&1 || { echo "FAIL: uninstall_target failed"; cat "$T/uninstall.out"; exit 1; }
[[ ! -e "$dest" ]] || { echo "FAIL: $dest still exists after uninstall — only SKILL.md was removed, not the whole toolkit copy"; exit 1; }

echo "CODEX NATIVE SKILL: pass (whole toolkit copied to <config_dir>/ai-dlc/ with SKILL.md generated; .git/.ai-dlc/PUBLISH_NOTES.md excluded; idempotent re-install; uninstall removes the full directory)"
