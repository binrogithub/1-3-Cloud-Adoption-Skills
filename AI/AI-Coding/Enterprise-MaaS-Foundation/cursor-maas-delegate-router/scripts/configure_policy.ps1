# USER-GLOBAL Rule + memory + hooks (all Cursor workspaces). Default = user home.
param(
  [switch]$Project,
  [switch]$ProjectOnly,
  [switch]$SkipHook,
  [switch]$WithHook
)

$ErrorActionPreference = "Stop"
if (-not $PSBoundParameters.ContainsKey('WithHook') -and -not $SkipHook) { $WithHook = $true }
if ($SkipHook) { $WithHook = $false }

$skillRoot = Split-Path $PSScriptRoot -Parent
$policy = Join-Path $skillRoot "assets\orchestrator-policy.md"
$memoryAsset = Join-Path $skillRoot "assets\orchestrator-memory.md"
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

function Write-PolicyPair([string]$RulePath, [string]$MemoryPath) {
  New-Item -ItemType Directory -Force -Path (Split-Path $RulePath) | Out-Null
  New-Item -ItemType Directory -Force -Path (Split-Path $MemoryPath) | Out-Null
  Copy-Item -Force $memoryAsset $MemoryPath
  $front = @"
---
description: USER-GLOBAL: code execution via Huawei MaaS GLM (all workspaces)
alwaysApply: true
---

"@
  $memBody = Get-Content -Raw -Path $memoryAsset
  $polBody = Get-Content -Raw -Path $policy
  Set-Content -Path $RulePath -Value ($front + $memBody.TrimEnd() + "`n`n" + $polBody.TrimEnd() + "`n") -Encoding UTF8
}

function Install-UserHooks {
  $hooksDir = Join-Path $HOME ".cursor\hooks"
  $hooksPath = Join-Path $HOME ".cursor\hooks.json"
  New-Item -ItemType Directory -Force -Path $hooksDir | Out-Null
  Copy-Item -Force $hookAssetRoute (Join-Path $hooksDir "maas-route-hint.py")
  Copy-Item -Force $hookAssetSession (Join-Path $hooksDir "maas-session-start.py")

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
  if (-not $data.hooks) {
    $data | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{}) -Force
  }

  function Filter-Our($list) {
    @($list | Where-Object {
        -not (
          ($_ -and $_.metadata -and $_.metadata.id -match '^maas-') -or
          ($_.command -match 'maas-route-hint|maas-session-start|route_hint')
        )
      })
  }

  $before = @()
  if ($data.hooks.beforeSubmitPrompt) { $before = Filter-Our @($data.hooks.beforeSubmitPrompt) }
  $before += $submitEntry
  $sessions = @()
  if ($data.hooks.sessionStart) { $sessions = Filter-Our @($data.hooks.sessionStart) }
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
  $out | ConvertTo-Json -Depth 8 | Set-Content -Path $hooksPath -Encoding UTF8
  Write-Host "Hooks registered (USER-GLOBAL): $hooksPath"
}

if ($ProjectOnly) {
  $rulePath = Join-Path (Get-Location) ".cursor\rules\maas-delegate-router.mdc"
  $memoryPath = Join-Path (Get-Location) ".cursor\memory\maas-delegate-router.md"
  Write-PolicyPair $rulePath $memoryPath
  Write-Host "CONFIGURE OK (project-only — not global)"
  return
}

$rulePath = Join-Path $HOME ".cursor\rules\maas-delegate-router.mdc"
$memoryPath = Join-Path $HOME ".cursor\memory\maas-delegate-router.md"
Write-PolicyPair $rulePath $memoryPath
Write-Host "Memory written (USER-GLOBAL): $memoryPath"
Write-Host "Policy written (USER-GLOBAL): $rulePath"

if ($WithHook) { Install-UserHooks }

if ($Project) {
  Write-PolicyPair (Join-Path (Get-Location) ".cursor\rules\maas-delegate-router.mdc") `
    (Join-Path (Get-Location) ".cursor\memory\maas-delegate-router.md")
  Write-Host "Also wrote project overlay under ./.cursor/"
}

Write-Host "CONFIGURE OK — scope=USER-GLOBAL (affects all Cursor projects)"
