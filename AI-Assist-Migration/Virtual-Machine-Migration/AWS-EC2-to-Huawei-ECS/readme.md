# AWS EC2 to Huawei ECS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **EC2** (AWS) to **ECS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | EC2 | ECS |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-ecs-setup | hcloud (target) | Deploy ECS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create EC2 instances (metadata)
2. Export instance configurations
3. Select ECS flavor and image in Huawei Cloud
4. Create ECS instances with matching specs
5. Configure security groups and EIP
6. Verify instance accessibility

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-ecs-setup | `./hcloud-ecs-setup/` | `~/.config/opencode/skills/hcloud-ecs-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
