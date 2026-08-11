# AWS KMS to Huawei KMS/DEW Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **KMS + Secrets Manager** (AWS) to **KMS + DEW** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | KMS + Secrets Manager | KMS + DEW |
| Description | Encryption keys and secrets | Encryption keys and data encryption |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-services-quickstart | hcloud (target) | Deploy KMS + DEW in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create KMS keys and secrets
2. Export key metadata and secret values
3. Create KMS keys in Huawei Cloud
4. Import secrets into DEW
5. Verify encryption/decryption works

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-services-quickstart | `./hcloud-services-quickstart/` | `~/.config/opencode/skills/hcloud-services-quickstart/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
