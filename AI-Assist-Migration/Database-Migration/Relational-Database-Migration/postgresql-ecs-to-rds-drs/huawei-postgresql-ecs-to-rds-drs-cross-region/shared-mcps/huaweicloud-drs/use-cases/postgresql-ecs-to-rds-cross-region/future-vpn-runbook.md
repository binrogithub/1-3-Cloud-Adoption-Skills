# VPN Runbook — OUT_OF_SCOPE_FOR_THIS_SCENARIO

> **ARCHIVED REFERENCE:**
> The active PostgreSQL DRS skill uses public EIP connectivity.
> VPN is not required and is outside the supported scenario.
> This document is retained for historical reference only and must not be used as an active runbook.

## Classification

VPN connectivity is **OUT_OF_SCOPE_FOR_THIS_SCENARIO**. The supported PostgreSQL ECS-to-RDS cross-region migration architecture uses public EIP connectivity with /32 CIDR restrictions, Security Groups, and pg_hba.conf access controls. This runbook is retained for reference only and must not be used for the current scenario.

## Overview

This runbook explains how to convert the EIP-based DRS migration to use VPN/private network connectivity. This is NOT the supported architecture for the current PostgreSQL ECS-to-RDS cross-region migration skill.

## Current State (Supported Architecture)

- Source ECS PostgreSQL has an EIP
- DRS connects to source PostgreSQL over public Internet
- Security group allows PostgreSQL 5432 from DRS public CIDR (/32 only)
- pg_hba.conf allows DRS user from DRS public CIDR
- This is the **intentional and supported** architecture for this scenario

## Target State (VPN/Private)

- Source ECS has no EIP (or EIP restricted to admin SSH only)
- DRS connects to source PostgreSQL over VPN/private network
- Security group allows PostgreSQL 5432 from VPN/private CIDR only
- pg_hba.conf allows DRS user from VPN/private CIDR only
- No public PostgreSQL exposure

## Step 1: Create Inter-Region VPN

### 1a. Deploy VPN Gateway in Source Region

Use `terraform/future-vpn/` to create:

- VPN Gateway in source VPC
- VPN Gateway in target VPC (la-south-2)

### 1b. Create VPN Connection

- Source VPN Gateway ↔ Target VPN Gateway
- IKE/IPsec configuration with shared pre-shared key (PSK)
- Routing: source subnet ↔ target subnet

### 1c. Verify VPN Tunnel

- Check VPN connection status (both tunnels UP)
- Test connectivity: ping from source ECS to target RDS private IP
- Verify routing tables include the remote subnet

## Step 2: Update Security Groups

### Source Security Group

| Current Rule | New Rule |
|-------------|----------|
| Ingress TCP 5432 from DRS public CIDR | Ingress TCP 5432 from VPN/target CIDR |
| Ingress TCP 22 from admin IP | Ingress TCP 22 from admin IP (keep) |

### Target Security Group

| Current Rule | New Rule |
|-------------|----------|
| Ingress TCP 5432 from DRS public CIDR | Ingress TCP 5432 from VPN/source CIDR |
| Ingress TCP 5432 from DAS CIDR | Ingress TCP 5432 from DAS CIDR (keep) |

## Step 3: Update pg_hba.conf

SSH to the source ECS and update pg_hba.conf:

```bash
# Comment out the public DRS access rule
# host  demomigration  drs_replicator  <DRS_PUBLIC_CIDR>  md5
# host  replication    drs_replicator  <DRS_PUBLIC_CIDR>  md5

# Add VPN/private access rule
# Replace <VPN_TARGET_CIDR> with the target VPC subnet CIDR through VPN
echo "host  demomigration  drs_replicator  <VPN_TARGET_CIDR>  md5" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf
echo "host  replication    drs_replicator  <VPN_TARGET_CIDR>  md5" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf

sudo systemctl reload postgresql
```

## Step 4: Switch DRS Network Mode

DRS may need to be reconfigured or recreated for private network mode:

### Option A: Modify Existing Task (if supported)

1. Stop the DRS task
2. Change network type from Public to VPC/Private
3. Update source connection to use private IP instead of EIP
4. Re-run pre-check
5. Start the task

### Option B: Create New Task

1. Stop and delete the existing DRS task
2. Create a new DRS task with:
   - Network type: **VPC** or **Private network**
   - Source: ECS private IP (not EIP)
   - Target: RDS private IP
3. Run pre-check
4. Start the task

## Step 5: Remove Public PostgreSQL Exposure

### 5a. Remove or Restrict ECS EIP

- **Option 1**: Release the EIP entirely (if SSH is through VPN/bastion)
- **Option 2**: Keep EIP but remove the PostgreSQL security group rule for public access
- **Option 3**: Keep EIP for SSH only, ensure security group only allows TCP 22 from admin IP

### 5b. Remove Public Security Group Rules

Delete any inbound rules on port 5432 from public CIDRs.

### 5c. Remove Public pg_hba.conf Entries

Comment out or remove any pg_hba.conf entries with public IP ranges.

### 5d. Reload PostgreSQL

```bash
sudo systemctl reload postgresql
```

## Step 6: Validate Private Connectivity

1. Verify DRS task connects successfully over VPN
2. Verify full sync works (if new task) or incremental continues
3. Run validation queries on target via DAS
4. Insert test row on source and verify replication over VPN
5. Verify no public PostgreSQL access exists

## Step 7: Verify No Public Exposure

| Check | Command/Action |
|-------|----------------|
| ECS EIP | Verify EIP is removed or restricted |
| Source SG | No 0.0.0.0/0 or broad CIDR on 5432 |
| Target SG | No 0.0.0.0/0 or broad CIDR on 5432 |
| pg_hba.conf | No public IP entries |
| DRS task | Network type = VPC/Private |
| VPN tunnels | Both UP and stable |

## VPN Configuration Reference

| Parameter | Source | Target |
|-----------|--------|--------|
| Region | (your source region) | la-south-2 |
| VPC | source-vpc | target-vpc |
| Subnet CIDR | e.g., 192.168.0.0/24 | e.g., 10.0.0.0/24 |
| VPN Gateway | source-vpn-gw | target-vpn-gw |
| IKE Version | v2 | v2 |
| PSK | *(generate secure PSK)* | *(same PSK)* |

## Timeline

| Phase | Duration | Notes |
|-------|----------|-------|
| Deploy VPN gateways | 5-10 min | Terraform apply |
| Create VPN connection | 5 min | Console or API |
| Verify tunnel | 2-5 min | Ping test |
| Update security groups | 5 min | Console or CLI |
| Update pg_hba.conf | 2 min | SSH to ECS |
| Switch DRS network | 10-20 min | May require task recreation |
| Remove public exposure | 5 min | Console or CLI |
| Validate | 10 min | DAS + psql |
| **Total** | **45-60 min** | |
