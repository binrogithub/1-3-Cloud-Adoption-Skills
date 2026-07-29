---
name: multi-account-landing-zone
description: Build HuaweiCloud multi-account landing zone Terraform code with modular governance (OUs, accounts, SCP, IAM, Identity Center) and per-account infrastructure (VPC, compute, tagging)
license: MIT
compatibility: opencode
metadata:
  audience: platform-engineers
  workflow: landing-zone
  provider: huaweicloud
---

## What I do

- Build modular HuaweiCloud multi-account landing zone Terraform code
- Generate governance workspace (OUs, accounts, SCP with policy_attach, IAM agencies, Identity Center)
- Generate per-account infrastructure workspaces (VPC, compute, tagging)
- Support dual path: RGC-managed or raw Organizations
- Always include `huaweicloud_organizations_policy_attach` (SCPs without attach are ineffective)
- Enforce FinOps/Sec tag governance across accounts
- Validate generated code with `terraform init` + `terraform validate`

## When to use me

Use this skill when the user asks to:
- Create or modify a HuaweiCloud landing zone
- Set up multi-account organization structure (OUs, accounts)
- Configure Service Control Policies (SCPs)
- Set up Identity Center permission sets and account assignments
- Create cross-account IAM agencies and custom policies
- Deploy per-account infrastructure (VPC, compute, networking)
- Manage FinOps/security tagging across accounts

## Architecture

```
modules/                          # Shared reusable Terraform modules
├── rgc-landing-zone/            #   RGC setup (dual path: RGC-managed or raw Organizations)
├── org-units/                   #   OU hierarchy (max 2 levels)
├── accounts/                    #   Account creation (regular + security accounts)
├── scp/                         #   SCP baseline-01 (IAM guard) + policy_attach (always)
├── iam-agencies/                #   Cross-account agencies + custom policies
├── identity-center/             #   Permission sets + group assignments
├── vpc-baseline/                #   VPC + Subnet + Security Group
├── compute/                     #   KPS keypair + ECS instances
└── tagging/                     #   FinOps/Sec tag schema

landing-zone/                    # Governance workspace (single remote state)
├── main.tf                      #   Composes governance modules
├── provider.tf                  #   master_account + new_account + OBS backend
├── variables.tf
├── outputs.tf
└── Variables/
    ├── non-prod.tfvars
    └── prod.tfvars

accounts/                        # Per-account infrastructure workspaces
├── <account-name>/              #   Each = independent TF state
│   ├── main.tf                  #     Composes: vpc-baseline, compute, tagging
│   ├── provider.tf              #     assume_role into account
│   ├── variables.tf
│   ├── outputs.tf
│   └── Variables/
│       └── non-prod.tfvars
└── ...
```

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

## Workflow

### Step 1: Discovery Questions

Ask the user these questions before generating any code:

1. **Approach**: RGC-managed or raw Organizations? (RGC is recommended for new landing zones; raw Organizations for existing orgs or when RGC is not available)
2. **Region**: Home region (e.g., la-south-2)
3. **Root OU ID**: The root organization unit ID
4. **OU Structure**:
   - Level-1 OUs: IT OU name + business line OU names (e.g., Infrastructure, BSS, CBS)
   - Security OUs at L1: SecOps, Log-Archive, Audit (optional, can use parent_id different from root)
5. **Level-2 OUs**: Environment OUs under each business line (e.g., Production, NonProduction, or Prod/Dev/Test)
6. **Accounts**: List of accounts with name, agency_name, description, target OU, tags
7. **Security Accounts**: Dedicated security/logging/audit accounts (if applicable)
8. **SCP Requirements**: Which entities (root, OUs, accounts) to attach baseline-01 to? Region lock needed?
9. **IAM Agencies**: BISO admin agency, CPE admin agency, or custom agencies?
10. **Identity Center**: Permission sets, group-to-account assignments?
11. **Workload**: Which accounts need VPC/compute baseline? What specs?

### Step 2: Generate Code

Generate all files based on answers. Module source code already exists in `modules/`. Compose them in:

1. `landing-zone/main.tf` — root composition of governance modules
2. `landing-zone/Variables/*.tfvars` — populated from user answers
3. `accounts/<name>/` — copy from `accounts/_template/` and customize for each account that needs infrastructure

### Step 3: Validate

Run `terraform init` and `terraform validate` in both `landing-zone/` and each `accounts/` workspace.

### Step 4: Remediate

Fix common issues:
- Missing `huaweicloud_organizations_policy_attach` (SCPs without attach)
- Provider alias mismatches (master_account vs new_account)
- Missing `depends_on` for OU hierarchy
- Incorrect parent_id references

## Module Details

### rgc-landing-zone
- `huaweicloud_rgc_landing_zone` — Initial setup (home region, Identity Center, logging/audit accounts, region config)
- `huaweicloud_rgc_organizational_unit` — RGC-managed OUs (CORE + CUSTOM types)
- `huaweicloud_rgc_account` — RGC-managed accounts (with optional blueprint)
- `huaweicloud_rgc_control` — Governance controls on OUs

### org-units
- Level-1 OUs with `for_each` (IT, business lines, security OUs)
- Level-2 OUs with `for_each` + `depends_on` on level-1
- Parent resolution by name for level-2

### accounts
- Regular accounts under level-2 OUs (environment-scoped)
- Security/logging/audit accounts under level-1 OUs
- `OrganizationAccountAccessAgency` pattern
- Account tags

### scp
- `huaweicloud_organizations_policy` — SCP definition with inline JSON
- `huaweicloud_organizations_policy_attach` — ALWAYS included (attach to root, OUs, or accounts)
- Baseline-01 template: IAM guard (deny user/group/agency CRUD except via approved agencies)
- Optional region lock via `g:RequestedRegion` condition
- `flat_scp` local for flattening entity_ids

### iam-agencies
- `huaweicloud_identity_agency` — Cross-account agency creation
- `huaweicloud_identity_policy` — Custom policies
- `huaweicloud_identity_policy_agency_attach` — Policy-to-agency attachment
- Configurable provider: master_account or new_account

### identity-center
- `huaweicloud_identitycenter_permission_set` — Permission sets
- `huaweicloud_identitycenter_system_policy_attachment` — System policy attachment
- `huaweicloud_identitycenter_account_assignment` — Group-to-account assignment
- Data sources: identitycenter_instance, identitycenter_groups, organizations_accounts

### vpc-baseline
- `huaweicloud_vpc` — VPC creation
- `huaweicloud_vpc_subnet` — Subnet with gateway_ip, availability_zone, DHCP
- `huaweicloud_networking_secgroup` — Security group
- `huaweicloud_networking_secgroup_rule` — Security group rules (ICMP baseline + custom)

### compute
- `huaweicloud_kps_keypair` — SSH key pair
- `huaweicloud_compute_instance` — ECS instances with for_each

### tagging
- Enforces FinOps/Sec tag schema on resources
- Tag keys: financial_team, technical_team, finops_business, finops_cost_center, negocio, finops_budget_cod, sec_confidentiality, info_app, region

## SCP Baseline-01 Template

The IAM guard SCP denies the following actions unless performed by approved agencies:
- `organizations:*:*`
- `iam:users:create/delete/update`
- `iam:groups:create/delete`
- `iam::createAccessKey/deleteAccessKey`
- `iam:groups:attachPolicyV5/detachPolicyV5`
- `iam:users:attachPolicyV5/detachPolicyV5`
- `iam:agencies:attachPolicyV5/detachPolicyV5`
- `identitycenter:*:*`
- `iam:agencies:create/update/delete`

Excepted principals (StringNotMatch on g:PrincipalUrn):
- `sts::*:assumed-agency:hwc-biso-admin-agency*`
- `sts::*:assumed-agency:hwc-cpe-rw-agency*`
- `sts::*:assumed-agency:SysReservedV3_PS-hwc-teco-ar-biso-sample*`
- `sts::*:assumed-agency:SysReservedV3_RGCAdministratorAccess_*`
- `sts::*:assumed-agency:SysReservedV3_RGCOrganizationsFullAccess_*`
- `sts::*:assumed-agency:SysReservedV3_RGCPowerUserAccess_*`
- `sts::*:assumed-agency:SysReservedV3_RGC_COE_CLOUD_CPE_RW_*`

Optional: Add `g:RequestedRegion` condition to restrict to specific region.

## Provider Configuration Pattern

### Governance workspace (landing-zone/)
```hcl
provider "huaweicloud" {
  alias  = "master_account"
  region = var.region
}

data "huaweicloud_organizations_accounts" "this" {
  provider = huaweicloud.master_account
  name     = var.new_account_name
}

provider "huaweicloud" {
  alias  = "new_account"
  region = var.region
  assume_role {
    agency_name = "OrganizationAccountAccessAgency"
    domain_id   = data.huaweicloud_organizations_accounts.this.accounts[0].id
  }
}
```

### Account workspace (accounts/<name>/)
```hcl
provider "huaweicloud" {
  region = var.region
  assume_role {
    agency_name = var.agency_name
    domain_id   = var.account_id
  }
}
```

## Backend Configuration Pattern

```hcl
terraform {
  backend "s3" {
    bucket    = "terraformbucket"
    key       = "landing-zone/terraform.tfstate"
    region    = var.region
    endpoints = {
      s3 = "https://obs.<region>.myhuaweicloud.com"
    }
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
  }
}
```

For account workspaces, change the key to `accounts/<account-name>/terraform.tfstate`.
