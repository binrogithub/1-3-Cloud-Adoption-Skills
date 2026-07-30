---
name: opencode-litellm-maas
description: Configure OpenCode with LiteLLM proxy for Huawei Cloud MaaS models with latency-based routing and fallbacks. Covers venv setup, config generation, opencode integration, and startup script.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: opencode-litellm-maas
---

# OpenCode + LiteLLM Proxy for Huawei Cloud MaaS

Set up **OpenCode** to use **LiteLLM proxy** as a unified gateway to Huawei Cloud ModelArts MaaS models. The proxy provides latency-based routing across model groups with automatic fallbacks, so OpenCode always gets a working model without hardcoding a single endpoint.

## Rules

1. **ALWAYS use a Python 3.12 venv** — Python 3.14+ breaks `orjson` which `litellm[proxy]` depends on. Use `uv` to manage the venv if the system Python is too new.
2. **NEVER hardcode `MAAS_API_KEY` in config.yaml** — use `os.environ/MAAS_API_KEY` so the key stays in env vars only.
3. **NEVER expose `MAAS_API_KEY` in logs** — LiteLLM logs may contain request details. Keep the key out of shell history by sourcing env scripts instead of passing it inline.
4. **ALWAYS kill existing LiteLLM on port 4000 before starting** — stale processes cause "address already in use" errors.
5. **Use `setsid` + `disown` to daemonize LiteLLM** — `nohup` alone may die when the parent shell exits. `setsid` creates a new session group so the proxy survives.
6. **Health check via `/v1/models` with auth header** — the `/health` endpoint returns 500 on some LiteLLM versions even when the proxy is fully functional. `/v1/models` with `Authorization: Bearer <master_key>` is the reliable check.
7. **Preserve existing `opencode.json` MCP config** — only replace the `provider` section. Never overwrite MCP server definitions (terraform, playwright, hcloud, etc.).

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python 3.12+ | 3.14+ is NOT supported (orjson build fails). Install via `uv` if needed. |
| `uv` (recommended) or `pip` | For venv + package management. `uv` handles Python version downloads automatically. |
| `MAAS_API_KEY` | Huawei Cloud ModelArts API key (same account as your Huawei Cloud console). |
| `opencode` | Installed globally (`npm install -g opencode` or equivalent). |
| `lsof` | For port checking in the startup script. Usually pre-installed on Linux. |
| `curl` | For health checks. Pre-installed on most systems. |

**Minimum resources:** 512 MB RAM, 200 MB disk (for venv + litellm packages).

## Available MaaS Models (July 2026)

| Model | Context | Max Output | Deep Thinking | Cost Tier |
|-------|---------|------------|---------------|-----------|
| DeepSeek-V3.1-Terminus | 128K | 32K | Configurable | $ |
| DeepSeek-V3 | 128K | 64K | No | $ |
| DeepSeek-V3.2 | 160K | 32K | Configurable | $$ |
| DeepSeek-V4-Flash | 1M | 128K | Configurable | $$$ |
| GLM-5.2 | 198K | 128K | Configurable | $$$ |
| GLM-5.1 | 198K | 128K | Configurable | $$$$ |
| GLM-5 | 198K | 64K | Configurable | $$$$ |
| DeepSeek-V4-Pro | 1M | 128K | Configurable | $$$$$ |
| DeepSeek-R1 | 128K | 32K | Always active | $$$$$ |

All MaaS models tolerate `reasoning_content` in history, so they are **mutually compatible** in fallback chains (unlike Groq/Cerebras which break on thinking tokens).

## Routing Groups

| Group | Fallback Chain | Use Case | Alias |
|-------|---------------|----------|-------|
| `economy` | V3.1-Terminus → V3 → V3.2 | Simple tasks, minimize cost | `cheap` |
| `fast` | V3.1-Terminus → V3.2 → GLM-5.2 | Quick edits, simple questions | — |
| `coding` | V4-Flash → GLM-5.2 → V3.2 | General coding (default) | `default` |
| `coding-heavy` | V4-Pro → GLM-5.2 → V4-Flash | Complex refactors, architecture | `heavy` |
| `reasoning` | R1 → GLM-5.1 → V4-Pro | Deep reasoning | — |

**Cross-group fallbacks:**

- `economy` → fast → coding
- `fast` → coding
- `coding` → fast
- `coding-heavy` → coding → fast
- `reasoning` → coding-heavy

## Workflow

### Step 1: CHECK PREREQUISITES

Verify Python, uv/pip, and opencode are available:

```bash
python3 --version          # Need 3.12+ (NOT 3.14+)
which opencode             # Must be installed
which uv || which pip3     # At least one package manager
```

If system Python is 3.14+, install `uv` to manage a 3.12 venv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# uv is now at ~/.local/bin/uv
```

### Step 2: CREATE VENV & INSTALL LITELLM

```bash
# With uv (recommended — auto-downloads Python 3.12 if needed):
~/.local/bin/uv venv ~/litellm-env --python 3.12
~/.local/bin/uv pip install 'litellm[proxy]' --python ~/litellm-env/bin/python

# Or with system Python 3.12:
python3.12 -m venv ~/litellm-env
source ~/litellm-env/bin/activate
pip install 'litellm[proxy]'
```

Verify:

```bash
source ~/litellm-env/bin/activate
python -c "import litellm; print('litellm OK')"
which litellm   # Should point to ~/litellm-env/bin/litellm
```

### Step 3: CREATE CONFIG DIRECTORY & FILES

```bash
mkdir -p ~/litellm
```

#### 3a. `~/litellm/config.yaml`

Create the LiteLLM proxy config with all MaaS models organized by routing group:

```yaml
# ============================================================
# LiteLLM Proxy Config - MaaS-Only (Huawei ModelArts)
# ============================================================
# All MaaS models tolerate reasoning_content in history,
# so ALL are mutually compatible in fallbacks.
#
# Available models (July 2026):
#   Deep Thinking configurable: glm-5.2, glm-5.1, glm-5,
#     deepseek-v4-pro, deepseek-v4-flash, deepseek-v3.2, deepseek-v3.1-terminus
#   Deep Thinking always active: deepseek-r1-250528
#   Without Deep Thinking: DeepSeek-V3
#
# Cost order (cheap → expensive):
#   v3.1-terminus < V3 < v3.2 < v4-flash < glm-5.2 < glm-5.1 < glm-5 < v4-pro < r1
#
# Groups:
#   economy:      Cheap models rotating, simple tasks
#   fast:         Quick edits with decent quality
#   coding:       General coding (default)
#   coding-heavy: Complex refactors, architecture
#   reasoning:    Deep reasoning

model_list:
  # ── ECONOMY: simple tasks, minimize cost ──
  # DeepSeek-V3 NO deep thinking = fewer output tokens
  # Rotate among the 3 cheapest
  - model_name: economy
    litellm_params:
      model: custom_openai/deepseek-v3.1-terminus
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: economy
    litellm_params:
      model: custom_openai/DeepSeek-V3
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: economy
    litellm_params:
      model: custom_openai/deepseek-v3.2
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  # ── FAST: quick edits, simple questions with quality ──
  - model_name: fast
    litellm_params:
      model: custom_openai/deepseek-v3.1-terminus
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: fast
    litellm_params:
      model: custom_openai/deepseek-v3.2
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: fast
    litellm_params:
      model: custom_openai/glm-5.2
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  # ── CODING: general coding tasks ──
  - model_name: coding
    litellm_params:
      model: custom_openai/deepseek-v4-flash
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: coding
    litellm_params:
      model: custom_openai/glm-5.2
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: coding
    litellm_params:
      model: custom_openai/deepseek-v3.2
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  # ── CODING-HEAVY: complex refactors, architecture ──
  - model_name: coding-heavy
    litellm_params:
      model: custom_openai/deepseek-v4-pro
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: coding-heavy
    litellm_params:
      model: custom_openai/glm-5.2
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: coding-heavy
    litellm_params:
      model: custom_openai/deepseek-v4-flash
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  # ── REASONING: deep reasoning ──
  - model_name: reasoning
    litellm_params:
      model: custom_openai/deepseek-r1-250528
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: reasoning
    litellm_params:
      model: custom_openai/glm-5.1
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: reasoning
    litellm_params:
      model: custom_openai/deepseek-v4-pro
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  # ── Individual models (direct access) ──
  - model_name: deepseek-v4-pro
    litellm_params:
      model: custom_openai/deepseek-v4-pro
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: deepseek-v4-flash
    litellm_params:
      model: custom_openai/deepseek-v4-flash
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: deepseek-v3.2
    litellm_params:
      model: custom_openai/deepseek-v3.2
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: deepseek-v3.1-terminus
    litellm_params:
      model: custom_openai/deepseek-v3.1-terminus
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: deepseek-v3
    litellm_params:
      model: custom_openai/DeepSeek-V3
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: deepseek-r1
    litellm_params:
      model: custom_openai/deepseek-r1-250528
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: glm-5.2
    litellm_params:
      model: custom_openai/glm-5.2
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: glm-5.1
    litellm_params:
      model: custom_openai/glm-5.1
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: glm-5
    litellm_params:
      model: custom_openai/glm-5
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

router_settings:
  routing_strategy: latency-based-routing
  allowed_fails: 3
  cooldown_time: 60
  num_retries: 2
  timeout: 600
  retry_after: 0
  model_group_alias:
    heavy: coding-heavy
    default: coding
    cheap: economy

litellm_settings:
  drop_params: true
  set_verbose: false
  request_timeout: 600
  fallbacks:
    - economy: ["fast", "coding"]
    - fast: ["coding"]
    - coding: ["fast"]
    - coding-heavy: ["coding", "fast"]
    - reasoning: ["coding-heavy"]

general_settings:
  master_key: sk-123456
  database_url: null
```

#### 3b. `~/litellm/init_litellm_env.sh`

Exports the MaaS API key. **Replace the placeholder with your actual key.**

```bash
#!/bin/bash
export MAAS_API_KEY="<YOUR_MAAS_API_KEY>"
```

```bash
chmod +x ~/litellm/init_litellm_env.sh
```

#### 3c. `~/litellm/init_opencode_env.sh`

Sets environment variables so OpenCode talks to the local LiteLLM proxy instead of any direct provider:

```bash
#!/bin/bash
source ~/litellm/init_litellm_env.sh
export LITELLM_MASTER_KEY="sk-123456"
export OPENAI_API_KEY="$LITELLM_MASTER_KEY"
export OPENAI_BASE_URL="http://127.0.0.1:4000"
export API_TIMEOUT_MS=600000
unset ANTHROPIC_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN 2>/dev/null || true
```

```bash
chmod +x ~/litellm/init_opencode_env.sh
```

### Step 4: CONFIGURE OPENCODE

Edit `~/.opencode/opencode.json`. **Preserve the existing `mcp` section** — only replace the `provider` section.

Replace any existing provider (e.g. `huawei-maas`) with the `litellm` provider:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "...": "keep existing MCP servers unchanged"
  },
  "provider": {
    "litellm": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "LiteLLM Proxy (MaaS)",
      "options": {
        "baseURL": "http://127.0.0.1:4000",
        "apiKey": "sk-123456"
      },
      "models": {
        "economy": {
          "name": "Economy (V3.1-Terminus → V3 → V3.2) — min cost",
          "limit": { "context": 160000, "output": 32000 }
        },
        "fast": {
          "name": "Fast (V3.1-Terminus → V3.2 → GLM-5.2)",
          "limit": { "context": 198000, "output": 32000 }
        },
        "coding": {
          "name": "Coding (V4-Flash → GLM-5.2 → V3.2)",
          "limit": { "context": 1048576, "output": 131072 }
        },
        "coding-heavy": {
          "name": "Coding Heavy (V4-Pro → GLM-5.2 → V4-Flash)",
          "limit": { "context": 1048576, "output": 131072 }
        },
        "reasoning": {
          "name": "Reasoning (R1 → GLM-5.1 → V4-Pro)",
          "limit": { "context": 131072, "output": 32000 }
        },
        "deepseek-v4-pro": {
          "name": "DeepSeek-V4-Pro (direct)",
          "limit": { "context": 1048576, "output": 131072 }
        },
        "deepseek-v4-flash": {
          "name": "DeepSeek-V4-Flash (direct)",
          "limit": { "context": 1048576, "output": 131072 }
        },
        "deepseek-v3.2": {
          "name": "DeepSeek-V3.2 (direct)",
          "limit": { "context": 163840, "output": 32768 }
        },
        "deepseek-v3.1-terminus": {
          "name": "DeepSeek-V3.1-Terminus (direct)",
          "limit": { "context": 131072, "output": 32768 }
        },
        "deepseek-v3": {
          "name": "DeepSeek-V3 no CoT (direct)",
          "limit": { "context": 131072, "output": 65536 }
        },
        "deepseek-r1": {
          "name": "DeepSeek-R1 (direct)",
          "limit": { "context": 131072, "output": 32768 }
        },
        "glm-5.2": {
          "name": "GLM-5.2 (direct)",
          "limit": { "context": 202752, "output": 131072 }
        },
        "glm-5.1": {
          "name": "GLM-5.1 (direct)",
          "limit": { "context": 202752, "output": 131072 }
        },
        "glm-5": {
          "name": "GLM-5 (direct)",
          "limit": { "context": 202752, "output": 65536 }
        }
      }
    }
  }
}
```

### Step 5: CREATE STARTUP SCRIPT

Create `~/start_opencode.sh` — a simple script that kills any stale proxy, starts LiteLLM, waits for it to be ready, then launches OpenCode:

```bash
#!/bin/bash
set -euo pipefail

LITELLM_DIR="$HOME/litellm"
LITELLM_ENV="$HOME/litellm-env"
LITELLM_PORT=4000

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# 1. Kill existing LiteLLM on port 4000
PID=$(lsof -ti :$LITELLM_PORT 2>/dev/null || true)
if [[ -n "$PID" ]]; then
    warn "Killing LiteLLM on port $LITELLM_PORT (PID: $PID)..."
    kill -9 $PID 2>/dev/null || true
    sleep 1
    PID2=$(lsof -ti :$LITELLM_PORT 2>/dev/null || true)
    [[ -n "$PID2" ]] && error "Cannot free port $LITELLM_PORT"
    info "Port freed"
else
    info "Port $LITELLM_PORT free"
fi

# 2. Activate venv and source env vars
source "$LITELLM_ENV/bin/activate"
source "$LITELLM_DIR/init_litellm_env.sh"

# 3. Start LiteLLM proxy
info "Starting LiteLLM proxy on port $LITELLM_PORT..."
setsid litellm --config "$LITELLM_DIR/config.yaml" --port $LITELLM_PORT \
    > "$LITELLM_DIR/proxy.log" 2>&1 &
disown
info "LiteLLM started"

# 4. Wait for health check
info "Waiting for proxy..."
for i in $(seq 1 30); do
    if curl -sf -H "Authorization: Bearer sk-123456" "http://127.0.0.1:$LITELLM_PORT/v1/models" >/dev/null 2>&1; then
        echo
        info "Proxy ready at http://127.0.0.1:$LITELLM_PORT"
        break
    fi
    sleep 1
    printf "."
done

if ! curl -sf -H "Authorization: Bearer sk-123456" "http://127.0.0.1:$LITELLM_PORT/v1/models" >/dev/null 2>&1; then
    echo
    error "Proxy did not respond in 30s. Check: tail -20 $LITELLM_DIR/proxy.log"
fi

# 5. Set opencode env vars and launch
source "$LITELLM_DIR/init_opencode_env.sh"
info "Launching opencode..."
opencode
```

```bash
chmod +x ~/start_opencode.sh
```

### Step 6: VERIFY

Start the proxy manually and confirm it works:

```bash
source ~/litellm-env/bin/activate
source ~/litellm/init_litellm_env.sh
setsid litellm --config ~/litellm/config.yaml --port 4000 > ~/litellm/proxy.log 2>&1 &
disown

# Wait ~15s for startup, then check:
curl -s -H "Authorization: Bearer sk-123456" http://127.0.0.1:4000/v1/models | python3 -m json.tool | head -20
```

Expected output: a JSON list with 17 model IDs including `economy`, `fast`, `coding`, `coding-heavy`, `reasoning`, and all individual model names.

## Generated Files

```
~/litellm/
  config.yaml              # LiteLLM proxy config (MaaS-only, routing + fallbacks)
  init_litellm_env.sh      # Exports MAAS_API_KEY
  init_opencode_env.sh     # Sets OPENAI_API_KEY/BASE_URL to local proxy
  proxy.log                # LiteLLM proxy log (created at runtime)

~/litellm-env/             # Python 3.12 venv with litellm[proxy]

~/start_opencode.sh        # One-command startup: kill stale → start proxy → launch opencode

~/.opencode/
  opencode.json            # OpenCode config (litellm provider + MCP servers)
```

## Daily Usage

```bash
# Start everything (proxy + opencode):
~/start_opencode.sh

# Or manually:
source ~/litellm/init_opencode_env.sh
opencode
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `orjson` build fails | System Python is 3.14+. Use `uv venv --python 3.12` to get a compatible venv. |
| Proxy dies when shell closes | Use `setsid` + `disown` instead of `nohup` alone. |
| `/health` returns 500 | This is a known LiteLLM quirk. Use `/v1/models` with auth header for health checks. |
| "address already in use" | Kill stale process: `kill $(lsof -ti :4000)` |
| Model not found in cost map | Harmless warning — LiteLLM defaults cost to 0 for custom models. |
| `MAAS_API_KEY` not set | Source `init_litellm_env.sh` before starting the proxy. |
| OpenCode uses wrong provider | Ensure `opencode.json` has `litellm` as the only provider, and env vars point to `localhost:4000`. |

```bash
# View proxy log:
tail -f ~/litellm/proxy.log

# Check proxy health:
curl -s -H "Authorization: Bearer sk-123456" http://127.0.0.1:4000/v1/models

# List available models:
curl -s -H "Authorization: Bearer sk-123456" http://127.0.0.1:4000/v1/models | python3 -m json.tool

# Kill proxy:
kill $(lsof -ti :4000)

# Full restart:
~/start_opencode.sh
```
