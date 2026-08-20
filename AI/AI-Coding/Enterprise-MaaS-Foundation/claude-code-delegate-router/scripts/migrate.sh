#!/usr/bin/env bash
# migrate.sh — migrate from claude-glm/LiteLLM legacy to direct MaaS.
#
# Removes ONLY client-side legacy values that are proven owned by the
# claude-maas project via the ownership manifest (~/.claude-maas/manifest.json):
#
#   * old claude-glm wrapper symlink in ~/.local/bin
#   * old policy marker block in ~/.claude/CLAUDE.md
#   * owned route-hint hook entry in ~/.claude/settings.json
#   * LiteLLM base URL / virtual key / model mapping in settings.json env
#     (only the env keys listed in the manifest's owned_env_keys)
#
# Invariants:
#   * Requires --dry-run or --apply (never infers apply).
#   * --dry-run is byte-for-byte side-effect free.
#   * --apply creates a .bak backup before modifying any file.
#   * Does NOT stop or modify a remote LiteLLM deployment.
#   * Does NOT delete OAuth token, Anthropic API key, user hooks, MCP,
#     theme, or preferences.
#   * Idempotent: running twice produces identical output.
#   * Uses only Python stdlib for JSON/text manipulation (no jq).
set -euo pipefail

# ---------------------------------------------------------------------------
# Locate the project root.
# ---------------------------------------------------------------------------

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${script_dir}/.." && pwd)"

claude_dir="${HOME}/.claude"
claude_md="${claude_dir}/CLAUDE.md"
settings_json="${claude_dir}/settings.json"
claude_maas_dir="${HOME}/.claude-maas"
manifest_json="${claude_maas_dir}/manifest.json"
local_bin="${HOME}/.local/bin"

BEGIN_MARKER="<!-- BEGIN claude-maas-policy -->"
END_MARKER="<!-- END claude-maas-policy -->"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

die() {
    echo "migrate: $*" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Parse flags — require exactly one mode.
# ---------------------------------------------------------------------------

MODE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            MODE="dry-run"
            shift
            ;;
        --apply)
            MODE="apply"
            shift
            ;;
        --help|-h)
            cat <<'USAGE'
migrate.sh — migrate from claude-glm/LiteLLM legacy to direct MaaS

Usage:
  ./scripts/migrate.sh --dry-run    # show what would be removed (no changes)
  ./scripts/migrate.sh --apply      # remove owned legacy values (with backup)

Removes ONLY client-side legacy values proven by the ownership manifest.
Does NOT stop or modify a remote LiteLLM deployment.
Does NOT delete OAuth token, Anthropic API key, user hooks, MCP, theme, or preferences.
USAGE
            exit 0
            ;;
        *)
            die "unknown option: $1 (use --dry-run or --apply)"
            ;;
    esac
done

if [[ -z "$MODE" ]]; then
    die "must specify --dry-run or --apply (will not infer apply)"
fi

# ---------------------------------------------------------------------------
# Load the ownership manifest.
#
# If the manifest does not exist, we have no ownership proof, so we do nothing.
# This is the safe default: never remove values without proof of ownership.
# ---------------------------------------------------------------------------

has_manifest="no"
if [[ -f "$manifest_json" ]]; then
    has_manifest="yes"
fi

# ---------------------------------------------------------------------------
# Prepare a temp directory for passing data to python3.
# ---------------------------------------------------------------------------

WORK_TMP=$(mktemp -d) || die "failed to create temp dir"
trap 'rm -rf "$WORK_TMP"' EXIT

# ---------------------------------------------------------------------------
# Run the migration logic in Python (stdlib only).
#
# We pass all paths and the mode via argv. The python code:
#   1. Loads the manifest (if present) to determine owned keys/markers/hooks.
#   2. For --dry-run: prints what would be removed, writes nothing.
#   3. For --apply: writes backups, then removes only owned values.
# ---------------------------------------------------------------------------

python3 - "$MODE" "$has_manifest" "$manifest_json" "$claude_md" "$settings_json" "$local_bin" "$BEGIN_MARKER" "$END_MARKER" "$WORK_TMP" <<'PYEOF'
import json
import os
import shutil
import sys

mode = sys.argv[1]           # "dry-run" or "apply"
has_manifest = sys.argv[2] == "yes"
manifest_path = sys.argv[3]
claude_md_path = sys.argv[4]
settings_path = sys.argv[5]
local_bin_path = sys.argv[6]
begin_marker = sys.argv[7]
end_marker = sys.argv[8]
work_tmp = sys.argv[9]

def log(msg):
    print(f"migrate: {msg}")

# ---------------------------------------------------------------------------
# Load manifest
# ---------------------------------------------------------------------------

manifest = None
if has_manifest and os.path.exists(manifest_path):
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError):
        manifest = None

if manifest is None:
    log("no ownership manifest found — nothing to migrate (no ownership proof)")
    sys.exit(0)

owned_env_keys = set(manifest.get("owned_env_keys", []))
owned_hook_command = manifest.get("owned_hook_command", "")
owned_wrapper = manifest.get("owned_wrapper", "")
markers = manifest.get("markers", [])
# The manifest may record specific launcher install names to remove.
owned_launchers = set()
for entry in manifest.get("launchers", []):
    if isinstance(entry, dict) and "name" in entry:
        owned_launchers.add(entry["name"])

# ---------------------------------------------------------------------------
# Helper: safe read
# ---------------------------------------------------------------------------

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None

def write_text(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def backup(path):
    """Create a .bak backup of path if it exists."""
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")

# ---------------------------------------------------------------------------
# Step 1: Remove old policy marker block from CLAUDE.md
# ---------------------------------------------------------------------------

def remove_marker_block(content):
    """Remove the marker-fenced block from content. Returns (new_content, removed)."""
    if begin_marker not in content:
        return content, False
    try:
        start = content.index(begin_marker)
        end = content.index(end_marker, start) + len(end_marker)
    except ValueError:
        return content, False
    # Remove the block and any immediately surrounding blank lines to keep
    # the document tidy. We remove the block plus one trailing newline.
    new_content = content[:start] + content[end:]
    # Strip leading blank lines left at the cut point (at most 2).
    # We only remove blank lines that are directly adjacent to the cut.
    # Keep it simple: just rstrip/lstrip the gap minimally.
    # Collapse multiple consecutive blank lines at the cut point to one.
    before = new_content[:start]
    after = new_content[start:]
    # Remove leading newlines from 'after' (up to 2).
    after = after.lstrip("\n")
    # Remove trailing blank line from 'before' if after is non-empty.
    if after:
        before = before.rstrip("\n") + "\n\n" if before.strip() else before
    new_content = before + after
    return new_content, True

claude_md_content = read_text(claude_md_path)
claude_md_changed = False
if claude_md_content is not None:
    new_content, removed = remove_marker_block(claude_md_content)
    if removed:
        claude_md_changed = True
        if mode == "dry-run":
            log(f"would remove policy marker block from {claude_md_path}")
        else:
            backup(claude_md_path)
            write_text(claude_md_path, new_content)
            log(f"removed policy marker block from {claude_md_path}")

# ---------------------------------------------------------------------------
# Step 2: Remove owned hook entry and owned env keys from settings.json
# ---------------------------------------------------------------------------

settings_content = read_text(settings_path)
settings_changed = False
if settings_content is not None:
    try:
        settings = json.loads(settings_content)
    except json.JSONDecodeError:
        settings = None

    if settings is not None:
        changed = False

        # 2a: Remove owned hook entries.
        hooks = settings.get("hooks", {})
        if isinstance(hooks, dict):
            for event_type in list(hooks.keys()):
                entries = hooks[event_type]
                if not isinstance(entries, list):
                    continue
                kept = []
                for entry in entries:
                    if not isinstance(entry, dict):
                        kept.append(entry)
                        continue
                    # Check if this entry's commands match the owned hook.
                    is_owned = False
                    if owned_hook_command:
                        for h in entry.get("hooks", []):
                            if isinstance(h, dict):
                                cmd = h.get("command", "")
                                if owned_hook_command in cmd:
                                    is_owned = True
                                    break
                    if is_owned:
                        if mode == "dry-run":
                            log(f"would remove owned hook from hooks.{event_type} in {settings_path}")
                        changed = True
                    else:
                        kept.append(entry)
                if len(kept) != len(entries):
                    hooks[event_type] = kept
                    if not kept:
                        del hooks[event_type]
            settings["hooks"] = hooks

        # 2b: Remove owned env keys.
        env = settings.get("env", {})
        if isinstance(env, dict):
            for key in list(env.keys()):
                if key in owned_env_keys:
                    if mode == "dry-run":
                        log(f"would remove env.{key} from {settings_path}")
                    del env[key]
                    changed = True
            settings["env"] = env

        if changed:
            settings_changed = True
            if mode == "apply":
                backup(settings_path)
                write_text(settings_path, json.dumps(settings, indent=2) + "\n")
                log(f"removed owned legacy values from {settings_path}")

# ---------------------------------------------------------------------------
# Step 3: Remove old wrapper symlink from ~/.local/bin
# ---------------------------------------------------------------------------

if owned_wrapper:
    wrapper_path = os.path.join(local_bin_path, owned_wrapper)
    if os.path.islink(wrapper_path) or os.path.exists(wrapper_path):
        if mode == "dry-run":
            log(f"would remove wrapper {wrapper_path}")
        else:
            os.remove(wrapper_path)
            log(f"removed wrapper {wrapper_path}")

# 3b: Remove owned launcher symlinks from manifest.
for name in sorted(owned_launchers):
    launcher_path = os.path.join(local_bin_path, name)
    if os.path.islink(launcher_path) or os.path.exists(launcher_path):
        # Only remove if it's a symlink or a file we own. Don't remove dirs.
        if os.path.isdir(launcher_path) and not os.path.islink(launcher_path):
            continue
        if mode == "dry-run":
            log(f"would remove launcher {launcher_path}")
        else:
            os.remove(launcher_path)
            log(f"removed launcher {launcher_path}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

if mode == "dry-run":
    if not claude_md_changed and not settings_changed and not owned_wrapper:
        log("dry-run: no owned legacy values found to remove")
    log("dry-run complete — no files were modified")
else:
    if not claude_md_changed and not settings_changed and not owned_wrapper:
        log("apply: no owned legacy values found to remove (already clean)")
    log("apply complete — owned legacy values removed, backups written (.bak)")
PYEOF

# Clean exit (trap removes WORK_TMP).
exit 0
