# Waiter Patterns — Async Operation Polling

Use `--cli-waiter` to poll async operations until they reach a target state. Never poll manually with sleep loops.

## Syntax

```bash
hcloud <Service> <AsyncOperation> --cli-waiter='{"expr":"<jmespath>","to":"<target>","timeout":<seconds>,"interval":<seconds>}'
```

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `expr` | Yes | string | JMESPath expression pointing to the status field in the response |
| `to` | Yes | string | Target value that indicates success |
| `timeout` | No | int | Maximum wait time in seconds (1–600, default 180) |
| `interval` | No | int | Polling interval in seconds (2–10, default 5) |

## Per-service patterns

### ECS (Elastic Cloud Server)

| Operation | expr | Success | Failure | Typical timeout |
|-----------|------|---------|---------|-----------------|
| CreateServers | `server.status` | `ACTIVE` | `ERROR` | 300 |
| BatchStartServers | `server.status` | `ACTIVE` | `ERROR` | 120 |
| BatchStopServers | `server.status` | `SHUTOFF` | `ERROR` | 120 |
| BatchRebootServers | `server.status` | `ACTIVE` | `ERROR` | 120 |
| BatchResizeServers | `server.status` | `ACTIVE` | `ERROR` | 300 |
| ChangeServerOsWithCloudInit | `server.status` | `ACTIVE` | `ERROR` | 300 |
| RebuildServer | `server.status` | `ACTIVE` | `ERROR` | 300 |

```bash
# Create and wait
hcloud ECS CreateServers --cli-region=X \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' \
  ...

# Stop and wait
hcloud ECS BatchStopServers --cli-region=X \
  --cli-waiter='{"expr":"server.status","to":"SHUTOFF","timeout":120}' \
  --servers.1.id=SERVER_ID
```

### RDS (Relational Database Service)

| Operation | expr | Success | Failure | Typical timeout |
|-----------|------|---------|---------|-----------------|
| CreateInstance | `instances[0].status` | `ACTIVE` | `FAILED` | 600 |
| BatchStopInstance | `instances[0].status` | `SHUTDOWN` | `FAILED` | 300 |
| BatchStartInstance | (check manually) | `ACTIVE` | `FAILED` | 300 |

```bash
hcloud RDS CreateInstance --cli-region=X \
  --cli-waiter='{"expr":"instances[0].status","to":"ACTIVE","timeout":600}' \
  ...
```

RDS creation is slow — use `timeout=600` (10 minutes) or higher.

### CCE (Cloud Container Engine)

| Operation | expr | Success | Failure | Typical timeout |
|-----------|------|---------|---------|-----------------|
| CreateCluster | `status.phase` | `Available` | `Unavailable` | 600 |
| AddNode | (check node status separately) | `ACTIVE` | `ERROR` | 300 |

```bash
hcloud CCE CreateCluster --cli-region=X \
  --cli-waiter='{"expr":"status.phase","to":"Available","timeout":600}' \
  ...
```

### ELB (Elastic Load Balancer)

| Operation | expr | Success | Failure | Typical timeout |
|-----------|------|---------|---------|-----------------|
| CreateLoadbalancer | `provisioning_status` | `ACTIVE` | `ERROR` | 120 |
| CreateListener | `provisioning_status` | `ACTIVE` | `ERROR` | 60 |
| CreatePool | `provisioning_status` | `ACTIVE` | `ERROR` | 60 |

```bash
hcloud ELB CreateLoadbalancer --cli-region=X \
  --cli-waiter='{"expr":"provisioning_status","to":"ACTIVE","timeout":120}' \
  ...
```

### EVS (Elastic Volume Service)

| Operation | expr | Success | Failure | Typical timeout |
|-----------|------|---------|---------|-----------------|
| CreateVolume | `status` | `available` | `error` | 300 |
| BatchResizeVolumes | `status` | `available` | `error` | 120 |

```bash
hcloud EVS CreateVolume --cli-region=X \
  --cli-waiter='{"expr":"status","to":"available","timeout":300}' \
  ...
```

### AS (Auto Scaling)

| Operation | expr | Success | Failure | Typical timeout |
|-----------|------|---------|---------|-----------------|
| CreateScalingGroup | (check manually) | `INSERVICE` | — | 120 |

### NAT Gateway

| Operation | expr | Success | Failure | Typical timeout |
|-----------|------|---------|---------|-----------------|
| CreateNatGateway | `status` | `ACTIVE` | `ERROR` | 120 |

### VPN

| Operation | expr | Success | Failure | Typical timeout |
|-----------|------|---------|---------|-----------------|
| CreateVpnGateway | `status` | `ACTIVE` | `ERROR` | 300 |

## When waiter doesn't work

Some operations don't return the resource status in a format the waiter can poll. In these cases:

1. Execute the operation without `--cli-waiter`
2. Capture the resource ID from the response
3. Poll manually using list/show commands:

```bash
# Create without waiter
hcloud CCE AddNode --cli-region=X --cluster_id=CLUSTER_ID ...
# → node_id

# Poll manually
hcloud CCE ShowNode --cli-region=X --cluster_id=CLUSTER_ID --node_id=NODE_ID --cli-output=json --cli-query='status.phase'
# Repeat until phase is "Active" or timeout
```

## Failure detection

The waiter only checks for the success state. To detect failures, check the resource status separately:

```bash
# After waiter times out, check for error state
hcloud ECS ShowServer --cli-region=X --server_id=SERVER_ID --cli-output=json --cli-query='server.status'
# If "ERROR", check fault details:
hcloud ECS ShowServer --cli-region=X --server_id=SERVER_ID --cli-output=json --cli-query='server.fault'
```

## Common issues

- **Waiter times out but operation succeeds** — increase `timeout`. Some operations (RDS create, CCE cluster create) can take 10+ minutes.
- **Wrong `expr` path** — use `--debug` on a synchronous call first to inspect the response structure, then construct the JMESPath.
- **Operation returns immediately** — some operations are synchronous (VPC create, security group create). Don't use `--cli-waiter` for these.
- **`interval` too small** — minimum is 2 seconds. For long-running operations, use `interval=5` or `interval=10` to reduce API call volume.
