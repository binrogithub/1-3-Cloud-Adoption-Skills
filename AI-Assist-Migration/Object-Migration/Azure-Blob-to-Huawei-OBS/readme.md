# Azure Blob Storage to Huawei OBS Migration


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **Blob Storage** (Azure) to **OBS** (Huawei Cloud).


| Aspect | Source | Target |
|--------|--------|--------|
| Service | Blob Storage | OBS |
| Description | Block blobs, append blobs | Object Storage Service |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs

## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hcloud-obs-setup | hcloud (target) | Deploy OBS in Huawei Cloud |
| aws-huaweicloud-migration | mapping | AWS to Huawei Cloud service mapping |

## Migration Steps

1. Create Blob containers-az
2. List all blobs and metadata
3. Create OBS buckets in Huawei Cloud
4. Transfer blobs to OBS
5. Verify integrity with MD5 checks

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hcloud-obs-setup | `./hcloud-obs-setup/` | `~/.config/opencode/skills/hcloud-obs-setup/SKILL.md` |
| aws-huaweicloud-migration | `./aws-huaweicloud-migration/` | `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md` |

## Nota sobre API Keys y Placeholders

en lugar de claves reales. Esto se hizo por seguridad al publicar en un repositorio público.

**Importante:** El modelo que utilice este skill debe generar una API key fake o de
prueba y reemplazar el placeholder antes de ejecutar los comandos MCP.

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
