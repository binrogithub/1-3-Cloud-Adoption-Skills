# Discovery Prompt

You are performing discovery for a CCE cross-region migration.

Given the following inputs:
- Source CCE cluster ID: {{source_cluster_id}}
- Source region: {{source_region}}
- Namespaces: {{namespaces}}

Generate the kubectl commands needed to enumerate all resources in the specified namespaces. Include commands for:
- Deployments, StatefulSets, DaemonSets
- Services, Ingress
- ConfigMaps, Secrets
- PVCs, PVs
- StorageClasses
- CRDs and CRs

Also generate commands to identify:
- Load Balancers and EIPs associated with Services
- OBS buckets referenced by applications
- Image repositories used

Present the commands for human execution. Do NOT execute them.
