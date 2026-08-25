# Docker Compose to CCI Migration Notes

## API Version: v2 Required

All CCI resources must use the v2 API:
- Namespaces + workloads: `cci/v2`
- Networks: `yangtse/v2`

The v1beta1 API (`networking.cci.io/v1beta1`) strips `securityGroups` from Network spec, causing `400 securitygroup can not be empty`.

## Namespace Store Separation

Namespaces created via `api/v1` are NOT visible to v2 APIs. Always create namespaces via `cci/v2`.

## Image Pull Considerations

- **Docker Hub**: Works with NAT gateway. No imagePullSecret needed.
- **SWR**: Internal endpoint (100.125.x.x) may timeout from CCI. Create imagePullSecret with AK/SK.
- If SWR times out, use Docker Hub images instead.

## Resource Limits (Required)

CCI rejects pods without CPU/memory requests:
```
403: "pod without specifying resource requirement"
```

Minimum: `250m` CPU, `512Mi` memory.

## Service Types

| Type | Supported | Notes |
|------|-----------|-------|
| ClusterIP | NO | - |
| NodePort | NO | - |
| LoadBalancer | YES | Requires `kubernetes.io/elb.id` annotation |
| ExternalName | YES | DNS alias only |

## Storage

Only SFS Turbo supported for persistent volumes:
- `storageClassName: sfs-turbo`
- `accessModes: ["ReadWriteMany"]`
- No EVS or OBS support

## Pay-Per-Use

All resources pay-per-use:
- CCI pods: per-second billing
- NAT gateway: per-hour
- EIP: per-bandwidth
- SWR: pay-per-use
