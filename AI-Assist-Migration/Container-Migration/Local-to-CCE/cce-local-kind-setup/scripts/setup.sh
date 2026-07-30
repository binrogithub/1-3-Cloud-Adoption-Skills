#!/usr/bin/env bash
# ============================================================================
# setup.sh — Create a CCE-compatible local Kubernetes cluster with Kind
#
# WHAT:
#   Sets up a 3-node Kind cluster (1 control-plane + 2 workers) that mirrors
#   Huawei Cloud CCE topology. Installs the Rancher local-path provisioner for
#   dynamic PVC and the NGINX Ingress Controller via Helm with pre-loaded images.
#   Idempotent — safe to re-run if the cluster already exists.
#
# USAGE:
#   setup.sh    (no arguments required)
#
# PREREQUISITES:
#   - Docker 20.x+ running
#   - Kind 0.27+ installed
#   - kubectl 1.28+ installed
#   - Helm 3.14+ installed
#   - Minimum: 4 GB RAM, 2 CPUs, 20 GB free disk
#
# STEPS:
#   1. Create Kind cluster (cce-local) from kind-cluster.yaml
#   2. Install Rancher local-path provisioner for dynamic PVC
#   3. Pre-pull ingress-nginx images via Docker (fast)
#   4. Load images into Kind nodes via docker save | ctr import
#   5. Install NGINX Ingress Controller via Helm (no SHA digests)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

INGRESS_CONTROLLER_IMG="registry.k8s.io/ingress-nginx/controller:v1.12.1"
INGRESS_CERTGEN_IMG="registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.6.9"
CLUSTER_NAME="cce-local"

echo "=== CCE-Local Kind Setup ==="
echo ""

echo "[1/5] Creating Kind cluster..."
if kind get clusters 2>/dev/null | grep -q "$CLUSTER_NAME"; then
  echo "Cluster '$CLUSTER_NAME' already exists. Skipping."
else
  kind create cluster --config "$SKILL_DIR/kind-cluster.yaml" --wait 180s
  echo "Cluster created."
fi

echo ""
echo "[2/5] Installing local-path provisioner..."
if kubectl get storageclass local-path -o jsonpath='{.provisioner}' 2>/dev/null | grep -q "rancher"; then
  echo "Rancher local-path provisioner already installed. Skipping."
else
  kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.28/deploy/local-path-storage.yaml
  kubectl wait --namespace local-path-storage \
    --for=condition=ready pod \
    --selector=app=local-path-provisioner \
    --timeout=60s 2>/dev/null || echo "Provisioner may still be starting."
fi

echo ""
echo "[3/5] Pre-pulling ingress-nginx images via Docker..."
docker pull --quiet "$INGRESS_CONTROLLER_IMG" 2>/dev/null || echo "Warning: Docker pull for controller failed (may already exist)"
docker pull --quiet "$INGRESS_CERTGEN_IMG" 2>/dev/null || echo "Warning: Docker pull for certgen failed (may already exist)"

echo ""
echo "[4/5] Loading images into Kind nodes (docker save | ctr import)..."
for node in ${CLUSTER_NAME}-control-plane ${CLUSTER_NAME}-worker ${CLUSTER_NAME}-worker2; do
  echo "  Loading into $node..."
  docker save "$INGRESS_CONTROLLER_IMG" 2>/dev/null | \
    docker exec -i "$node" ctr --namespace=k8s.io images import - 2>/dev/null || \
    echo "  Warning: Failed to load controller into $node"
  docker save "$INGRESS_CERTGEN_IMG" 2>/dev/null | \
    docker exec -i "$node" ctr --namespace=k8s.io images import - 2>/dev/null || \
    echo "  Warning: Failed to load certgen into $node"
done

echo ""
echo "[5/5] Installing NGINX Ingress Controller via Helm..."
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx 2>/dev/null || true
helm repo update

kubectl label nodes ${CLUSTER_NAME}-worker ingress-ready=true --overwrite 2>/dev/null || true

if helm list -n ingress-nginx 2>/dev/null | grep -q "ingress-nginx"; then
  echo "ingress-nginx release exists. Upgrading..."
  helm upgrade ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx \
    -f "$SKILL_DIR/ingress-values.yaml" \
    --wait --timeout 5m
else
  helm install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx --create-namespace \
    -f "$SKILL_DIR/ingress-values.yaml" \
    --wait --timeout 5m
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Cluster: $CLUSTER_NAME"
echo "Nodes:"
kubectl get nodes
echo ""
echo "Ingress controller:"
kubectl get pods -n ingress-nginx
echo ""
echo "StorageClasses:"
kubectl get storageclass
