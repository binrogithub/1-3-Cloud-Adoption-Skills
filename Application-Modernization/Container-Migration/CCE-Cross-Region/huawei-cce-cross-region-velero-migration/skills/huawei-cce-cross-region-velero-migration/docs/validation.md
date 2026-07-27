# Validation

## Pre-migration
- Source cluster resources enumerated correctly
- Target cluster has sufficient capacity
- Kubernetes versions compatible
- OBS bucket accessible from both regions
- Velero operational on both clusters

## Post-migration
- All Deployments running on target cluster
- All Services accessible
- Ingress routing correct
- PVCs bound in target region
- Application smoke tests pass
- Resource counts match (source vs target)
- DNS resolves to target cluster
- Load Balancer health checks pass
