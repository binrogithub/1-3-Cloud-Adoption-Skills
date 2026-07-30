# OpenCode + LiteLLM Proxy for Huawei Cloud MaaS

This scenario demonstrates how to configure **OpenCode** to use **LiteLLM proxy** as a unified gateway to Huawei Cloud ModelArts (MaaS) models, with latency-based routing and automatic fallbacks across model groups.

## What's Included

| File | Description |
|------|-------------|
| `SKILL.md` | OpenCode skill definition — structured workflow for automated setup |
| `opencode-litellm-maas.docx` | Step-by-step manual configuration guide (Word document) |

## Two Ways to Set Up

### Option 1: Automated Setup (Recommended)

Use the **`SKILL.md`** file with an AI coding assistant (Hermes, OpenCode, Claude, or any compatible agent). The skill contains a complete, verified workflow that will:

1. Check prerequisites (Python 3.12, uv/pip, OpenCode)
2. Create a Python venv and install LiteLLM
3. Generate the proxy config with all MaaS models organized by routing group
4. Configure OpenCode to use the LiteLLM proxy
5. Create a one-command startup script
6. Verify the setup is working

The AI agent reads the skill and executes each step autonomously, including verification checks.

### Option 2: Manual Setup

Follow the **`opencode-litellm-maas.docx`** Word document for a step-by-step manual configuration. This is useful when:

- You want to understand each step in detail
- You are configuring an environment without an AI assistant
- You need to troubleshoot a specific step
- You prefer full control over the process

## Architecture

```
OpenCode → LiteLLM Proxy (localhost:4000) → Huawei Cloud MaaS → DeepSeek/GLM models
```

LiteLLM provides latency-based routing across 5 model groups:

| Group | Fallback Chain | Use Case |
|-------|---------------|----------|
| `economy` | V3.1-Terminus → V3 → V3.2 | Simple tasks, minimize cost |
| `fast` | V3.1-Terminus → V3.2 → GLM-5.2 | Quick edits, simple questions |
| `coding` | V4-Flash → GLM-5.2 → V3.2 | General coding (default) |
| `coding-heavy` | V4-Pro → GLM-5.2 → V4-Flash | Complex refactors, architecture |
| `reasoning` | R1 → GLM-5.1 → V4-Pro | Deep reasoning |

## Prerequisites

- Python 3.12+ (NOT 3.14+ — orjson build fails)
- `uv` (recommended) or `pip`
- `MAAS_API_KEY` (Huawei Cloud ModelArts API key)
- `opencode` installed globally

## License

MIT
