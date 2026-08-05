# AWS IAM to Huawei IAM Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **IAM** (AWS (floci)) to **IAM** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Cloud | AWS (floci) | Huawei Cloud |
| Service | IAM | IAM |
| Description | Users, roles, policies, groups | Users, agencies, policies |

## Prerequisites

- floci running locally (`floci start && floci wait`)
- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs
- See `../../Cloud-Foundation/Local-Cloud-Emulators/` for floci setup

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| floci-aws-mcp-setup | floci (source) | Simulate IAM locally |
| floci-services-quickstart | floci (source) | Simulate IAM locally |
| hcloud-cli-setup | hcloud (target) | Deploy IAM in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Start floci and create IAM users/roles/policies
2. Export IAM configuration via AWS CLI
3. Map IAM entities to Huawei IAM equivalents
4. Create IAM users and agencies in Huawei Cloud
5. Attach policies and verify permissions

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| floci-aws-mcp-setup | `./floci-aws-mcp-setup/` | `~/.config/opencode/skills/floci-aws-mcp-setup/SKILL.md` |
| floci-services-quickstart | `./floci-services-quickstart/` | `~/.config/opencode/skills/floci-services-quickstart/SKILL.md` |
| hcloud-cli-setup | `./hcloud-cli-setup/` | `~/.config/opencode/skills/hcloud-cli-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- floci Local Cloud Emulators: `../../Cloud-Foundation/Local-Cloud-Emulators/`
- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
