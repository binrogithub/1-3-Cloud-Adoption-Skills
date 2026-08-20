#!/usr/bin/env bash
# configure-policy.sh — additively install the OAuth orchestration policy.
#
# Merges the marker-fenced policy block from assets/orchestrator-policy.md
# into ~/.claude/CLAUDE.md (preserving existing content, replacing only its
# own marker block) and additively merges the route-hint hook into
# ~/.claude/settings.json hooks (preserving existing hooks, never overwriting
# the whole hooks object).
#
# Invariants:
#   * Writes a fresh .bak backup of CLAUDE.md and settings.json before merging.
#   * Never writes ANTHROPIC_* env entries to settings.json.
#   * Idempotent: running twice produces identical output.
#   * Preserves all existing user content, hooks, permissions, and env vars.
#   * Uses only Python stdlib for JSON and text manipulation (no jq dependency).
set -euo pipefail

# ---------------------------------------------------------------------------
# Locate the project root (directory containing this script's parent).
# ---------------------------------------------------------------------------

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${script_dir}/.." && pwd)"

policy_doc="${project_root}/assets/orchestrator-policy.md"
route_hint_script="${script_dir}/route-hint.sh"

claude_dir="${HOME}/.claude"
claude_md="${claude_dir}/CLAUDE.md"
settings_json="${claude_dir}/settings.json"

# ---------------------------------------------------------------------------
# Ensure ~/.claude/ exists.
# ---------------------------------------------------------------------------

mkdir -p "${claude_dir}"

# ---------------------------------------------------------------------------
# Step 1: Merge policy block into CLAUDE.md (using Python for reliability).
# ---------------------------------------------------------------------------

# Backup CLAUDE.md if it exists.
if [[ -f "${claude_md}" ]]; then
    cp -p "${claude_md}" "${claude_md}.bak"
fi

python3 - "$policy_doc" "$claude_md" <<'PYEOF'
import sys

policy_doc = sys.argv[1]
claude_md = sys.argv[2]
begin_marker = '<!-- BEGIN claude-maas-policy -->'
end_marker = '<!-- END claude-maas-policy -->'

# Read the policy document and extract the marker-fenced block.
with open(policy_doc, 'r') as f:
    doc_content = f.read()

begin_idx = doc_content.index(begin_marker)
end_idx = doc_content.index(end_marker, begin_idx) + len(end_marker)
policy_block = doc_content[begin_idx:end_idx]

# Read existing CLAUDE.md or start empty.
try:
    with open(claude_md, 'r') as f:
        content = f.read()
except FileNotFoundError:
    content = ''

# Check if the marker block already exists.
if begin_marker in content:
    # Replace only the marker block, preserving everything else.
    existing_begin = content.index(begin_marker)
    existing_end = content.index(end_marker, existing_begin) + len(end_marker)
    new_content = content[:existing_begin] + policy_block + content[existing_end:]
else:
    # No existing marker block — append it with a blank line separator.
    if content:
        # Ensure content ends with a newline before appending.
        stripped = content.rstrip()
        new_content = stripped + '\n\n' + policy_block + '\n'
    else:
        new_content = policy_block + '\n'

with open(claude_md, 'w') as f:
    f.write(new_content)
PYEOF

# ---------------------------------------------------------------------------
# Step 2: Additively merge route-hint hook into settings.json.
# ---------------------------------------------------------------------------

# Backup settings.json if it exists.
if [[ -f "${settings_json}" ]]; then
    cp -p "${settings_json}" "${settings_json}.bak"
fi

python3 - "$settings_json" "$route_hint_script" <<'PYEOF'
import json
import os
import sys

settings_path = sys.argv[1]
route_hint_script = sys.argv[2]

# Load existing settings or create empty dict.
if os.path.exists(settings_path) and os.path.getsize(settings_path) > 0:
    with open(settings_path, 'r') as f:
        settings = json.load(f)
else:
    settings = {}

# Ensure 'hooks' dict exists.
if 'hooks' not in settings or not isinstance(settings['hooks'], dict):
    settings['hooks'] = {}

# The route-hint hook fires on UserPromptSubmit, is advisory, and always
# exits 0. We add it additively without removing existing hooks.
hook_event = 'UserPromptSubmit'
if hook_event not in settings['hooks'] or not isinstance(settings['hooks'][hook_event], list):
    settings['hooks'][hook_event] = []

# Build our hook entry.
our_hook_entry = {
    'matcher': '',
    'hooks': [
        {
            'type': 'command',
            'command': 'bash ' + route_hint_script,
        }
    ],
}

# Check if our hook is already installed (by looking for route-hint in commands).
def has_route_hint(entries):
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for h in entry.get('hooks', []):
            if isinstance(h, dict) and 'route-hint' in h.get('command', ''):
                return True
    return False

if not has_route_hint(settings['hooks'][hook_event]):
    settings['hooks'][hook_event].append(our_hook_entry)

# We NEVER write ANTHROPIC_* env entries, and we NEVER delete existing env
# entries (including the user's own ANTHROPIC_API_KEY).  The env dict is left
# byte-for-byte untouched — we only add the route-hint hook above.

# Write the settings back with indentation.
with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')
PYEOF

echo "Policy configured successfully."
echo "  CLAUDE.md: ${claude_md}"
echo "  settings.json: ${settings_json}"
echo "  Backups: ${claude_md}.bak, ${settings_json}.bak"
