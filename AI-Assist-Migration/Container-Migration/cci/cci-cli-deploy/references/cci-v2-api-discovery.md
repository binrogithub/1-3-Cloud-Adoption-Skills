# CCI v2 API Discovery

## The Problem: v1beta1 Strips `securityGroups`

The standard CCI v1beta1 API (`networking.cci.io/v1beta1`) does NOT include `securityGroups` in the Network CRD schema. When you create a Network with `securityGroups` in the spec, the Kubernetes API server strips the field during CRD validation (no `x-kubernetes-preserve-unknown-fields` in the schema!).

The CCI backend then rejects the request:

```
400 Bad Request
CCI.01.400101
"security-group not found: securitygroup can not be empty"
```

### v1beta1 NetworkSpec Schema Properties

```
attachedVPC, availableZone, cidr, hostaccessible,
networkID, networkType, physicalNetwork, plugin,
subnetID, subnets
```

**`securityGroups` is NOT in this list.**

## The Solution: v2 API

CCI exposes two v2 API groups that include `securityGroups`:

### API Group Discovery

```
GET /apis
```

Returns 15 API groups. The relevant ones:

| Group | Version | Purpose |
|-------|---------|---------|
| `cci` | `v2` | Namespaces, Deployments, Services, Pods, ConfigMaps, Secrets, PVCs |
| `yangtse` | `v2` | Networks (with securityGroups) |
| `networking.cci.io` | `v1beta1` | Networks (WITHOUT securityGroups) |

### cci/v2 Resources

```
GET /apis/cci/v2
```

| Resource | Kind | Verbs |
|----------|------|-------|
| namespaces | Namespace | create, delete, get, list, watch |
| deployments | Deployment | create, delete, get, list, patch, update, watch |
| services | Service | create, delete, get, list, patch, update, watch |
| pods | Pod | create, delete, get, list, patch, update, watch |
| pods/exec | PodExecOptions | create, get |
| pods/log | Pod | get |
| configmaps | ConfigMap | create, delete, get, list, patch, update, watch |
| secrets | Secret | create, delete, get, list, patch, update, watch |
| persistentvolumeclaims | PersistentVolumeClaim | create, delete, get, list, patch, update, watch |
| persistentvolumes | PersistentVolume | create, delete, get, list, patch, update, watch |
| deployments/scale | Scale | get, patch, update |
| replicasets | ReplicaSet | get, list, watch |
| storageclasses | StorageClass | list, watch |
| horizontalpodautoscalers | HorizontalPodAutoscaler | create, delete, get, list, patch, update, watch |
| imagesnapshots | ImageSnapshot | create, delete, get, list, watch |

### yangtse/v2 Resources

```
GET /apis/yangtse/v2
```

| Resource | Kind | Verbs |
|----------|------|-------|
| networks | Network | create, delete, get, list, patch, update, watch |

### v2 NetworkSpec Schema

```
networkType: string ("underlay_neutron" with underscore)
securityGroups: array<string>
subnets: array<{ subnetID: string }>
ipFamilies: array<string> (optional)
```

## Critical: Namespace Store Separation

**Namespaces created via `api/v1` are NOT visible to v2 APIs.**

```
# Create namespace via api/v1
POST /api/v1/namespaces → 201 Created

# v2 API cannot find it
GET /apis/yangtse/v2/namespaces/<name>/networks → 404 "namespace not found"
GET /apis/cci/v2/namespaces/<name>/pods → 404 "namespace not found"
```

**Namespaces MUST be created via `cci/v2`:**

```
POST /apis/cci/v2/namespaces → 201 Created
GET /apis/cci/v2/namespaces/<name>/pods → 200 OK
GET /apis/yangtse/v2/namespaces/<name>/networks → 200 OK
```

## Endpoint Summary

| Operation | Method | Path |
|-----------|--------|------|
| Create namespace | POST | `/apis/cci/v2/namespaces` |
| Get namespace | GET | `/apis/cci/v2/namespaces/{ns}` |
| List namespaces | GET | `/apis/cci/v2/namespaces` |
| Delete namespace | DELETE | `/apis/cci/v2/namespaces/{ns}` |
| Create network | POST | `/apis/yangtse/v2/namespaces/{ns}/networks` |
| Get network | GET | `/apis/yangtse/v2/namespaces/{ns}/networks/{name}` |
| List networks | GET | `/apis/yangtse/v2/namespaces/{ns}/networks` |
| Delete network | DELETE | `/apis/yangtse/v2/namespaces/{ns}/networks/{name}` |
| Create deployment | POST | `/apis/cci/v2/namespaces/{ns}/deployments` |
| Get deployment | GET | `/apis/cci/v2/namespaces/{ns}/deployments/{name}` |
| List pods | GET | `/apis/cci/v2/namespaces/{ns}/pods` |
| Create service | POST | `/apis/cci/v2/namespaces/{ns}/services` |
| Create configmap | POST | `/apis/cci/v2/namespaces/{ns}/configmaps` |
| Create secret | POST | `/apis/cci/v2/namespaces/{ns}/secrets` |

All endpoints use the CCI host: `https://cci.<region>.myhuaweicloud.com`
