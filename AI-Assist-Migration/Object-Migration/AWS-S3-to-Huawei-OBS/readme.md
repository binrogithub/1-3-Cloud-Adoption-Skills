# AWS S3 to Huawei OBS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **S3** (AWS) to **OBS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | S3 | OBS |
| Description | Object storage (in-process) | Object Storage Service |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-obs-setup | hcloud (target) | Deploy OBS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create S3 buckets and upload objects
2. List all buckets, objects, and metadata
3. Create OBS buckets in Huawei Cloud
4. Sync objects using obsutil or OMS
5. Verify object counts and checksums

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-obs-setup | `./hcloud-obs-setup/` | `~/.config/opencode/skills/hcloud-obs-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
