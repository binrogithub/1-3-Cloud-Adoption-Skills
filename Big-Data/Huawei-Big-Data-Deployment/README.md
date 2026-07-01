# Huawei-Big-Data-Deployment

Reusable AI skill for designing and generating Terraform code to deploy big data services on Huawei Cloud.

This skill helps an AI assistant produce GitHub-ready Terraform projects for Huawei Cloud big data environments using reusable modules, environment folders, validation scripts, and deployment guidance.

## Primary services

- VPC
- Subnet
- Security Groups
- OBS
- MRS
- DWS
- DLI General Purpose queue
- CDM
- IAM Agency
- ECS Bastion / Jump Host
- EIP
- KMS
- DataArts Studio, planned for later versions

## Supported deployment patterns

1. Minimal MRS cluster
2. CDM + MRS + OBS data lake
3. MRS + DWS analytics warehouse
4. DLI serverless lakehouse
5. Full big data platform: OBS + MRS + DWS + DataArts-ready baseline
6. CDM + DataArts DataFactory + DWS + OBS reference architecture

## Default assumptions

- Region: `la-north-2`
- Naming convention: `{project}-{env}-{service}-{region}`
- Environments: `dev`, `test`, `prod`, `demo`, `workshop`
- Network is created from zero when not provided
- Public service access is disabled by default
- Bastion host is enabled by default
- NAT Gateway is disabled by default
- Security model: workshop/simple, but no open security group rules unless explicitly requested

## Folder structure

```text
Huawei-Big-Data-Deployment/
  README.md
  SKILL.md
  skill.yaml
  references/
  templates/
    terraform-flat/
    terraform-modular/
  examples/
  scripts/
```

## How to use this skill manually

1. Open `SKILL.md`.
2. Copy the full content.
3. Paste it into the AI assistant as instruction context.
4. Add the deployment request, for example:

```text
Use this skill to generate Terraform for a demo big data platform in Huawei Cloud using OBS, MRS, DWS, DLI, CDM, VPC, IAM agency, and bastion host.
```

## How to use it in a GitHub skill repository

Place this folder under:

```text
Big-Data/Huawei-Big-Data-Deployment/
```

The `SKILL.md` file is the agent-facing instruction file. The `references/` folder provides reusable technical guidance. The `templates/` folder provides Terraform scaffolding.

## Important provider note

Huawei Cloud Terraform resource coverage varies by service, region, and provider version. The skill must always generate Terraform with clear TODO markers when an exact resource argument needs provider or region validation. DataArts Studio Terraform support should be treated as a future extension unless confirmed in the active provider version.
