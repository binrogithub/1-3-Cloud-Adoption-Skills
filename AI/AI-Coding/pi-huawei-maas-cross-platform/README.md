# Pi Huawei MaaS Cross Platform Skill

This README describes only the `pi-huawei-maas-cross-platform/` skill directory and its files.

## Directory Structure

```text
pi-huawei-maas-cross-platform/
  README.md
  SKILL.md
  agents/
    openai.yaml
```

## Files

### `README.md`

This file. It describes the `pi-huawei-maas-cross-platform/` skill directory and the purpose of each file in the folder.

### `SKILL.md`

The main Codex skill file. It contains the English cross-platform instructions for configuring Pi Coding Agent on Windows or Linux to use Huawei Cloud ModelArts MaaS through the OpenAI-compatible endpoint.

It covers:

- Shared Huawei MaaS provider configuration
- `glm-5.1` model settings
- Windows PowerShell setup flow
- Linux bash/Python setup flow
- JSON validation commands
- Endpoint smoke tests
- Troubleshooting notes
- API key and secret-handling rules

### `agents/openai.yaml`

The skill UI metadata file. It defines the display name, short description, and default prompt used when the skill appears in Codex-compatible skill lists or interfaces.
