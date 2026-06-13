---
name: pi-huawei-maas-cross-platform
description: Configure Pi Coding Agent on Windows or Linux to use Huawei Cloud ModelArts MaaS through an OpenAI-compatible endpoint. Use when reproducing Pi provider configuration, creating or updating Models.json or models.json under the Pi agent directory, selecting glm-5.1 as the default model, handling Windows and Linux path or filename differences, validating MaaS connectivity, or documenting a secure cross-platform Pi Coding Agent MaaS setup without exposing API keys.
---

# Pi Huawei MaaS Cross Platform

## Overview

Use this skill to configure Pi Coding Agent on Windows or Linux so its local model registry points to Huawei Cloud ModelArts MaaS through the OpenAI-compatible API.

```text
Pi Coding Agent
  -> local Pi agent config
  -> provider: huawei-cloud-maas
  -> Huawei ModelArts MaaS OpenAI-compatible endpoint
  -> default model: glm-5.1
```

Default endpoint and model:

```text
https://api-ap-southeast-1.modelarts-maas.com/openai/v1/
glm-5.1
```

Use placeholders in reusable material. Never write a real MaaS API key into this skill or any shared documentation.

## Platform Decision

Choose the platform-specific path and commands first:

| Platform | Pi agent directory | Model registry file | Settings file |
| --- | --- | --- | --- |
| Windows | `%USERPROFILE%\.pi\agent` | `models.json` or `Models.json` | `settings.json` |
| Linux | `$HOME/.pi/agent` | `models.json` or `Models.json` | `settings.json` |

Windows filesystems are usually case-insensitive, but Linux filesystems are case-sensitive. Detect the model registry filename that Pi already uses and preserve that casing. The observed local Pi setup used `models.json`; some references may write `Models.json`.

## Shared Provider Configuration

Add or update this provider under the top-level `providers` object in the Pi model registry. Preserve any existing unrelated providers.

```json
{
  "providers": {
    "huawei-cloud-maas": {
      "baseUrl": "https://api-ap-southeast-1.modelarts-maas.com/openai/v1/",
      "api": "openai-completions",
      "apiKey": "replace-with-your-maas-api-key",
      "models": [
        {
          "id": "glm-5.1",
          "name": "glm-5.1",
          "contextWindow": 128000,
          "maxTokens": 4096,
          "reasoning": true,
          "compat": {
            "thinkingFormat": "zai",
            "supportsDeveloperRole": false,
            "supportsReasoningEffort": false
          }
        },
        {
          "id": "glm-5",
          "name": "glm-5",
          "contextWindow": 128000,
          "maxTokens": 4096
        },
        {
          "id": "deepseek-v4-flash",
          "name": "DeepSeek-V4-Flash",
          "contextWindow": 64000,
          "maxTokens": 2048
        },
        {
          "id": "deepseek-v3.2",
          "name": "deepseek-v3.2",
          "contextWindow": 64000,
          "maxTokens": 2048
        }
      ]
    }
  }
}
```

Set or merge these defaults in `settings.json`:

```json
{
  "defaultProvider": "huawei-cloud-maas",
  "defaultModel": "glm-5.1",
  "defaultThinkingLevel": "high"
}
```

Preserve existing settings such as `lastChangelogVersion` or `shellPath`. Only change `shellPath` when the target Pi build uses it and the current value is wrong for the operating system.

## Windows Setup

Use PowerShell for Windows configuration.

1. Resolve the Pi config files and create backups.

```powershell
$PiAgentDir = Join-Path $env:USERPROFILE ".pi\agent"
New-Item -ItemType Directory -Path $PiAgentDir -Force | Out-Null

$ModelsLower = Join-Path $PiAgentDir "models.json"
$ModelsUpper = Join-Path $PiAgentDir "Models.json"
if (Test-Path -LiteralPath $ModelsLower) {
  $PiModelsFile = $ModelsLower
} elseif (Test-Path -LiteralPath $ModelsUpper) {
  $PiModelsFile = $ModelsUpper
} else {
  $PiModelsFile = $ModelsLower
}

$PiSettingsFile = Join-Path $PiAgentDir "settings.json"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

if (Test-Path -LiteralPath $PiModelsFile) {
  Copy-Item -LiteralPath $PiModelsFile -Destination "$PiModelsFile.bak.$Stamp" -Force
}
if (Test-Path -LiteralPath $PiSettingsFile) {
  Copy-Item -LiteralPath $PiSettingsFile -Destination "$PiSettingsFile.bak.$Stamp" -Force
}
```

2. Merge the Huawei MaaS provider and defaults.

```powershell
$env:HUAWEI_MAAS_API_KEY = "replace-with-your-maas-api-key"

$Provider = [ordered]@{
  baseUrl = "https://api-ap-southeast-1.modelarts-maas.com/openai/v1/"
  api = "openai-completions"
  apiKey = $env:HUAWEI_MAAS_API_KEY
  models = @(
    [ordered]@{
      id = "glm-5.1"
      name = "glm-5.1"
      contextWindow = 128000
      maxTokens = 4096
      reasoning = $true
      compat = [ordered]@{
        thinkingFormat = "zai"
        supportsDeveloperRole = $false
        supportsReasoningEffort = $false
      }
    },
    [ordered]@{ id = "glm-5"; name = "glm-5"; contextWindow = 128000; maxTokens = 4096 },
    [ordered]@{ id = "deepseek-v4-flash"; name = "DeepSeek-V4-Flash"; contextWindow = 64000; maxTokens = 2048 },
    [ordered]@{ id = "deepseek-v3.2"; name = "deepseek-v3.2"; contextWindow = 64000; maxTokens = 2048 }
  )
}

if (Test-Path -LiteralPath $PiModelsFile) {
  $Models = Get-Content -LiteralPath $PiModelsFile -Raw | ConvertFrom-Json
} else {
  $Models = [pscustomobject]@{ providers = [pscustomobject]@{} }
}

if (-not $Models.PSObject.Properties["providers"]) {
  $Models | Add-Member -NotePropertyName providers -NotePropertyValue ([pscustomobject]@{})
}

$Models.providers | Add-Member -NotePropertyName "huawei-cloud-maas" -NotePropertyValue $Provider -Force
$Models | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $PiModelsFile -Encoding UTF8

if (Test-Path -LiteralPath $PiSettingsFile) {
  $Settings = Get-Content -LiteralPath $PiSettingsFile -Raw | ConvertFrom-Json
} else {
  $Settings = [pscustomobject]@{}
}

$Settings | Add-Member -NotePropertyName defaultProvider -NotePropertyValue "huawei-cloud-maas" -Force
$Settings | Add-Member -NotePropertyName defaultModel -NotePropertyValue "glm-5.1" -Force
$Settings | Add-Member -NotePropertyName defaultThinkingLevel -NotePropertyValue "high" -Force
$Settings | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $PiSettingsFile -Encoding UTF8
```

3. Restart Pi Coding Agent.

## Linux Setup

Use bash for Linux configuration.

1. Resolve the Pi config files and create backups.

```bash
set -euo pipefail

PI_AGENT_DIR="${PI_AGENT_DIR:-$HOME/.pi/agent}"
mkdir -p "$PI_AGENT_DIR"

if [ -f "$PI_AGENT_DIR/models.json" ]; then
  PI_MODELS_FILE="$PI_AGENT_DIR/models.json"
elif [ -f "$PI_AGENT_DIR/Models.json" ]; then
  PI_MODELS_FILE="$PI_AGENT_DIR/Models.json"
else
  PI_MODELS_FILE="$PI_AGENT_DIR/models.json"
fi

PI_SETTINGS_FILE="$PI_AGENT_DIR/settings.json"
STAMP="$(date +%Y%m%d-%H%M%S)"

[ -f "$PI_MODELS_FILE" ] && cp -p "$PI_MODELS_FILE" "$PI_MODELS_FILE.bak.$STAMP"
[ -f "$PI_SETTINGS_FILE" ] && cp -p "$PI_SETTINGS_FILE" "$PI_SETTINGS_FILE.bak.$STAMP"
```

2. Merge the Huawei MaaS provider and defaults.

```bash
export HUAWEI_MAAS_API_KEY="replace-with-your-maas-api-key"

python3 - <<'PY'
import json
import os
from pathlib import Path

agent_dir = Path(os.environ.get("PI_AGENT_DIR", Path.home() / ".pi" / "agent"))
agent_dir.mkdir(parents=True, exist_ok=True)

models_path = agent_dir / "models.json"
if not models_path.exists() and (agent_dir / "Models.json").exists():
    models_path = agent_dir / "Models.json"

settings_path = agent_dir / "settings.json"
api_key = os.environ["HUAWEI_MAAS_API_KEY"]

provider = {
    "baseUrl": "https://api-ap-southeast-1.modelarts-maas.com/openai/v1/",
    "api": "openai-completions",
    "apiKey": api_key,
    "models": [
        {
            "id": "glm-5.1",
            "name": "glm-5.1",
            "contextWindow": 128000,
            "maxTokens": 4096,
            "reasoning": True,
            "compat": {
                "thinkingFormat": "zai",
                "supportsDeveloperRole": False,
                "supportsReasoningEffort": False,
            },
        },
        {"id": "glm-5", "name": "glm-5", "contextWindow": 128000, "maxTokens": 4096},
        {"id": "deepseek-v4-flash", "name": "DeepSeek-V4-Flash", "contextWindow": 64000, "maxTokens": 2048},
        {"id": "deepseek-v3.2", "name": "deepseek-v3.2", "contextWindow": 64000, "maxTokens": 2048},
    ],
}

models = json.loads(models_path.read_text()) if models_path.exists() else {}
models.setdefault("providers", {})["huawei-cloud-maas"] = provider
models_path.write_text(json.dumps(models, indent=2) + "\n")

settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
settings["defaultProvider"] = "huawei-cloud-maas"
settings["defaultModel"] = "glm-5.1"
settings["defaultThinkingLevel"] = "high"
settings_path.write_text(json.dumps(settings, indent=2) + "\n")

os.chmod(agent_dir, 0o700)
os.chmod(models_path, 0o600)
os.chmod(settings_path, 0o600)

print(f"Updated {models_path}")
print(f"Updated {settings_path}")
PY
```

3. Restart Pi Coding Agent.

## Field Notes

- Keep `baseUrl` at the OpenAI-compatible root ending in `/openai/v1/`. Do not append `/chat/completions` in the Pi model registry.
- Use `api: "openai-completions"` for the Huawei MaaS OpenAI-compatible chat completion adapter.
- For `glm-5.1`, keep `reasoning: true` and `compat.thinkingFormat: "zai"` so Pi formats thinking requests as expected.
- Keep `supportsDeveloperRole: false` when the MaaS route should not receive developer-role messages.
- Keep `supportsReasoningEffort: false` so Pi does not send OpenAI-style `reasoning_effort` upstream.
- Treat `contextWindow` as the model context length and `maxTokens` as the generation cap.

## Validation

Validate JSON before restarting Pi.

Windows:

```powershell
Get-Content -LiteralPath $PiModelsFile -Raw | ConvertFrom-Json | Out-Null
Get-Content -LiteralPath $PiSettingsFile -Raw | ConvertFrom-Json | Out-Null

$Settings = Get-Content -LiteralPath $PiSettingsFile -Raw | ConvertFrom-Json
$Settings.defaultProvider
$Settings.defaultModel
$Settings.defaultThinkingLevel
```

Linux:

```bash
python3 -m json.tool "$PI_MODELS_FILE" >/dev/null
python3 -m json.tool "$PI_SETTINGS_FILE" >/dev/null

python3 - <<'PY'
import json
import os
from pathlib import Path

agent_dir = Path(os.environ.get("PI_AGENT_DIR", Path.home() / ".pi" / "agent"))
settings = json.loads((agent_dir / "settings.json").read_text())
print(settings.get("defaultProvider"))
print(settings.get("defaultModel"))
print(settings.get("defaultThinkingLevel"))
PY
```

Smoke-test the endpoint directly. These direct tests call `/chat/completions`; the Pi registry should still keep only the `/openai/v1/` base URL.

Windows:

```powershell
$env:HUAWEI_MAAS_API_KEY = "replace-with-your-maas-api-key"
$Body = @{
  model = "glm-5.1"
  messages = @(@{ role = "user"; content = "Reply with OK only." })
  max_tokens = 16
} | ConvertTo-Json -Depth 6

Invoke-RestMethod `
  -Uri "https://api-ap-southeast-1.modelarts-maas.com/openai/v1/chat/completions" `
  -Method Post `
  -Headers @{ Authorization = "Bearer $env:HUAWEI_MAAS_API_KEY"; "Content-Type" = "application/json" } `
  -Body $Body
```

Linux:

```bash
export HUAWEI_MAAS_API_KEY="replace-with-your-maas-api-key"

curl -sS \
  -H "Authorization: Bearer $HUAWEI_MAAS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5.1",
    "messages": [{"role": "user", "content": "Reply with OK only."}],
    "max_tokens": 16
  }' \
  "https://api-ap-southeast-1.modelarts-maas.com/openai/v1/chat/completions"
```

Finally, open Pi Coding Agent, confirm `glm-5.1` is selected, and run `Reply with OK only.`

## Troubleshooting

- **Model does not appear**: Confirm the provider is inside the top-level `providers` object and restart Pi.
- **Wrong file casing on Linux**: Check whether Pi reads `models.json` or `Models.json`; keep one canonical file with the expected casing.
- **Windows path confusion**: Use `%USERPROFILE%\.pi\agent`, not the Codex workspace directory.
- **Linux permission denied**: Ensure the Pi user owns `~/.pi/agent`; fix with `chown -R "$USER:$USER" ~/.pi/agent` if needed.
- **Authentication failure**: Replace the placeholder with a valid Huawei MaaS API key and confirm the service is enabled in the selected region.
- **404 or bad endpoint**: Keep the registry `baseUrl` as `https://api-ap-southeast-1.modelarts-maas.com/openai/v1/`; only manual smoke tests should call `/chat/completions`.
- **Reasoning errors**: Confirm `glm-5.1` includes `reasoning: true`, `thinkingFormat: "zai"`, and `supportsReasoningEffort: false`.
- **Unexpected role errors**: Keep `supportsDeveloperRole: false` and avoid forwarding developer-role messages upstream.

## Security Rules

- Never publish a real MaaS API key in a skill, README, screenshot, chat transcript, Git commit, or package archive.
- Use placeholders such as `replace-with-your-maas-api-key` in reusable documentation.
- Store real keys only in the local Pi config or a local secret manager.
- Keep backup files that contain real keys out of source control.
- Rotate the MaaS API key if it was pasted into shared materials.

Windows secret scan:

```powershell
Get-ChildItem -Recurse -File | Select-String -Pattern 'apiKey"\s*:\s*"[A-Za-z0-9._-]{20,}','Bearer\s+[A-Za-z0-9._-]{20,}'
```

Linux secret scan:

```bash
grep -RInE 'apiKey"[[:space:]]*:[[:space:]]*"[A-Za-z0-9._-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}' .
```

