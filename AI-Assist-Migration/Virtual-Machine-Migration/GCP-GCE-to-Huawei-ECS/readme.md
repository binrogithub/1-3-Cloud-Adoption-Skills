# GCP GCE to Huawei ECS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **GCE** (GCP (floci-gcp)) to **ECS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Cloud | GCP (floci-gcp) | Huawei Cloud |
| Service | GCE | ECS |
| Description | Compute Engine VMs | Elastic Cloud Server |

## Prerequisites

- floci running locally (`floci start && floci wait`)
- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs
- See `../../Cloud-Foundation/Local-Cloud-Emulators/` for floci setup

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| floci-gcp-mcp-setup | floci (source) | Simulate GCE locally |
| floci-multicloud | floci (source) | Simulate GCE locally |
| hcloud-ecs-setup | hcloud (target) | Deploy ECS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create GCE instances in floci-gcp
2. Export instance configurations
3. Select ECS flavor and image in Huawei Cloud
4. Create ECS instances with matching specs
5. Configure networking and security
6. Verify instance accessibility

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| floci-gcp-mcp-setup | `./floci-gcp-mcp-setup/` | `~/.config/opencode/skills/floci-gcp-mcp-setup/SKILL.md` |
| floci-multicloud | `./floci-multicloud/` | `~/.config/opencode/skills/floci-multicloud/SKILL.md` |
| hcloud-ecs-setup | `./hcloud-ecs-setup/` | `~/.config/opencode/skills/hcloud-ecs-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- floci Local Cloud Emulators: `../../Cloud-Foundation/Local-Cloud-Emulators/`
- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
