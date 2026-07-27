# Skill Loading

## How Skills Work

A skill is loaded by an agent runtime (OpenCode or Hermes) and provides:

1. **SKILL.md**: Operational instructions for the agent
2. **skill.yaml**: Machine-readable manifest
3. **mcp-dependencies.yaml**: MCP tool dependencies
4. **workflows/**: Phase-specific workflow definitions
5. **prompts/**: Ready-to-use prompts for each phase
6. **docs/**: Supporting documentation

## Loading Process

1. Agent reads SKILL.md for instructions
2. Agent reads skill.yaml for configuration
3. Agent verifies MCP dependencies are available
4. Agent follows the workflow defined in SKILL.md
5. Agent uses prompts/ for each phase
6. Agent refers to docs/ for detailed procedures

## Skill Convention

Based on analysis of the existing environment:
- No pre-existing skill convention was found in the codebase
- The format defined in this package is the canonical convention
- SKILL.md uses YAML front matter + Markdown body
- skill.yaml is a machine-readable manifest
- mcp-dependencies.yaml maps MCP tools to skill phases
