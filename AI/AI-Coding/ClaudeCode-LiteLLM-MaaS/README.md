# Claude Code + LiteLLM Proxy for Huawei Cloud MaaS

This scenario demonstrates how to configure **Claude Code** to use **LiteLLM proxy** as a gateway to Huawei Cloud ModelArts (MaaS) models. Claude Code sends requests to LiteLLM (localhost:4000), which transparently forwards them to MaaS using the `custom_openai` provider.

## What's Included

| File | Description |
|------|-------------|
| `SKILL.md` | Claude Code skill definition — structured workflow for automated setup |
| `how-to-config-litellm-with-claude-for-hwc-maas-v1.docx` | Step-by-step manual configuration guide (Word document) |

## Two Ways to Set Up

### Option 1: Automated Setup (Recommended)

Use the **`SKILL.md`** file with an AI coding assistant (Hermes, OpenCode, Claude, or any compatible agent). The skill contains a complete, verified workflow that will:

1. Check prerequisites (Node.js 20+, Python 3.12, Claude Code)
2. Install Claude Code via npm (if not already installed)
3. Create a Python venv and install LiteLLM
4. Generate the proxy config with Claude model-name aliases mapped to MaaS models
5. Configure environment variables for Claude Code → LiteLLM routing
6. Create a one-command startup script
7. Verify the setup is working

The AI agent reads the skill and executes each step autonomously, including verification checks.

### Option 2: Manual Setup

Follow the **`how-to-config-litellm-with-claude-for-hwc-maas-v1.docx`** Word document for a step-by-step manual configuration. This is useful when:

- You want to understand each step in detail
- You are configuring an environment without an AI assistant
- You need to troubleshoot a specific step
- You prefer full control over the process

## Architecture

```
Claude Code → LiteLLM Proxy (localhost:4000) → Huawei Cloud MaaS → DeepSeek/GLM models
```

**Key technique:** Claude Code validates model names at startup. The LiteLLM config registers Claude-recognized model names (e.g. `claude-3-5-haiku-coding`) as aliases that map to actual MaaS models (e.g. `deepseek-v4-flash`). Claude Code thinks it's using Claude models; LiteLLM transparently routes to MaaS.

| Claude Code sees | LiteLLM routes to | Use case |
|-------------------|-------------------|----------|
| `claude-3-5-haiku-coding` | `deepseek-v4-flash` | Default main model |
| `claude-3-5-haiku-20241022` | `deepseek-v3.2` | Background/fast tasks |
| `claude-3-5-sonnet-20241022` | `deepseek-v4-pro` | Heavy coding |
| `claude-3-opus-20240229` | `deepseek-v4-pro` | Opus tier |

## Prerequisites

- Node.js 20+ (for Claude Code)
- Python 3.12+ (NOT 3.14+ — orjson build fails)
- `uv` (recommended) or `pip`
- `MAAS_API_KEY` (Huawei Cloud ModelArts API key)

## License

MIT
