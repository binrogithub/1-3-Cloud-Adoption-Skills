# Discovery Workflow

## Objective
Enumerate all Kubernetes resources and regional dependencies in the source CCE cluster.

## Steps
1. Connect to source CCE cluster (kubectl)
2. List namespaces to migrate
3. For each namespace, enumerate: Deployments, StatefulSets, DaemonSets, Services, Ingress, ConfigMaps, Secrets, PVCs, PVs, CRDs
4. Identify regional dependencies: ELB, EIP, OBS, SWR, DNS
5. Assess application statefulness
6. Generate discovery report

## Automation Level
ASSISTED — Agent generates commands, human executes and provides output

## MCP Tools
None available for CCE discovery

## Capability Gaps
- GAP-CCE-001: No MCP tool for CCE cluster discovery
