#!/usr/bin/env bash
#
# dream-stop-hook.sh - Claude Code Stop hook for maas-dreaming.
#
# Fires when a Claude Code session ends. It ONLY evaluates the schedule gate and,
# if a dream is due, writes a project-scoped `.dream-pending` flag under the
# native memory dir. It NEVER spawns a nested LLM (no `claude`/`claude-glm`).
# The dream itself is run by the next real session's host agent via the
# session-start CLAUDE.md directive (see SKILL.md). Always exits 0 so it can
# never block a session from closing.
#
# Install (opt-in) in ~/.claude/settings.json:
#   "hooks": { "Stop": [{ "type": "command",
#     "command": "bash $HOME/.claude/skills/maas-dreaming/bin/dream-stop-hook.sh" }] }
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${CLAUDE_PROJECT_DIR:-$PWD}"

python3 "$ROOT/scripts/should_run.py" pending --repo-root "$REPO" >/dev/null 2>&1 || true
exit 0
