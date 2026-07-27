# Architecture: PostgreSQL ECS to RDS DRS Cross-Region Migration

## Overview

Migration of self-managed PostgreSQL on ECS to Huawei Cloud RDS for PostgreSQL using DRS Full + Incremental synchronization over public Internet (experimental phase).

## Architecture Diagram

```
Source Region (la-south-2)              Target Region (cn-north-4)
┌───────────────────────┐              ┌───────────────────────┐
│ VPC: source-vpc       │              │ VPC: target-vpc       │
│  └── Subnet           │              │  └── Subnet           │
│       └── SG: source  │              │       └── SG: target  │
│            └── ECS    │              │            └── RDS    │
│                 PG 16 │◄─EIP─────────│ DRS Instance (EIP)   │
│  wal_level=logical    │  /32 CIDR    │ Full + Incremental   │
│  replication slots    │              │                       │
│  pg_hba.conf          │              │                       │
└───────────────────────┘              └───────────────────────┘
```

## Key Design Decisions

1. **Public Internet via EIP**: This scenario uses EIP for DRS connectivity. VPN is OUT_OF_SCOPE_FOR_THIS_SCENARIO — the supported architecture is EIP + Security Groups + /32 CIDR + TCP 5432.
2. **DRS Full + Incremental**: Provides near-zero-downtime migration with full sync followed by incremental change capture.
3. **/32 CIDR enforcement**: DRS MCP rejects 0.0.0.0/0 and CIDRs broader than /32 for PostgreSQL port.
4. **Explicit approval**: Task creation and start require explicit_approval=true.

## Security Considerations

- PostgreSQL port exposed via EIP (mitigated by /32 CIDR to DRS EIP only)
- Replication user must have minimal required permissions
- Secrets redacted in all DRS reports
- Source SG rules should be removed post-migration

## Network Architecture (Confirmed)

- Connectivity: Public EIP
- Security: Security Groups + /32 CIDR restriction
- Port: TCP 5432
- Source access: DRS EIP only, restricted by SG rule and pg_hba.conf
- DRS connectivity validation: Connection test + Pre-check before task start
- VPN: OUT_OF_SCOPE_FOR_THIS_SCENARIO
