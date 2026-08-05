# AWS ECR to Huawei SWR Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **ECR** (AWS (floci)) to **SWR** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Cloud | AWS (floci) | Huawei Cloud |
| Service | ECR | SWR |
| Description | Container image registry (registry:2) | Software Repository for container images |

## Prerequisites

- floci running locally (`floci start && floci wait`)
- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs
- See `../../Cloud-Foundation/Local-Cloud-Emulators/` for floci setup

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| floci-aws-mcp-setup | floci (source) | Simulate ECR locally |
| floci-services-quickstart | floci (source) | Simulate ECR locally |
| hcloud-services-quickstart | hcloud (target) | Deploy SWR in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Push container images to floci ECR
2. List all images and tags
3. Login to Huawei SWR
4. Pull and re-tag images for SWR
5. Push images to SWR
6. Verify images are accessible

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| floci-aws-mcp-setup | `./floci-aws-mcp-setup/` | `~/.config/opencode/skills/floci-aws-mcp-setup/SKILL.md` |
| floci-services-quickstart | `./floci-services-quickstart/` | `~/.config/opencode/skills/floci-services-quickstart/SKILL.md` |
| hcloud-services-quickstart | `./hcloud-services-quickstart/` | `~/.config/opencode/skills/hcloud-services-quickstart/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- floci Local Cloud Emulators: `../../Cloud-Foundation/Local-Cloud-Emulators/`
- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
