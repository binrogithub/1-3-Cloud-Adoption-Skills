# Azure CosmosDB to Huawei GeminiDB Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **CosmosDB** (Azure (floci-az)) to **GeminiDB** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Cloud | Azure (floci-az) | Huawei Cloud |
| Service | CosmosDB | GeminiDB |
| Description | Multi-model NoSQL | NoSQL (managed, Cassandra-compatible) |

## Prerequisites

- floci running locally (`floci start && floci wait`)
- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs
- See `../../Cloud-Foundation/Local-Cloud-Emulators/` for floci setup

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| floci-az-mcp-setup | floci (source) | Simulate CosmosDB locally |
| floci-multicloud | floci (source) | Simulate CosmosDB locally |
| hcloud-rds-setup | hcloud (target) | Deploy GeminiDB in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create CosmosDB containers in floci-az
2. Export collections and documents
3. Create GeminiDB instance in Huawei Cloud
4. Transform and import data
5. Verify query consistency

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| floci-az-mcp-setup | `./floci-az-mcp-setup/` | `~/.config/opencode/skills/floci-az-mcp-setup/SKILL.md` |
| floci-multicloud | `./floci-multicloud/` | `~/.config/opencode/skills/floci-multicloud/SKILL.md` |
| hcloud-rds-setup | `./hcloud-rds-setup/` | `~/.config/opencode/skills/hcloud-rds-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## Nota sobre API Keys y Placeholders

Algunos skills en este escenario contienen placeholders (ej. `<YOUR_ADMIN_PASSWORD>`,
`<AZURE_STORAGE_EMULATOR_KEY>`) en lugar de claves reales. Esto se hizo por seguridad
al publicar en un repositorio público.

**Importante:** El modelo que utilice estos skills debe generar API keys fake o de
prueba antes de ejecutar los comandos MCP. Los placeholders deben reemplazarse con
valores válidos para el entorno local (floci/floci-az) antes de usar los skills.

## References

- floci Local Cloud Emulators: `../../Cloud-Foundation/Local-Cloud-Emulators/`
- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
