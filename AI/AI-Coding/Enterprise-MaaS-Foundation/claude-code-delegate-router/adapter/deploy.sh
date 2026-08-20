#!/usr/bin/env bash
# deploy.sh — deploy the candidate adapter to the production path.
#
# Copies adapter/server.js AND adapter/lifecycle.js (server.js requires it at
# load time) to /opt/claude-code-maas-proxy/, records the SHA-256 of each,
# saves rollback copies, and restarts the systemd service. Never touches the
# host env file (/etc/claude-code-proxy/maas.env) or any secret.
#
# Usage:
#   bash adapter/deploy.sh                  # deploy to production port
#   bash adapter/deploy.sh --candidate-port 3001  # canary on alternate port
set -euo pipefail

ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ADAPTER_DIR/.." && pwd)"
DEST_DIR="${ADAPTER_DEST_DIR:-/opt/claude-code-maas-proxy}"
SERVICE="${ADAPTER_SERVICE:-claude-code-maas-proxy.service}"
ENV_FILE="/etc/claude-code-proxy/maas.env"

# Every file the adapter needs at runtime. server.js requires lifecycle.js —
# deploying server.js alone puts the service into a crash-restart loop.
ARTIFACTS=(server.js lifecycle.js)

CANDIDATE_PORT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --candidate-port) CANDIDATE_PORT="$2"; shift 2 ;;
        --help|-h)
            cat <<'USAGE'
deploy.sh — deploy the candidate adapter

Usage:
  bash adapter/deploy.sh                        # deploy to production
  bash adapter/deploy.sh --candidate-port 3001  # canary on alternate port
USAGE
            exit 0 ;;
        *) echo "deploy: unknown option: $1" >&2; exit 1 ;;
    esac
done

# Pre-flight: every artifact must exist and parse.
for artifact in "${ARTIFACTS[@]}"; do
    src="$ADAPTER_DIR/$artifact"
    [[ -f "$src" ]] || { echo "deploy: source not found: $src" >&2; exit 1; }
    if command -v node >/dev/null 2>&1; then
        node --check "$src" >/dev/null || { echo "deploy: syntax error in $artifact — aborting" >&2; exit 1; }
    fi
done

mkdir -p "$DEST_DIR"

# Save rollback targets, then deploy each artifact and verify the checksum.
for artifact in "${ARTIFACTS[@]}"; do
    src="$ADAPTER_DIR/$artifact"
    dest="$DEST_DIR/$artifact"
    src_sha=$(sha256sum "$src" | cut -d' ' -f1)
    echo "deploy: candidate $artifact SHA-256: $src_sha"

    if [[ -f "$dest" ]]; then
        dest_sha=$(sha256sum "$dest" | cut -d' ' -f1)
        if [[ "$dest_sha" != "$src_sha" ]]; then
            cp "$dest" "$DEST_DIR/$artifact.rollback"
            echo "deploy: saved rollback target $artifact.rollback (SHA-256: $dest_sha)"
        fi
    fi

    cp "$src" "$dest"

    installed_sha=$(sha256sum "$dest" | cut -d' ' -f1)
    if [[ "$installed_sha" != "$src_sha" ]]; then
        echo "deploy: CHECKSUM MISMATCH after copy ($artifact) — aborting" >&2
        exit 1
    fi
    echo "deploy: installed $artifact SHA-256: $installed_sha"
done

# Load gate: the deployed tree must satisfy its own requires before restart.
if command -v node >/dev/null 2>&1; then
    node --check "$DEST_DIR/server.js" >/dev/null || {
        echo "deploy: deployed server.js failed syntax check — aborting" >&2; exit 1; }
    node -e "require('$DEST_DIR/lifecycle.js')" >/dev/null || {
        echo "deploy: deployed lifecycle.js failed to load — aborting" >&2; exit 1; }
    echo "deploy: deployed artifacts load ok"
fi

# Restart the service (if systemd is available and the unit exists).
if command -v systemctl >/dev/null 2>&1 && systemctl cat "$SERVICE" >/dev/null 2>&1; then
    systemctl restart "$SERVICE"
    echo "deploy: service restarted"
    systemctl is-active "$SERVICE" >/dev/null 2>&1 && echo "deploy: service active" || {
        echo "deploy: service failed to start" >&2
        exit 1
    }
else
    echo "deploy: systemd unit not found — skipping restart (candidate/canary mode)"
fi

echo "deploy: complete"
