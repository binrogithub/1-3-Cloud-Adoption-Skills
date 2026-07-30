---
name: huaweicloud-velero-cce-migration-planner
description: Migrate Huawei Cloud CCE (Cloud Container Engine) workloads between clusters (including different regions) using Velero backup and restore. Covers source environment deployment, SWR image management, Velero installation, backup creation, destination environment setup, restore execution, and post-migration SWR reconfiguration for cross-region migrations.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: cce-migration-velero
---

# Huawei Cloud CCE Migrator with Velero

Migrate CCE workloads across clusters (including different regions) using Velero. Always verify connectivity at every step. Never skip verification. Ask the user for missing values (AK/SK, bucket name, region, namespaces, SWR credentials) before executing commands.

## Rules

1. **ALWAYS verify before proceeding** — after every major step (kubectl connect, velero install, backup, restore), run the corresponding verification command. Do not assume success.
2. **NEVER hardcode secrets** — ask the user for AK/SK and SWR credentials. Use placeholder prompts like `YOUR_AK_HERE` / `YOUR_SK_HERE` only in templates the user will fill.
3. **NEVER skip the OBS connection check** — if `backupstoragelocation` is not available, Velero backups will silently fail.
4. **Ask for required values upfront** — region, OBS bucket name, AK/SK, namespaces to include, source and destination cluster kubeconfigs, SWR credentials. Batch related questions.
5. **Verify both clusters** — the source AND destination CCE must be reachable from the local terminal before starting migration.
6. **Recommend sensible defaults** — namespace `default`, uploader-type `restic`, `use-volume-snapshots=false` (OBS doesn't support CSI snapshots natively in all regions). Explain when deviating.
7. **Order matters** — source configuration → Velero install → backup → destination configuration → Velero install → restore → post-migration SWR fix. Never restore before a successful backup is verified.
8. **Warn about PVCs** — if workloads use PersistentVolumeClaims, ensure `use-node-agent` and `uploader-type=restic` are set. File-level backup is required for PVC data.
9. **Use Huawei MCP for deployments** — when deploying workloads (PVC, Deployment, Service, etc.) on CCE, whether in the source or destination environment, always use the Huawei MCP tools available in opencode.
10. **Kubeconfig switching** — always use `~/.kube/config` for the source cluster and `~/.kube/config-destination` for the destination cluster. Switch between them using `export KUBECONFIG=~/.kube/config` (source) or `export KUBECONFIG=~/.kube/config-destination` (destination).
11. **Cross-region SWR migration** — when migrating between different regions, the container image will NOT be available in the destination region's SWR. You MUST push the image to the destination SWR and update the deployment to reference it, otherwise pods will be in `ImagePullBackOff` state.
12. **SWR secret for CCE** — CCE needs a `swr-secret` to pull images from SWR. Create it in every cluster/namespace where the workload is deployed: `kubectl create secret docker-registry swr-secret --from-file ~/.docker/config.json`.
13. **docker login to SWR** — exists several ways to have a docker login, also you can use long term command `docker login -u <REGION>@HPUAZVPIR0EU2FNQ0MG9 -p f652a5f188b7831c3500ce170a071e8b5150ad1767a91b89832c307e75cef8fa swr.<REGION>.myhuaweicloud.com` to login, or ask the user for the long term login command.
14. **EIPs are required for Velero on CCE** — CCE nodes without EIPs cannot pull Velero images from Docker Hub (the internal registry mirror at `100.125.x.x:20202` times out for public images). Always verify and assign EIPs to destination nodes before running `velero install`. This also means nodes with EIPs CAN pull from cross-region SWR, so `ImagePullBackOff` after restore is not guaranteed — but reconfiguring to the destination SWR (Step 7) is still required for long-term reliability.
15. **Recreate swr-secret after restore** — the `swr-secret` restored by Velero may contain stale or incorrect credentials for the destination SWR (different AK/SK). Always delete and recreate it from `~/.docker/config.json` which has valid credentials for both regions.

## Workflow

### Step 1: PARSE INTENT

Extract from the user's request:

- **Source cluster** — kubeconfig path or CCE details (cluster ID, region, EIP)
- **Destination cluster** — kubeconfig path or CCE details
- **Source Region** — required for OBS endpoint and SWR registry (e.g. `la-north-2`)
- **Destination Region** — required for cross-region migration (destination SWR registry URL)
- **OBS bucket** — for Velero backups (e.g. `velero-cce-84448406`)
- **AK/SK** — credentials with OBS access
- **Namespaces to migrate** — default: `default`
- **Workload details** — deployment names, PVC names, container images (if known)
- **SWR details** — organization, image name/tag (if container images need migration)
- **Deploy in source?** — whether the user needs the workload deployed in the source environment first

**Gaps** — any required value the user did NOT specify. Ask for these.

Example: `"Deploy openwebui in the source region, and migrate my open-webui deployment from CCE cluster in la-north-2 to cluster B in na-mexico-1"` →

- Source region: la-north-2 → **already given**
- Destination region: na-mexico-1 → **already given**
- Source/Destination clusters: not specified → **ask**
- OBS bucket: not specified → **ask** (recommend `velero-cce-<project-id>`)
- AK/SK: not specified → **ask**
- SWR credentials: not specified → **ask**
- Namespace: not specified → **use default, confirm**
- Deploy in source: yes → **proceed with deployment steps**

**Step 1.1: Reset proxy (Execute this in order to clean proxies, sometimes proxies generates error in this exercise)**
```bash
unset HTTP_PROXY
unset HTTPS_PROXY
unset http_proxy
unset https_proxy
```

### Step 2: CONFIGURE SOURCE ENVIRONMENT

Connect the local terminal to the **source** CCE cluster.

**2.1 Download and configure source kubeconfig:**

```bash
# From the source CCE overview page, download kubeconfig.json
mkdir -p ~/.kube
mv ~/Downloads/kubeconfig.json ~/.kube/config
```

**2.2 Verify connectivity:**

```bash
kubectl get nodes
```

If this fails, the cluster is unreachable. Ask the user to verify the EIP and kubeconfig.

**2.3 Initialize environment variables:**

```bash
set -e
REGION="la-north-2"  # Source region
SWR_ORG="organization84448406"
SWR_REGISTRY="swr.${REGION}.myhuaweicloud.com"
IMAGE_NAME="open-webui"
IMAGE_TAG="v1.0.0"
FULL_IMAGE="${SWR_REGISTRY}/${SWR_ORG}/${IMAGE_NAME}:${IMAGE_TAG}"
PVC_NAME="open-webui-data-pvc"
DEPLOYMENT_NAME="open-webui"
NAMESPACE="default"
export BUILDX_NO_DEFAULT_ATTESTATIONS=1
```

> **Note:** Adapt these variables to the actual workload. The above is an example for open-webui [1].

**2.4 Build container image if needed (for workloads requiring PVC):**

```bash
cat <<DOCKERFILE_EOF > Dockerfile
FROM ghcr.io/open-webui/open-webui:latest
ENV DATA_DIR=/app/backend/data
DOCKERFILE_EOF

docker build --platform linux/amd64 -t ${IMAGE_NAME}:${IMAGE_TAG} .
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE}
```

**2.5 Connect Docker to source SWR and push the image:**

```bash
# Login to source region SWR (replace with actual credentials)
docker login -u ${REGION}@XXXXXXXXXX -p xxxxxxxxxxxxxxxxxx swr.${REGION}.myhuaweicloud.com

# Push the image to source SWR
docker push ${FULL_IMAGE}
```

> **Important:** Ask the user for their SWR login credentials (IAM user ID and token). The format is `docker login -u <region>@<IAM_user_ID> -p <token> swr.<region>.myhuaweicloud.com` [1].

**2.6 Create swr-secret in the source cluster:**

CCE needs an image pull secret to authenticate with SWR:

```bash
kubectl create secret docker-registry swr-secret --from-file ~/.docker/config.json
```

> **Note:** This uses the Docker config generated by `docker login`. The secret must be created in the same namespace as the deployment [1].

**2.7 Deploy workload on source CCE (if required by the user):**

Use **Huawei MCP** tools to deploy the workload. This includes creating PVCs and Deployments that reference the SWR image.

Example PVC creation:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ${PVC_NAME}
  namespace: ${NAMESPACE}
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 10Gi
  storageClassName: csi-disk
EOF
```

Example Deployment creation:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${DEPLOYMENT_NAME}
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${DEPLOYMENT_NAME}
  template:
    metadata:
      labels:
        app: ${DEPLOYMENT_NAME}
    spec:
      imagePullSecrets:
        - name: swr-secret
      containers:
        - name: ${DEPLOYMENT_NAME}
          image: ${FULL_IMAGE}
          volumeMounts:
            - name: data
              mountPath: /app/backend/data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: ${PVC_NAME}
EOF
```

> **Important:** Always use **Huawei MCP** for deploying resources on CCE. The Deployment must reference `swr-secret` in `imagePullSecrets` and use the full SWR image path (`swr.<region>.myhuaweicloud.com/org/image:tag`) [1].

**2.8 Verify deployment on source:**

```bash
kubectl get pods -n ${NAMESPACE}
kubectl get pvc -n ${NAMESPACE}
```

Ensure pods are in `Running` state before proceeding.

### Step 3: INSTALL VELERO ON SOURCE

**3.1 Verify Velero CLI is available:**

```bash
velero version
```

**3.2 Create credentials file:**

Ask the user for AK/SK, then:

```bash
cat <<EOF > credentials-velero
[default]
aws_access_key_id=YOUR_AK_HERE
aws_secret_access_key=YOUR_SK_HERE
EOF
```

**3.3 Install Velero on the source cluster (use source region):**

```bash
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.7.1 \
  --bucket <OBS_BUCKET_NAME> \
  --secret-file ./credentials-velero \
  --use-node-agent \
  --uploader-type=restic \
  --use-volume-snapshots=false \
  --backup-location-config region=<REGION>,s3ForcePathStyle=false,s3Url=https://obs.<REGION>.myhuaweicloud.com
```

> **Important:** Replace `<OBS_BUCKET_NAME>` and `<REGION>` with actual values. `use-volume-snapshots=false` is recommended because OBS does not natively support CSI volume snapshots in all regions. `use-node-agent` + `uploader-type=restic` enables file-level PVC backup [1].

**3.4 Verify Velero installation:**

```bash
# Check Velero pods are running
kubectl get pods -n velero

# Check VolumeSnapshotClass (should be empty or N/A if use-volume-snapshots=false)
kubectl get volumesnapshotclass

# Verify OBS BackupStorageLocation is available
kubectl get backupstoragelocation default -n velero -o yaml
```

The `backupstoragelocation` must show `phase: Available`. If not, check AK/SK permissions and OBS bucket existence [1].

### Step 4: CREATE BACKUP ON SOURCE

**4.1 Execute backup:**

```bash
velero backup create <BACKUP_NAME> --include-namespaces <NAMESPACE> --wait
```

Example:
```bash
velero backup create openwebui-backup --include-namespaces default --wait
```

**4.2 Verify backup:**

```bash
velero backup get
```

Confirm the backup shows `STATUS: Completed`. If it shows `Failed` or `InProgress`, investigate with:

```bash
velero backup describe <BACKUP_NAME> --details
```

Do NOT proceed to restore until backup status is `Completed`.

### Step 5: CONFIGURE DESTINATION ENVIRONMENT

**5.1 Deploy equivalent infrastructure:**

The destination must have matching resources:
- CCE cluster (same or compatible Kubernetes version)
- ECS (if used by workloads)
- EIP (if workloads require public access, by default use an EIP for the CCE)
- Security groups (matching rules, in case of need, create an inbound rule for port 22 or the realted port for the workload)
- OBS bucket (same bucket or accessible from destination, when migrating with velero, use the same bucket for backup and restore)

Use **Huawei MCP** to create any required infrastructure in the destination region.

**5.2 Switch kubeconfig to destination cluster:**

```bash
# Download kubeconfig from destination CCE overview
mv ~/Downloads/kubeconfig-destination.json ~/.kube/config-destination
export KUBECONFIG=~/.kube/config-destination

# Verify connectivity
kubectl get nodes
```

> **Important:** Always use `config-destination` for the destination cluster. Switch back to `config` for source operations if needed: `export KUBECONFIG=~/.kube/config` [1].

**5.3 Ensure destination nodes have internet access (EIPs):**

CCE nodes without EIPs cannot pull images from Docker Hub or cross-region SWR. The internal CCE registry mirror (`100.125.x.x:20202`) times out for public images like `velero/velero:v1.13.0`. Before installing Velero, verify nodes have EIPs and assign them if missing.

```bash
# Check if nodes have EIPs (via Huawei Cloud MCP or CLI)
hcloud ECS ListServersDetails --cli-region=<DEST_REGION>
```

If nodes lack EIPs, create and bind them:

```bash
# Create EIP
hcloud EIP CreatePublicip --cli-region=<DEST_REGION> \
  --bandwidth.share_type=PER --bandwidth.charge_mode=traffic \
  --bandwidth.size=8 --publicip.type=5_bgp

# Get the port ID for each node (needed to bind the EIP)
hcloud ECS ListServerInterfaces --cli-region=<DEST_REGION> --server_id=<SERVER_ID>

# Bind EIP to node
hcloud EIP UpdatePublicip --cli-region=<DEST_REGION> \
  --publicip_id=<EIP_ID> --publicip.port_id=<NODE_PORT_ID>
```

> **⚠️ WARNING:** Without EIPs, `velero install` will create pods that enter `ImagePullBackOff` because the internal CCE registry mirror cannot resolve public Docker Hub images. You MUST assign EIPs to all worker nodes before installing Velero.

**5.4 Install Velero on destination cluster:**

Use the **same** Velero install command as Step 3.3, pointing to the **same OBS bucket, source region** so it can read the backup:

```bash
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.7.1 \
  --bucket <OBS_BUCKET_NAME> \
  --secret-file ./credentials-velero \
  --use-node-agent \
  --uploader-type=restic \
  --use-volume-snapshots=false \
  --backup-location-config region=<REGION>,s3ForcePathStyle=false,s3Url=https://obs.<REGION>.myhuaweicloud.com
```

> **If Velero pods enter ImagePullBackOff:** This means nodes still lack internet access.
> 1. Uninstall the failed installation: `velero uninstall --force`
> 2. Assign EIPs to nodes (see Step 5.3)
> 3. Re-run `velero install`

**5.5 Verify destination Velero:**

```bash
kubectl get pods -n velero
kubectl get backupstoragelocation default -n velero -o yaml
velero backup get
```

The backup from the source cluster must be visible here (stored in OBS). If not, verify the bucket and credentials match.

### Step 6: RESTORE ON DESTINATION

**6.1 Execute restore:**

```bash
velero restore create <RESTORE_NAME> --from-backup <BACKUP_NAME> --wait
```

Example:
```bash
velero restore create openwebui-restore --from-backup openwebui-backup --wait
```

**6.2 Verify restore:**

```bash
velero restore get
kubectl get deployments -n <NAMESPACE>
kubectl get pods -n <NAMESPACE>
kubectl get pvc -n <NAMESPACE>
```

> **⚠️ NOTE:** After restore, pod image pull behavior depends on node internet access:
> - **Nodes WITH EIPs:** Pods may successfully pull from the source region's SWR (cross-region access works with EIPs). However, this creates a fragile cross-region dependency — proceed to Step 7 to reconfigure for the destination SWR for long-term reliability.
> - **Nodes WITHOUT EIPs:** Pods will be in `ImagePullBackOff` because the destination CCE cannot reach the source region's SWR. Step 7 is mandatory.

### Step 7: POST-MIGRATION — RECONFIGURE SWR FOR DESTINATION REGION

This step is **CRITICAL** for cross-region migrations. After Velero restore, the deployment still references the source region's SWR image. Even if pods are Running (nodes with EIPs can pull cross-region), this creates a fragile dependency on the source region's SWR. You must point the destination CCE to the destination region's SWR for long-term reliability [1].

**7.1 Check pod status after restore:**

```bash
# Ensure KUBECONFIG points to destination
export KUBECONFIG=~/.kube/config-destination
kubectl get pods -n <NAMESPACE>
```

If pods show `ImagePullBackOff`, the destination CCE cannot reach the source SWR — proceed with the following steps to fix. If pods are `Running`, they are pulling from the source region's SWR via EIPs — still proceed to reconfigure for the destination SWR to eliminate the cross-region dependency.

**7.2 Set destination region environment variables:**

```bash
DEST_REGION="na-mexico-1"  # Destination region
DEST_SWR_REGISTRY="swr.${DEST_REGION}.myhuaweicloud.com"
DEST_FULL_IMAGE="${DEST_SWR_REGISTRY}/${SWR_ORG}/${IMAGE_NAME}:${IMAGE_TAG}"
```

**7.3 Login to destination SWR and push the image:**

```bash
# Login to destination region SWR (ask user for credentials if different from source)
docker login -u ${DEST_REGION}@XXXXXXXXXX -p xxxxxxxxxxxxxxxxxx swr.${DEST_REGION}.myhuaweicloud.com

# Tag the image for destination SWR
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${DEST_FULL_IMAGE}

# Push the image to destination SWR
docker push ${DEST_FULL_IMAGE}
```

> **Important:** The image must exist in the destination region's SWR for CCE to pull it. Ask the user for destination SWR credentials if different from source [1].

**7.4 Recreate swr-secret in the destination cluster:**

> **⚠️ IMPORTANT:** Do NOT rely on the `swr-secret` restored by Velero. The restored secret may contain stale or incorrect credentials for the destination SWR (e.g., a different AK/SK), causing `401 Unauthorized` errors when pulling images. Always delete and recreate it from the current Docker config which has valid credentials for both regions.

```bash
# Ensure KUBECONFIG points to destination
export KUBECONFIG=~/.kube/config-destination

# Delete the restored (potentially stale) secret
kubectl delete secret swr-secret -n <NAMESPACE> --ignore-not-found

# Recreate from current Docker config (has valid credentials for both regions)
kubectl create secret docker-registry swr-secret \
  --from-file /.docker/config.json -n <NAMESPACE>
```

**7.5 Update the deployment to reference the destination SWR image:**

```bash
kubectl set image deployment/${DEPLOYMENT_NAME} ${DEPLOYMENT_NAME}=${DEST_FULL_IMAGE} -n <NAMESPACE>
```

This changes the image reference from the source SWR (e.g. `swr.la-north-2.myhuaweicloud.com/org/open-webui:v1.0.0`) to the destination SWR (e.g. `swr.na-mexico-1.myhuaweicloud.com/org/open-webui:v1.0.0`), pointing the destination CCE to the correct SWR [1].

**7.6 Verify pods recover from ImagePullBackOff:**

```bash
kubectl get pods -n <NAMESPACE>
```

Pods should transition from `ImagePullBackOff` → `Pulling` → `Running`. If they remain in `ImagePullBackOff`, verify:
- The image exists in destination SWR: check `docker push` output
- The `swr-secret` exists in the namespace: `kubectl get secret swr-secret -n <NAMESPACE>`
- The deployment references `swr-secret` in `imagePullSecrets`

**7.7 Final validation:**

```bash
kubectl get pods -n <NAMESPACE>
kubectl get pvc -n <NAMESPACE>
kubectl get deployment ${DEPLOYMENT_NAME} -n <NAMESPACE>
kubectl get svc -n <NAMESPACE>
```

All pods should be `Running`, PVCs `Bound`, and the deployment image should reference the destination SWR.

**7.8 (Optional) Remove EIPs from destination nodes:**

After migration is complete and images are cached on the nodes, you can unbind EIPs from nodes to reduce costs:

```bash
# Unbind EIP from a node (set port_id to empty)
hcloud EIP UpdatePublicip --cli-region=<DEST_REGION> \
  --publicip_id=<EIP_ID> --publicip.port_id=""
```

> **⚠️ WARNING:** Only remove EIPs if no workloads on the node require internet access. Future pod scheduling or image pulls of new tags will fail without EIPs. Consider whether the workload needs ongoing internet access before removing EIPs.