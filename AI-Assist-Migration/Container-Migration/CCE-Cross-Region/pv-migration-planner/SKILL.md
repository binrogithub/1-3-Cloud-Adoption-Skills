---
name: pv-migration-planner
description: Migrate PersistentVolumeClaim (PVC) data between Huawei Cloud CCE clusters using obsutil as the data transfer mechanism via OBS bucket as intermediary storage. Use when Velero's file-level backup (restic/kopia) fails due to Huawei Cloud OBS S3 API incompatibility (virtual-hosted-style requirement). Covers helper pod deployment, obsutil installation, data upload/download, symlink preservation, permission fixup, and post-migration validation.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: cce-pvc-migration-obsutil
---

# PVC Data Migration via obsutil

Migrate PVC data between Huawei Cloud CCE clusters (same-region or cross-region) using **obsutil** inside helper pods, with an OBS bucket as intermediary storage. This is the recommended fallback when Velero's file-level backup (restic/kopia) cannot complete due to Huawei Cloud OBS requiring virtual-hosted-style S3 access — which restic and kopia do not support.

## When to Use This Skill

- Velero backup completes as **PartiallyFailed** with error: `Virtual host domain is required while accessing a specific bucket.`
- The BackupRepository CR shows `phase: NotReady` with the same virtual-hosted-style error
- You need to migrate PVC data (databases, model caches, user uploads, etc.) between CCE clusters
- Both same-region and cross-region migrations are supported

## Why Velero File-Level Backup Fails on Huawei Cloud OBS

Huawei Cloud OBS's S3-compatible API **only supports virtual-hosted-style** access:

```
# Virtual-hosted-style (OBS accepts this):
https://<bucket>.obs.<region>.myhuaweicloud.com/<key>

# Path-style (OBS rejects this):
https://obs.<region>.myhuaweicloud.com/<bucket>/<key>
```

Velero's `s3ForcePathStyle=false` setting works for **metadata operations** (the AWS SDK respects it), but **not** for the restic/kopia file-level backup client inside the node-agent DaemonSet. Both restic (minio-go) and kopia construct S3 URLs in path-style, which OBS rejects. There is no environment variable or configuration to force virtual-hosted-style in these clients for non-AWS endpoints.

**obsutil** uses the Huawei Cloud OBS SDK directly, which always uses virtual-hosted-style correctly — making it the reliable alternative for PVC data transfer.

## Rules

1. **ALWAYS use a glibc-based helper image** — obsutil is a dynamically-linked binary requiring `/lib64/ld-linux-x86-64.so.2`. Alpine (musl libc) cannot run it. Use `ubuntu:22.04` or any glibc-based image as the helper pod base.
2. **ALWAYS use `-f` (force mode)** — obsutil prompts for confirmation on every file/folder. Without `-f`, `kubectl exec` fails with `EOF` because there is no interactive terminal.
3. **ALWAYS fix file permissions after download** — obsutil creates files with `640` (`rw-r-----`) permissions. If the application container runs as a non-root user, it cannot read the files. Run `chmod -R a+rX` on the data directory after download.
4. **ALWAYS check for symlinks** — obsutil does **not** preserve symlinks. It converts them to small regular files containing partial content. Any symlink-based directory structure (HuggingFace model cache, Python virtual environments, Node.js `node_modules/.bin`, etc.) will be broken after copy and must be reconstructed.
5. **ALWAYS use the source-region OBS endpoint** — the OBS bucket lives in the source region. The destination helper pod accesses it via EIP (internet). Use `obs.<source-region>.myhuaweicloud.com` as the endpoint for both source and destination obsutil configurations.
6. **Verify EIPs on destination nodes** — destination CCE nodes need EIPs to reach the source-region OBS bucket over the internet. If nodes lack EIPs, bind them before starting.
7. **Do not scale down the destination deployment** — it is not necessary. The app writes to a fresh DB; overwriting files during copy causes at most a brief inconsistency. Restart the pod after copy so it picks up the restored data.
8. **Clean up helper pods** — delete helper pods on both clusters after migration to free resources.
9. **Validate data integrity** — after migration, verify file count, sizes, and application HTTP response. Compare source and destination PVC contents.

## Prerequisites

Before starting, ensure the following are available:

| Prerequisite | Description |
|---|---|
| Source cluster kubeconfig | `~/.kube/config` pointing to the source CCE cluster |
| Destination cluster kubeconfig | `~/.kube/config-destination` pointing to the destination CCE cluster |
| OBS bucket | Existing bucket in the source region for data transfer (can reuse Velero's bucket with a different prefix) |
| AK/SK | Huawei Cloud credentials with OBS read/write access to the bucket |
| Source region | e.g. `la-north-2` — used for OBS endpoint |
| PVC name | The name of the PersistentVolumeClaim in both clusters (must exist on destination before download) |
| PVC mount path | The path where the PVC is mounted inside the application container (e.g. `/app/backend/data`) |
| Namespace | The namespace where the workload and PVC exist (default: `default`) |
| Destination nodes with EIPs | Required for internet access to source-region OBS |

## Workflow

### Step 1: Deploy Helper Pod on Source Cluster

Create a pod that mounts the source PVC and stays alive for obsutil operations.

```bash
export KUBECONFIG=~/.kube/config
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: obsutil-helper
  namespace: <NAMESPACE>
spec:
  containers:
  - name: obsutil
    image: ubuntu:22.04
    command: ["sleep", "3600"]
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: <PVC_NAME>
EOF

kubectl wait --for=condition=Ready pod/obsutil-helper -n <NAMESPACE> --timeout=180s
```

> **Why ubuntu:22.04?** obsutil requires glibc (`/lib64/ld-linux-x86-64.so.2`). Alpine uses musl libc and cannot execute the binary.

### Step 2: Install obsutil Inside Source Helper Pod

```bash
kubectl exec -n <NAMESPACE> obsutil-helper -- sh -c "
  apt-get update -qq && apt-get install -y -qq wget &&
  wget -q https://obs-community.obs.cn-north-1.myhuaweicloud.com/obsutil/current/obsutil_linux_amd64.tar.gz -O /tmp/obsutil.tar.gz &&
  tar -xzf /tmp/obsutil.tar.gz -C /tmp/ &&
  chmod +x /tmp/obsutil_linux_amd64_5.*/obsutil &&
  /tmp/obsutil_linux_amd64_5.*/obsutil version
"
```

> The obsutil version directory may change. Use `5.*` glob to match whatever version is current.

### Step 3: Configure obsutil and Upload PVC Data to OBS

```bash
# Configure credentials
kubectl exec -n <NAMESPACE> obsutil-helper -- /tmp/obsutil_linux_amd64_5.*/obsutil config \
  -i=<AK> \
  -k=<SK> \
  -e=obs.<SOURCE_REGION>.myhuaweicloud.com

# Upload PVC data to OBS bucket
kubectl exec -n <NAMESPACE> obsutil-helper -- /tmp/obsutil_linux_amd64_5.*/obsutil cp \
  /data/ obs://<OBS_BUCKET>/<OBS_PREFIX>/ -flat -r -f -j=5
```

| Flag | Purpose |
|------|---------|
| `-flat` | Flatten directory structure in OBS object keys (preserves relative paths) |
| `-r` | Recursive — upload all files and subdirectories |
| `-f` | Force mode — skip confirmation prompts (required for non-interactive `kubectl exec`) |
| `-j=5` | 5 parallel jobs for faster upload |

> **OBS_PREFIX**: Use a unique prefix (e.g. `pvc-data-migration/<namespace>/<pvc-name>/`) to avoid collisions with other data in the bucket.

### Step 4: Deploy Helper Pod on Destination Cluster

Same pod spec, pointing to the destination cluster's kubeconfig:

```bash
export KUBECONFIG=~/.kube/config-destination
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: obsutil-helper
  namespace: <NAMESPACE>
spec:
  containers:
  - name: obsutil
    image: ubuntu:22.04
    command: ["sleep", "3600"]
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: <PVC_NAME>
EOF

kubectl wait --for=condition=Ready pod/obsutil-helper -n <NAMESPACE> --timeout=180s
```

> The destination PVC must already exist (created by Velero restore or manually). It can be empty or contain files from a fresh app startup — the download will overwrite/add files.

### Step 5: Install obsutil Inside Destination Helper Pod

Same as Step 2, but against the destination cluster.

### Step 6: Configure obsutil and Download from OBS to Destination PVC

```bash
# Configure credentials — use SOURCE region endpoint (bucket lives there)
kubectl exec -n <NAMESPACE> obsutil-helper -- /tmp/obsutil_linux_amd64_5.*/obsutil config \
  -i=<AK> \
  -k=<SK> \
  -e=obs.<SOURCE_REGION>.myhuaweicloud.com

# Download data from OBS to PVC
kubectl exec -n <NAMESPACE> obsutil-helper -- /tmp/obsutil_linux_amd64_5.*/obsutil cp \
  obs://<OBS_BUCKET>/<OBS_PREFIX>/ /data/ -flat -r -f -j=5
```

> The OBS endpoint is always the **source region** because the bucket resides there. The destination pod reaches it via EIP.

### Step 7: Fix File Permissions

obsutil creates files with restrictive permissions (`640`). Fix them so the application can read the data:

```bash
kubectl exec -n <NAMESPACE> obsutil-helper -- chmod -R a+rX /data/
```

- `a+rX` = add read permission for all users, and execute permission for all users **only if** the file is a directory or already has execute for some user.

### Step 8: Reconstruct Broken Symlinks

obsutil converts symlinks to small regular files. If the PVC contains symlink-based structures, they must be reconstructed.

**How to detect broken symlinks:**

1. On the source cluster, list all symlinks with their targets:
   ```bash
   kubectl exec -n <NAMESPACE> deploy/<APP_DEPLOYMENT> -- \
     find <MOUNT_PATH> -type l -printf "%p -> %l\n"
   ```

2. On the destination, check for suspiciously small files in the same locations (these are the broken symlink replacements).

3. For each symlink, delete the broken file and recreate the symlink:
   ```bash
   kubectl exec -n <NAMESPACE> obsutil-helper -- sh -c '
     rm -f <BROKEN_FILE_PATH> && ln -s <TARGET_RELATIVE_PATH> <BROKEN_FILE_PATH>
   '
   ```

**Common symlink scenarios:**

| Scenario | Description | Fix |
|----------|-------------|-----|
| HuggingFace model cache | `snapshots/<hash>/` files are symlinks to `../../blobs/<hash>` | Delete small files in snapshots, recreate symlinks pointing to `../../blobs/<hash>` or `../../../blobs/<hash>` depending on depth |
| Python virtual environments | `lib/python3.x/site-packages/` contains symlinks | Recreate venv from scratch on destination, or use `pip install` instead of copying |
| Node.js `node_modules/.bin/` | Symlinks to `../<package>/bin.js` | Run `npm install` on destination instead of copying `node_modules` |

### Step 9: Restart Application Pod

Restart the destination pod so it picks up the restored data:

```bash
export KUBECONFIG=~/.kube/config-destination
kubectl delete pod -n <NAMESPACE> -l app=<APP_LABEL>
kubectl wait --for=condition=Ready pod -l app=<APP_LABEL> -n <NAMESPACE> --timeout=180s
```

### Step 10: Validate Data Integrity

```bash
# Check file listing and sizes
kubectl exec -n <NAMESPACE> deploy/<APP_DEPLOYMENT> -- ls -la <MOUNT_PATH>/

# Check specific critical files (compare sizes with source)
kubectl exec -n <NAMESPACE> deploy/<APP_DEPLOYMENT> -- du -sh <MOUNT_PATH>/

# Check application HTTP response (if applicable)
curl -s -o /dev/null -w "HTTP %{http_code}" http://<EIP>:<NODE_PORT>/
```

### Step 11: Clean Up

```bash
# Delete helper pods
export KUBECONFIG=~/.kube/config
kubectl delete pod obsutil-helper -n <NAMESPACE>

export KUBECONFIG=~/.kube/config-destination
kubectl delete pod obsutil-helper -n <NAMESPACE>

# (Optional) Delete transferred data from OBS to reduce storage costs
# Use obsutil locally or via a helper pod:
# obsutil rm obs://<OBS_BUCKET>/<OBS_PREFIX>/ -r -f
```

## Combined Migration Strategy: Velero + obsutil

For a complete CCE migration with PVC data, use a **two-phase approach**:

| Phase | Tool | What it handles |
|-------|------|-----------------|
| **Phase 1: Metadata** | Velero | Deployment, Service, PVC, PV, ConfigMap, Secret, Ingress YAMLs |
| **Phase 2: Data** | obsutil (this skill) | File-level PVC data (databases, caches, uploads) |

**Phase 1 — Velero (metadata only):**

```bash
# Source: backup without file-level PVC data
velero backup create <BACKUP_NAME> --include-namespaces <NAMESPACE> --wait

# Destination: restore creates PVC/PV/Deployment/Service but disk is empty
velero restore create <RESTORE_NAME> --from-backup <BACKUP_NAME> --wait
```

> Do NOT annotate the deployment with `backup.velero.io/backup-volumes` — this would trigger the broken restic/kopia file-level backup. Let Velero handle only metadata.

**Phase 2 — obsutil (PVC data):**

Follow Steps 1–11 of this skill's workflow to transfer the actual file data from source PVC to destination PVC.

**Post-migration (if cross-region):**

- Reconfigure SWR: push image to destination region's SWR, update deployment image reference
- Recreate `swr-secret` with valid credentials for destination SWR
- Verify pods are `Running` with the new image

## Troubleshooting

### obsutil binary fails with "no such file or directory" on Alpine

**Cause:** obsutil is dynamically linked against glibc (`/lib64/ld-linux-x86-64.so.2`). Alpine uses musl libc.

**Fix:** Use `ubuntu:22.04` (or any glibc-based image) as the helper pod base image instead of `alpine`.

### obsutil prompts for confirmation and fails with "EOF"

**Cause:** obsutil asks `Do you want upload file [...] ? Please input (y/n) to confirm:` for each file. `kubectl exec` has no interactive terminal.

**Fix:** Add the `-f` flag to the `obsutil cp` command:
```bash
obsutil cp /data/ obs://bucket/prefix/ -flat -r -f -j=5
```

### Application crashes after data copy with "No embedding model loaded" or similar

**Cause:** obsutil converts symlinks to small regular files. HuggingFace model cache (and similar symlink-based structures) breaks because the snapshot files no longer point to the blob files.

**Fix:** Reconstruct symlinks manually (see Step 8). Get the symlink map from the source cluster and recreate each symlink on the destination.

### Application cannot read files (Permission denied)

**Cause:** obsutil creates files with `640` (`rw-r-----`) permissions. If the app runs as a non-root user (UID 1000, etc.), it cannot read the files.

**Fix:** Run `chmod -R a+rX /data/` inside the helper pod after download.

### BackupRepository shows "NotReady" with virtual-hosted-style error

**Cause:** This is the root problem that triggers the need for this skill. Velero's restic/kopia client uses path-style S3 URLs, which Huawei Cloud OBS rejects.

**Fix:** Use this obsutil-based approach instead of Velero file-level backup for PVC data transfer.

### Slow transfer speed

**Cause:** Data goes through: source pod → source node EIP → OBS → destination node EIP → destination pod. Cross-region latency adds overhead.

**Fix:** Increase parallel jobs with `-j=10` (default is 1). For very large datasets (>10GB), consider using OBS multipart upload by increasing `-threshold` and `-ps` (part size) parameters.

## Reference: Real-World Example (open-webui Migration)

This example shows the actual commands used to migrate the `open-webui` workload from CCE in `la-north-2` to CCE in `na-mexico-1`.

### Context

| Parameter | Value |
|-----------|-------|
| Source region | `la-north-2` |
| Destination region | `na-mexico-1` |
| OBS bucket | `velero-cce-84448406` (in la-north-2) |
| OBS prefix | `pvc-data-migration/` |
| PVC name | `open-webui-data-pvc` (10Gi, csi-disk) |
| Mount path | `/app/backend/data` |
| Namespace | `default` |
| AK | `HPUAZVPIR0EU2FNQ0MG9` |
| Data size | 2.61GB (101 files) |
| App label | `app=open-webui` |
| Destination EIPs | `94.74.70.219`, `94.74.74.204` |
| NodePort | `30783` |

### Step 1: Deploy helper pod on source

```bash
export KUBECONFIG=~/.kube/config
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: obsutil-helper
  namespace: default
spec:
  containers:
  - name: obsutil
    image: ubuntu:22.04
    command: ["sleep", "3600"]
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: open-webui-data-pvc
EOF
kubectl wait --for=condition=Ready pod/obsutil-helper -n default --timeout=180s
```

### Step 2: Install obsutil on source helper

```bash
kubectl exec -n default obsutil-helper -- sh -c "
  apt-get update -qq && apt-get install -y -qq wget &&
  wget -q https://obs-community.obs.cn-north-1.myhuaweicloud.com/obsutil/current/obsutil_linux_amd64.tar.gz -O /tmp/obsutil.tar.gz &&
  tar -xzf /tmp/obsutil.tar.gz -C /tmp/ &&
  chmod +x /tmp/obsutil_linux_amd64_5.*/obsutil &&
  /tmp/obsutil_linux_amd64_5.*/obsutil version
"
# Output: obsutil version:5.8.3, obssdk version:3.24.12
```

### Step 3: Configure and upload

```bash
kubectl exec -n default obsutil-helper -- /tmp/obsutil_linux_amd64_5.8.3/obsutil config \
  -i=HPUAZVPIR0EU2FNQ0MG9 \
  -k=<SK> \
  -e=obs.la-north-2.myhuaweicloud.com

kubectl exec -n default obsutil-helper -- /tmp/obsutil_linux_amd64_5.8.3/obsutil cp \
  /data/ obs://velero-cce-84448406/pvc-data-migration/ -flat -r -f -j=5
# Result: Succeed count: 101, Failed count: 0, Succeed bytes: 2.61GB, Time: ~11s
```

### Step 4: Deploy helper pod on destination

```bash
export KUBECONFIG=~/.kube/config-cce-openwebui-lab-mexico
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: obsutil-helper
  namespace: default
spec:
  containers:
  - name: obsutil
    image: ubuntu:22.04
    command: ["sleep", "3600"]
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: open-webui-data-pvc
EOF
kubectl wait --for=condition=Ready pod/obsutil-helper -n default --timeout=180s
```

### Step 5: Install obsutil on destination helper

(Same command as Step 2, against destination kubeconfig)

### Step 6: Configure and download

```bash
kubectl exec -n default obsutil-helper -- /tmp/obsutil_linux_amd64_5.8.3/obsutil config \
  -i=HPUAZVPIR0EU2FNQ0MG9 \
  -k=<SK> \
  -e=obs.la-north-2.myhuaweicloud.com

kubectl exec -n default obsutil-helper -- /tmp/obsutil_linux_amd64_5.8.3/obsutil cp \
  obs://velero-cce-84448406/pvc-data-migration/ /data/ -flat -r -f -j=5
# Result: Succeed count: 101, Failed count: 0, Succeed bytes: 2.61GB, Time: ~11s
```

### Step 7: Fix permissions

```bash
kubectl exec -n default obsutil-helper -- chmod -R a+rX /data/
```

### Step 8: Reconstruct HuggingFace symlinks

The HuggingFace model cache at `/data/cache/embedding/models/` uses symlinks from `snapshots/<hash>/` pointing to `../../blobs/<hash>` (or `../../../blobs/<hash>` for nested subdirectories). obsutil converted these to small broken files.

**Detection on source:**
```bash
kubectl exec -n default deploy/open-webui -- \
  find /app/backend/data/cache/embedding/models -type l -printf "%p -> %l\n"
```

**Fix on destination (example for one file):**
```bash
kubectl exec -n default obsutil-helper -- sh -c '
  rm -f /data/cache/embedding/models/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243.../config.json
  ln -s ../../blobs/72b987fd805cfa2b58c4c8c952b274a11bfd5a00 \
    /data/cache/embedding/models/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243.../config.json
'
```

Repeat for all symlinks. The full list was 30 symlinks in this case.

### Step 9: Restart application

```bash
export KUBECONFIG=~/.kube/config-cce-openwebui-lab-mexico
kubectl delete pod -n default -l app=open-webui
kubectl wait --for=condition=Ready pod -l app=open-webui -n default --timeout=180s
```

### Step 10: Validate

```bash
# Data integrity
kubectl exec -n default deploy/open-webui -- ls -la /app/backend/data/
# Shows: chunk-aa through chunk-ai (100MB each), webui.db (606KB), cache/, vector_db/, uploads/

# HTTP access
curl -s -o /dev/null -w "HTTP %{http_code}" http://94.74.70.219:30783/
# HTTP 200
curl -s -o /dev/null -w "HTTP %{http_code}" http://94.74.74.204:30783/
# HTTP 200
```

### Step 11: Clean up

```bash
export KUBECONFIG=~/.kube/config
kubectl delete pod obsutil-helper -n default

export KUBECONFIG=~/.kube/config-cce-openwebui-lab-mexico
kubectl delete pod obsutil-helper -n default
```

### Total time: ~12 minutes (including pod startup, obsutil install, 2.61GB upload + download, symlink fix, app restart)

## Performance Estimates

| Data Size | Upload Time | Download Time | Total (approx) |
|-----------|-------------|---------------|-----------------|
| < 1 GB | ~5s | ~5s | ~5 min (mostly pod startup) |
| 1-5 GB | ~10-30s | ~10-30s | ~10 min |
| 5-20 GB | ~1-3 min | ~1-3 min | ~15 min |
| 20-100 GB | ~5-15 min | ~5-15 min | ~30-45 min |
| > 100 GB | 15+ min | 15+ min | Consider OBS intra-VPC endpoint for better throughput |
