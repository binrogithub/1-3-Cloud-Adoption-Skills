# AWS EC2 to Huawei ECS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **EC2** (AWS (floci)) to **ECS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Cloud | AWS (floci) | Huawei Cloud |
| Service | EC2 | ECS |
| Description | Virtual machines (metadata-only in floci) | Elastic Cloud Server |

## Prerequisites

- floci running locally (`floci start && floci wait`)
- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs
- See `../../Cloud-Foundation/Local-Cloud-Emulators/` for floci setup

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| floci-aws-mcp-setup | floci (source) | Simulate EC2 locally |
| floci-services-quickstart | floci (source) | Simulate EC2 locally |
| hcloud-ecs-setup | hcloud (target) | Deploy ECS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create EC2 instances in floci (metadata)
2. Export instance configurations
3. Select ECS flavor and image in Huawei Cloud
4. Create ECS instances with matching specs
5. Configure security groups and EIP
6. Verify instance accessibility

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| floci-aws-mcp-setup | `./floci-aws-mcp-setup/` | `~/.config/opencode/skills/floci-aws-mcp-setup/SKILL.md` |
| floci-services-quickstart | `./floci-services-quickstart/` | `~/.config/opencode/skills/floci-services-quickstart/SKILL.md` |
| hcloud-ecs-setup | `./hcloud-ecs-setup/` | `~/.config/opencode/skills/hcloud-ecs-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- floci Local Cloud Emulators: `../../Cloud-Foundation/Local-Cloud-Emulators/`
- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
