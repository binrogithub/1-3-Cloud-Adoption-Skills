# GCP Cloud Storage to Huawei OBS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **GCS** (GCP) to **OBS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | GCS | OBS |
| Description | Object storage buckets | Object Storage Service |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-obs-setup | hcloud (target) | Deploy OBS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create GCS buckets-gcp
2. List all objects and metadata
3. Create OBS buckets in Huawei Cloud
4. Transfer objects to OBS
5. Verify object integrity

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-obs-setup | `./hcloud-obs-setup/` | `~/.config/opencode/skills/hcloud-obs-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
