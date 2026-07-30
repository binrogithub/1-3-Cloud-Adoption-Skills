#!/usr/bin/env bash
# ============================================================================
# deploy.sh — Deploy the nginx-demo Helm chart on the local Kind cluster
#
# WHAT:
#   Installs or upgrades the nginx-demo Helm chart on the cce-local Kind
#   cluster. The chart includes Deployment, Service, Ingress, ConfigMap,
#   Secret, HPA, and PVC — all common K8s resources for CCE migration practice.
#
# USAGE:
#   deploy.sh [chart-path]
#
#   If chart-path is omitted, defaults to the helm/nginx-demo/ directory
#   included in this skill.
#
# PREREQUISITES:
#   - Kind cluster 'cce-local' running (run setup.sh first)
#   - Helm 3.14+ installed
#   - kubectl configured for the Kind cluster
#
# STEPS:
#   1. Install/upgrade the nginx-demo Helm chart
#   2. Print ingress access instructions (add demo.local to /etc/hosts)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
CLUSTER_NAME="cce-local"

echo "=== Deploying nginx-demo ==="
echo ""

kubectl config use-context kind-${CLUSTER_NAME} 2>/dev/null || true

CHART_PATH="${1:-$SKILL_DIR/helm/nginx-demo}"
if [ ! -d "$CHART_PATH" ]; then
  echo "Error: Helm chart not found at $CHART_PATH"
  echo "Usage: $0 [chart-path]"
  exit 1
fi

echo "[1/2] Installing Helm chart..."
helm upgrade --install nginx-demo "$CHART_PATH" \
  --namespace default \
  --wait --timeout 180s

echo ""
echo "[2/2] Ingress access info..."
if ! grep -q "demo.local" /etc/hosts 2>/dev/null; then
  echo "Add this line to /etc/hosts for ingress access:"
  echo "  127.0.0.1 demo.local"
else
  echo "demo.local already in /etc/hosts."
fi

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Pods:"
kubectl get pods -l app.kubernetes.io/name=nginx-demo
echo ""
echo "PVC:"
kubectl get pvc
echo ""
echo "Ingress:"
kubectl get ingress
echo ""
echo "HPA:"
kubectl get hpa
echo ""
echo "Test: kubectl port-forward svc/nginx-demo 8080:80 && curl http://localhost:8080"
