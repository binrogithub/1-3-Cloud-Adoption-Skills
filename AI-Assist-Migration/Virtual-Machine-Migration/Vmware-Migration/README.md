# VMware Migration to Huawei Cloud

This scenario covers migrating VMware virtual machines (on-premises or cloud) to Huawei Cloud ECS using the MGC (Migration Center) / SMS (Server Migration Service) with Terraform automation.

## Skills

### [mgc-cross-region-migration](./mgc-cross-region-migration/)

Execute and troubleshoot Huawei Cloud server migration with Terraform. Supports two paths:

1. **Primary path (default): SMS** - block-level disk copy via Server Migration Service
2. **Fallback path: rsync** - when source is SMS-incompatible (e.g., SMS.6504, SMS.6617)

**Key files:**
- `SKILL.md` - Metadata and step-by-step instructions for AI/human7uman execution
- `scripts/mgc_migrate.py` - Main migration script (precheck -> migrate -> postcheck)
- `scripts/run_migration.sh` - Shell wrapper for Terraform + Python execution
- `references/runbook.md` - Detailed runbook with error codes and troubleshooting
- `references/lessons-learned.md` - Post-mortem insights from real migrations
- `assets/` - Terraform configuration files (main.tf, variables.tf, terraform.tfvars)
- `assets/bundles/` - Reusable migration bundles with architecture diagrams and plans
- `tools/build_bundle_from_latest_out.sh` - Bundle builder from migration output

## Usage

```bash
cd mgc-cross-region-migration
# Review prerequisites in SKILL.md
# Edit assets/terraform.tfvars with your source/target details
terraform init
terraform apply
# Check out/migration_result.json for results
```

## Prerequisites

- Source server registered in SMS/MGC and available/connected
- AK/SK with IAM, SMS, ECS, and VPC permissions
- Target image ID exists in target region
- For rsync fallback: source/target SSH reachable and rsync available
