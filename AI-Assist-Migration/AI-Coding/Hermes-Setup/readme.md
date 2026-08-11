# Hermes Agent Setup


> **Status: Beta — Under active testing.** Content may change as scenarios are validated in real migration workflows.

## Overview

Migration from **Hermes Agent** (N/A) to **Hermes Agent** (Hermes).


| Aspect | Source | Target |
|--------|--------|--------|
| Cloud | N/A | Hermes |
| Service | Hermes Agent | Hermes Agent |
| Description | Local Linux setup | Configured on Linux (Ubuntu 24.04+) |

## Prerequisites

- hcloud CLI configured with AK/SK credentials
- Network access to Huawei Cloud APIs


## Skills Required

| Skill | Type | Purpose |
|-------|------|---------|
| hermes-setup | utility | Configuration and setup |

## Migration Steps

1. Copy hermes-repro directory to target PC
2. Run install.sh (idempotent)
3. Replace PLACEHOLDER_* values with real API keys
4. Verify Hermes Agent is running

## Skill Locations

| Skill | Repo Path | OpenCode Path |
|-------|-----------|---------------|
| hermes-setup | `./hermes-setup/` | `~/.config/opencode/skills/hermes-setup/SKILL.md` |

## Nota sobre API Keys y Placeholders

El skill `hermes-setup` contiene placeholders para URLs y claves de Huawei Cloud MaaS
en lugar de valores reales. Esto se hizo por seguridad al publicar en un repositorio público.

**Importante:** El modelo que utilice este skill debe generar API keys fake o de
prueba y reemplazar los placeholders antes de ejecutar los comandos MCP.

## References

- OpenCode skills directory: `~/.config/opencode/skills/`
- AWS to Huawei Cloud service mapping: `~/.config/opencode/skills/aws-huaweicloud-migration/SKILL.md`
