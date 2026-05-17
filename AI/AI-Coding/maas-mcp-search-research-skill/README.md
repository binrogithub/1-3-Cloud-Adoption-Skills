# MaaS MCP Search Research Skill

This README describes only the `maas-mcp-search-research-skill/` directory.

## Directory Structure

```text
maas-mcp-search-research-skill/
  README.md
  SKILL.md
  agents/
    openai.yaml
```

## Files

### `SKILL.md`

The main skill file. It defines a generic AI coding research workflow that uses Huawei Cloud MaaS, or another OpenAI-compatible MaaS model, together with MCP search, crawl, code-search, or deep-research tools.

It covers:

- when to activate the skill
- Huawei MaaS default endpoint and model baseline
- MCP search capability expectations
- a search then synthesize workflow
- research output structure for engineering decisions

### `agents/openai.yaml`

UI metadata for skill browsers or launchers. It defines the display name, short description, brand color, and a default prompt for MaaS plus MCP research tasks.
