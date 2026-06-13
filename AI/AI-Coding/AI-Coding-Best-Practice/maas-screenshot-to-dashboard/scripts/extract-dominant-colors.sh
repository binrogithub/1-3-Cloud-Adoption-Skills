#!/bin/bash
set -euo pipefail
# Extract dominant colors from a screenshot using anydesign's extract_colors.py
#
# Usage:
#   ./extract-dominant-colors.sh <screenshot_path> [--top N]
#
# Example:
#   ./extract-dominant-colors.sh dashboard.jpeg --top 8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"

ANYDESIGN_SCRIPT=""
for candidate in \
    "${ANYDESIGN_SCRIPT_PATH:-}" \
    "$REPO_ROOT/.claude/skills/anydesign/scripts/extract_colors.py" \
    "$PWD/.claude/skills/anydesign/scripts/extract_colors.py" \
    "$HOME/.claude/skills/anydesign/scripts/extract_colors.py"; do
    if [ -n "$candidate" ] && [ -f "$candidate" ]; then
        ANYDESIGN_SCRIPT="$candidate"
        break
    fi
done

if [ -z "$ANYDESIGN_SCRIPT" ]; then
    echo "Error: anydesign extract_colors.py not found"
    echo "Install: git clone https://github.com/uxKero/anydesign.git && cp -r anydesign .claude/skills/anydesign"
    echo "Or set ANYDESIGN_SCRIPT_PATH=/path/to/extract_colors.py"
    exit 1
fi

python3 "$ANYDESIGN_SCRIPT" "$@"
