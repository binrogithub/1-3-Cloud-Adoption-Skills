# Architecture - PostgreSQL ECS to RDS Migration via DRS

## Experimental Phase Architecture (Internet/Public Network)

```
┌─────────────────────────────────────────────────────────────┐
│  SOURCE REGION (e.g., cn-north-4 or your ECS region)       │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  VPC: source-vpc                                     │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  Subnet: source-subnet                          │  │  │
│  │  │                                                 │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │  Security Group: source-sg               │  │  │  │
│  │  │  │  - SSH from admin IP                     │  │  │  │
│  │  │  │  - PostgreSQL 5432 from DRS CIDR ⚠️      │  │  │  │
│  │  │  │  - Outbound: allow                       │  │  │  │
│  │  │  │                                          │  │  │  │
│  │  │  │  ┌────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  ECS: Ubuntu 22.04                │  │  │  │  │
│  │  │  │  │  - PostgreSQL 16 (self-managed)   │  │  │  │  │
│  │  │  │  │  - wal_level = logical            │  │  │  │  │
│  │  │  │  │  - Demo DB: demomigration         │  │  │  │  │
│  │  │  │  │  - DRS user: drs_replicator       │  │  │  │  │
│  │  │  │  └────────────────────────────────────┘  │  │  │  │
│  │  │  │                                          │  │  │  │
│  │  │  │  EIP: source-eip (for SSH + DRS access)  │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │  Public Internet (EXPERIMENTAL)
                            │  ⚠️ PostgreSQL port exposed to DRS CIDR
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  DRS - Data Replication Service                            │
│                                                             │
│  Task Type:    Full + Incremental                           │
│  Source Type:  Self-managed PostgreSQL (ECS)                │
│  Target Type:  RDS for PostgreSQL                           │
│  Network:      Public network (Internet)                    │
│                                                             │
│  ┌──────────────┐    Full Sync    ┌──────────────────────┐ │
│  │  Source DB   │ ──────────────▶ │  Target RDS DB      │ │
│  │  (ECS)       │    + Incremental│  (la-south-2)       │ │
│  └──────────────┘                 └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  TARGET REGION: la-south-2 (Santiago, Chile)               │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  VPC: target-vpc                                     │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  Subnet: target-subnet                          │  │  │
│  │  │                                                 │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │  Security Group: target-sg               │  │  │  │
│  │  │  │  - PostgreSQL 5432 from DRS CIDR         │  │  │  │
│  │  │  │  - PostgreSQL 5432 from DAS CIDR         │  │  │  │
│  │  │  │  - Outbound: allow                       │  │  │  │
│  │  │  │                                          │  │  │  │
│  │  │  │  ┌────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  RDS for PostgreSQL 16             │  │  │  │  │
│  │  │  │  │  - DB: demomigration               │  │  │  │  │
│  │  │  │  │  - HA: Single (lab)                │  │  │  │  │
│  │  │  │  │  - Storage: 40GB ULTRAHIGH         │  │  │  │  │
│  │  │  │  └────────────────────────────────────┘  │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions - Experimental Phase

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Source DB | Self-managed PostgreSQL on ECS | Demonstrates migration from self-managed to RDS |
| DRS Network | Public Internet | Lab convenience; VPN for presentation |
| Migration Mode | Full + Incremental | Demonstrates CDC and real-time replication |
| Target Region | la-south-2 (Santiago) | Inter-region migration demo |
| PostgreSQL Version | 16 | Match source and target versions |
| Security Group | DRS CIDR only | Minimal exposure; no 0.0.0.0/0 |

## Public Exposure Inventory - EXPERIMENTAL PHASE

| Exposure | Type | Scope | Removal |
|----------|------|-------|---------|
| ECS EIP | Public IP | SSH + DRS connectivity | Remove EIP or restrict to VPN |
| pg_hba.conf | Network ACL | DRS user from DRS CIDR | Change to VPN/private CIDR |
| Security Group | Inbound rule | Port 5432 from DRS CIDR | Change to VPN/private CIDR |

## Future Target Architecture (VPN/Private Network)

```
┌─────────────────────────────────────┐
│  SOURCE REGION                      │
│  ECS + PostgreSQL                   │
│  (No EIP on ECS)                    │
│  pg_hba.conf: VPN CIDR only        │
└──────────────┬──────────────────────┘
               │
               │  VPN Tunnel
               │  (Inter-region)
               │
               ▼
┌─────────────────────────────────────┐
│  TARGET REGION: la-south-2          │
│  RDS for PostgreSQL                 │
│  Security Group: VPN CIDR only     │
└─────────────────────────────────────┘

DRS Network Mode: VPC/Private network
No public PostgreSQL exposure
```

### VPN Migration Changes

1. Create inter-region VPN between source VPC and target VPC
2. Remove ECS EIP (or restrict to admin-only SSH)
3. Update source security group: replace DRS public CIDR with VPN CIDR
4. Update target security group: replace DRS public CIDR with VPN CIDR
5. Update pg_hba.conf: replace DRS public CIDR with VPN/private CIDR
6. Switch DRS task network type from Public to VPC/Private
7. Validate connectivity through VPN
8. Remove all public PostgreSQL access rules
