# Windows Native Setup

Use this path when the user wants to run the Opus/Fable advisor plus GLM executor workflow directly on Windows, without WSL or systemd.

## What Changes Versus Linux

- Use PowerShell scripts instead of Bash/systemd.
- Run forky as a hidden background PowerShell process.
- Use a Windows PowerShell hook at `bin\forky-hook.ps1`.
- Apply the same local forky compatibility fixes for image routing and Anthropic
  cache-control TTL ordering.
- Refresh Machine/User `PATH` inside `run-forky.ps1` so newly installed Bun is found by background processes.
- Redirect stdout and stderr to separate files because Windows PowerShell cannot redirect both streams to the same file in `Start-Process`.
- Optionally connect forky directly to Huawei MaaS GLM-5.2 at `https://api.modelarts-maas.com/v2`, without a local LiteLLM hop.

## Quick Path

From this skill directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-forky.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\setup-huawei-maas-glm.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\configure-forky-direct-huawei.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-forky.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify-forky.ps1
claude-forky
```

The Huawei setup script accepts the full MaaS endpoint:

```text
https://api.modelarts-maas.com/v2/chat/completions
```

It stores the base URL used by forky:

```text
https://api.modelarts-maas.com/v2
```

## Routing

Default Windows direct routing:

```text
normal execution -> Huawei MaaS GLM-5.2
plan / forced advisor / image turns -> Claude OAuth
classifier pings -> Claude OAuth Sonnet
```

The default plan model in `configure-forky-direct-huawei.ps1` is `claude-fable-5`. Override with `-PlanModel` if the account uses a different advisor model.

## Verify Routing

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\forky-route-stats.ps1
```

Interpretation:

- `actualProvider: aistack` means GLM-5.2 when `EXEC_MODEL=glm-5.2`.
- `actualProvider: anthropic-oauth` means Claude OAuth.
- `routedVia: classifier` is normal Claude Code safety/classifier traffic.
- `routedVia: sentinel` means Plan mode or forced Claude routing.

## Safety

Do not commit:

- `%USERPROFILE%\dev\forky\.env`
- `glm-local.env`
- `%USERPROFILE%\.claude\.credentials.json`
- Huawei MaaS API keys
