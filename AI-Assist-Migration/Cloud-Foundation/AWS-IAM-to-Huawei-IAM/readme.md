# AWS IAM to Huawei IAM Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **IAM** (AWS) to **IAM** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | IAM | IAM |
| Description | Users, roles, policies, groups | Users, agencies, policies |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-cli-setup | hcloud (target) | Deploy IAM in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create IAM users/roles/policies
2. Export IAM configuration via AWS CLI
3. Map IAM entities to Huawei IAM equivalents
4. Create IAM users and agencies in Huawei Cloud
5. Attach policies and verify permissions

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-cli-setup | `./hcloud-cli-setup/` | `~/.config/opencode/skills/hcloud-cli-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
