# Reporte de Migración: PostgreSQL ECS → RDS (DRS Cross-Region)

**Fecha:** 25-26 de agosto, 2026  
**Skill utilizada:** `postgresql-ecs-to-rds-drs`  
**Estado final:** Completado y verificado
**By:** Naher Santiago Herrera Castro - Cloud Engineer at Huawei Cloud LATIN AMERICA CLOUD DELIVERY & SERVICE DEPT

---

## Resumen ejecutivo

Se migró la base de datos `demomigration` (PostgreSQL 16) desde un ECS auto-gestionado en la región **ap-southeast-3** a una instancia nueva de RDS for PostgreSQL en la región **la-north-2**, utilizando DRS (Data Replication Service) con replicación Full + Incremental sobre red pública (EIP). La migración transfirió 5 tablas y 29 filas, verificadas contra un baseline previo. Tras la validación, se destruyó toda la infraestructura temporal y se limpió el acceso en el source.

---

## Configuración inicial

### Source (existente — no modificado directamente)

| Parámetro | Valor |
|---|---|
| Región | ap-southeast-3 |
| IP pública (EIP) | 114.119.174.124 |
| Puerto | 5432 |
| Base de datos | demomigration |
| Usuario de replicación | drs_replicator |
| Security group ID | df1dceb1-cff6-4c86-845a-ed709f3de0f1 |
| Server ID | e8d7cfa7-cec7-43cf-b701-9d16cf22ba8a |
| Nombre del servidor | source-ecs-postgresql |
| IP privada | 192.168.0.90 |
| VPC ID | f5d66064-7aae-45ec-a8b0-21c0bb016622 |
| Subnet ID | 52b09b65-e916-471d-86d2-fe814d3b4d61 |
| Subnet CIDR | 192.168.0.0/24 |
| Flavor | s6.large.2 (2 vCPUs, 4 GB RAM) |
| OS | Ubuntu 24.04 |
| Project ID | 86a68f30d0ea47b7bb642e0fb19f1a6f |

### Target (creado y luego destruido)

| Parámetro | Valor |
|---|---|
| Región | la-north-2 |
| Instance ID | f7c428d8cb33467b944f829ab3e9bad6in03 |
| Private IP | 10.0.0.12 |
| Flavor | rds.pg.n1.large.2 (2 vCPUs, 4 GB) |
| Storage | CLOUDSSD 40 GB |
| AZ | la-north-2a |
| Engine | PostgreSQL 16.13.260200 |
| Admin user | root |
| VPC ID | 3e264636-9e58-4b7d-8a5a-61eaf8103f75 |
| Subnet ID | f7663f8e-4ab1-4263-b7c3-0b66fa5364fc |
| Security group ID | b86b2d2a-7a4d-4378-82c0-9c3421be4b57 |
| Project ID | 2df55005434b4d1e8b0aafd81244fc25 |

---

## Paso 0 — Preflight

**Objetivo:** Confirmar que el entorno puede completar la migración.

| Verificación | Estado |
|---|---|
| Modo de ejecución (Build) | OK |
| MCP `h2cloud` responde (KooCLI 7.2.12) | OK |
| MCP `terraform` disponible | OK |
| Credenciales CLI (hcloud) | OK |
| `HW_ACCESS_KEY` / `HW_SECRET_KEY` para7para Terraform | Proporcionadas por el usuario |
| DRS soporta `postgresql` y `postgresql-to-postgresql` | OK |
| Regiones difieren (ap-southeast-3 vs la-north-2) | OK |

---

## Paso 1 — Descubrimiento y verificación del source

### 1.1 — Red del ECS (descubierta automáticamente)

Se listaron los EIPs en ap-southeast-3, se identificó el EIP 114.119.174.124, se obtuvo el server ID, y se consultaron las interfaces de red para extraer VPC ID, subnet ID e IP privada.

### 1.2 — Verificación de la base de datos (ejecutada por el usuario)

Script ejecutado: `01_source_readiness_check.sql`

| Verificación | Valor | Estado |
|---|---|---|
| Versión PostgreSQL | 16.15 (major 16) | OK |
| `wal_level` | logical | OK |
| `max_replication_slots` | 4 | OK (≥ 1) |
| `max_wal_senders` | 4 | OK (≥ 1) |
| `password_encryption` | scram-sha-256 | Registrado |
| `lc_monetary` | en_US.UTF-8 | Registrado |
| `lc_collate` / `lc_ctype` | en_US.UTF-8 | Registrado |
| Usuario `drs6rs_replicator` con REPLICATION | Sí | OK |
| SELECT en tablas | 5 tablas | OK |
| SELECT en secuencias | 5 de 5 | OK |
| Extensiones | solo plpgsql | OK |
| Tablas sin PK | ninguna | OK |
| Tamaño de BD | 7975 kB (~8 MB) | Registrado |

**No se requirió ningún cambio de configuración ni reinicio.**

---

## Paso 2 — Baseline del source

Script ejecutado: `03_source_baseline.sql`

| Tabla | Filas |
|---|---|
| demo_customers | 6 |
| demo_migration_audit | 2 |
| demo_order_items | 10 |
| demo_orders | 6 |
| demo_products | 5 |
| **Total** | **5 tablas, 29 filas** |

| Tipo de objeto | Cantidad |
|---|---|
| Índices | 9 |
| Constraints | 14 |
| Secuencias | 5 |
| Vistas | 0 |
| Extensiones | 1 |

Baseline capturado a las 2026-08-26 04:07:50 (UTC+8).

---

## Paso 3 — Provisionar el target

### 3.1 — Decisiones de configuración

- Red: VPC y subnet nuevas en la-north-2
- Sizing: valores por defecto basados en el source

### 3.2 — Contraseña RDS

`Migration@2026` — validada contra las 5 reglas de Huawei RDS (8-32 chars, mayúscula, minúscula, dígito, especial).

### 3.3 — Terraform plan

6 recursos a crear:

| Recurso | Detalle |
|---|---|
| VPC | target-vpc, CIDR 10.0.0.0/16 |
| Subnet | target-subnet, CIDR 10.0.0.0/24, AZ la-north-2a |
| Security Group | target-rds-sg (sin reglas por defecto) |
| Regla egress | Todo el tráfico saliente |
| Regla ingress | TCP 5432 desde el subnet (para DRS) |
| RDS PostgreSQL 16 | target-rds-postgresql, 2 vCPUs/4 GB, CLOUDSSD 40 GB |

### G1 — Aprobación: concedida

### 3.4 — Terraform apply

`terraform apply` completado en **4m49s**.) RDS instance ID: `f7c428d8cb33467b944f829ab3e9bad6in03`

### 3.5 — Verificación

RDS instance status: **ACTIVE**. Private IP: 10.0.0.12. Engine: PostgreSQL 16.13.260200.

---

## Paso 4 — Alinear locale y verificar que la BD target no existe

### 4.1 — Locale

- Target `lc_monetary` original: `C`
- Source `lc_monetary`: `en_US.UTF-8`
- Acción: `RDS UpdateInstanceConfiguration` → `lc_monetary=en_US.UTF-8`
- `restart_required`: false (no requirió reinicio)

### 4.2 — Base de datos target

`RDS ListDatabases` retornó solo `postgres`. La base `demomigration` **no existe** — DRS la creará durante el$full sync.

---

## Paso 5 — Crear la tarea DRS

### 5.1 — Parámetros de la tarea

| Campo | Valor |
|---|---|
| db_type | postgresql |
| engine_type | postgresql-to-postgresql |
| job_type | sync |
| task_type | FULL_INCR_TRANS |
| job_direction | up |
| net_type | eip |
| node_type | micro |
| instance_type | single |
| availability_zone | la-north-2a |

Source endpoint: `ecs_postgresql`, 114.119.174.124:5432, user drs_replicator, VPC/subnet/SG del source.

Target endpoint: `cloud_postgresql`, RDS instance f7c428d8..., user root, VPC/subnet/SG del target.

### G2 — Aprobación: concedida

### 5.2 — Creación

- Primer intento: nombre `drs-pg-migration` ya existía (DRS.10020077)
- Segundo intento: nombre `drs-pg-mig-260826` — creado exitosamente
- Job ID: `8dae7601-2506-42d1-8344-2a28e7djb204`

### 5.3 — Instancia de replicación DRS

| Dato | Valor |
|---|---|
| Estado | CONFIGURATION |
| IP pública (reach source) | 101.44.24.109 |
| IP privada (reach target) | 10.0.0.80 |

---

## Paso 6 — Dar acceso de red a la instancia DRS

### 6.2 — Security group del source

Regla creada en ap-southeast-3:

| Parámetro | Valor |
|---|---|
| Security group |F | df1dceb1-cff6-4c86-845a-ed709f3de0f1 |
| Dirección | ingress |
| Protocolo | TCP |
| Puerto | 5432 |
| Remote IP | 101.44.24.109/32 |
| Rule ID | 54968347-9234-493c-9353-04a31069b1db |

### 6.3 — Security group del target

Verificado: ya contiene regla ingress TCP 5432 desde 10.0.0.0/24 (creada por Terraform), que cubre la IP privada de DRS (10.0.0.80).

### 6.4 — `pg_hba.conf` en el source (ejecutado por el usuario)

Tres entradas agregadas con método `scram-sha-256`:

```
host  all          drs_replicator  101.44.24.109/32  scram-sha-256
host  demomigration  drs_replicator  101.44.24.109/32  scram-sha-256
host  replication  drs_replicator  101.44.24.109/32  scram-sha-256
```

`pg_reload_conf()` devolvió `t`. Confirmado por el usuario.

---

## Paso 7 — Test de conexión, selección de objetos y pre-check

### 7.1 — Test de conexión

`DRS BatchValidateConnections` — ambos endpoints retornaron `success: true`.

### 7.2 — Recolección de objetos

`DRS CollectDbObjectsInfo` (con `is_refresh=true`) — status: success.

Objetos encontrados:

| Tipo | Objetos |
|---|---|
| Tablas | demo_customers, demo_migration_audit, demo_order_items, demo_orders, demo_products |
| Secuencias | demo_customers_customer_id_seq, demo_migration_audit_audit_id_seq, demo_order_items_order_item_id_seq, demo_orders_order_id_seq, demo_products_product_id_seq |

Total: 11 objetos. Las 5 tablas coinciden con el baseline del Paso 2.

### 7.3 — Selección de objetos

`DRS BatchSetObjects` — base de datos `demomigration` seleccionada con `select=true`. Status: true.

### 7.4 — Pre-check

`DRS BatchCheckJobs` — result: **true**, total_passed_rate: **100%**.

Todos los checks pasaron. 4 alarmas no bloqueantes:

| Alarma | Código | Significado |
|---|---|---|
| dstDbDiskSize | DST_DB_DISK_SIZE_UP_ALARM | Disco target (40 GB) mucho mayor que BD (~192 KB). Informativo. |
| dstReplicationRoleCheck | DB_PARAS_REPLICATION_ROLE_CONFIG_ERROR | session_replication_role=origin en target. DRS lo maneja. |
| pgSrcHasLargeColumnTypeCheck | PG_HAS_LARGE_COLUMN_TYPE_TABLES | Tabla demo_migration_audit tiene columnas large. Informativo. |
| srcDbLogicalSlotSupportFailoverCheck | PG_SRC_NOT_SUPPORT_FAILOVER_SLOT_ALARM | Source no soporta failover slots. Esperado para single. |

---

## Paso 8 — Iniciar la tarea y monitorear el full sync

### G3 — Aprobación: concedida

### 8.1 — Inicio

`DRS BatchStartJobs` — status: success.

### 8.2 — Monitoreo

Transición de estados: `STARTJOBING` → `FULL_TRANSFER_STARTED` → `INCRE_TRANSFER_STARTED`

| Métrica | Valor |
|---|---|
| Estructura | 100% |
| Datos | 100% |
| Índices | 100% |
| Estado final | INCRE_TRANSFER_STARTED |
| Delay incremental | 1 segundo (209 ms) |
| Duración full sync | ~1 minuto |

---

## Paso 9 — Validar la migración

### 9.1 — Comparación a nivel de objetos

`DRS CreateObjectLevelCompareJob` — status: **SUCCESSFUL**.

| Tipo | Source | Target | ¿Coincide? |
|---|---|---|---|
| Tablas | 5 | 5 | Sí |
| Índices | 9 | 9 | Sí |
| Constraints | 14 | 14 | Sí |
| Extensiones | 1 | 1 | Sí |
| BD | 1 | 1 | Sí |

### 9.2 — Conteo de filas (DAS console)

Query ejecutada por el usuario en DAS:

```sql
SELECT 'demo_customers' AS tabla, count(*) AS filas FROM demo_customers
UNION ALL SELECT 'demo_migration_audit', count(*) FROM demo_migration_audit
UNION ALL SELECT 'demo_order_items', count(*) FROM demo_order_items
UNION ALL SELECT 'demo_orders', count(*) FROM demo_orders
UNION ALL SELECT 'demo_products', count(*) FROM demo_products;
```

| Tabla | Source (baseline) | Target | ¿Coincide? |
|---|---|---|---|
| demo_customers | 6 | 6 | Sí |
| demo_migration_audit | 2 | 2 | Sí |
| demo_order_items | 10 | 10 | Sí |
| demo_orders | 6 | 6 | Sí |
| demo_products | 5 | 5 | Sí |
| **Total** | **29** | **29** | **Sí** |

---

## Paso 10 — Verificar replicación incremental

### G4 — Aprobación: concedida (escritura de fila de prueba)

**Tabla seleccionada:** demo_customers (6 filas en baseline)

**INSERT ejecutado en el source:**

```sql
INSERT INTO demo_customers (customer_code, full_name, email, country)
VALUES ('DRSTEST', 'DRS Incremental Test', 'drs.incremental.test@verify.com', 'TestLand');
```

**Resultado en el target (DAS):** `count(*) = 7` (era 6).

**Conclusión:** La replicación incremental está verificada — un cambio en el source llega al target automáticamente.

---

## Paso 11 — Cutover

No aplica. El usuario indicó al inicio que no hay aplicación que redirigir. G5 registrado como omitido.

---

## Paso 12 — Confirmar éxito y limpiar

### 12.1 — Reporte de éxito

La migración está completa y verificada: 5 tablas y 29 filas, coincidiendo con el source exactamente. Full sync en ~1 minuto, replicación incremental con delay de 1 segundo.

### 12.2 — Decisión del usuario

Destruir todo (tarea DRS + RDS target).

### G6 — Aprobación: concedida

### 12.3 — Limpieza cloud

| Acción | Resultado |
|---|---|
| `DRS BatchStopJobs` (pause_mode=all) | success |
| `DRS BatchDeleteJobs` (force_terminate) | success |
| `VPC DeleteSecurityGroupRule` (source SG) | Eliminada |
| `terraform destroy` | 6 recursos destruidos |
| `hcloud_list_rds_instances(la-north-2)` | 0 instancias |

### 12.4 — Limpieza en el source (ejecutada por el usuario)

```bash
sed -i '/101.44.24.109/d' /etc/postgresql/16/main/pg_hba.conf
sudo -u postgres psql -c "SELECT pg_reload_conf();"
```

```bash
sudo -u postgres psql -d demomigration -c "DELETE FROM demo_customers WHERE customer_code = 'DRSTEST';"
```

Ambos ejecutados y confirmados por el usuario.

---

## Gates de aprobación

| Gate | Operación | Step | Estado |
|---|---|---|---|
| G1 | `terraform apply` para el target | 3 | Aprobado |
| G2 | Crear la tarea DRS | 5 | Aprobado |
| G3 | Iniciar la tarea DRS | 8 | Aprobado |
| G4 | Escribir fila de prueba en el source | 10 | Aprobado |
| G5 | Cutover | 11 | Omitido (sin aplicación) |
| G6 | Detener tarea, limpiar, destruir target | 12 | Aprobado |

---

## Validación de la skill

La skill `postgresql-ecs-to-rds-drs` funcionó correctamente de extremo a extremo:

1. **Preflight robusto:** detectó correctamente el entorno, las credenciales, y el soporte de DRS para PostgreSQL.
2. **Descubrimiento automático:** resolvió VPC, subnet y security group del source a partir del EIP sin intervención manual.
3. **Verificación del source:** el script SQL detectó todos los requisitos de DRS sin falsos positivos.
4. **Baseline:** capturó nombres de tablas y conteos que sirvieron para validar después.
5. **Terraform:** creó y destruyó la infraestructura del target sin errores. La regla ingress del subnet CIDR fue suficiente para DRS.
6. **Locale:** detectó y corrigió la diferencia de `lc_monetary` sin reinicio.
7. **DRS lifecycle:** creación, conexión, recolección de objetos, selección, pre-check, inicio, monitoreo y limpieza — todos exitosos.
8. **Validación:** la comparación de objetos y el conteo de filas confirmaron la migración. La fila de prueba confirmó la replicación incremental.
9. **Limpieza:** todos los recursos temporales fueron eliminados (DRS, SG rule, RDS, VPC, subnet, SG, pg_hba.conf).
10. **Comunicación:** los comandos entregados al usuario fueron completos, ejecutables y con el contexto adecuado. Ninguno falló.

**Conclusión:** La skill está operativa y lista para migraciones reales.
