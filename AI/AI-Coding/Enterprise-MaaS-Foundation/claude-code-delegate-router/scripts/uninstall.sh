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
audit_dir="${HOME}/.claude-hybrid/audit"

BEGIN_MARKER="<!-- BEGIN claude-maas-policy -->"
END_MARKER="<!-- END claude-maas-policy -->"

# Project-owned launcher names to remove from ~/.local/bin.
OWNED_LAUNCHERS=("claude-maas" "claude-select" "delegate" "workflow" "claude-glm")

# Project-owned agent/skill file name prefixes. We remove files whose names
# start with these prefixes. We do NOT remove user's own agents/skills.
OWNED_AGENT_PREFIXES=("maas-" "claude-maas")
OWNED_SKILL_PREFIXES=("maas-" "claude-maas")

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
# Step 6: Retain or purge ~/.claude-maas and audit
# ---------------------------------------------------------------------------

if [[ "$PURGE" == "yes" ]]; then
    # Remove ~/.claude-maas entirely.
    if [[ -d "$claude_maas_dir" ]]; then
        rm -rf "$claude_maas_dir"
        echo "uninstall: purged $claude_maas_dir"
    fi
    # Remove audit data.
    if [[ -d "$audit_dir" ]]; then
        rm -rf "$audit_dir"
        echo "uninstall: purged $audit_dir"
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
    echo "uninstall: default complete — project items removed, key/audit retained"
fi

exit 0
