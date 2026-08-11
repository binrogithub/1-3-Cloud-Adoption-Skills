# AWS CloudWatch to Huawei CES/AOM Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **CloudWatch** (AWS) to **CES + AOM + LTS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | CloudWatch | CES + AOM + LTS |
| Description | Alarms, log groups, metrics | Alarms, log groups, metrics |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-services-quickstart | hcloud (target) | Deploy CES + AOM + LTS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create CloudWatch alarms and log groups
2. Export alarm rules and metric configurations
3. Map to CES alarm rules
4. Create CES alarms in Huawei Cloud
5. Configure AOM for application monitoring
6. Verify alerts fire correctly

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-services-quickstart | `./hcloud-services-quickstart/` | `~/.config/opencode/skills/hcloud-services-quickstart/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
