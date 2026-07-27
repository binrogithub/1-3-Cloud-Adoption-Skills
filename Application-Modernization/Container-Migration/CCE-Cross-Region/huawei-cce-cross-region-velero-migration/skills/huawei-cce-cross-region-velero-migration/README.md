# huawei-cce-cross-region-velero-migration

## Resumen

Skill para orquestar la migración de cargas de trabajo Kubernetes entre clústeres Huawei Cloud CCE ubicados en regiones diferentes, utilizando Velero como mecanismo de backup y restore.

## Problema que resuelve

Las migraciones de cargas Kubernetes entre regiones de Huawei Cloud requieren coordinación de múltiples componentes: namespaces, deployments, services, ingress, configmaps, secrets, PVCs, storage classes, load balancers, EIPs, DNS y repositorios de imágenes. Sin orquestación, el proceso es propenso a errores y difícil de rastrear.

## Escenario soportado

- **Origen**: Clúster CCE en región A
- **Destino**: Clúster CCE en región B (región diferente)
- **Mecanismo**: Velero backup + restore
- **Almacenamiento**: OBS como repositorio de backup
- **Topología**: Cross-region

## Arquitectura

```
Source Region A                    Target Region B
┌─────────────┐                   ┌─────────────┐
│  CCE Cluster │──Velero Backup──>│  OBS Bucket  │
│  (source)    │                   │  (shared)    │
└─────────────┘                   └──────┬───────┘
                                          │
                                   Velero Restore
                                          │
                                   ┌──────▼───────┐
                                   │  CCE Cluster  │
                                   │  (target)     │
                                   └──────────────┘
```

Componentes adicionales que requieren migración manual:
- Load Balancers (ELB) → recrear en región destino
- EIPs → asignar nuevos en región destino
- DNS → actualizar registros
- Image repos → replicar o configurar acceso cross-region
- StorageClasses → mapear entre CSI drivers de cada región

## MCP utilizados

| MCP | Obligatorio | Propósito | Read/Write | Riesgo |
|---|---|---|---|---|
| huaweicloud-deploy | Sí | Generar Terraform para infraestructura destino | Read + Write (local .tf) | Low (apply bloqueado) |
| huaweicloud-pricing | No | Estimar costos de infraestructura destino | Read-only | None |
| huaweicloud-ticket | No | Crear ticket de soporte si hay problemas | Read + Write | Medium |
| playwright | No | Automación de consola si se requiere | Read + Write | Medium |

## Capacidades

- Descubrimiento de recursos Kubernetes del clúster origen
- Validación de compatibilidad entre versiones de Kubernetes
- Generación de Terraform para infraestructura destino
- Generación de comandos Velero backup/restore
- Plan de migración de DNS, Load Balancers e imágenes
- Procedimiento de rollback documentado

## Flujo general

1. Discovery → 2. Architecture Validation → 3. Readiness → 4. Plan → 5. Approval → 6. Execution → 7. Validation → 8. Cutover → 9. Rollback (if needed) → 10. Closure

## Nivel de automatización

| Fase | Estado | Responsable |
|---|---|---|
| Discovery | ASSISTED | Agente + Humano |
| Architecture Validation | ASSISTED | Agente + Humano |
| Readiness and Prechecks | MANUAL | Humano |
| Plan Generation | ASSISTED | Agente + Humano |
| Approval | MANUAL | Humano |
| Execution | MANUAL | Humano |
| Validation | MANUAL | Humano |
| Cutover | MANUAL | Humano |
| Rollback | MANUAL | Humano |
| Closure and Reporting | ASSISTED | Agente + Humano |

## Prerrequisitos

- Huawei Cloud CCE cluster en región origen con Velero instalado
- Huawei Cloud CCE cluster en región destino con Velero instalado
- OBS bucket accesible desde ambas regiones
- IAM credentials con permisos para Velero (OBS read/write, CCE admin)
- kubectl configurado para ambos clústeres
- Velero CLI instalado
- Conectividad de red entre regiones (Internet o VPN/Direct Connect)
- huaweicloud-deploy MCP configurado

## Entradas

- source_cluster_id: ID del clúster CCE origen
- source_region: Región del clúster origen (ej: cn-north-4)
- target_region: Región del clúster destino (ej: la-north-2)
- namespaces: Lista de namespaces a migrar
- obs_bucket: Bucket OBS para backups de Velero
- kubernetes_version_source: Versión K8s del origen
- kubernetes_version_target: Versión K8s del destino

## Salidas

- discovery-report.md
- architecture-validation-report.md
- readiness-report.md
- migration-plan.md
- terraform/ (archivos .tf para infra destino)
- execution-log.md
- validation-report.md
- rollback-plan.md
- final-report.md

## Instalación

```bash
# Configurar huaweicloud-deploy MCP
# Ver shared/docs/installation.md para instrucciones detalladas
```

## Configuración

Configurar en opencode.json:

```json
{
  "skills": {
    "huawei-cce-cross-region-velero-migration": {
      "path": "<INSTALLATION_ROOT>/skills/huawei-cce-cross-region-velero-migration"
    }
  },
  "mcp": {
    "huaweicloud-deploy": {
      "path": "<INSTALLATION_ROOT>/shared-mcps/huaweicloud-deploy"
    }
  }
}
```

## Uso con OpenCode o Hermes

1. Cargar la skill: `skill huawei-cce-cross-region-velero-migration`
2. Seguir el workflow documentado en SKILL.md
3. Las fases ASSISTED serán guiadas por el agente
4. Las fases MANUAL requieren ejecución humana

## Ejemplo seguro

```
# Fase 4: Generar Terraform para infraestructura destino
GenerateTerraformFromArchitecture({
  "architecture": {
    "architecture_id": "cce-target-infra",
    "region": "la-north-2",
    "deployment_mode": "terraform",
    "components": [
      {"service": "vpc", "name": "target-vpc", "cidr": "192.168.0.0/16"},
      {"service": "subnet", "name": "target-subnet", "cidr": "192.168.0.0/24"},
      {"service": "security_group", "name": "target-sg", "rules": [...]}
    ]
  }
})

# Validar Terraform generado
ValidateTerraformConfiguration({"architecture_id": "cce-target-infra"})

# Preview de cambios
RunTerraformPlan({"architecture_id": "cce-target-infra"})
```

## Aprobaciones requeridas

- Aprobación del plan de migración completo
- Aprobación de terraform apply (ejecución manual fuera del MCP)
- Aprobación de Velero backup (modifica datos en OBS)
- Aprobación de Velero restore (modifica estado del clúster destino)
- Aprobación de cutover DNS (redirige tráfico)
- Aprobación de rollback (si es necesario)

## Validación

- Verificar que los Deployments estén running en el destino
- Verificar Services accesibles
- Verificar Ingress configurado
- Verificar PVCs bound en región destino
- Comparar conteos de recursos origen vs destino
- Ejecutar smoke tests de aplicación

## Rollback

1. Revertir DNS a clúster origen
2. Restaurar tráfico en clúster origen
3. Limpiar recursos en clúster destino
4. Destruir infraestructura destino (terraform destroy manual)
5. Documentar lecciones aprendidas

## Manejo de gaps de capacidad

Los siguientes gaps requieren atención:

| Gap ID | Descripción | Decisión |
|---|---|---|
| GAP-CCE-001 | No MCP tool para CCE discovery | MANUAL_STEP |
| GAP-CCE-002 | No MCP tool para Velero operations | MANUAL_STEP |
| GAP-CCE-003 | No MCP tool para K8s version validation | MANUAL_STEP |
| GAP-CCE-004 | No MCP tool para StorageClass mapping | MANUAL_STEP |
| GAP-CCE-005 | No MCP tool para DNS migration | MANUAL_STEP |
| GAP-CCE-006 | No MCP tool para ELB/EIP migration | MANUAL_STEP |
| GAP-CCE-007 | CCE not in deploy MCP supported services | EXTEND_EXISTING_MCP |

## Pruebas

- Validar que SKILL.md existe y es válido
- Validar que skill.yaml es válido
- Validar que los MCP referenciados existen
- Validar que las tools mencionadas existen en los MCP
- Validar que no se mencionan tools inexistentes
- Las pruebas de ejecución requieren clústeres CCE reales (SKIPPED_CLOUD_SIDE_EFFECT)

## Seguridad

- Secrets de Kubernetes se migran sin encriptación adicional por Velero (configurar encryption)
- IAM credentials para OBS deben tener permisos mínimos necesarios
- No ejecutar terraform apply desde el MCP (bloqueado por diseño)
- No exponer EIPs públicamente innecesariamente
- Documentar todas las operaciones con timestamps

## Limitaciones

- CCE no está soportado por huaweicloud-deploy MCP
- Velero no tiene automatización MCP
- La mayoría de fases son MANUALES
- PVCs cross-region requieren mapeo manual de StorageClasses
- Load Balancers deben recrearse en región destino
- EIPs son region-specific
- Versión Kubernetes debe ser compatible entre regiones

## Troubleshooting

| Problema | Solución |
|---|---|
| Velero backup falla | Verificar OBS connectivity, IAM permissions, disk space |
| Velero restore falla | Verificar resource compatibility, StorageClass mapping, PVC availability |
| Terraform validation falla | Revisar architecture JSON, servicios soportados |
| Target cluster sin capacidad | Escalar node pools antes del restore |
| DNS no resuelve | Verificar DNS propagation, TTL, fallback a source |

## Estado de madurez

**EXPERIMENTAL**

La migración CCE cross-region con Velero está documentada pero no implementada en el MCP actual. La mayoría de las fases requieren ejecución manual.

## Evidencia utilizada

| Evidencia | Tipo |
|---|---|
| CCE Velero use-case documentado como NOT_IMPLEMENTED | VERIFIED_FROM_DOCUMENTATION |
| huaweicloud-deploy no soporta CCE | VERIFIED_FROM_CODE |
| No existe Velero MCP tool | VERIFIED_FROM_CODE |
| terraform apply bloqueado en deploy MCP | VERIFIED_FROM_CODE |
| 7/10 fases son MANUAL o NOT_IMPLEMENTED | INFERRED |
