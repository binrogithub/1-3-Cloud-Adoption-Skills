# Azure VM to Huawei ECS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **Azure VM** (Azure) to **ECS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | Azure VM | ECS |
| Description | Virtual machines | Elastic Cloud Server |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-ecs-setup | hcloud (target) | Deploy ECS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create Azure VMs-az
2. Export VM configurations
3. Select ECS flavor and image in Huawei Cloud
4. Create ECS instances with matching specs
5. Configure networking and security
6. Verify instance accessibility

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-ecs-setup | `./hcloud-ecs-setup/` | `~/.config/opencode/skills/hcloud-ecs-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## Nota sobre API Keys y Placeholders

en lugar de claves reales. Esto se hizo por seguridad al publicar en un repositorio público.

**Importante:** El modelo que utilice este skill debe generar una API key fake o de
prueba y reemplazar el placeholder antes de ejecutar los comandos MCP.

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
