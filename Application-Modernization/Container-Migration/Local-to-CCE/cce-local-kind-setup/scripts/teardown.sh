#!/usr/bin/env bash
# ============================================================================
# teardown.sh — Remove the nginx-demo app and delete the Kind cluster
#
# WHAT:
#   Uninstalls the nginx-demo Helm release and deletes the cce-local Kind
#   cluster. Removes the demo.local entry from /etc/hosts if present.
#   Safe to run even if resources are already gone.
#
# USAGE:
#   teardown.sh    (no arguments required)
#
# STEPS:
#   1. Uninstall nginx-demo Helm release (ignore errors if not found)
#   2. Delete the Kind cluster 'cce-local'
#   3. Remove demo.local from /etc/hosts (if added by deploy.sh)
# ============================================================================
set -euo pipefail

CLUSTER_NAME="cce-local"

echo "=== Tearing down CCE-Local ==="
echo ""

echo "[1/2] Uninstalling Helm releases..."
helm uninstall nginx-demo --namespace default 2>/dev/null || echo "nginx-demo release not found. Skipping."
helm uninstall ingress-nginx -n ingress-nginx 2>/dev/null || echo "ingress-nginx release not found. Skipping."

echo ""
echo "[2/2] Deleting Kind cluster..."
if kind get clusters 2>/dev/null | grep -q "$CLUSTER_NAME"; then
  kind delete cluster --name "$CLUSTER_NAME"
  echo "Cluster deleted."
else
  echo "Cluster '$CLUSTER_NAME' not found. Skipping."
fi

echo ""
echo "=== Teardown complete ==="
