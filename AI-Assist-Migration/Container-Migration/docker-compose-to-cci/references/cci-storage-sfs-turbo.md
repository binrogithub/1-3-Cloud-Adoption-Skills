# CCI Storage with SFS Turbo

## Overview

CCI supports persistent storage via **SFS Turbo** (Scalable File Service Turbo). This is the only persistent storage option in CCI — unlike CCE which supports EVS, OBS, and SFS.

## SFS Turbo Characteristics

- **Access mode**: ReadWriteMany (shared access from multiple pods)
- **Performance**: High IOPS, low latency (SSD-backed)
- **Scaling**: Auto-scaling capacity
- **Billing**: Pay-per-use (GB-hour)

## Creating a PVC in CCI

```bash
hcloud CCI createCoreV1NamespacedPersistentVolumeClaim \
  --cli-region=<region> \
  --namespace=<namespace> \
  --body='{
    "apiVersion": "v1",
    "kind": "PersistentVolumeClaim",
    "metadata": {"name": "data-pvc"},
    "spec": {
      "accessModes": ["ReadWriteMany"],
      "storageClassName": "sfs-turbo",
      "resources": {
        "requests": {"storage": "20Gi"}
      }
    }
  }'
```

## Storage Classes

CCI provides the following storage class:

| Storage Class | Backend | Access Mode | Use Case |
|--------------|---------|-------------|----------|
| `sfs-turbo` | SFS Turbo | ReadWriteMany | Shared file storage, config, logs |

Note: `csi-disk` (EVS) and `csi-obs` (OBS) are NOT available in CCI.

## Mapping Docker Compose Volumes

### Named Volume → PVC

```yaml
# docker-compose.yaml
volumes:
  db-data:
services:
  db:
    volumes:
      - db-data:/var/lib/postgresql/data
```

Create a PVC named `db-data` with SFS Turbo, then reference it in the Deployment:

```yaml
spec:
  template:
    spec:
      volumes:
      - name: db-data
        persistentVolumeClaim:
          claimName: db-data
      containers:
      - name: db
        volumeMounts:
        - name: db-data
          mountPath: /var/lib/postgresql/data
```

### Bind Mount (config files) → ConfigMap

```yaml
# docker-compose.yaml
volumes:
  - ./config/nginx.conf:/etc/nginx/nginx.conf:ro
```

Create a ConfigMap with the file content:

```bash
hcloud CCI createCoreV1NamespacedConfigMap \
  --namespace=<namespace> \
  --body='{
    "apiVersion": "v1",
    "kind": "ConfigMap",
    "metadata": {"name": "nginx-config"},
    "data": {"nginx.conf": "<file-content>"}
  }'
```

### Bind Mount (persistent data) → PVC

```yaml
# docker-compose.yaml
volumes:
  - ./data:/app/data
```

Create a PVC and mount it. The local data must be uploaded to SFS Turbo separately.

## Size Recommendations

| Use Case | Minimum Size | Recommended |
|----------|-------------|-------------|
| Config files | 1Gi | 5Gi |
| Application logs | 5Gi | 20Gi |
| Database data | 10Gi | 50Gi+ |
| Media/uploads | 20Gi | 100Gi+ |

## Limitations

- Only SFS Turbo available (no block storage)
- ReadWriteMany only (no ReadWriteOnce)
- No snapshot support via CCI API
- Must create PVC before referencing in Deployment
- SFS Turbo has a minimum size of 1Gi
