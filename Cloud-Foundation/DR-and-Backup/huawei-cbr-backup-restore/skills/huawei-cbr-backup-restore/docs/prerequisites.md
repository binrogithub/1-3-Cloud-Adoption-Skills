# Prerequisites

## hcloud CLI

- hcloud CLI version 6.2.9 installed and configured
- Version 7.2.12 validation pending
- Authentication configured (AK/SK or IAM)

```bash
hcloud version
```

## Huawei Cloud Authentication

- Valid AK/SK or IAM token configured in hcloud
- Do NOT pass credentials in commands or logs
- Verify with a read-only operation:

```bash
hcloud CBR ListVault --cli-region=<SOURCE_REGION> --limit=1
```

## Region and Project

- Target region specified and accessible
- Project or enterprise project context configured
- CBR service available in target region

## Source Resource

- ECS instance, EVS volume, or CCE node identified by name
- Resource exists in target region
- Resource state compatible with backup (ACTIVE for ECS, available for EVS)

## IAM Permissions

Required permissions:
- CBR vault: create, read, update, delete
- CBR backup: create, read, delete, restore
- CBR policy: create, read, update, delete
- ECS: read (for discovery)
- EVS: read (for discovery)

## Vault Quota

- Sufficient vault quota in target region
- Sufficient vault capacity for backup data
- Verify with ShowVault or ShowSummary

## Backup Quota

- Sufficient backup count quota
- Verify with ListBackups

## CBR Agent (for ECS application-consistent backup)

- Agent installed on ECS instance
- Agent registered with CBR
- Verify with:

```bash
hcloud CBR ListAgent --cli-region=<SOURCE_REGION>
```

## Optional MCPs

- huaweicloud-pricing: for cost estimation (read-only, does not block workflow)
- huaweicloud-ticket: for support ticket creation (create_ticket requires explicit approval)
- huaweicloud-deploy: for VPC/subnet/SG prerequisites only (NOT for CBR resources)
