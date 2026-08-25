# Docker Compose to CCI Translation Table

Complete field-by-field mapping from `docker-compose.yaml` to CCI v2 API resources.

## Services → Deployments

| Docker Compose Field | CCI v2 API Field | Notes |
% | Example |
|---------------------|-----------------|-------|---------|
| `services.<name>` | `Deployment.metadata.name` | Direct mapping | `web` → `name: web` |
| `.image` | `spec.template.spec.containers[0].image` | SWR URL or Docker Hub | `nginx:latest` |
| `.replicas` (compose v3) | `spec.replicas` | Default: 1 | `deploy.replicas: 3` |
| `.restart: always` | `spec.replicas: 1` | Pod always running | - |
| `.restart: "no"` | `spec.replicas: 0` | Scale to zero | - |
| `.restart: on-failure` | `spec.replicas: 1` | CCI doesn't distinguish | - |

## Ports → Services

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `ports: ["80:80"]` | `Service` type=LoadBalancer | External port maps to ELB |
| `ports: ["8080"]` | `Service` type=LoadBalancer | Exposes container port |
| `expose: ["3000"]` | (no Service) | Internal only, no CCI equivalent |

**CCI does NOT support ClusterIP or NodePort services.** All exposed ports require a LoadBalancer service with an ELB ID annotation.

## Volumes → PVCs

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| Named volume: `data:/data` | `PersistentVolumeClaim` | `storageClassName: sfs-turbo` |
| Bind mount: `./config:/config` | `ConfigMap` (if files) or `PVC` | Depends on content |
| `volumes_from:` | `PersistentVolumeClaim` | Shared PVC |

### PVC Example

```json
{
  "apiVersion": "cci/v2",
  "kind": "PersistentVolumeClaim",
  "metadata": {"name": "app-data"},
  "spec": {
    "accessModes": ["ReadWriteMany"],
    "storageClassName": "sfs-turbo",
    "resources": {"requests": {"storage": "10Gi"}}
  }
}
```

**Only SFS Turbo is supported.** No EVS or OBS.

## Environment → ConfigMaps

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `environment: {KEY: value}` | `ConfigMap.data` | Non-sensitive values |
| `environment: [KEY=value]` | `ConfigMap.data` | List format |
| `env_file: .env` | `ConfigMap` or `Secret` | Parse file, split by sensitivity |

### ConfigMap Example

```json
{
  "apiVersion": "cci/v2",
  "kind": "ConfigMap",
  "metadata": {"name": "app-config"},
  "data": {
    "LOG_LEVEL": "info",
    "MAX_CONNECTIONS": "100"
  }
}
```

## Secrets → Secrets

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `secrets: db_password` | `Secret` type=Opaque | Base64 encode |
| `.env` with sensitive vars | `Secret` type=Opaque | Split sensitive from non-sensitive |

### Secret Example

```json
{
  "apiVersion": "cci/v2",
  "kind": "Secret",
  "metadata": {"name": "app-secrets"},
  "type": "Opaque",
  "data": {
    "DB_PASSWORD": "c2VjcmV0",
    "API_KEY": "dG9rZW4xMjM="
  }
}
```

## Resource Limits (Required)

| Docker Compose | CCI v2 API | Default | Notes |
|---------------|-----------|---------|-------|
| `.cpus: 0.5` | `resources.limits.cpu: 500m` | `250m` | **Required** by CCI |
| `.memD: 512m` | `resources.limits.memory: 512Mi` | `512Mi` | **Required** by CCI |
| `deploy.resources.limits.cpus` | `resources.limits.cpu` | - | Compose v3 deploy section |
| `deploy.resources.limits.memory` | `resources.limits.memory` | - | Compose v3 deploy section |
| `deploy.resources.reservations.cpus` | `resources.requests.cpu` | - | Compose v3 deploy section |
| `deploy.resources.reservations.memory` | `resources.requests.memory` | - | Compose v3 deploy section |

**CCI rejects pods without resource limits** with 403: "pod without specifying resource requirement".

## Health Checks → Probes

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `healthcheck.test: ["CMD", "curl", "-f", "http://localhost"]` | `livenessProbe.exec.command` | Remove "CMD" prefix |
| `healthcheck.interval: 30s` | `livenessProbe.periodSeconds: 30` | Strip "s" suffix |
| `healthcheck.timeout: 10s` | `livenessProbe.timeoutSeconds: 10` | Strip "s" suffix |
| `healthcheck.start_period: 40s` | `livenessProbe.initialDelaySeconds: 40` | Strip "s" suffix |
| `healthcheck.retries: 3` | (no direct mapping) | CCI uses failureThreshold |

## Command/Entrypoint

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `command: ["nginx", "-g", "daemon off;"]` | `containers[].command` | Direct mapping |
| `command: nginx -g "daemon off;"` | `containers[].command` (split) | String → list |
| `entrypoint: ["/docker-entrypoint.sh"]` | `containers[].args` | Direct mapping |

## Networks

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `networks: default` | Network (yangtse/v2) | One network per namespace |
| `networks: custom` | Network (yangtse/v2) | All services share one CCI network |
| `networks.aliases:` | (no equivalent) | Use service name for DNS |

**CCI supports one network per namespace.** All services in the same Compose file share the same CCI network.

## Depends On

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `depends_on: [db]` | init containers | Or startup ordering via probes |
| `depends_on: {db: {condition: service_healthy}}` | init containers + readinessProbe | Wait for dependency health |

## Build (Not Supported)

| Docker Compose | CCI v2 API | Notes |
|---------------|-----------|-------|
| `build: .` | (not supported) | Build image locally, push to SWR, then deploy |

CCI does not build images. Build locally with `docker build`, push to SWR or Docker Hub, then reference in the Deployment.
