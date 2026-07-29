# DWS Cluster Deployment Architecture

## Service

Huawei Cloud DWS (GaussDB(DWS)) — Data Warehouse Service

## Protocol

PostgreSQL-compatible (partial compatibility). Default port: 8000 (range: 8000-30000).

## Cluster Types

| Type | Node count | Use case |
|---|---|---|
| Cluster | 3-256 | Production, HA workloads |
| Standalone (hybrid) | 1 | Development, testing |

## Architecture Components

```
┌─────────────────────────────────────────────────┐
│                   VPC                           │
│  ┌──────────────────────────────────────────┐   │
│  │              Subnet                      │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐      │   │
│  │  │  CN    │ │  DN    │ │  DN    │      │   │
│  │  │(Coord) │ │(Data)  │ │(Data)  │ ...  │   │
│  │  └────────┘ └────────┘ └────────┘      │   │
│  │                                          │   │
│  │  Security Group: Port 8000 from CIDR    │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  Optional: EIP → Public Access                  │
└─────────────────────────────────────────────────┘
```

## Node Roles

- **CN (Coordinator Node)**: Query routing, transaction coordination. Default: 3 (range: 2-20).
- **DN (Data Node)**: Data storage and processing. Minimum: 3 for cluster mode.

## Network Requirements

- VPC with subnet in target region
- Security group allowing DWS port from authorized CIDR
- Sufficient IP addresses in subnet for all nodes + internal components
- Never allow 0.0.0.0/0 on DWS port

## Storage

Storage types are region-dependent. Discover via ListNodeTypes.

## HA

HA topology depends on region, version, and AZ availability. Validate before deployment.

## Snapshots

Snapshots provide point-in-time recovery. Restore creates a new cluster. Snapshot policy configuration is version-dependent.

## OBS Integration

Data loading from OBS via external tables. Syntax is version-dependent and must be validated.

## Credential Handling

- Administrator username: lowercase letters, digits, underscores; 1-63 chars
- Password: 8-32 chars, complexity rules enforced by DWS
- Never pass password in visible command line

## Component Classification

| Component | Source | Mechanism |
|---|---|---|
| VPC | Existing or create | huaweicloud-deploy MCP or hcloud CLI |
| Subnet | Existing or create | huaweicloud-deploy MCP or hcloud CLI |
| Security group | Existing or create | huaweicloud-deploy MCP or hcloud CLI |
| DWS cluster | Create | hcloud DWS CreateCluster |
| EIP | Existing or create | hcloud VPC CLI |
| Snapshot policy | Create | hcloud DWS CreateSnapshot |
| Database/schemas | Create | SQL via psql/JDBC |
| OBS external tables | Create | SQL via psql/JDBC |
