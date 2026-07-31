# mcp-capability-builder

## Resumen

Skill compartida que analiza gaps de capacidad encontrados por las skills de migración y prepara extensiones de MCP existentes o nuevos MCPs de forma controlada, sin ejecutar operaciones cloud ni activar automáticamente los resultados.

## Problema que resuelve

Las skills de migración pueden descubrir que los MCP actuales no cubren todas las capacidades requeridas. Esta skill proporciona un mecanismo controlado para cerrar esos gaps, ya sea extendiendo un MCP existente o creando uno nuevo, siempre con revisión manual antes de activación.

## Escenario soportado

- Una skill de migración reporta un capability gap
- Se evalúan alternativas: herramienta existente, extensión, nuevo MCP, paso manual
- Se genera un scaffold con pruebas y documentación
- Se marca para revisión manual (nunca se activa automáticamente)

## Arquitectura

```
Migration Skill → Gap Report → mcp-capability-builder → Analysis → Decision
                                                        │
                                          ┌─────────────┼─────────────┐
                                          │             │             │
                                   USE_EXISTING   EXTEND_MCP    CREATE_NEW_MCP
                                          │             │             │
                                          │        Scaffold +    Scaffold +
                                          │        Tests +       Tests +
                                          │        Docs         Docs
                                          │             │             │
                                          └─────────────┼─────────────┘
                                                        │
                                                  DRAFT/EXPERIMENTAL
                                                        │
                                                  Manual Review
                                                        │
                                                  Promotion (if approved)
```

## MCP utilizados

| MCP | Obligatorio | Propósito | Read/Write | Riesgo |
|---|---|---|---|---|
| Ninguno | N/A | Operación local únicamente | N/A | None |

## Capacidades

- Análisis de gaps de capacidad
- Búsqueda de herramientas existentes equivalentes
- Evaluación de extensiones de MCP
- Diseño de contratos de tools
- Generación de scaffolds de MCP
- Generación de pruebas y mocks
- Revisión de seguridad estática
- Instrucciones de integración

## Flujo general

1. Recibir gap → 2. Buscar tools existentes → 3. Evaluar extensión → 4. Determinar si nuevo MCP → 5. Diseñar contrato → 6. Generar scaffold → 7. Crear tests → 8. Crear docs → 9. Security review → 10. Marcar para revisión

## Nivel de automatización

| Fase | Estado | Responsable |
|---|---|---|
| Receive gap | AUTOMATED | Agente |
| Search existing tools | AUTOMATED | Agente |
| Evaluate extension | ASSISTED | Agente + Humano |
| Determine new MCP | ASSISTED | Agente + Humano |
| Design contract | AUTOMATED | Agente |
| Generate scaffold | AUTOMATED | Agente |
| Create tests | AUTOMATED | Agente |
| Create docs | AUTOMATED | Agente |
| Security review | AUTOMATED | Agente |
| Mark for review | MANUAL | Humano |

## Prerrequisitos

- Ninguno (operación local)

## Entradas

- gap_id: ID del gap
- skill_name: Skill solicitante
- phase: Fase afectada
- required_capability: Descripción de la capacidad requerida
- evaluated_mcps: MCPs ya evaluados

## Salidas

- gap-analysis.md
- tool-contract.md
- mcp-scaffold/ (si CREATE_NEW_MCP)
- tests/
- security-review.md
- integration-instructions.md
- promotion-checklist.md

## Instalación

No requiere instalación. Es una skill de análisis local.

## Configuración

```json
{
  "skills": {
    "mcp-capability-builder": {
      "path": "<INSTALLATION_ROOT>/shared-skills/mcp-capability-builder"
    }
  }
}
```

## Ejemplo seguro

```
# Invocado por una skill de migración
mcp-capability-builder({
  gap_id: "GAP-CCE-002",
  skill_name: "huawei-cce-cross-region-velero-migration",
  phase: "execution",
  required_capability: "Velero backup/restore operations",
  evaluated_mcps: ["huaweicloud-deploy", "huaweicloud-pricing"]
})

# Resultado posible:
# Decision: CREATE_NEW_MCP
# New MCP: huaweicloud-velero
# Status: DRAFT
# Requires manual review before activation
```

## Aprobaciones requeridas

- Promoción de MCP generado a READY (requiere revisión manual)
- Integración en configuración OpenCode (requiere acción manual)

## Validación

- Verificar que no hay credenciales hardcodeadas
- Verificar que no hay patrones 0.0.0.0/0
- Verificar que operaciones write requieren aprobación
- Verificar secret redaction en outputs

## Rollback

No aplica (no se ejecutan operaciones)

## Seguridad

- Nunca usa credenciales reales
- Nunca llama servicios cloud
- Nunca crea recursos
- Nunca modifica infraestructura
- Nunca activa MCPs automáticamente
- Security review incluida en workflow

## Limitaciones

- No prueba MCPs generados contra servicios reales
- Security review es estática
- Integración testing debe hacerse manualmente
- Promoción requiere juicio humano

## Estado de madurez

**READY_WITH_WARNINGS**

La skill opera localmente sin riesgo cloud. Los MCPs generados requieren revisión manual.

## Evidencia utilizada

| Evidencia | Tipo |
|---|---|
| Operación local sin acceso cloud | VERIFIED_FROM_DESIGN |
| MCPs generados nunca auto-activados | VERIFIED_FROM_DESIGN |
| Security review incluida | VERIFIED_FROM_DESIGN |
| Código generado no probado contra servicios reales | INFERRED |
