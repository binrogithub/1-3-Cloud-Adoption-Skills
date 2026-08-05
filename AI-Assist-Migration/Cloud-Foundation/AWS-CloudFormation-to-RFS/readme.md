# AWS CloudFormation to Huawei RFS/AOS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **CloudFormation** (AWS (floci)) to **RFS/AOS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Cloud | AWS (floci) | Huawei Cloud |
| Service | CloudFormation | RFS/AOS |
| Description | Stacks and templates (YAML/JSON) | HCL/Terraform templates and stacks |

## Prerequisites

- floci running locally (`floci start && floci wait`)
- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs
- See `../../Cloud-Foundation/Local-Cloud-Emulators/` for floci setup

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| floci-cloudformation-guide | floci (source) | Simulate CloudFormation locally |
| floci-aws-mcp-setup | floci (source) | Simulate CloudFormation locally |
| hcloud-rfs-aos-guide | hcloud (target) | Deploy RFS/AOS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |
| terraform-codegen | IaC | Terraform code generation |

## Migration Steps

1. Deploy CloudFormation stacks in floci
2. Export template definitions
3. Translate CFN templates to HCL/Terraform
4. Deploy RFS stacks in Huawei Cloud
5. Validate resource parity

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| floci-cloudformation-guide | `./floci-cloudformation-guide/` | `~/.config/opencode/skills/floci-cloudformation-guide/SKILL.md` |
| floci-aws-mcp-setup | `./floci-aws-mcp-setup/` | `~/.config/opencode/skills/floci-aws-mcp-setup/SKILL.md` |
| hcloud-rfs-aos-guide | `./hcloud-rfs-aos-guide/` | `~/.config/opencode/skills/hcloud-rfs-aos-guide/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |
| terraform-codegen | `./terraform-codegen/` | `~/.config/opencode/skills/terraform-codegen/SKILL.md` |

## References

- floci Local Cloud Emulators: `../../Cloud-Foundation/Local-Cloud-Emulators/`
- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
