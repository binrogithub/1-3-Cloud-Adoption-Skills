# AWS ECS Fargate to Huawei CCE Volcano Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **ECS + Fargate** (AWS) to **CCE + Volcano** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | ECS + Fargate | CCE + Volcano |
| Description | Serverless Docker tasks | Serverless Kubernetes pods |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-cce-setup | hcloud (target) | Deploy CCE + Volcano in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Run ECS tasks
2. Export task definitions
3. Create CCE cluster with Volcano scheduler
4. Translate task defs to Kubernetes manifests
5. Deploy as serverless pods
6. Verify autoscaling and execution

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-cce-setup | `./hcloud-cce-setup/` | `~/.config/opencode/skills/hcloud-cce-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
