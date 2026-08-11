# AWS VPC to Huawei VPC Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **VPC** (AWS) to **VPC** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | VPC | VPC |
| Description | VPC, subnets, security groups, route tables, NAT, IGW | VPC, subnets, security groups, route tables, NAT gateway, EIP |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-vpc-networking | hcloud (target) | Deploy VPC in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create VPC topology (subnets, SG, routes, NAT)
2. Export network configuration
3. Map to Huawei VPC equivalents
4. Create VPC and subnets in Huawei Cloud
5. Configure security groups and NAT gateway
6. Verify connectivity

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-vpc-networking | `./hcloud-vpc-networking/` | `~/.config/opencode/skills/hcloud-vpc-networking/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
