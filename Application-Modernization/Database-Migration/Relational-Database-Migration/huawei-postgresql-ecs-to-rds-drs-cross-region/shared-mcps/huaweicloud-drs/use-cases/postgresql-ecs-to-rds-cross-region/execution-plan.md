# Execution Plan - PostgreSQL ECS to RDS Migration via DRS

## Overview

Self-managed PostgreSQL on ECS → Internet-based DRS → RDS for PostgreSQL in la-south-2

## Phase 1: Deploy Source Infrastructure

| Step | Action | Tool | Notes |
|------|--------|------|-------|
| 1.1 | Deploy source VPC, Subnet, Security Group | Terraform | `terraform/source-ecs-postgresql/` |
| 1.2 | Deploy ECS Ubuntu instance | Terraform | With optional EIP |
| 1.3 | Assign EIP to ECS | Terraform | For SSH access and DRS connectivity |
| 1.4 | Configure security group: SSH from admin, PostgreSQL from DRS CIDR placeholder | Terraform | Use `allowed_drs_cidr` variable |
| 1.5 | Apply Terraform | Manual approval | `terraform apply` after review |

## Phase 2: Configure Source PostgreSQL

| Step | Action | Tool | Notes |
|------|--------|------|-------|
| 2.1 | SSH to ECS | Manual | Using EIP |
| 2.2 | Run bootstrap script | Bash | `scripts/source_postgresql_bootstrap.sh` |
| 2.3 | Verify PostgreSQL is running | psql | `pg_isready` |
| 2.4 | Verify wal_level = logical | psql | `SHOW wal_level` |
| 2.5 | Replace placeholder passwords | Manual | Set secure passwords for demo and DRS users |

## Phase 3: Load Demo Data

| Step | Action | Tool | Notes |
|------|--------|------|-------|
| 3.1 | Create schema | psql | `sql/01_schema.sql` |
| 3.2 | Insert seed data | psql | `sql/02_seed_data.sql` |
| 3.3 | Run source validation | psql | `sql/03_source_validation.sql` |
| 3.4 | Record validation results | Manual | Save output for comparison |

## Phase 4: Deploy Target Infrastructure

| Step | Action | Tool | Notes |
|------|--------|------|-------|
| 4.1 | Deploy target VPC, Subnet in la-south-2 | Terraform | `terraform/target-rds-santiago/` |
| 4.2 | Deploy target Security Group | Terraform | Allow PostgreSQL from DRS and DAS |
| 4.3 | Deploy RDS for PostgreSQL | Terraform | Version 16, single AZ (lab) |
| 4.4 | Apply Terraform | Manual approval | `terraform apply` after review |
| 4.5 | Wait for RDS to become available | Console/CLI | Typically 5-10 minutes |

## Phase 5: Configure DRS Migration Task

| Step | Action | Tool | Notes |
|------|--------|------|-------|
| 5.1 | Open DRS console | Browser | Navigate to DRS service |
| 5.2 | Create migration task | DRS Console | See `docs/drs-internet-runbook.md` |
| 5.3 | Set source: self-managed PostgreSQL | DRS Console | ECS EIP, port 5432, DB name, DRS user |
| 5.4 | Set target: RDS PostgreSQL | DRS Console | la-south-2 RDS instance |
| 5.5 | Set network: Public network | DRS Console | Internet-based for experimental phase |
| 5.6 | Set mode: Full + Incremental | DRS Console | |
| 5.7 | Note DRS source IP/CIDR | DRS Console | Copy the CIDR shown by DRS |
| 5.8 | Update source security group with DRS CIDR | Console/CLI | Replace placeholder |
| 5.9 | Update pg_hba.conf with DRS CIDR | SSH to ECS | Replace `REPLACE_WITH_DRS_SOURCE_CIDR` |
| 5.10 | Reload PostgreSQL | SSH to ECS | `sudo systemctl reload postgresql` |
| 5.11 | Run DRS pre-check | DRS Console | Verify all checks pass |
| 5.12 | Start DRS task | DRS Console | Full sync begins |

## Phase 6: Validate Full Migration

| Step | Action | Tool | Notes |
|------|--------|------|-------|
| 6.1 | Wait for full sync to complete | DRS Console | Monitor progress |
| 6.2 | Open DAS for target RDS | Console | Navigate to DAS |
| 6.3 | Run target validation queries | DAS SQL | `sql/04_target_validation_das.sql` |
| 6.4 | Compare with source validation results | Manual | All counts and totals must match |
| 6.5 | Verify DRS status shows incremental sync running | DRS Console | |

## Phase 7: Validate Incremental Sync

| Step | Action | Tool | Notes |
|------|--------|------|-------|
| 7.1 | Run incremental test on source | psql | `sql/05_incremental_test_source.sql` |
| 7.2 | Wait 10-30 seconds for replication | Manual | DRS incremental latency |
| 7.3 | Run incremental validation on target | DAS SQL | `sql/06_incremental_validation_target_das.sql` |
| 7.4 | Verify new rows appear in target | Manual | C006, ORD006, INCREMENTAL_TEST audit |
| 7.5 | Verify updated totals match | Manual | Revenue = 3486.42 |

## Phase 8: Document and Clean Up

| Step | Action | Tool | Notes |
|------|--------|------|-------|
| 8.1 | Record all validation results | Manual | Save to `reports/` |
| 8.2 | Document DRS latency observations | Manual | |
| 8.3 | Review public exposure inventory | Manual | See `docs/security-and-cleanup.md` |
| 8.4 | Plan VPN migration | Manual | See `docs/future-vpn-runbook.md` |

## Future: Switch to VPN

| Step | Action | Tool | Notes |
|------|--------|------|-------|
| F.1 | Create inter-region VPN | Terraform | `terraform/future-vpn/` |
| F.2 | Update security groups to VPN CIDR | Console/CLI | |
| F.3 | Update pg_hba.conf to VPN CIDR | SSH | |
| F.4 | Switch DRS network to VPC/Private | DRS Console | May require task recreation |
| F.5 | Remove ECS EIP | Console/CLI | |
| F.6 | Remove public SG rules | Console/CLI | |
| F.7 | Validate migration over VPN | DAS + psql | |
