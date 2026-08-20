#!/usr/bin/env bash
# rollback.sh — restore the prior adapter artifacts and restart.
#
# Restores /opt/claude-code-maas-proxy/<artifact>.rollback for every artifact
# that has one, verifies each checksum, and restarts the service. Never touches
# the env file or secrets.
#
# Usage:
#   bash adapter/rollback.sh
set -euo pipefail

DEST_DIR="${ADAPTER_DEST_DIR:-/opt/claude-code-maas-proxy}"
SERVICE="${ADAPTER_SERVICE:-claude-code-maas-proxy.service}"
ARTIFACTS=(server.js lifecycle.js)

restored=0
for artifact in "${ARTIFACTS[@]}"; do
    rollback="$DEST_DIR/$artifact.rollback"
    dest="$DEST_DIR/$artifact"
    [[ -f "$rollback" ]] || continue

    rollback_sha=$(sha256sum "$rollback" | cut -d' ' -f1)
    echo "rollback: restoring $artifact SHA-256: $rollback_sha"
    cp "$rollback" "$dest"

    installed_sha=$(sha256sum "$dest" | cut -d' ' -f1)
    if [[ "$installed_sha" != "$rollback_sha" ]]; then
        echo "rollback: CHECKSUM MISMATCH after restore ($artifact) — aborting" >&2
        exit 1
    fi
    echo "rollback: installed $artifact SHA-256: $installed_sha"
    restored=$((restored + 1))
done

if (( restored == 0 )); then
    echo "rollback: no rollback target found in $DEST_DIR" >&2
    exit 1
fi

if command -v systemctl >/dev/null 2>&1 && systemctl cat "$SERVICE" >/dev/null 2>&1; then
    systemctl restart "$SERVICE"
    echo "rollback: service restarted"
    systemctl is-active "$SERVICE" >/dev/null 2>&1 && echo "rollback: service active" || {
        echo "rollback: service failed to start" >&2
        exit 1
    }
else
    echo "rollback: systemd unit not found — skipping restart"
fi

echo "rollback: complete"
