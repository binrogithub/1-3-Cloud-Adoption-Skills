# AWS ElastiCache to Huawei DCS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **ElastiCache** (AWS) to **DCS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | ElastiCache | DCS |
| Description | Redis/Valkey cache (Docker container) | Distributed Cache Service (Redis) |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-rds-setup | hcloud (target) | Deploy DCS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create ElastiCache cluster
2. Dump Redis data (RDB/AOF)
3. Create DCS instance in Huawei Cloud
4. Import Redis data dump
5. Verify cache hits and performance

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-rds-setup | `./hcloud-rds-setup/` | `~/.config/opencode/skills/hcloud-rds-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## Nota sobre API Keys y Placeholders

El skill `hcloud-rds-setup` contiene placeholders (ej. `<YOUR_ADMIN_PASSWORD>`) en
lugar de claves reales. Esto se hizo por seguridad al publicar en un repositorio público.

**Importante:** El modelo que utilice este skill debe generar una contraseña fake o de
prueba y reemplazar el placeholder antes de ejecutar los comandos MCP.

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
