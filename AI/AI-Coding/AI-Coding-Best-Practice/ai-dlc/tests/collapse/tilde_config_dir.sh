#!/usr/bin/env bash
# Regression test: a target's config_dir in targets/*.json may use `~` for
# portability (the shipped public repo's claude.json/claude-glm.json/
# claude-maas.json all do, since they can't hardcode a machine-specific
# absolute path). But a JSON string read via `python -c ... | var=$(...)`
# never passes through bash's own tilde expansion — that only fires for a
# literal unquoted tilde in shell source text, never for a variable's
# stored value — so config_dir stayed the literal 2-byte string "~/..."
# and every path built from it was wrong (a real user hit this: Codex CLI
# installing from a checkout whose claude.json had config_dir: "~/.claude"
# failed with "config dir does not exist: ~/.claude" even though
# ~/.claude was a real, writable directory).
#
# This test builds a target JSON with a literal `~` config_dir, points a
# temp HOME at a fresh dir, and asserts install_skills_to_target() (via
# expand_tilde()) resolves it to the real expanded path — not a literal
# "~" directory created under cwd.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

grep -vxF 'main "$@"' "$ROOT/install.sh" > "$T/install_funcs.sh"
sed -i 's|^SCRIPT_DIR=.*|SCRIPT_DIR="'"$ROOT"'"|' "$T/install_funcs.sh"

# ── 1. expand_tilde() itself: unit-level checks ─────────────────────
fake_home="$T/fakehome"
mkdir -p "$fake_home"
(
  export HOME="$fake_home"
  source "$T/install_funcs.sh"
  [[ "$(expand_tilde '~')" == "$fake_home" ]] \
    || { echo "FAIL: expand_tilde '~' did not resolve to \$HOME"; exit 1; }
  [[ "$(expand_tilde '~/.claude')" == "$fake_home/.claude" ]] \
    || { echo "FAIL: expand_tilde '~/.claude' did not resolve correctly"; exit 1; }
  [[ "$(expand_tilde '/already/absolute')" == "/already/absolute" ]] \
    || { echo "FAIL: expand_tilde must pass through an already-absolute path unchanged"; exit 1; }
) || exit 1

# ── 2. End-to-end: a target JSON with a literal ~ config_dir installs
#      to the real expanded directory, never a literal "~" dir under cwd
work="$T/work"; mkdir -p "$work/fakehome"
cat > "$work/claude-tilde.json" <<'JSONEOF'
{"name": "claude-tilde-test", "kind": "claude-skill", "config_dir": "~/.claude"}
JSONEOF

(
  cd "$work"
  export HOME="$work/fakehome"
  source "$T/install_funcs.sh"
  MANIFEST_FILE="$T/test-manifest.json"
  TARGETS_DIR="$work"
  mkdir -p "${HOME}/.claude"
  tconfig=$(python3 -c "import json; print(json.load(open('claude-tilde.json'))['config_dir'])")
  tconfig="$(expand_tilde "${tconfig}")"
  install_skills_to_target "claude-tilde-test" "${tconfig}" "claude-skill" >"$T/install.out" 2>&1
) || { echo "FAIL: install with a literal ~ config_dir failed"; cat "$T/install.out" 2>/dev/null; exit 1; }

[[ -d "$work/fakehome/.claude/skills/ai-dlc" ]] \
  || { echo "FAIL: skills were not installed under the expanded \$HOME/.claude"; exit 1; }
[[ ! -e "$work/~" ]] \
  || { echo "FAIL: a literal '~' directory was created under cwd — tilde was not expanded"; exit 1; }

echo "TILDE CONFIG DIR: pass (expand_tilde resolves ~ and ~/path to \$HOME; a literal-tilde config_dir installs to the real expanded directory, not a literal '~' dir)"
