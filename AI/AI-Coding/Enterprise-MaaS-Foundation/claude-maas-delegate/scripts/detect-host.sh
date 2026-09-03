#!/usr/bin/env bash
# Return a documented host hint only; never inspect private host databases.
set -euo pipefail

if [[ "${CODEX_HOME:-}" != "" ]] || command -v codex >/dev/null 2>&1; then
  printf '%s\n' codex
elif [[ "${COPILOT_AGENT_MODE:-}" != "" ]] || command -v copilot >/dev/null 2>&1; then
  printf '%s\n' copilot
elif [[ "${CURSOR_AGENT_MODE:-}" != "" ]] || command -v cursor >/dev/null 2>&1; then
  printf '%s\n' cursor
elif [[ "${OPENCODE_CONFIG:-}" != "" ]] || command -v opencode >/dev/null 2>&1; then
  printf '%s\n' opencode
else
  printf '%s\n' generic
fi
