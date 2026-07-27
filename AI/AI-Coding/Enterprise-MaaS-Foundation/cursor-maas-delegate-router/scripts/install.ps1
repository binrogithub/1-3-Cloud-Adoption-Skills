# Bootstrap ~/.cursor-hybrid without requiring Python on PATH.
# Also writes Cursor memory + alwaysApply rule: default code exec → MaaS GLM.
param(
  [string]$BaseUrl = "https://api-ap-southeast-1.modelarts-maas.com/openai/v1",
  [string]$ApiKey = "",
  [string]$Model = "glm-5.1",
  [switch]$SkipMemory,
  [switch]$SkipHook,
  [switch]$WithHook
)
# Hook is ON by default (needed for silent MaaS routing). -SkipHook to disable.
if (-not $PSBoundParameters.ContainsKey('WithHook') -and -not $SkipHook) {
  $WithHook = $true
}
if ($SkipHook) { $WithHook = $false }

$ErrorActionPreference = "Stop"
$hybrid = Join-Path $HOME ".cursor-hybrid"
$bin = Join-Path $hybrid "bin"
$envFile = Join-Path $hybrid "env.json"
$audit = Join-Path $hybrid "route-audit.jsonl"
$skillRoot = Split-Path $PSScriptRoot -Parent
$skillScripts = $PSScriptRoot
$memoryAsset = Join-Path $skillRoot "assets\orchestrator-memory.md"
$policyAsset = Join-Path $skillRoot "assets\orchestrator-policy.md"
$memoryPath = Join-Path $HOME ".cursor\memory\maas-delegate-router.md"
$rulePath = Join-Path $HOME ".cursor\rules\maas-delegate-router.mdc"
$hooksPath = Join-Path $HOME ".cursor\hooks.json"
$hooksDir = Join-Path $HOME ".cursor\hooks"
$hookAssetRoute = Join-Path $skillRoot "assets\hooks\route_hint.py"
$hookAssetSession = Join-Path $skillRoot "assets\hooks\maas-session-start.py"

function Resolve-PythonHookCommand([string]$ScriptPath) {
  foreach ($candidate in @("python", "python3", "py")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
      $source = $cmd.Source
      if ($source -match '\s') { $source = '"' + $source + '"' }
      return "$source $ScriptPath"
    }
  }
  return "python $ScriptPath"
}

New-Item -ItemType Directory -Force -Path $bin | Out-Null
if (-not (Test-Path $audit)) { New-Item -ItemType File -Path $audit | Out-Null }

# Preserve existing env.json values so re-install without -ApiKey does not wipe the key.
$existing = $null
if (Test-Path $envFile) {
  try { $existing = Get-Content -Raw $envFile | ConvertFrom-Json } catch { $existing = $null }
}
if (-not $ApiKey -and $existing -and $existing.DELEGATE_API_KEY) { $ApiKey = [string]$existing.DELEGATE_API_KEY }
if (-not $ApiKey -and $env:DELEGATE_API_KEY) { $ApiKey = $env:DELEGATE_API_KEY }
if (-not $ApiKey -and $env:HUAWEI_MAAS_API_KEY) { $ApiKey = $env:HUAWEI_MAAS_API_KEY }
if ($env:DELEGATE_API_BASE) { $BaseUrl = $env:DELEGATE_API_BASE }
elseif ($existing -and $existing.DELEGATE_API_BASE) { $BaseUrl = [string]$existing.DELEGATE_API_BASE }
if ($env:DELEGATE_MODEL) { $Model = $env:DELEGATE_MODEL }
elseif ($existing -and $existing.DELEGATE_MODEL) { $Model = [string]$existing.DELEGATE_MODEL }

$verifySsl = "1"
if ($existing -and $existing.VERIFY_SSL) { $verifySsl = [string]$existing.VERIFY_SSL }

$envObj = [ordered]@{
  DELEGATE_API_BASE     = $BaseUrl.TrimEnd("/")
  DELEGATE_MODEL        = $Model
  VERIFY_SSL            = $verifySsl
  CODE_EXECUTION_ROUTE  = "maas_glm"
  ROUTE_PRIORITY        = "maas_over_cursor"
}
if ($ApiKey) { $envObj.DELEGATE_API_KEY = $ApiKey }

$envObj | ConvertTo-Json | Set-Content -Path $envFile -Encoding UTF8

foreach ($name in @("delegate.py", "workflow.py", "verify.py", "route_stats.py", "preprocess_doc.py")) {
  $src = Join-Path $skillScripts $name
  $cmd = Join-Path $bin ($name -replace "\.py$", ".cmd")
  "@echo off`r`npython `"$src`" %*`r`n" | Set-Content -Path $cmd -Encoding ASCII
}

if (-not $SkipMemory) {
  if (-not (Test-Path $memoryAsset)) { throw "Missing memory asset: $memoryAsset" }
  if (-not (Test-Path $policyAsset)) { throw "Missing policy asset: $policyAsset" }

  New-Item -ItemType Directory -Force -Path (Split-Path $memoryPath) | Out-Null
  New-Item -ItemType Directory -Force -Path (Split-Path $rulePath) | Out-Null

  Copy-Item -Force $memoryAsset $memoryPath
  $front = @"
---
description: USER-GLOBAL: code execution via Huawei MaaS GLM (all workspaces)
alwaysApply: true
---

"@
  $memBody = Get-Content -Raw -Path $memoryAsset
  $polBody = Get-Content -Raw -Path $policyAsset
  Set-Content -Path $rulePath -Value ($front + $memBody.TrimEnd() + "`n`n" + $polBody.TrimEnd() + "`n") -Encoding UTF8
  Write-Host "Memory written (USER-GLOBAL): $memoryPath"
  Write-Host "Rule written (USER-GLOBAL): $rulePath"
  Write-Host "Route default: CODE_EXECUTION_ROUTE=maas_glm (all Cursor workspaces)"
}

if ($WithHook) {
  New-Item -ItemType Directory -Force -Path $hooksDir | Out-Null
  Copy-Item -Force $hookAssetRoute (Join-Path $hooksDir "maas-route-hint.py")
  Copy-Item -Force $hookAssetSession (Join-Path $hooksDir "maas-session-start.py")

  # Relative commands: Cursor runs user hooks with cwd = ~/.cursor
  $submitEntry = [ordered]@{
    command  = Resolve-PythonHookCommand "./hooks/maas-route-hint.py"
    metadata = @{ id = "maas-delegate-router" }
  }
  $sessionEntry = [ordered]@{
    command  = Resolve-PythonHookCommand "./hooks/maas-session-start.py"
    metadata = @{ id = "maas-session-start" }
  }

  if (Test-Path $hooksPath) {
    $data = Get-Content -Raw $hooksPath | ConvertFrom-Json
  } else {
    $data = [pscustomobject]@{ version = 1; hooks = [pscustomobject]@{} }
  }
  if (-not $data.hooks) { $data | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{}) -Force }

  function Filter-OurHooks($list) {
    @($list | Where-Object {
        -not (
          ($_ -and $_.metadata -and $_.metadata.id -match '^maas-') -or
          ($_.command -match 'maas-route-hint|maas-session-start|route_hint')
        )
      })
  }

  $before = @()
  if ($data.hooks.beforeSubmitPrompt) { $before = Filter-OurHooks @($data.hooks.beforeSubmitPrompt) }
  $before += $submitEntry

  $sessions = @()
  if ($data.hooks.sessionStart) { $sessions = Filter-OurHooks @($data.hooks.sessionStart) }
  $sessions += $sessionEntry

  $hooksObj = [ordered]@{}
  foreach ($p in $data.hooks.PSObject.Properties) {
    if ($p.Name -ne "beforeSubmitPrompt" -and $p.Name -ne "sessionStart") {
      $hooksObj[$p.Name] = $p.Value
    }
  }
  $hooksObj["beforeSubmitPrompt"] = $before
  $hooksObj["sessionStart"] = $sessions
  $out = [ordered]@{ version = 1; hooks = $hooksObj }
  New-Item -ItemType Directory -Force -Path (Split-Path $hooksPath) | Out-Null
  $out | ConvertTo-Json -Depth 8 | Set-Content -Path $hooksPath -Encoding UTF8
  Write-Host "Hooks registered (USER-GLOBAL): $hooksPath"
  Write-Host "Events: sessionStart + beforeSubmitPrompt (all workspaces)"
}

Write-Host "Installed runtime: $hybrid"
Write-Host "Env file: $envFile"
if (-not $ApiKey) { Write-Warning "DELEGATE_API_KEY not set. Re-run with -ApiKey or set env var." }
Write-Host "INSTALL OK — scope=USER-GLOBAL"
