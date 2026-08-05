# GCP Cloud Storage to Huawei OBS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **GCS** (GCP (floci-gcp)) to **OBS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Cloud | GCP (floci-gcp) | Huawei Cloud |
| Service | GCS | OBS |
| Description | Object storage buckets | Object Storage Service |

## Prerequisites

- floci running locally (`floci start && floci wait`)
- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs
- See `../../Cloud-Foundation/Local-Cloud-Emulators/` for floci setup

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| floci-gcp-mcp-setup | floci (source) | Simulate GCS locally |
| floci-multicloud | floci (source) | Simulate GCS locally |
| hcloud-obs-setup | hcloud (target) | Deploy OBS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create GCS buckets in floci-gcp
2. List all objects and metadata
3. Create OBS buckets in Huawei Cloud
4. Transfer objects to OBS
5. Verify object integrity

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| floci-gcp-mcp-setup | `./floci-gcp-mcp-setup/` | `~/.config/opencode/skills/floci-gcp-mcp-setup/SKILL.md` |
| floci-multicloud | `./floci-multicloud/` | `~/.config/opencode/skills/floci-multicloud/SKILL.md` |
| hcloud-obs-setup | `./hcloud-obs-setup/` | `~/.config/opencode/skills/hcloud-obs-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- floci Local Cloud Emulators: `../../Cloud-Foundation/Local-Cloud-Emulators/`
- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
