# AWS ECR to Huawei SWR Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **ECR** (AWS) to **SWR** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | ECR | SWR |
| Description | Container image registry (registry:2) | Software Repository for container images |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-services-quickstart | hcloud (target) | Deploy SWR in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Push container images to ECR
2. List all images and tags
3. Login to Huawei SWR
4. Pull and re-tag images for SWR
5. Push images to SWR
6. Verify images are accessible

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-services-quickstart | `./hcloud-services-quickstart/` | `~/.config/opencode/skills/hcloud-services-quickstart/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
