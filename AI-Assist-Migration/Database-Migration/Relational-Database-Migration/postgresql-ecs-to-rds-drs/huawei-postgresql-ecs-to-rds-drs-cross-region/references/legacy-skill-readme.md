# huawei-postgresql-ecs-to-rds-drs-cross-region

## Resumen

Skill para orquestar la migración de PostgreSQL autogestionado en ECS hacia Huawei Cloud RDS for PostgreSQL mediante DRS Full + Incremental, con origen y destino en regiones diferentes.

## Problema que resuelve

Migrar bases de datos PostgreSQL de servidores autogestionados a RDS gestionado requiere coordinación de múltiples pasos: configuración del origen, creación de tarea DRS, pruebas de conectividad, pre-checks, sincronización full + incremental, validación y cutover. Sin orquestación, el proceso es propenso a errores de configuración y difícil de rastrear.

## Escenario soportado

- **Origen**: PostgreSQL autogestionado en ECS (región A)
- **Destino**: RDS for PostgreSQL (región B, diferente)
- **Mecanismo**: DRS Full + Incremental (Real-Time Synchronization)
- **Red**: Internet público vía EIP (arquitectura soportada; VPN OUT_OF_SCOPE_FOR_THIS_SCENARIO)
- **Topología**: Cross-region

## Arquitectura

```
Source Region A                        Target Region B
┌──────────────────┐                  ┌──────────────────┐
│  ECS + PostgreSQL │◄──SG Rule───────│  DRS Instance    │
│  (self-managed)   │   /32 CIDR      │  (EIP)           │
│  pg_hba.conf      │◄──Replication───│                  │
│  wal_level=logical│                  │                  │
└──────────────────┘                  └────────┬─────────┘
                                               │
                                        Full + Incremental
                                               │
                                      ┌────────▼─────────┐
                                      │  RDS PostgreSQL   │
                                      │  (managed)        │
                                      └──────────────────┘
```

## MCP utilizados

| MCP | Obligatorio | Propósito | Read/Write | Riesgo |
|---|---|---|---|---|
| huaweicloud-drs | Sí | Gestión de tareas DRS (crear, test, precheck, iniciar, monitorear) | Read + Write | High (write requiere approval) |
| huaweicloud-pricing | No | Estimar costos de RDS destino | Read-only | None |
| huaweicloud-ticket | No | Crear ticket de soporte si hay problemas | Read + Write | Medium |

## Capacidades

- Descubrimiento de tareas DRS existentes
- Detección de tareas duplicadas (EXACT_MATCH, PARTIAL_MATCH)
- Generación de plan de acceso al origen (SG rules, pg_hba.conf)
- Prueba de conectividad origen-destino
- Pre-check DRS
- Creación de tarea DRS Full + Incremental
- Inicio de tarea DRS con aprobación explícita
- Monitoreo de progreso de sincronización
- Generación de reporte de migración
- Guards de seguridad: CIDR /32, región, pre-check, duplicados

## Flujo general

1. Discovery → 2. Architecture Validation → 3. Readiness → 4. Plan → 5. Approval → 6. Execution → 7. Validation → 8. Cutover → 9. Rollback (if needed) → 10. Closure

## Nivel de automatización

| Fase | Estado | Responsable |
|---|---|---|
| Discovery | AUTOMATED | Agente |
| Architecture Validation | AUTOMATED | Agente |
| Readiness and Prechecks | ASSISTED | Agente + Humano |
| Plan Generation | AUTOMATED | Agente |
| Approval | MANUAL | Humano |
| Execution | ASSISTED | Agente + Humano |
| Validation | ASSISTED | Agente + Humano |
| Cutover | MANUAL | Humano |
| Rollback | MANUAL | Humano |
| Closure and Reporting | AUTOMATED | Agente |

## Prerrequisitos

- PostgreSQL en ECS con wal_level=logical, max_replication_slots>=1
- Usuario de replicación configurado en PostgreSQL origen
- RDS for PostgreSQL creado en región destino
- Security Group del origen permite acceso PostgreSQL desde DRS EIP
- pg_hba.conf configurado para usuario de replicación desde DRS EIP
- huaweicloud-drs MCP configurado y operativo
- Playwright instalado (requerido por huaweicloud-drs MCP)

## Entradas

- source_region: Región del ECS origen (ej: la-south-2)
- target_region: Región del RDS destino (ej: cn-north-4)
- source_endpoint: IP/EIP del ECS origen
- source_port: Puerto PostgreSQL origen (default: 5432)
- source_database: Nombre de la base de datos origen
- source_username: Usuario de replicación
- target_rds_id: ID de la instancia RDS destino
- target_database: Nombre de la base de datos destino
- task_name: Nombre de la tarea DRS
- source_security_group_id: ID del SG del ECS origen

## Salidas

- discovery-report.md
- architecture-validation-report.md
- source-access-plan.md
- readiness-report.md
- migration-plan.md
- drs-task-config.json
- execution-log.md
- validation-report.md
- drs-report.md
- rollback-plan.md
- final-report.md

## Instalación

```bash
# Instalar huaweicloud-drs MCP
cd <INSTALLATION_ROOT>/shared-mcps/huaweicloud-drs
npm install
npx playwright install chromium

# Verificar instalación
node server.mjs --help
```

## Configuración

```json
{
  "skills": {
    "huawei-postgresql-ecs-to-rds-drs-cross-region": {
      "path": "<INSTALLATION_ROOT>/skills/huawei-postgresql-ecs-to-rds-drs-cross-region"
    }
  },
  "mcp": {
    "huaweicloud-drs": {
      "path": "<INSTALLATION_ROOT>/shared-mcps/huaweicloud-drs"
    }
  }
}
```

## Uso con OpenCode o Hermes

1. Cargar la skill: `skill huawei-postgresql-ecs-to-rds-drs-cross-region`
2. Seguir el workflow documentado en SKILL.md
3. Las fases AUTOMATED serán ejecutadas por el agente
4. Las fases ASSISTED requieren revisión humana
5. Las fases MANUAL requieren ejecución humana

## Ejemplo seguro

```
# Fase 1: Discovery
drs_list_tasks({ region: "cn-north-4", source_engine: "postgresql" })

drs_find_matching_tasks({
  region: "cn-north-4",
  task_name: "pg-ecs-to-rds-migration",
  source_engine: "postgresql",
  target_engine: "postgresql",
  source_region: "la-south-2",
  target_region: "cn-north-4"
})

# Fase 3: Readiness
drs_generate_source_access_plan({
  drs_eip: "1.92.124.245",
  source_security_group_id: "sg-xxxxx",
  source_database: "demodb",
  source_user: "drs_replication"
})

drs_run_connection_test({ region: "cn-north-4", task_name: "pg-ecs-to-rds-migration" })

drs_run_precheck({ region: "cn-north-4", task_name: "pg-ecs-to-rds-migration" })

# Fase 6: Execution (requires explicit_approval=true)
drs_create_postgresql_full_incremental_task({
  task_name: "pg-ecs-to-rds-migration",
  target_region: "cn-north-4",
  explicit_approval: true,
  ...
})

drs_start_task({
  region: "cn-north-4",
  task_name: "pg-ecs-to-rds-migration",
  explicit_approval: true
})
```

## Aprobaciones requeridas

- Crear tarea DRS (explicit_approval=true)
- Iniciar tarea DRS (explicit_approval=true)
- Seleccionar tarea DRS existente (explicit_approval=true)
- Aplicar cambios de acceso al origen (SG rules, pg_hba.conf)
- Ejecutar cutover (redirigir conexiones de aplicación)
- Ejecutar rollback
- Eliminar recursos post-migración

## Validación

- DDL comparison: Estructura de tablas origen vs destino
- Row count validation: Conteo de registros por tabla
- Incremental test: Insertar dato en origen, verificar replicación a destino
- Application smoke tests post-cutover

## Rollback

1. Redirigir conexiones de aplicación a ECS origen
2. Detener tarea DRS (consola manual)
3. Verificar base de datos origen operativa
4. Limpiar datos en RDS destino si es necesario
5. Documentar razón de rollback

## Manejo de gaps de capacidad

| Gap ID | Descripción | Decisión |
|---|---|---|
| GAP-PG-001 | No MCP tool para PostgreSQL config validation | MANUAL_STEP |
| GAP-PG-002 | No MCP tool para extension compatibility | MANUAL_STEP |
| GAP-PG-003 | No MCP tool para DRS task stop | MANUAL_STEP |
| GAP-PG-004 | VPN OUT_OF_SCOPE_FOR_THIS_SCENARIO | NOT_REQUIRED |
| GAP-PG-005 | No MCP tool para app connection update | MANUAL_STEP |
| GAP-PG-006 | No MCP tool para DDL comparison | MANUAL_STEP |
| GAP-PG-007 | No MCP tool para row count validation | MANUAL_STEP |

## Pruebas

- 58 tests en 8 test suites pasan [VERIFIED_FROM_TEST]
- Safety guards: CIDR /32, región, pre-check, duplicados [VERIFIED_FROM_TEST]
- Secret redaction verified [VERIFIED_FROM_TEST]
- Connection test and pre-check verified [VERIFIED_FROM_TEST]
- DRS task creation and start require explicit_approval [VERIFIED_FROM_CODE]

## Seguridad

- CIDR /32 enforced para acceso PostgreSQL (no 0.0.0.0/0)
- Source access plan generado para revisión antes de aplicar
- Secrets redacted en reportes DRS
- Public Internet exposure es un riesgo (mitigado por /32 CIDR)
- VPN es OUT_OF_SCOPE_FOR_THIS_SCENARIO (arquitectura EIP es la intencional, seguridad mitigada por /32 CIDR)
- Replication user debe tener permisos mínimos necesarios

## Limitaciones

- VPN fuera de alcance (arquitectura EIP es la soportada para este escenario)
- Configuración PostgreSQL requiere SSH manual
- DRS task stop requiere consola manual
- DRS pricing BLOCKED en huaweicloud-pricing MCP
- Actualización de connection strings es manual
- DDL y row count validation son manuales

## Troubleshooting

| Problema | Solución |
|---|---|
| Connection test falla | Verificar SG rules, pg_hba.conf, PostgreSQL status, EIP |
| Pre-check falla | Revisar items BLOCKING, resolver antes de iniciar |
| Task creation falla | Verificar duplicados, parámetros, límites DRS |
| Full sync lento | Verificar tamaño de datos, ancho de banda, tamaño instancia DRS |
| Incremental lag alto | Verificar volumen de writes, ancho de banda, tamaño DRS |
| Cutover falla | Revertir conexiones a origen inmediatamente |

## Estado de madurez

**READY_WITH_WARNINGS**

La mayoría de las operaciones DRS están automatizadas con safety guards. Las limitaciones principales son: VPN OUT_OF_SCOPE_FOR_THIS_SCENARIO (not missing/unimplemented, intentionally out of scope per GAP-PG-004), configuración PostgreSQL manual, y DRS task stop manual.

## Evidencia utilizada

| Evidencia | Tipo |
|---|---|
| 13 DRS MCP tools disponibles | VERIFIED_FROM_CODE |
| 3 write tools requieren explicit_approval | VERIFIED_FROM_CODE |
| 58 tests pasan en 8 test suites | VERIFIED_FROM_TEST |
| Safety guards implementados | VERIFIED_FROM_TEST |
| 18-step runbook documentado | VERIFIED_FROM_DOCUMENTATION |
| VPN OUT_OF_SCOPE | VERIFIED_FROM_DESIGN |
| DRS pricing BLOCKED | VERIFIED_FROM_DOCUMENTATION |
| Source config validation requiere SSH | INFERRED |
| DRS task stop requiere consola | NOT_VERIFIED |
