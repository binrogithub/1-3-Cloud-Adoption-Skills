# Security and Cleanup Guide

## Credential Handling

### Rules

- **Never** print, echo, log, or expose AK/SK values
- **Never** write credentials into Terraform files, scripts, reports, or logs
- **Never** commit credentials to git
- Use environment variables or Huawei Cloud secure configuration for credentials
- All passwords in scripts use `REPLACE_WITH_*` placeholders
- DRS passwords are entered only in the DRS console UI

### Credential Inventory

| Credential | Storage | Notes |
|------------|---------|-------|
| AK/SK | Environment variables / IAM | Never in files |
| ECS SSH key | Huawei Cloud keypair | Downloaded once, stored securely |
| PostgreSQL demo user password | Set manually on ECS | Not in files |
| PostgreSQL DRS user password | Set manually on ECS | Not in files |
| RDS admin password | Set in terraform.tfvars | Not committed |
| VPN PSK | Generated securely | Only in VPN configuration |

## Security Group Restrictions

### Source ECS Security Group

| Direction | Protocol | Port | Source | Status |
|-----------|----------|------|--------|--------|
| Ingress | TCP | 22 | Admin IP | Permanent |
| Ingress | TCP | 5432 | DRS CIDR | **Temporary - remove after test** |
| Egress | All | All | 0.0.0.0/0 | Permanent |

### Target RDS Security Group

| Direction | Protocol | Port | Source | Status |
|-----------|----------|------|--------|--------|
| Ingress | TCP | 5432 | DRS CIDR | **Temporary - update for VPN** |
| Ingress | TCP | 5432 | DAS CIDR | Permanent |
| Egress | All | All | 0.0.0.0/0 | Permanent |

## Public Access Warning

### Current Public Exposure (EXPERIMENTAL PHASE ONLY)

| Exposure | Risk Level | Mitigation |
|----------|-----------|------------|
| ECS EIP | Medium | Restrict SG; remove after test |
| PostgreSQL 5432 open to DRS CIDR | Medium | Narrow CIDR only; remove after test |
| pg_hba.conf allows DRS CIDR | Medium | Narrow CIDR only; change to VPN CIDR |

### ⚠️ NEVER DO

- **Never** open PostgreSQL 5432 to 0.0.0.0/0
- **Never** use `trust` authentication in pg_hba.conf for network connections
- **Never** leave DRS CIDR rules in place after the test without a plan to remove them
- **Never** expose AK/SK in any output

## How to Remove Public Database Exposure

### Step 1: Remove Security Group Rules

1. Go to the source ECS security group
2. Delete the inbound rule for TCP 5432 from the DRS CIDR
3. Go to the target RDS security group
4. Delete or update the inbound rule for TCP 5432 from the DRS CIDR

### Step 2: Remove pg_hba.conf Entries

SSH to the source ECS:

```bash
# Comment out the DRS public access lines
sudo sed -i 's/^host.*drs_replicator.*md5/# &/' /etc/postgresql/16/main/pg_hba.conf
sudo systemctl reload postgresql
```

### Step 3: Release or Restrict ECS EIP

- **Option A**: Release the EIP entirely
- **Option B**: Keep the EIP but ensure no SG rule allows 5432 from public

### Step 4: Verify

```bash
# Verify PostgreSQL is not accessible from public
# (from a machine outside the network)
psql -h <ECS_EIP> -p 5432 -U drs_replicator -d demomigration
# Expected: connection refused / timeout
```

## Cleanup Order

When you are done with the lab, clean up resources in this order:

### 1. DRS Task

1. Stop the DRS task
2. Delete the DRS task
3. This does not delete source or target data

### 2. Target RDS (la-south-2)

1. Delete the RDS instance
2. Delete the target security group
3. Delete the target subnet
4. Delete the target VPC

### 3. Source ECS

1. Release the ECS EIP
2. Delete the ECS instance
3. Delete the source security group
4. Delete the source subnet
5. Delete the source VPC

### 4. Terraform

```bash
# Source
cd terraform/source-ecs-postgresql
terraform destroy  # ONLY after explicit approval

# Target
cd terraform/target-rds-santiago
terraform destroy  # ONLY after explicit approval
```

## DRS Cleanup Notes

- Stopping a DRS task does not delete it; you must explicitly delete
- Deleting a DRS task does not affect source or target data
- If the DRS task is in incremental sync, stopping it will end CDC
- DRS tasks may incur charges while running — stop/delete when not in use

## RDS/ECS Cleanup Notes

- RDS instances continue to incur charges while running
- ECS instances continue to incur charges while running
- EIPs incur charges while allocated (even if not attached)
- Delete all resources when the lab is complete to avoid ongoing charges

## Future VPN Hardening Checklist

- [ ] Deploy inter-region VPN gateways
- [ ] Create VPN connection with secure PSK
- [ ] Verify VPN tunnels are UP
- [ ] Update source SG: replace DRS public CIDR with VPN/private CIDR
- [ ] Update target SG: replace DRS public CIDR with VPN/private CIDR
- [ ] Update pg_hba.conf: replace DRS public CIDR with VPN/private CIDR
- [ ] Reload PostgreSQL on source ECS
- [ ] Switch DRS task network mode to VPC/Private
- [ ] Remove ECS EIP (or restrict to SSH only)
- [ ] Remove all public PostgreSQL SG rules
- [ ] Remove all public pg_hba.conf entries
- [ ] Verify DRS connects over VPN
- [ ] Verify no public PostgreSQL access exists
- [ ] Run full validation over VPN path

## Cost-Control Recommendations

| Resource | Action | Estimated Savings |
|----------|--------|-------------------|
| DRS task | Stop/delete when not testing | DRS task charges |
| RDS instance | Delete or scale down after test | RDS hourly charges |
| ECS instance | Delete after test | ECS hourly charges |
| EIP | Release when not needed | EIP retention charges |
| VPN gateways | Deploy only for presentation | VPN gateway charges |
| Terraform | Use `terraform destroy` after lab | All associated resources |

### Lab Duration Estimate

| Phase | Duration | Active Resources |
|-------|----------|------------------|
| Deploy infrastructure | 30 min | ECS, RDS, EIP |
| Configure PostgreSQL | 15 min | ECS, RDS, EIP |
| Load data | 5 min | ECS, RDS, EIP |
| DRS full sync | 5-15 min | ECS, RDS, EIP, DRS |
| DRS incremental validation | 5 min | ECS, RDS, EIP, DRS |
| Cleanup | 15 min | Reducing |
| **Total** | **1-1.5 hours** | |
