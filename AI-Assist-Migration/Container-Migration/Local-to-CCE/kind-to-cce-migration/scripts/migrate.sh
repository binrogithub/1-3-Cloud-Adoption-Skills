#!/usr/bin/env bash
# ============================================================================
# migrate.sh — Migrate a Helm application to Huawei Cloud CCE
#
# WHAT:
#   Automates the deployment phase of a Kind-to-CCE migration. Assumes the
#   CCE cluster and ELB already exist. Logs into SWR, installs the NGINX
#   Ingress Controller with ELB annotation, creates an imagePullSecret for
#   private SWR, deploys the application via Helm, and validates the result.
#
# USAGE:
#   migrate.sh <REGION> <CLUSTER_ID> <ELB_ID> <SWR_NAMESPACE> \
#             <KUBECONFIG_PATH> <CHART_PATH> <HELM_RELEASE>
#
#   Example:
#     migrate.sh la-north-2 4a82d04e-... 3577ef45-... cce-migrated \
#               ~/.kube/config-cce-migrated ./helm/nginx-demo nginx-demo
#
# PREREQUISITES:
#   - hcloud (KooCLI) authenticated for the target region
#   - kubectl, helm, docker installed
#   - CCE cluster created and API server accessible (EIP bound)
#   - ELB created with L4+L7 flavors and public IP
#   - Application images already pushed to SWR
#
# STEPS:
#   1. Verify CCE cluster connectivity
#   2. Login to SWR registry
#   3. Create SWR namespace (if not exists)
#   4. Create imagePullSecret for private SWR namespace
#   5. Install NGINX Ingress Controller via Helm with SWR images + ELB annotation
#   6. Deploy the application with CCE-specific values
#   7. Validate: pods, ingress, HPA
# ============================================================================
set -euo pipefail

REGION="${1:?Usage: migrate.sh <REGION> <CLUSTER_ID> <ELB_ID> <SWR_NAMESPACE> <KUBECONFIG_PATH> <CHART_PATH> <HELM_RELEASE>}"
CLUSTER_ID="${2:?}"
ELB_ID="${3:?}"
SWR_NAMESPACE="${4:?}"
KUBECONFIG_PATH="${5:?}"
CHART_PATH="${6:?}"
HELM_RELEASE="${7:?}"

export KUBECONFIG="$KUBECONFIG_PATH"

echo "=== Step 1: Verify CCE cluster ==="
kubectl get nodes

echo "=== Step 2: Login to SWR ==="
SWR_AUTH=$(hcloud SWR CreateAuthorizationToken --cli-region="$REGION" 2>/dev/null | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['auths']['swr.${REGION}.myhuaweicloud.com']['auth'])")
DECODED=$(echo "$SWR_AUTH" | base64 -d)
SWR_USER=$(echo "$DECODED" | cut -d: -f1)
SWR_PASS=$(echo "$DECODED" | cut -d: -f2)
echo "$SWR_PASS" | docker login "swr.${REGION}.myhuaweicloud.com" -u "$SWR_USER" --password-stdin

echo "=== Step 3: Create SWR namespace ==="
hcloud SWR CreateNamespace --cli-region="$REGION" --namespace="$SWR_NAMESPACE" 2>/dev/null || true

echo "=== Step 4: Create imagePullSecret ==="
kubectl create secret docker-registry swr-secret \
  --docker-server="swr.${REGION}.myhuaweicloud.com" \
  --docker-username="$SWR_USER" \
  --docker-password="$SWR_PASS" \
  -n default 2>/dev/null || true
kubectl patch serviceaccount default -n default \
  -p '{"imagePullSecrets":[{"name":"swr-secret"}]}' 2>/dev/null || true

echo "=== Step 5: Install Ingress Controller ==="
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx 2>/dev/null || true
helm repo update

INGRESS_VALUES=$(mktemp)
sed "s/REPLACE_WITH_ELB_ID/$ELB_ID/" "$SCRIPT_DIR/../templates/ingress-values-cce.yaml" > "$INGRESS_VALUES"

INGRESS_TAG=$(hcloud CCE ListAddonTemplates --cli-region="$REGION" --addon_template_name=nginx-ingress 2>/dev/null | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data.get('items', []):
    for v in item['spec']['versions']:
        tag = v.get('input', {}).get('basic', {}).get('tag', '')
        if tag:
            print(tag)
            sys.exit(0)
print('v1.14.3_6.0.2')
")

helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  -f "$INGRESS_VALUES" \
  --set controller.image.registry="swr.${REGION}.myhuaweicloud.com" \
  --set controller.image.image=hwofficial/nginx-ingress \
  --set controller.image.tag="$INGRESS_TAG" \
  --set controller.image.digest="" \
  --timeout 5m

echo "=== Step 6: Deploy application ==="
VALUES_CCE=$(mktemp)
sed -e "s/REGION/$REGION/g" -e "s/SWR_NAMESPACE/$SWR_NAMESPACE/g" \
  "$SCRIPT_DIR/../templates/values-cce.yaml" > "$VALUES_CCE"

helm upgrade --install "$HELM_RELEASE" "$CHART_PATH" \
  -f "$VALUES_CCE" --timeout 5m

echo "=== Step 7: Validate ==="
kubectl get pods -l "app.kubernetes.io/name=${HELM_RELEASE}"
kubectl get ingress
kubectl get hpa

echo ""
echo "Migration complete. Test with:"
echo "  curl -H 'Host: <HOSTNAME>' http://<ELB_PUBLIC_IP>/"
