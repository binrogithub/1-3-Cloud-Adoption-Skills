# MCP Design Standard

## Required Structure

```
<mcp-name>/
├── README.md
├── src/
│   └── server.mjs
├── tests/
├── examples/
├── docs/
│   ├── architecture.md
│   ├── tools-reference.md
│   ├── security-model.md
│   └── integration.md
├── mcp-manifest.yaml
├── package.json
├── .gitignore
└── .env.example
```

## Tool Contract Requirements

Every tool must define:
- name: Exact tool name (no ambiguity)
- description: Clear, concise description
- inputSchema: JSON Schema for inputs
- outputSchema: JSON Schema for outputs
- access: read_only | write | write_local
- risk: none | low | medium | high | critical
- sideEffects: List of side effects
- approvalRequired: boolean
- expectedErrors: List of possible errors

## Naming Convention

- MCP: huaweicloud-<service> or <domain>-<function>
- Tool: <domain>_<action>_<object>
- Example: drs_create_postgresql_task

## Safety Requirements

- No hardcoded credentials
- No 0.0.0.0/0 access patterns
- Write operations require explicit approval
- Secret redaction in all outputs
- Dry-run mode where applicable
