# Scenario 3: Multi-Account Landing Zone on Huawei Cloud

## Overview

This scenario demonstrates how to build a multi-account landing zone on Huawei Cloud using Terraform. The AI agent uses the `multi-account-landing-zone` skill to generate modular Terraform code for organizational governance — including Organizational Units (OUs), accounts, Service Control Policies (SCPs), IAM agencies, Identity Center, and per-account infrastructure (VPC, compute, tagging).

## Architecture

```
modules/                          # Shared reusable Terraform modules
+-- rgc-landing-zone/            #   RGC setup (dual path: RGC-managed or raw Organizations)
+-- org-units/                   #   OU hierarchy (max 2 levels)
+-- accounts/                    #   Account creation (regular + security accounts)
+-- scp/                         #   SCP baseline-01 (IAM guard) + policy_attach (always)
+-- iam-agencies/                #   Cross-account agencies + custom policies
+-- identity-center/             #   Permission sets + group assignments
+-- vpc-baseline/                #   VPC + Subnet + Security Group
+-- compute/                     #   KPS keypair + ECS instances
+-- tagging/                     #   FinOps/Sec tag schema

landing-zone/                    # Governance workspace (single remote state)
+-- main.tf                      #   Composes governance modules
+-- provider.tf                  #   master_account + new_account + OBS backend
+-- variables.tf
+-- outputs.tf
+-- Variables/
    +-- non-prod.tfvars
    +-- prod.tfvars

accounts/                        # Per-account infrastructure workspaces
+-- <account-name>/              #   Each = independent TF state
    +-- main.tf                  #     Composes: vpc-baseline, compute, tagging
    +-- provider.tf              #     assume_role into account
    +-- variables.tf
    +-- outputs.tf
    +-- Variables/
        +-- non-prod.tfvars
```

## What's Included

| Path | Description |
|------|-------------|
| `skills/multi-account-landing-zone/SKILL.md` | Complete skill with workflow, module details, SCP templates, and provider configuration patterns |

## Key Design Decisions

| Decision | Choice |
|----------|--------|
| RGC vs raw Organizations | Dual path — ask user at start |
| OU depth | Max 2 levels (L1: IT + business lines, L2: environments) |
| SCP | Baseline-01 (IAM guard) always + policy_attach always included |
| Policy attach | ALWAYS included (SCPs without attach are ineffective) |
| Workspace structure | Modular |
| Account infra | Parallel accounts/ dir, each account = independent workspace |
| Account modules | Fine-grained: vpc-baseline, compute, tagging |
| Governance state | Single remote state in landing-zone/ |
| Account state | Per-account remote state in accounts/<name>/ |

## SCP Baseline-01

The IAM guard SCP denies CRUD actions on users, groups, agencies, and access keys unless performed by approved agencies (BISO admin, CPE admin, RGC administrator). This prevents direct IAM modifications outside of the approved governance workflow.

## Workflow

1. **Discovery** — Ask user: approach (RGC vs raw), region, OU structure, accounts, SCP requirements, IAM agencies, Identity Center, workload specs
2. **Generate** — Create `landing-zone/main.tf` composing governance modules + `accounts/<name>/` for each account with infrastructure
3. **Validate** — Run `terraform init` + `terraform validate` in both governance and account workspaces
4. **Remediate** — Fix common issues: missing policy_attach, provider alias mismatches, missing depends_on

## Related Skills

- [multi-account-landing-zone](../multi-account-landing-zone/SKILL.md) — The skill used in this scenario, also available directly in the Landing Zone directory.

## Video Reference

This scenario corresponds to the training video `landingzonedemo.mkv` (not included in the repository).
