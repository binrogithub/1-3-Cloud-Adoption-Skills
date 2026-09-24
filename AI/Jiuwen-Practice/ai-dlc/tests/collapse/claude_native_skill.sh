#!/usr/bin/env bash
# Regression test for a real report: a user installed ai-dlc via the
# claude-maas launcher on a fresh host. The launcher exports
# CLAUDE_CONFIG_DIR=~/.claude-maas before exec'ing the real claude
# binary, but install.sh's default (no --target) path always wrote to
# the static targets/claude.json config_dir (~/.claude) regardless —
# so the skill was invisible until the user manually symlinked
# ~/.claude-maas/skills -> ~/.claude/skills. Once visible, /ai-dlc was
# STILL non-functional: the claude-skill kind only ever copied
# SKILL.md, never bin/plan.py or config/ — a manual, no automated
# tool.
#
# Two fixes, both covered here:
#  1. install.sh's default branch now prefers $CLAUDE_CONFIG_DIR when
#     set, over the static targets/claude.json value — no symlink,
#     no --target guessing, whichever launcher's session ran the
#     install is the one that gets the skill.
#  2. kind=claude-native-skill (now what targets/claude*.json declare)
#     bundles the whole toolkit into <config_dir>/skills/ai-dlc/, the
#     same self-contained approach as codex-native-skill, so /ai-dlc
#     can actually run bin/plan.py instead of being prose with no
#     tools behind it.
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

# ── 1. kind=claude-native-skill: whole toolkit lands under skills/ai-dlc/ ──
config_root="$T/claude-root"
mkdir -p "$config_root"
(
  source_funcs
  install_skills_to_target "claude-native-test" "$config_root" "claude-native-skill"
) > "$T/install.out" 2>&1 || { echo "FAIL: install_skills_to_target (claude-native-skill) failed"; cat "$T/install.out"; exit 1; }

dest="$config_root/skills/ai-dlc"
[[ -f "$dest/SKILL.md" ]] || { echo "FAIL: SKILL.md not created at $dest"; exit 1; }
[[ -f "$dest/bin/plan.py" ]] || { echo "FAIL: bin/plan.py did not travel — /ai-dlc would still be prose with no tools"; exit 1; }
[[ -f "$dest/config/collapsed.config.yaml" ]] || { echo "FAIL: config/ did not travel"; exit 1; }
[[ ! -e "$dest/.git" ]] || { echo "FAIL: .git was copied"; exit 1; }
[[ ! -e "$dest/.ai-dlc" ]] || { echo "FAIL: .ai-dlc (install-state) was copied"; exit 1; }

# ── 2. all three claude targets declare the self-contained kind ────────
for f in claude claude-glm claude-maas; do
  kind=$(python3 -c "import json; print(json.load(open('$ROOT/targets/$f.json'))['kind'])")
  [[ "$kind" == "claude-native-skill" ]] \
    || { echo "FAIL: targets/$f.json kind is '$kind', expected claude-native-skill"; exit 1; }
done

# ── 3. CLAUDE_CONFIG_DIR auto-detection in the default install path ────
# Real subprocess test (not the sourced-function unit test above) — this
# exercises main()'s actual --target-dir-less, --target-less branch,
# which is exactly what a plain `./install.sh` run inside a launcher's
# session hits.
launcher_home="$T/launcher-home"
mkdir -p "$launcher_home/fake-config-dir"
out=$(cd "$ROOT" && CLAUDE_CONFIG_DIR="$launcher_home/fake-config-dir" HOME="$launcher_home" \
      AI_DLC_MANIFEST_FILE="$T/subprocess-manifest.json" bash install.sh 2>&1) \
  || { echo "FAIL: default install with CLAUDE_CONFIG_DIR set exited non-zero"; echo "$out"; exit 1; }
echo "$out" | grep -qi "CLAUDE_CONFIG_DIR is set" \
  || { echo "FAIL: default install did not report detecting CLAUDE_CONFIG_DIR: $out"; exit 1; }
[[ -f "$launcher_home/fake-config-dir/skills/ai-dlc/bin/plan.py" ]] \
  || { echo "FAIL: skill did not land under \$CLAUDE_CONFIG_DIR (fake-config-dir), the launcher's real skill dir"; exit 1; }
[[ ! -d "$launcher_home/.claude" ]] \
  || { echo "FAIL: skill also landed under \$HOME/.claude — CLAUDE_CONFIG_DIR should have taken priority, not both"; exit 1; }

echo "CLAUDE NATIVE SKILL: pass (claude-native-skill bundles the whole toolkit under skills/ai-dlc/; all three claude targets declare it; CLAUDE_CONFIG_DIR is honored by the default install path over the static target config_dir)"
