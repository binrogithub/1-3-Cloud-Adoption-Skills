# Azure CosmosDB to Huawei GeminiDB Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **CosmosDB** (Azure) to **GeminiDB** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | CosmosDB | GeminiDB |
| Description | Multi-model NoSQL | NoSQL (managed, Cassandra-compatible) |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-rds-setup | hcloud (target) | Deploy GeminiDB in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create CosmosDB containers-az
2. Export collections and documents
3. Create GeminiDB instance in Huawei Cloud
4. Transform and import data
5. Verify query consistency

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-rds-setup | `./hcloud-rds-setup/` | `~/.config/opencode/skills/hcloud-rds-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## Nota sobre API Keys y Placeholders

Algunos skills en este escenario contienen placeholders (ej. `<YOUR_ADMIN_PASSWORD>`,
`<AZURE_STORAGE_EMULATOR_KEY>`) en lugar de claves reales. Esto se hizo por seguridad
al publicar en un repositorio público.

**Importante:** El modelo que utilice estos skills debe generar API keys fake o de
prueba antes de ejecutar los comandos MCP. Los placeholders deben reemplazarse con
valores válidos para el entorno local antes de usar los skills.

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
