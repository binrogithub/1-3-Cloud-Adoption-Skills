# huawei-snowflake-to-dataarts-migration

## Resumen

Skill para orquestar o asistir la migración desde Snowflake hacia Huawei Cloud DataArts (Factory + DLI), utilizando el dataarts-deploy-agent MCP para generación de planes, ejecución y validación de equivalencia.

## Problema que resuelve

Migrar cargas de trabajo analíticas desde Snowflake a Huawei Cloud DataArts requiere adaptación de SQL, mapeo de schemas, creación de jobs en DataArts Factory, ejecución en DLI, y validación de equivalencia de resultados. Sin orquestación, el proceso es manual y propenso a inconsistencias.

## Escenario soportado

- **Origen**: Snowflake (SQL tasks, task graphs, schemas)
- **Destino**: Huawei Cloud DataArts Factory + DLI
- **Mecanismo**: Artifact-based migration con SQL adaptation
- **Alcance actual**: Demo/POC flow (one-shot)

## Arquitectura

```
Snowflake                          Huawei Cloud
┌──────────────┐                   ┌──────────────────────┐
│ SQL Tasks    │──manual extract──>│ Migration Artifacts  │
│ Task Graphs  │                   │ (SQL, manifest)      │
│ Schemas      │                   └──────────┬───────────┘
└──────────────┘                              │
                                    dataarts-deploy-agent
                                              │
                                   ┌──────────▼───────────┐
                                   │ DataArts Factory     │
                                   │  └── Jobs (adapted) │
                                   │ DLI                  │
                                   │  └── SQL execution   │
                                   └──────────────────────┘
```

Adapters available: legacy-demo, native-dli, koocli, runtime-engine

## MCP utilizados

| MCP | Obligatorio | Propósito | Read/Write | Riesgo |
|---|---|---|---|---|
| dataarts-deploy-agent | Sí | Plan, ejecutar, monitorear y validar migración Snowflake→DataArts | Read + Write | Medium (write requiere confirm) |
| huaweicloud-pricing | No | Estimar costos de DataArts/DLI | Read-only | None |
| huaweicloud-ticket | No | Crear ticket de soporte | Read + Write | Medium |
| playwright | No | Automación de consola | Read + Write | Medium |

## Capacidades

- Plan generation (read-only, safe)
- Synchronous execution (demo_run with confirm=true)
- Asynchronous execution (demo_start with confirm=true)
- Status monitoring
- Equivalence validation (source vs target results)
- Report generation with secret scrubbing
- Stale result detection

## Flujo general

1. Discovery → 2. Architecture Validation → 3. Readiness → 4. Plan → 5. Approval → 6. Execution → 7. Validation → 8. Cutover (N/A for demo) → 9. Rollback → 10. Closure

## Nivel de automatización

| Fase | Estado | Responsable |
|---|---|---|
| Discovery | AUTOMATED | Agente |
| Architecture Validation | ASSISTED | Agente + Humano |
| Readiness and Prechecks | ASSISTED | Agente + Humano |
| Plan Generation | AUTOMATED | Agente |
| Approval | MANUAL | Humano |
| Execution | ASSISTED | Agente + Humano |
| Validation | AUTOMATED | Agente |
| Cutover | NOT_IMPLEMENTED | N/A (demo only) |
| Rollback | MANUAL | Humano |
| Closure and Reporting | AUTOMATED | Agente |

## Prerrequisitos

- Migration artifacts prepared (SQL files, manifest, expected results)
- DLI queue configured and available
- DataArts Factory workspace configured
- Huawei Cloud credentials with DataArts and DLI access
- dataarts-deploy-agent MCP configured and operational

## Entradas

- job_name: Nombre del job en DataArts Factory
- artifact_dir: Ruta al directorio de artefactos de migración
- dli_queue: Nombre de la cola DLI (default: "default")

## Salidas

- migration-plan.md
- execution-status.json
- equivalence-summary.md
- demo-report.md
- validation-results.json

## Instalación

```bash
cd <INSTALLATION_ROOT>/shared-mcps/dataarts-deploy-agent
npm install
```

## Configuración

```json
{
  "skills": {
    "huawei-snowflake-to-dataarts-migration": {
      "path": "<INSTALLATION_ROOT>/skills/huawei-snowflake-to-dataarts-migration"
    }
  },
  "mcp": {
    "dataarts-deploy-agent": {
      "path": "<INSTALLATION_ROOT>/shared-mcps/dataarts-deploy-agent"
    }
  }
}
```

## Uso con OpenCode o Hermes

1. Cargar la skill: `skill huawei-snowflake-to-dataarts-migration`
2. Seguir el workflow documentado en SKILL.md
3. Las fases AUTOMATED serán ejecutadas por el agente
4. Las fases ASSISTED requieren revisión humana
5. Las fases MANUAL requieren ejecución humana

## Ejemplo seguro

```
# Fase 1: Discovery (read-only)
snowflake_dataarts_demo_plan({
  job_name: "customer_status_pipeline",
  artifact_dir: "./artifacts/customer_status_pipeline_simple",
  dli_queue: "default"
})

# Fase 4: Plan generation (read-only)
snowflake_dataarts_demo_plan({
  job_name: "customer_status_pipeline",
  artifact_dir: "./artifacts/customer_status_pipeline_simple"
})

# Fase 7: Validation (read-only)
snowflake_dataarts_demo_equivalence_summary({
  job_name: "customer_status_pipeline"
})

snowflake_dataarts_demo_last_report({
  job_name: "customer_status_pipeline"
})
```

## Aprobaciones requeridas

- Ejecutar migración (demo_run con confirm=true)
- Iniciar migración asíncrona (demo_start con confirm=true)
- Cutover (no aplicable en demo, requerido en producción futura)
- Rollback de recursos DataArts/DLI

## Validación

- Equivalence summary: Comparación de resultados Snowflake vs DataArts/DLI
- Row count match
- Value match
- Schema match
- Report review

## Rollback

1. Limpiar jobs de DataArts Factory creados
2. Limpiar tablas/datos DLI creados
3. Revertir a Snowflake como fuente de verdad
4. Documentar razón de rollback

## Manejo de gaps de capacidad

| Gap ID | Descripción | Decisión |
|---|---|---|
| GAP-DA-001 | No automated Snowflake source extraction | MANUAL_STEP |
| GAP-DA-002 | No automated schema mapping | MANUAL_STEP |
| GAP-DA-003 | No automated SQL compatibility analysis | MANUAL_STEP |
| GAP-DA-004 | No production migration flow | NOT_REQUIRED (demo only) |
| GAP-DA-005 | No automated rollback of DataArts resources | MANUAL_STEP |
| GAP-DA-006 | No incremental/delta migration support | NOT_REQUIRED (demo only) |

## Pruebas

- Golden package validation: orders_pipeline_simple (runtime-confirmed) [VERIFIED_FROM_DOCUMENTATION]
- Golden package validation: customer_status_pipeline_simple (package/dry-run validated) [VERIFIED_FROM_DOCUMENTATION]
- Secret scrubbing verified [VERIFIED_FROM_CODE]
- confirm=true gate verified [VERIFIED_FROM_CODE]
- Stale result detection verified [VERIFIED_FROM_CODE]

## Seguridad

- Secret scrubbing automático en reportes
- confirm=true requerido para operaciones write
- Stale result detection previene uso de resultados obsoletos
- No se exponen credenciales en reportes

## Limitaciones

- Solo flujo demo/POC soportado
- Extracción de Snowflake es manual
- Mapeo de schemas es manual
- No hay migración incremental/delta
- No hay rollback automatizado de DataArts
- Cutover no aplicable en demo

## Troubleshooting

| Problema | Solución |
|---|---|
| Plan generation falla | Verificar artifact package, DLI queue, credenciales |
| Execution falla | Revisar logs DataArts Factory, DLI job logs, SQL errors |
| Equivalence mismatch | Revisar SQL adaptation, data types, NULL handling |
| Stale results | Limpiar estado de run anterior |

## Estado de madurez

**PARTIAL**

El flujo demo/POC funciona end-to-end con validación de equivalencia. La migración producción completa no está disponible.

## Evidencia utilizada

| Evidencia | Tipo |
|---|---|
| 6 dataarts-deploy-agent tools disponibles | VERIFIED_FROM_CODE |
| 2 write tools requieren confirm=true | VERIFIED_FROM_CODE |
| Golden packages validados | VERIFIED_FROM_DOCUMENTATION |
| Secret scrubbing implementado | VERIFIED_FROM_CODE |
| Demo flow documentado | VERIFIED_FROM_DOCUMENTATION |
| Production migration NO disponible | VERIFIED_FROM_DOCUMENTATION |
| Snowflake extraction NO automatizado | NOT_VERIFIED |
