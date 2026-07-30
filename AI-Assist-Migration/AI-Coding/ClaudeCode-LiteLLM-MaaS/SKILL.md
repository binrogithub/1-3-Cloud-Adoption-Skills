---
name: claude-code-litellm-maas
description: Configure Claude Code with LiteLLM proxy for Huawei Cloud MaaS models. Covers Node.js/Claude Code installation, venv setup, config generation with Claude model-name aliases, environment variable configuration, startup script, and model switching.
license: MIT
compatibility: claude-code
metadata:
  audience: infrastructure-engineers
  workflow: claude-code-litellm-maas
---

# Claude Code + LiteLLM Proxy for Huawei Cloud MaaS

Set up **Claude Code** to use **LiteLLM proxy** as a gateway to Huawei Cloud ModelArts MaaS models. Claude Code sends requests to LiteLLM (localhost:4000), which forwards them to MaaS using the `custom_openai` provider.

**Key technique:** Claude Code validates model names at startup. We register Claude-recognized model names (e.g. `claude-3-5-haiku-coding`) as aliases in LiteLLM's `config.yaml`, mapping them to actual MaaS models (e.g. `deepseek-v4-flash`). Claude Code thinks it's using Claude models; LiteLLM transparently routes to MaaS.

```
Claude Code → LiteLLM (localhost:4000) → Huawei Cloud MaaS → DeepSeek/GLM models
```

## Rules

1. **ALWAYS use a Python 3.12 venv** — Python 3.14+ breaks `orjson` which `litellm[proxy]` depends on. Use `uv` to manage the venv if the system Python is too new.
2. **NEVER hardcode `MAAS_API_KEY` in config.yaml** — use `os.environ/MAAS_API_KEY` so the key stays in env vars only.
3. **NEVER expose `MAAS_API_KEY` in logs** — LiteLLM logs may contain request details. Keep the key out of shell history by sourcing env scripts instead of passing it inline.
4. **ALWAYS `unset ANTHROPIC_API_KEY`** — if this env var is set, Claude Code attempts official Anthropic authentication and ignores `ANTHROPIC_AUTH_TOKEN`. This is the #1 cause of "Claude Code still tries to login to Anthropic".
5. **ALWAYS kill existing LiteLLM on port 4000 before starting** — stale processes cause "address already in use" errors.
6. **Use `setsid` + `disown` to daemonize LiteLLM** — `nohup` alone may die when the parent shell exits. `setsid` creates a new session group so the proxy survives.
7. **ALWAYS register Claude model-name aliases in config.yaml** — Claude Code expects specific model name patterns (`claude-3-5-haiku-*`, `claude-3-5-sonnet-*`, `claude-3-opus-*`). Without these aliases mapped in LiteLLM, Claude Code will fail at startup or when switching model tiers.
8. **`ANTHROPIC_MODEL` must match a `model_name` in config.yaml** — this is the model Claude Code uses for main responses. If it doesn't match a LiteLLM entry, requests will fail.
9. **Health check via `/v1/models` with auth header** — the `/health` endpoint returns 500 on some LiteLLM versions even when the proxy is fully functional. `/v1/models` with `Authorization: Bearer <master_key>` is the reliable check.

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Node.js 20+ | Required by Claude Code. Install via nodesource setup script if missing. |
| npm | Comes with Node.js. Used to install `@anthropic-ai/claude-code`. |
| Python 3.12+ | 3.14+ is NOT supported (orjson build fails). Install via `uv` if needed. |
| `uv` (recommended) or `pip` | For venv + package management. `uv` handles Python version downloads automatically. |
| `MAAS_API_KEY` | Huawei Cloud ModelArts API key (create in MaaS console → API Key Management). |
| `lsof` | For port checking in the startup script. Usually pre-installed on Linux. |
| `curl` | For health checks and API testing. Pre-installed on most systems. |

**Pre-condition:** An ECS instance on Huawei Cloud with EIP (public IP) for accessing MaaS endpoints. Ubuntu 24.04 used as reference OS.

**Minimum resources:** 512 MB RAM, 200 MB disk (for venv + litellm packages).

## Available MaaS Models (July 2026)

> **Note:** DeepSeek-V3.1-Terminus was fully retired on 2026-07-24. DeepSeek-V4-Flash replaces it as the recommended cost-effective model. Source: [DeepSeek API changelog](https://api-docs.deepseek.com/updates).

| Model | MaaS model ID | Context | Max Output | Deep Thinking | Cost Tier |
|-------|---------------|---------|------------|---------------|-----------|
| DeepSeek-V4-Flash | `deepseek-v4-flash` | 1M | 128K | Configurable | $$ |
| DeepSeek-V4-Pro | `deepseek-v4-pro` | 1M | 128K | Configurable | $$$$ |
| DeepSeek-V3.2 | `deepseek-v3.2` | 160K | 32K | Configurable | $ |
| DeepSeek-V3 | `DeepSeek-V3` | 128K | 64K | No | $ |
| DeepSeek-R1 | `deepseek-r1-250528` | 128K | 32K | Always active | $$$$ |
| GLM-5.2 | `glm-5.2` | 198K | 128K | Configurable | $$$ |
| GLM-5.1 | `glm-5.1` | 198K | 128K | Configurable | $$$$ |
| GLM-5 | `glm-5` | 198K | 64K | Configurable | $$$$ |

## Model Name Aliases

Claude Code sends model names it recognizes. We map these to MaaS models in LiteLLM:

| Claude Code sees (`model_name`) | LiteLLM routes to (`litellm_params.model`) | Env var | Use case |
|----------------------------------|---------------------------------------------|--------|----------|
| `claude-3-5-haiku-coding` | `custom_openai/deepseek-v4-flash` | `ANTHROPIC_MODEL` | Default main model |
| `claude-3-5-haiku-20241022` | `custom_openai/deepseek-v3.2` | `ANTHROPIC_SMALL_FAST_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL` | Background/fast tasks |
| `claude-3-5-sonnet-20241022` | `custom_openai/deepseek-v4-pro` | `ANTHROPIC_DEFAULT_SONNET_MODEL` | Heavy coding |
| `claude-3-opus-20240229` | `custom_openai/deepseek-v4-pro` | `ANTHROPIC_DEFAULT_OPUS_MODEL` | Opus tier |

Additionally, all 8 MaaS models are registered with their real names for direct access via `/model` switching.

## Workflow

### Step 1: CHECK PREREQUISITES

Verify Node.js, Python, and check if Claude Code is already installed:

```bash
node --version              # Need 20+ (for Claude Code)
python3 --version          # Need 3.12+ (NOT 3.14+)
which claude 2>/dev/null   # Check if Claude Code is already installed
which uv || which pip3     # At least one package manager
```

If system Python is 3.14+, install `uv` to manage a 3.12 venv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# uv is now at ~/.local/bin/uv
```

### Step 2: INSTALL CLAUDE CODE

Skip this step if `claude --version` already returns a version number.

#### 2a. Install Node.js 20 (if missing or too old)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node --version    # Verify: v20.x.x
```

#### 2b. Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
claude --version  # Verify installation
```

### Step 3: CREATE VENV & INSTALL LITELLM

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

### Step 4: CREATE CONFIG DIRECTORY & FILES

```bash
mkdir -p ~/litellm
```

#### 4a. `~/litellm/config.yaml`

Create the LiteLLM proxy config with Claude model-name aliases + all MaaS models:

```yaml
# ============================================================
# LiteLLM Proxy Config - Claude Code + MaaS (Huawei ModelArts)
# ============================================================
# Claude Code sends model names it recognizes (claude-3-5-haiku-*,
# claude-3-5-sonnet-*, claude-3-opus-*). We map these to actual
# MaaS models. All 8 MaaS models are also available directly.
#
# Available models (July 2026):
#   Deep Thinking configurable: glm-5.2, glm-5.1, glm-5,
#     deepseek-v4-pro, deepseek-v4-flash, deepseek-v3.2
#   Deep Thinking always active: deepseek-r1-250528
#   Without Deep Thinking: DeepSeek-V3
#
# Retired: deepseek-v3.1-terminus (fully retired 2026-07-24)
#
# Cost order (cheap -> expensive):
#   v3.2 < V3 < v4-flash < glm-5.2 < glm-5.1 < glm-5 < v4-pro < r1

model_list:
  # ===============================================================
  # Claude model-name aliases (what Claude Code expects to see)
  # ===============================================================

  # Default main model: Claude Code thinks it's Haiku, uses V4-Flash
  - model_name: claude-3-5-haiku-coding
    litellm_params:
      model: custom_openai/deepseek-v4-flash
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  # Fast/background model: Claude Code thinks Haiku, uses V3.2
  - model_name: claude-3-5-haiku-20241022
    litellm_params:
      model: custom_openai/deepseek-v3.2
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  # Sonnet tier: Claude Code thinks Sonnet, uses V4-Pro
  - model_name: claude-3-5-sonnet-20241022
    litellm_params:
      model: custom_openai/deepseek-v4-pro
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  # Opus tier: Claude Code thinks Opus, uses V4-Pro
  - model_name: claude-3-opus-20240229
    litellm_params:
      model: custom_openai/deepseek-v4-pro
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  # ===============================================================
  # Direct MaaS model access (switch with /model <name>)
  # ===============================================================

  - model_name: deepseek-v4-flash
    litellm_params:
      model: custom_openai/deepseek-v4-flash
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: deepseek-v4-pro
    litellm_params:
      model: custom_openai/deepseek-v4-pro
      api_base: https://api-ap-southeast-1.modelarts-maas.com/openai/v1
      api_key: os.environ/MAAS_API_KEY

  - model_name: deepseek-v3.2
    litellm_params:
      model: custom_openai/deepseek-v3.2
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

litellm_settings:
  drop_params: true   # auto drop params MaaS doesn't support

general_settings:
  master_key: sk-123456
```

#### 4b. `~/litellm/init_litellm_env.sh`

Exports the MaaS API key. **Replace the placeholder with your actual key.**

```bash
#!/bin/bash
# Source before starting LiteLLM:
#   source ~/litellm/init_litellm_env.sh && litellm --config ~/litellm/config.yaml --port 4000
export MAAS_API_KEY="<YOUR_MAAS_API_KEY>"
```

```bash
chmod +x ~/litellm/init_litellm_env.sh
```

#### 4c. `~/litellm/init_claude_env.sh`

Sets environment variables so Claude Code talks to the local LiteLLM proxy instead of Anthropic's servers:

```bash
#!/bin/bash
# Source before starting Claude Code:
#   source ~/litellm/init_claude_env.sh && claude

# ── LiteLLM master key (must match master_key in config.yaml) ──
export LITELLM_MASTER_KEY="sk-123456"

# ── Huawei Cloud MaaS API key ──
source ~/litellm/init_litellm_env.sh

# ── Claude Code → LiteLLM proxy ──
export ANTHROPIC_BASE_URL="http://127.0.0.1:4000"
export ANTHROPIC_AUTH_TOKEN="$LITELLM_MASTER_KEY"

# ── Model mapping (all names must exist in config.yaml) ──
export ANTHROPIC_MODEL="claude-3-5-haiku-coding"            # → deepseek-v4-flash
export ANTHROPIC_SMALL_FAST_MODEL="claude-3-5-haiku-20241022" # → deepseek-v3.2
export ANTHROPIC_DEFAULT_HAIKU_MODEL="claude-3-5-haiku-20241022"  # → deepseek-v3.2
export ANTHROPIC_DEFAULT_SONNET_MODEL="claude-3-5-sonnet-20241022" # → deepseek-v4-pro
export ANTHROPIC_DEFAULT_OPUS_MODEL="claude-3-opus-20240229"      # → deepseek-v4-pro
export CLAUDE_CODE_SUBAGENT_MODEL="claude-3-5-haiku-20241022"     # → deepseek-v3.2

# ── CRITICAL: unset official Anthropic auth ──
# Without this, Claude Code tries to login to Anthropic and ignores ANTHROPIC_AUTH_TOKEN
unset ANTHROPIC_API_KEY

# ── API timeout (ms) ──
export API_TIMEOUT_MS=600000

# ── Disable non-essential traffic (optional, reduces noise) ──
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
```

```bash
chmod +x ~/litellm/init_claude_env.sh
```

### Step 5: CREATE STARTUP SCRIPT

Create `~/start_claude.sh` — kills any stale proxy, starts LiteLLM, waits for it to be ready, then launches Claude Code:

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
info "LiteLLM started (daemon)"

# 4. Wait for health check
info "Waiting for proxy..."
for i in $(seq 1 30); do
    if curl -sf -H "Authorization: Bearer sk-123456" \
        "http://127.0.0.1:$LITELLM_PORT/v1/models" >/dev/null 2>&1; then
        echo
        info "Proxy ready at http://127.0.0.1:$LITELLM_PORT"
        break
    fi
    sleep 1
    printf "."
done

if ! curl -sf -H "Authorization: Bearer sk-123456" \
    "http://127.0.0.1:$LITELLM_PORT/v1/models" >/dev/null 2>&1; then
    echo
    error "Proxy did not respond in 30s. Check: tail -20 $LITELLM_DIR/proxy.log"
fi

# 5. Source Claude env and launch
source "$LITELLM_DIR/init_claude_env.sh"
info "Launching Claude Code..."
info ""
info "Model aliases:"
info "  claude-3-5-haiku-coding       -> deepseek-v4-flash  (default)"
info "  claude-3-5-haiku-20241022     -> deepseek-v3.2     (fast/bg)"
info "  claude-3-5-sonnet-20241022    -> deepseek-v4-pro   (sonnet)"
info "  claude-3-opus-20240229        -> deepseek-v4-pro   (opus)"
info ""
info "Switch models with: /model <name>"
info "  e.g. /model deepseek-v4-pro, /model glm-5.2, /model deepseek-r1"
info ""
claude
```

```bash
chmod +x ~/start_claude.sh
```

### Step 6: VERIFY

Start the proxy manually and confirm it works:

```bash
source ~/litellm-env/bin/activate
source ~/litellm/init_litellm_env.sh
setsid litellm --config ~/litellm/config.yaml --port 4000 > ~/litellm/proxy.log 2>&1 &
disown

# Wait ~10s for startup, then check:
curl -s -H "Authorization: Bearer sk-123456" http://127.0.0.1:4000/v1/models | python3 -m json.tool
```

Expected output: a JSON list with 12 model IDs including `claude-3-5-haiku-coding`, `claude-3-5-haiku-20241022`, `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`, and all 8 MaaS model names.

Test an API call:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-123456" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-3-5-haiku-coding", "messages": [{"role": "user", "content": "Hello"}]}'
```

Verify Claude Code:

```bash
claude --version
```

## Generated Files

```
~/litellm/
  config.yaml              # LiteLLM proxy config (4 Claude aliases + 8 MaaS models)
  init_litellm_env.sh      # Exports MAAS_API_KEY
  init_claude_env.sh       # Sets ANTHROPIC_* env vars for Claude Code
  proxy.log                # LiteLLM proxy log (created at runtime)

~/litellm-env/             # Python 3.12 venv with litellm[proxy]

~/start_claude.sh          # One-command startup: kill stale -> start proxy -> launch claude
```

## Daily Usage

```bash
# Start everything (proxy + Claude Code):
~/start_claude.sh

# Or manually (two terminals):
# Terminal 1 - start proxy:
source ~/litellm-env/bin/activate
source ~/litellm/init_litellm_env.sh
litellm --config ~/litellm/config.yaml --port 4000

# Terminal 2 - start Claude Code:
cd ~/yourproject
source ~/litellm/init_claude_env.sh
claude
```

### Switching models in Claude Code

Inside a Claude Code conversation, use the `/model` command:

```bash
/model deepseek-v4-pro       # Switch to V4-Pro directly
/model deepseek-v4-flash     # Switch to V4-Flash directly
/model deepseek-v3.2         # Switch to V3.2 (economical)
/model glm-5.2               # Switch to GLM-5.2
/model deepseek-r1           # Switch to DeepSeek-R1 (deep reasoning)
/model claude-3-5-sonnet-20241022  # Switch to Sonnet alias (-> V4-Pro)
```

After switching, subsequent conversation will use the new model.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `orjson` build fails | System Python is 3.14+. Use `uv venv --python 3.12` to get a compatible venv. |
| Claude Code still tries to login to Anthropic | `ANTHROPIC_API_KEY` is set. Run `unset ANTHROPIC_API_KEY` and ensure `ANTHROPIC_AUTH_TOKEN` is set correctly. |
| API call timeout | Network connectivity issue. Increase `API_TIMEOUT_MS` (e.g. `export API_TIMEOUT_MS=600000`). |
| Authenticate fail | `master_key` in `config.yaml` doesn't match `ANTHROPIC_AUTH_TOKEN` in `init_claude_env.sh`. Make them consistent. |
| Proxy dies when shell closes | Use `setsid` + `disown` instead of `nohup` alone. |
| `/health` returns 500 | Known LiteLLM quirk. Use `/v1/models` with auth header for health checks. |
| "address already in use" | Kill stale process: `kill $(lsof -ti :4000)` |
| `MAAS_API_KEY` not set | Source `init_litellm_env.sh` before starting the proxy. |
| Model not found | The `model_name` in the error must exist in `config.yaml`. Check spelling and that LiteLLM is running with the correct config file. |
| `pip install` failure | Python env conflict. Use venv: `python3.12 -m venv ~/litellm-env && source ~/litellm-env/bin/activate` |

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
~/start_claude.sh
```

## FAQ

**Q: Why do we need Claude model-name aliases?**
A: Claude Code validates model names at startup and when switching model tiers (haiku/sonnet/opus). By registering aliases like `claude-3-5-haiku-coding` in LiteLLM's `config.yaml`, Claude Code accepts the model name while LiteLLM transparently routes the request to the actual MaaS model.

**Q: Can I use MaaS model names directly without aliases?**
A: Yes, for the `/model` switch command (e.g. `/model deepseek-v4-pro`). However, the default model in `ANTHROPIC_MODEL` should use a Claude-recognized name to avoid startup issues. The env vars `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, and `ANTHROPIC_DEFAULT_OPUS_MODEL` must also point to names that exist in `config.yaml`.

**Q: What happened to DeepSeek-V3.1-Terminus?**
A: It was fully retired on 2026-07-24. DeepSeek-V4-Flash replaces it as the recommended cost-effective model. The DeepSeek API changelog states: "deepseek-chat & deepseek-reasoner will be fully retired and inaccessible after Jul 24th, 2026."

**Q: Why is `unset ANTHROPIC_API_KEY` critical?**
A: If `ANTHROPIC_API_KEY` is set in the environment (e.g. from a previous Anthropic setup), Claude Code will attempt to authenticate with Anthropic's servers and ignore `ANTHROPIC_AUTH_TOKEN`. Unsetting it forces Claude Code to use the auth token against the proxy.

**Q: What is `drop_params: true`?**
A: MaaS doesn't support all OpenAI/Anthropic parameters. `drop_params: true` tells LiteLLM to automatically drop unsupported parameters instead of returning an error.
