# AWS CloudFormation to Huawei RFS/AOS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **CloudFormation** (AWS) to **RFS/AOS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | CloudFormation | RFS/AOS |
| Description | Stacks and templates (YAML/JSON) | HCL/Terraform templates and stacks |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-rfs-aos-guide | hcloud (target) | Deploy RFS/AOS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |
| terraform-codegen | IaC | Terraform code generation |

## Migration Steps

1. Deploy CloudFormation stacks
2. Export template definitions
3. Translate CFN templates to HCL/Terraform
4. Deploy RFS stacks in Huawei Cloud
5. Validate resource parity

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-rfs-aos-guide | `./hcloud-rfs-aos-guide/` | `~/.config/opencode/skills/hcloud-rfs-aos-guide/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |
| terraform-codegen | `./terraform-codegen/` | `~/.config/opencode/skills/terraform-codegen/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
