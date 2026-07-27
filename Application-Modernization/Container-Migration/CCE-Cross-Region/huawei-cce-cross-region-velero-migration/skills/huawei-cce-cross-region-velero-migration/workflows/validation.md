# Validation Workflow

## Objective
Verify migration success by comparing source and target cluster state.

## Steps
1. Verify Deployments running
2. Verify Services accessible
3. Verify Ingress configuration
4. Verify PVCs bound
5. Run application smoke tests
6. Compare resource counts
7. Verify DNS resolution
8. Verify Load Balancer health

## Automation Level
MANUAL — kubectl commands and application tests

## MCP Tools
None available for Kubernetes validation
