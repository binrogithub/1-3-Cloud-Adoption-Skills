# CCI Limitations: Docker Compose Features Impossible in CCI

This reference lists Docker Compose features that **cannot** be migrated to Huawei Cloud CCI, explains why, and suggests alternatives.

## Why CCI has limitations

CCI is a **serverless** container service. Unlike CCE (full Kubernetes cluster) or ECS (VMs), CCI does not expose host machines. Pods run on shared infrastructure managed by Huawei Cloud. This means any feature requiring host-level access is impossible.

## Impossible Features

### Privileged Containers

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `privileged: true` | IMPOSSIBLE | Use CCE (full Kubernetes) or ECS (VM) |

CCI pods cannot run in privileged mode. If your container needs privileged access (e.g., Docker-in-Docker, system-level operations), you need CCE or ECS.

### Host Network

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `network_mode: host` | IMPOSSIBLE | Use CCE with hostNetwork: true |

CCI pods run in their own network namespace. There is no "host" network to attach to. Use LoadBalancer services to expose ports.

### Host PID / IPC

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `pid: host` | IMPOSSIBLE | Use CCE |
| `ipc: host` | IMPOSSIBLE | Use CCE |

CCI pods have isolated PID and IPC namespaces.

### Device Access

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `devices: /dev/sda:/dev/xvda` | IMPOSSIBLE | Use ECS (VM with direct device access) |

CCI pods cannot access host devices (GPU, serial ports, block devices). For GPU workloads, use CCE with GPU nodes or ECS with GPU.

### Linux Capabilities

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `cap_add: [SYS_ADMIN]` | IMPOSSIBLE | Use CCE or ECS |
| `cap_drop: [ALL]` | IMPOSSIBLE | Use CCE |

CCI does not support adding or dropping Linux capabilities.

### Other Host-Level Features

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `cgroup_parent` | IMPOSSIBLE | Use CCE |
| `storage_opt` | IMPOSSIBLE | Use CCE |
| `ulimits` | IMPOSSIBLE | Use CCE or ECS |
| `sysctls` | IMPOSSIBLE | Use CCE or ECS |
| `isolation` | IMPOSSIBLE | Use ECS (hypervisor isolation) |

## CCI Service Type Limitations

### No ClusterIP

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| Internal service communication | Use CCI DNS | Services resolve by name within namespace |

CCI does not support `ClusterIP` services. Internal communication between pods works via DNS (service names resolve within the namespace). You do not need to create a Service for internal-only communication.

### No NodePort

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `ports` with NodePort | IMPOSSIBLE | Use LoadBalancer with ELB |

CCI does not support `NodePort` services (there are no nodes to expose ports on). All external access goes through LoadBalancer with an ELB.

### Only LoadBalancer + ExternalName

CCI supports:
- `LoadBalancer` (requires ELB ID annotation: `kubernetes.io/elb.id`)
- `ExternalName` (DNS alias)

## CCI Storage Limitations

### Only SFS Turbo

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| Named volumes | SFS Turbo PVC | `storageClassName: sfs-turbo` |
| Bind mounts (files) | ConfigMap | Inline data in ConfigMap |
| Bind mounts (directories) | SFS Turbo PVC | If data needs to persist |

CCI only supports SFS Turbo for persistent volumes. No EVS (block storage) or OBS (object storage) as PVCs.

**SFS Turbo characteristics:**
- `accessModes: [ReadWriteMany]` (shared, multi-pod access)
- Minimum size: 10Gi
- Billed per GB/hour
- Good for shared file storage, NOT for databases (use RDS instead)

### No Snapshot Support

CCI does not support volume snapshots via the CSI driver. For backups, use obsutil to copy data to OBS.

## CCI Workload Type Limitations

| Workload Type | Supported in CCI | Notes |
|---------------|-----------------|-------|
| Deployment | YES | Primary workload type |
| StatefulSet | YES | For ordered, stateful apps |
| Job | YES | For batch jobs |
| CronJob | YES | For scheduled jobs |
| DaemonSet | NO | Serverless — no nodes to run on every node |
| ReplicaSet | YES (via Deployment) | Use Deployment instead |
| Pod (bare) | YES | But Deployment is recommended |

### DaemonSet Alternative

If you need DaemonSet behavior (run on every node), CCI cannot do this. Alternatives:
- Use CCE (full Kubernetes with DaemonSet support)
- Use a Deployment with enough replicas to cover your needs

## CCI Networking Limitations

### One Network Per Namespace

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| Multiple isolated networks | IMPOSSIBLE | All services share one CCI network |

CCI supports one `yangtse/v2` Network per namespace. If your Compose uses multiple isolated networks (e.g., `frontend` + `backend`), all services will share the same CCI network. Use Security Groups for isolation.

### No Network Aliases

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `networks.aliases: [my-alias]` | NOT SUPPORTED | Use service name for DNS |

CCI resolves services by their Deployment name within the namespace. Custom aliases are not supported.

## CCI Resource Limitations

### Mandatory Resource Limits

| Aspect | Requirement |
|--------|-------------|
| CPU request | Minimum 250m (0.25 vCPU) |
| Memory request | Minimum 512Mi |
| CPU limit | Recommended 500m or higher |
| Memory limit | Recommended 1024Mi or higher |

CCI rejects pods without resource requests/limits with `403: "pod without specifying resource requirement"`.

### No CPU Pinning

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `cpuset: "0-1"` | IMPOSSIBLE | Use `cpus` for quota-based limits |

CCI does not support CPU pinning. Use `resources.limits.cpu` for quota-based limits.

## CCI Image Limitations

### SWR Internal Endpoint

| Issue | Solution |
|-------|----------|
| SWR internal endpoint (100.125.x.x) may not be reachable from CCI pods | Use Docker Hub, or configure VPC endpoint for SWR |

If image pulls from SWR timeout, switch to Docker Hub or configure a VPC endpoint.

### No Image Build

| Docker Compose | Status | Alternative |
|---------------|--------|-------------|
| `build: ./dir` | IMPOSSIBLE in CCI | Build locally, push to SWR, reference in Deployment |

CCI does not build images. Build locally with `docker build`, push to SWR or Docker Hub, then reference the image in the Deployment.

## Suggested Alternatives Summary

| Need | CCI Cannot | Use Instead |
|------|-----------|-------------|
| Privileged containers | Yes | CCE or ECS |
| Host network/PID/IPC | Yes | CCE |
| Device access (GPU, serial) | Yes | CCE with GPU nodes or ECS |
| Linux capabilities | Yes | CCE or ECS |
| DaemonSets | Yes | CCE |
| NodePort services | Yes | CCE or ELB |
| Multiple isolated networks | Yes | CCE with NetworkPolicy |
| EVS/OBS as PVC | Yes | CCE |
| Volume snapshots | Yes | CCE with Velero |
| Image build | Yes | CodeArts Build or local docker build + SWR |
| Database (HA, backup) | Not ideal | RDS with DRS |
| Redis (HA, backup) | Not ideal | DCS (Distributed Cache Service) |
| MongoDB | Not ideal | DDS (Document Database Service) |
