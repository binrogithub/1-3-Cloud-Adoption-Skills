#!/usr/bin/env bash
# uninstall.sh — precise uninstall of the claude-maas project.
#
# Default mode removes only:
#   * project marker block from ~/.claude/CLAUDE.md
#   * owned route-hint hook entry from ~/.claude/settings.json
#   * project agent/skill files from ~/.claude/agents/ and ~/.claude/skills/
#   * wrapper symlinks from ~/.local/bin (claude-maas, claude-select, delegate,
#     workflow, and the legacy claude-glm wrapper if present)
#
# Default mode RETAINS (and tells the user their location):
#   * ~/.claude-maas/          (api-key, config.json, manifest.json)
#   * ~/.claude-hybrid/audit/  (audit data)
#
# --purge (must be explicit): also removes ~/.claude-maas/ and ~/.claude-hybrid/audit/.
#
# Invariants:
#   * Never deletes OAuth token, Anthropic API key, user hooks, MCP, theme,
#     preferences, or user-installed tools.
#   * Idempotent: running twice is a no-op (exit 0).
#   * Without --purge, never deletes the key file.
#   * Uses only Python stdlib for JSON/text manipulation (no jq).
set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

die() {
    echo "uninstall: $*" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------

PURGE="no"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --purge)
            PURGE="yes"
            shift
            ;;
        --help|-h)
            cat <<'USAGE'
uninstall.sh — uninstall the claude-maas project

Usage:
  ./scripts/uninstall.sh            # remove project items, retain key/audit
  ./scripts/uninstall.sh --purge    # also remove ~/.claude-maas and audit

Default mode removes: project marker, owned hook, agents/skills, wrapper symlinks.
Default mode retains: ~/.claude-maas (key, config), ~/.claude-hybrid/audit.
--purge also removes ~/.claude-maas and audit data.
USAGE
            exit 0
            ;;
        *)
            die "unknown option: $1 (use --purge)"
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

claude_dir="${HOME}/.claude"
claude_md="${claude_dir}/CLAUDE.md"
settings_json="${claude_dir}/settings.json"
agents_dir="${claude_dir}/agents"
skills_dir="${claude_dir}/skills"
local_bin="${HOME}/.local/bin"
claude_maas_dir="${HOME}/.claude-maas"
# C4 (PRD PROJECT_CLOSURE_V2 §5): delegate/workflow write audit to
# ~/.claude-hybrid/route-audit.jsonl and ~/.claude-hybrid/workflows/, NOT to
# ~/.claude-hybrid/audit/. Point at the real location so --purge actually
# removes the audit file.
audit_dir="${HOME}/.claude-hybrid"
session_state_dir="${XDG_STATE_HOME:-${HOME}/.local/state}/claude-maas-delegate"
agent_adapter_manifest="${HOME}/.config/claude-maas/agent-adapters-manifest.json"
project_root="$(cd "$(dirname "$0")/.." && pwd)"

BEGIN_MARKER="<!-- BEGIN claude-maas-policy -->"
END_MARKER="<!-- END claude-maas-policy -->"

# Project-owned launcher names to remove from ~/.local/bin.
OWNED_LAUNCHERS=("claude-maas" "claude-select" "delegate" "maas-delegate" "workflow" "claude-glm")

# Project-owned agent/skill file name prefixes. We remove files whose names
# start with these prefixes. We do NOT remove user's own agents/skills.
OWNED_AGENT_PREFIXES=("maas-" "claude-maas")
OWNED_SKILL_PREFIXES=("maas-" "claude-maas")

# ---------------------------------------------------------------------------
# Step 0: Remove only the global-agent adapters recorded by this project.
# ---------------------------------------------------------------------------

if [[ -f "$agent_adapter_manifest" ]]; then
    # Resolve Skill source from repo layout or self-contained Skill-root layout.
    if [[ -f "$project_root/skills/claude-maas-delegate/SKILL.md" ]]; then
        _skill_source="$project_root/skills/claude-maas-delegate"
    elif [[ -f "$project_root/SKILL.md" && -f "$project_root/references/routing-policy.md" ]]; then
        _skill_source="$project_root"
    else
        _skill_source="$project_root/skills/claude-maas-delegate"
    fi
    python3 "$project_root/scripts/configure-agents.py" uninstall \
        --skill-source "$_skill_source" \
        --manifest "$agent_adapter_manifest" \
        || die "failed to remove global agent adapters"
    unset _skill_source
    echo "uninstall: removed global agent delegation adapters"
fi

# ---------------------------------------------------------------------------
# Step 1: Remove project marker block from CLAUDE.md
# ---------------------------------------------------------------------------

if [[ -f "$claude_md" ]]; then
    python3 - "$claude_md" "$BEGIN_MARKER" "$END_MARKER" <<'PYEOF'
import sys

path = sys.argv[1]
begin_marker = sys.argv[2]
end_marker = sys.argv[3]

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

if begin_marker not in content:
    sys.exit(0)

try:
    start = content.index(begin_marker)
    end = content.index(end_marker, start) + len(end_marker)
except ValueError:
    sys.exit(0)

# Remove the block and tidy surrounding blank lines.
new_content = content[:start] + content[end:]
before = new_content[:start]
after = new_content[start:]
after = after.lstrip("\n")
if after:
    before = before.rstrip("\n") + "\n\n" if before.strip() else before
new_content = before + after

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"uninstall: removed project marker block from {path}")
PYEOF
fi

# ---------------------------------------------------------------------------
# Step 2: Remove owned hook entry from settings.json
# ---------------------------------------------------------------------------

if [[ -f "$settings_json" ]]; then
    python3 - "$settings_json" <<'PYEOF'
import json
import os
import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

try:
    settings = json.loads(content)
except json.JSONDecodeError:
    sys.exit(0)

hooks = settings.get("hooks", {})
if not isinstance(hooks, dict):
    sys.exit(0)

changed = False
for event_type in list(hooks.keys()):
    entries = hooks[event_type]
    if not isinstance(entries, list):
        continue
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        is_owned = False
        for h in entry.get("hooks", []):
            if isinstance(h, dict):
                cmd = h.get("command", "")
                if "route-hint" in cmd:
                    is_owned = True
                    break
        if is_owned:
            changed = True
        else:
            kept.append(entry)
    if len(kept) != len(entries):
        hooks[event_type] = kept
        if not kept:
            del hooks[event_type]

if changed:
    settings["hooks"] = hooks
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print(f"uninstall: removed owned hook entry from {path}")
PYEOF
fi

# ---------------------------------------------------------------------------
# Step 3: Remove project-owned agent files from ~/.claude/agents/
# ---------------------------------------------------------------------------

if [[ -d "$agents_dir" ]]; then
    for agent_file in "$agents_dir"/*; do
        [[ -f "$agent_file" ]] || continue
        base="$(basename "$agent_file")"
        for prefix in "${OWNED_AGENT_PREFIXES[@]}"; do
            if [[ "$base" == "${prefix}"* ]]; then
                rm -f "$agent_file"
                echo "uninstall: removed agent $agent_file"
                break
            fi
        done
    done
fi

# ---------------------------------------------------------------------------
# Step 4: Remove project-owned skill files from ~/.claude/skills/
# ---------------------------------------------------------------------------

if [[ -d "$skills_dir" ]]; then
    for skill_file in "$skills_dir"/*; do
        [[ -f "$skill_file" ]] || continue
        base="$(basename "$skill_file")"
        for prefix in "${OWNED_SKILL_PREFIXES[@]}"; do
            if [[ "$base" == "${prefix}"* ]]; then
                rm -f "$skill_file"
                echo "uninstall: removed skill $skill_file"
                break
            fi
        done
    done
fi

# ---------------------------------------------------------------------------
# Step 5: Remove project wrapper symlinks from ~/.local/bin
# ---------------------------------------------------------------------------

if [[ -d "$local_bin" ]]; then
    for name in "${OWNED_LAUNCHERS[@]}"; do
        target="$local_bin/$name"
        if [[ -L "$target" || -f "$target" ]]; then
            rm -f "$target"
            echo "uninstall: removed launcher $target"
        fi
    done
fi

# ---------------------------------------------------------------------------
# Step 5b: Sweep *every* PATH dir (+ /usr/local/bin, /usr/bin) for symlinks
# pointing at this repository, regardless of link name.
#
# PRD PROJECT_CLOSURE_V1 R1: the name-based Step 5 only covers ~/.local/bin
# and misses 08-20 residue in /usr/local/bin — including the case variant
# `Claude-maas`. We resolve by *target*, not by name: any symlink whose
# realpath is this repo (or lives under it) is removed. Symlinks pointing
# elsewhere are left untouched.
# ---------------------------------------------------------------------------

_repo_root="$(cd "$(dirname "$0")/.." && pwd)"
_repo_real="$(readlink -f "$_repo_root" 2>/dev/null || echo "$_repo_root")"

_sweep_dirs=()
IFS=':' read -r -a _path_parts <<<"${PATH:-}"
for _d in "${_path_parts[@]}"; do
    [[ -n "$_d" ]] && _sweep_dirs+=("$_d")
done
# Always include the historical residue locations even if not on PATH.
# UNINSTALL_SYSTEM_BINS is overridable for test isolation (default: the
# real-world residue locations). Set to empty to sweep only $PATH.
for _d in ${UNINSTALL_SYSTEM_BINS:-/usr/local/bin /usr/bin}; do
    case ":${PATH:-}:" in
        *":$_d:"*) ;;            # already present
        *) _sweep_dirs+=("$_d") ;;
    esac
done

for _dir in "${_sweep_dirs[@]}"; do
    [[ -d "$_dir" ]] || continue
    for _entry in "$_dir"/*; do
        [[ -L "$_entry" ]] || continue
        _target="$(readlink -f "$_entry" 2>/dev/null || true)"
        [[ -n "$_target" ]] || continue
        # Remove if the link target IS the repo root or lives under it.
        if [[ "$_target" == "$_repo_real" || "$_target" == "$_repo_real"/* ]]; then
            rm -f "$_entry"
            echo "uninstall: removed repo-pointing symlink $_entry -> $_target"
        fi
    done
done
unset _repo_root _repo_real _sweep_dirs _path_parts _dir _entry _target

# ---------------------------------------------------------------------------
# Step 6: Clean up legacy adapter artifacts (idempotent, all optional)
# ---------------------------------------------------------------------------

if command -v systemctl >/dev/null 2>&1; then
    for _s in /etc/systemd/system/claude-*-proxy.service; do
        [[ -f "$_s" ]] && systemctl stop "$(basename "$_s")" 2>/dev/null || true
        rm -f "$_s" 2>/dev/null || true
    done
    systemctl daemon-reload 2>/dev/null || true
fi
rm -rf /opt/claude-*-proxy 2>/dev/null || true

# R2 (PRD PROJECT_CLOSURE_V1 §3.2): directory-integral cleanup of key-bearing
# /etc trees. The legacy precise-glob `rm -f /etc/claude-*-proxy/maas.env`
# missed every `.bak-*` file, leaving real keys on disk for weeks.
# UNINSTALL_ETC_ROOTS is overridable for test isolation.
for _etc_root in ${UNINSTALL_ETC_ROOTS:-/etc/claude-*-proxy /etc/claude-glm}; do
    [[ -e "$_etc_root" ]] && rm -rf "$_etc_root" 2>/dev/null || true
done
unset _etc_root

# C3 (PRD PROJECT_CLOSURE_V2 §4.3.3): scan the FULL ~/.config/claude-* tree
# and remove every non-live key-bearing file — by content, not just name.
# A file is "live" iff it is a top-level api-key/config.json/manifest.json
# directly under ~/.config/claude-<profile>/. Everything else that matches a
# key-bearing name pattern OR contains an API_KEY= assignment is residue and
# is deleted. This catches subdirectory backups (backups/, repair-backups/),
# timestamped names (api-key.<ts>), and env files with embedded keys — all of
# which the V1 name-glob missed.
python3 - "$HOME" <<'PYEOF'
import os, re, sys
from pathlib import Path

home = Path(sys.argv[1])
config_root = home / ".config"
if not config_root.is_dir():
    sys.exit(0)

key_name_re = re.compile(
    r"^(api-key.*|.*\.env|env|.*\.bak.*|.*key.*\.json)$", re.IGNORECASE
)
key_content_re = re.compile(
    r"^\s*(ANTHROPIC_API_KEY|MAAS_API_KEY|API_KEY)\s*=", re.MULTILINE
)
live_bases = {"api-key", "config.json", "manifest.json"}

removed = 0
for d in sorted(config_root.glob("claude-*")):
    if not d.is_dir():
        continue
    for path in d.rglob("*"):
        if not path.is_file():
            continue
        is_live = (
            path.name in live_bases
            and path.parent == d
        )
        if is_live:
            continue
        carries = bool(key_name_re.match(path.name))
        if not carries:
            try:
                carries = bool(key_content_re.search(path.read_text(errors="ignore")))
            except OSError:
                carries = False
        if carries:
            try:
                path.unlink()
                removed += 1
                print(f"uninstall: removed key-bearing file {path}")
            except OSError:
                pass
if removed:
    print(f"uninstall: removed {removed} key-bearing residue file(s) under ~/.config/claude-*")
PYEOF

# ---------------------------------------------------------------------------
# Step 7: Retain or purge ~/.claude-maas and audit
# ---------------------------------------------------------------------------

if [[ "$PURGE" == "yes" ]]; then
    # Remove ~/.claude-maas entirely.
    if [[ -d "$claude_maas_dir" ]]; then
        rm -rf "$claude_maas_dir"
        echo "uninstall: purged $claude_maas_dir"
    fi
    # C3: --purge also clears the live config tree ~/.config/claude-*/
    # (where the in-use api-key actually lives — ~/.claude-maas is the
    # CLAUDE_CONFIG_DIR, not the key location).
    for _purge_cfg in "$HOME"/.config/claude-*; do
        [[ -d "$_purge_cfg" ]] || continue
        rm -rf "$_purge_cfg"
        echo "uninstall: purged $_purge_cfg"
    done
    unset _purge_cfg
    # Remove audit data.
    if [[ -d "$audit_dir" ]]; then
        rm -rf "$audit_dir"
        echo "uninstall: purged $audit_dir"
    fi
    # Session registry contains only hashed ownership identifiers and Claude
    # session IDs, but removal is explicit and limited to this exact root.
    if [[ -d "$session_state_dir" ]]; then
        rm -rf "$session_state_dir"
        echo "uninstall: purged $session_state_dir"
    fi
    # Also remove the parent ~/.claude-hybrid if it's now empty.
    claude_hybrid_dir="${HOME}/.claude-hybrid"
    if [[ -d "$claude_hybrid_dir" ]]; then
        rmdir "$claude_hybrid_dir" 2>/dev/null || true
    fi
    echo "uninstall: --purge complete — key, config, and audit removed"
else
    # Tell the user where retained data lives.
    echo "uninstall: retained data (use --purge to remove):"
    if [[ -d "$claude_maas_dir" ]]; then
        echo "  key/config: $claude_maas_dir"
        if [[ -f "$claude_maas_dir/api-key" ]]; then
            echo "    api-key: $claude_maas_dir/api-key"
        fi
        if [[ -f "$claude_maas_dir/config.json" ]]; then
            echo "    config:  $claude_maas_dir/config.json"
        fi
    fi
    if [[ -d "$audit_dir" ]]; then
        echo "  audit: $audit_dir"
    fi
    if [[ -d "$session_state_dir" ]]; then
        echo "  delegation sessions: $session_state_dir"
    fi
    echo "uninstall: default complete — project items removed, key/audit retained"
fi

exit 0
