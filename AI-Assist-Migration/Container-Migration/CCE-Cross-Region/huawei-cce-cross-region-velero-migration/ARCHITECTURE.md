# Architecture

## Overview

The package is organized around migration skills as the primary unit of functionality.

## Layer Model

```
┌─────────────────────────────────────────┐
│           Migration Skills              │  ← Primary unit
│  (CCE Velero, PostgreSQL DRS,           │
│   Snowflake DataArts)                   │
├─────────────────────────────────────────┤
│           Shared Skills                 │  ← Cross-cutting
│  (mcp-capability-builder)               │
├─────────────────────────────────────────┤
│           MCP Layer                     │  ← Orchestration targets
│  (pricing, deploy, drs, ticket,         │
│   dataarts-deploy-agent)                │
├─────────────────────────────────────────┤
│           Integration Layer             │  ← External dependencies
│  (Playwright)                           │
├─────────────────────────────────────────┤
│           Shared Infrastructure         │  ← Docs, schemas, templates
└─────────────────────────────────────────┘
```

## Data Flow

```
User Request → Skill (SKILL.md) → Workflow Phases → MCP Tools → Cloud Operations
                                    ↓
                              Capability Gap?
                                    ↓
                         mcp-capability-builder → Scaffold → Review → Promote
```

## Skill Structure

Each migration skill contains:
- SKILL.md: Operational instructions for the agent
- README.md: Human-readable documentation
- skill.yaml: Machine-readable manifest
- mcp-dependencies.yaml: MCP tool mapping
- docs/: Architecture, prerequisites, runbooks, validation, rollback
- workflows/: Phase-specific workflow definitions
- prompts/: Ready-to-use prompts per phase
- examples/: Usage examples
- tests/: Validation tests
- generated-mcps/: MCPs generated to fill gaps (if any)
