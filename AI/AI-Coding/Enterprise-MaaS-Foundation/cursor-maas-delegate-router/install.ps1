<#
.SYNOPSIS
  USER-GLOBAL install: copy this skill to ~/.cursor/skills and configure runtime.
#>
param(
  [string]$ApiKey = "",
  [string]$BaseUrl = "https://api-ap-southeast-1.modelarts-maas.com/openai/v1",
  [string]$Model = "glm-5.1",
  [switch]$SkipMemory,
  [switch]$SkipHook
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$SkillsDst = Join-Path $HOME ".cursor\skills"
$Name = "cursor-maas-delegate-router"
$Dst = Join-Path $SkillsDst $Name

New-Item -ItemType Directory -Force -Path $SkillsDst | Out-Null
if (Test-Path $Dst) { Remove-Item -Recurse -Force $Dst }
Copy-Item -Recurse -Force $Root $Dst
Get-ChildItem -Recurse -Directory -Filter __pycache__ $Dst -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Installed skill: $Dst"

if (-not $ApiKey) {
  if ($env:DELEGATE_API_KEY) { $ApiKey = $env:DELEGATE_API_KEY }
  elseif ($env:HUAWEI_MAAS_API_KEY) { $ApiKey = $env:HUAWEI_MAAS_API_KEY }
}
if ($env:DELEGATE_API_BASE) { $BaseUrl = $env:DELEGATE_API_BASE }
elseif ($env:HUAWEI_MAAS_API_BASE) { $BaseUrl = $env:HUAWEI_MAAS_API_BASE }
if ($env:DELEGATE_MODEL) { $Model = $env:DELEGATE_MODEL }

$runtime = Join-Path $Dst "scripts\install.ps1"
$argsList = @("-File", $runtime, "-BaseUrl", $BaseUrl, "-Model", $Model)
if ($ApiKey) { $argsList += @("-ApiKey", $ApiKey) }
if ($SkipMemory) { $argsList += "-SkipMemory" }
if ($SkipHook) { $argsList += "-SkipHook" }

& powershell -NoProfile @argsList
Write-Host "INSTALL SKILL OK — scope=USER-GLOBAL"
Write-Host "Reload Cursor / start a new Agent chat."
