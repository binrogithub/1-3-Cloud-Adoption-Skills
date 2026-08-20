#!/usr/bin/env bash
set -euo pipefail

# configure-claude-code.sh — DEPRECATED.
#
# This script wrote global model mappings (opus/sonnet/haiku → GLM) into
# ~/.claude/settings.json. That approach is retired: native Claude must never
# be remapped, and GLM-5.2 is selected explicitly via the `claude-litellm` launcher.
#
# PRD-release-closure §4 Work Package D: this script no longer writes global
# mappings. It dispatches to the safe migration flow (claude-litellm-migrate.sh)
# to help users remove the legacy values. For new installations, use
# claude-litellm-setup.sh instead.
#
# Usage (deprecated):
#   configure-claude-code.sh              → dispatches to claude-litellm-migrate.sh --dry-run
#   configure-claude-code.sh --restore    → dispatches to claude-litellm-migrate.sh --dry-run
#                                        (PRD §3.2: --restore must NOT auto-apply;
#                                         it may only dispatch to dry-run or exit
#                                         with migration instructions)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRATE_SCRIPT="$SCRIPT_DIR/claude-litellm-migrate.sh"

if [ ! -f "$MIGRATE_SCRIPT" ]; then
    printf 'configure-claude-code.sh is deprecated.\n' >&2
    printf 'Install the isolated GLM launcher with claude-litellm-setup.sh instead.\n' >&2
    printf '(claude-litellm-migrate.sh not found alongside this script.)\n' >&2
    exit 1
fi

printf 'configure-claude-code.sh is deprecated — dispatching to the safe migration flow.\n' >&2
printf 'For new installations, use claude-litellm-setup.sh instead.\n' >&2
printf 'Review the dry-run plan, then run claude-litellm-migrate.sh --apply with the\n' >&2
printf 'exact --old-base-url and --old-key-fingerprint to remove old values.\n\n' >&2

# PRD §3.2: --restore must NOT convert directly into an unsafe apply. It may
# only dispatch to dry-run so the user reviews the plan and supplies exact
# ownership arguments before applying.
exec "$MIGRATE_SCRIPT" --dry-run "$@"

# Legacy global-mapping code below this line was removed (PRD-release-closure §4 WP-D).
# This script now only dispatches to claude-litellm-migrate.sh.
