# Huawei Cloud Migration Skills

## Propósito

Biblioteca organizada por skills de migración para Huawei Cloud. Cada skill representa un escenario completo de migración, orquesta uno o varios MCP, y documenta claramente sus capacidades, limitaciones y gaps.

La unidad funcional principal es la **skill de migración**, no el MCP individual.

## Arquitectura

```
huawei-cloud-migration-skills-handoff/
├── skills/              # Skills de migración (unidad principal)
├── shared-skills/       # Skills compartidas (mcp-capability-builder)
├── shared-mcps/         # MCP compartidos (referencias)
├── integrations/        # Integraciones externas (Playwright)
├── shared/              # Documentación, schemas, templates compartidos
├── inventory/           # Registros y matrices de dependencia
└── reports/             # Reportes de análisis y validación
```

## Catálogo de skills

| Skill | Escenario | MCP principal | Riesgo | Madurez |
|---|---|---|---|---|
| huawei-cce-cross-region-velero-migration | CCE cross-region con Velero | huaweicloud-deploy | High | EXPERIMENTAL |
| huawei-postgresql-ecs-to-rds-drs-cross-region | PostgreSQL ECS→RDS con DRS | huaweicloud-drs | High | READY_WITH_WARNINGS |
| huawei-snowflake-to-dataarts-migration | Snowflake→DataArts | dataarts-deploy-agent | Medium | PARTIAL |
| mcp-capability-builder | Análisis de gaps y generación de MCP | Ninguno | Low | READY_WITH_WARNINGS |

## Cómo funciona una skill

1. Una skill se carga en el agente (OpenCode/Hermes)
2. El agente lee SKILL.md para instrucciones operativas
3. El agente lee skill.yaml para configuración
4. El agente verifica que los MCP requeridos estén disponibles
5. El agente sigue el workflow fase por fase
6. Cada fase clasifica su nivel de automatización
7. Los gaps de capacidad se documentan y manejan explícitamente

## Relación entre skills y MCP

| Skill | Pricing | Deploy | DRS | Ticket | DataArts | Playwright |
|---|---|---|---|---|---|---|
| CCE Velero | optional | **required** | - | optional | - | optional |
| PostgreSQL DRS | optional | - | **required** | optional | - | - |
| Snowflake DataArts | optional | - | - | optional | **required** | optional |
| Capability Builder | - | - | - | - | - | - |

## Capability gap workflow

1. Skill identifica un gap durante una fase
2. Gap se documenta con ID, fase, capacidad requerida
3. Se invoca mcp-capability-builder para análisis
4. Decisión: USE_EXISTING_TOOL, EXTEND_EXISTING_MCP, CREATE_NEW_MCP, MANUAL_STEP
5. Si se genera un MCP: marcado como DRAFT, requiere revisión manual
6. Nunca se activa automáticamente

## Cómo generar un MCP faltante

1. Identificar el gap real (no solo un nombre diferente)
2. Invocar mcp-capability-builder con los detalles del gap
3. Revisar el scaffold generado
4. Ejecutar pruebas locales
5. Completar la implementación
6. Revisión de seguridad
7. Promover de DRAFT → EXPERIMENTAL → READY_FOR_REVIEW → READY

## Instalación

Ver [shared/docs/installation.md](shared/docs/installation.md)

## Configuración

Ver [shared/docs/opencode-integration.md](shared/docs/opencode-integration.md)

## Uso con OpenCode

```bash
# Cargar una skill
skill huawei-postgresql-ecs-to-rds-drs-cross-region

# Seguir el workflow guiado por el agente
```

## Uso con Hermes

Similar a OpenCode. Cargar la skill y seguir el workflow.

## Pruebas

Ver [reports/test-report.md](reports/test-report.md)

## Seguridad

Ver [SECURITY.md](SECURITY.md) y [shared/docs/security-guidelines.md](shared/docs/security-guidelines.md)

## Publicación en Git

1. Crear repositorio Git
2. Copiar contenido del ZIP al repositorio
3. Verificar que no hay secrets (ver security-scan-report.md)
4. Commit inicial
5. Configurar CI/CD para validación de skills

## Limitaciones

- CCE cross-region Velero: EXPERIMENTAL (la mayoría de fases son manuales)
- Snowflake→DataArts: PARTIAL (solo demo/POC flow)
- DRS VPN: NOT_IMPLEMENTED (solo Internet público)
- DRS pricing: BLOCKED en huaweicloud-pricing MCP

## Estado de los escenarios

| Escenario | Madurez | Fases automatizadas | Gaps |
|---|---|---|---|
| CCE cross-region Velero | EXPERIMENTAL | 0/10 | 7 |
| PostgreSQL ECS→RDS DRS | READY_WITH_WARNINGS | 4/10 | 7 |
| Snowflake→DataArts | PARTIAL | 4/10 | 6 |
