# AWS ElastiCache to Huawei DCS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **ElastiCache** (AWS (floci)) to **DCS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Cloud | AWS (floci) | Huawei Cloud |
| Service | ElastiCache | DCS |
| Description | Redis/Valkey cache (Docker container) | Distributed Cache Service (Redis) |

## Prerequisites

- floci running locally (`floci start && floci wait`)
- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs
- See `../../Cloud-Foundation/Local-Cloud-Emulators/` for floci setup

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| floci-aws-mcp-setup | floci (source) | Simulate ElastiCache locally |
| floci-services-quickstart | floci (source) | Simulate ElastiCache locally |
| hcloud-rds-setup | hcloud (target) | Deploy DCS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create ElastiCache cluster in floci
2. Dump Redis data (RDB/AOF)
3. Create DCS instance in Huawei Cloud
4. Import Redis data dump
5. Verify cache hits and performance

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| floci-aws-mcp-setup | `./floci-aws-mcp-setup/` | `~/.config/opencode/skills/floci-aws-mcp-setup/SKILL.md` |
| floci-services-quickstart | `./floci-services-quickstart/` | `~/.config/opencode/skills/floci-services-quickstart/SKILL.md` |
| hcloud-rds-setup | `./hcloud-rds-setup/` | `~/.config/opencode/skills/hcloud-rds-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## Nota sobre API Keys y Placeholders

El skill `hcloud-rds-setup` contiene placeholders (ej. `<YOUR_ADMIN_PASSWORD>`) en
lugar de claves reales. Esto se hizo por seguridad al publicar en un repositorio público.

**Importante:** El modelo que utilice este skill debe generar una contraseña fake o de
prueba y reemplazar el placeholder antes de ejecutar los comandos MCP.

## References

- floci Local Cloud Emulators: `../../Cloud-Foundation/Local-Cloud-Emulators/`
- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
