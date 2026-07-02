param(
  [string]$EnvFile = "$PSScriptRoot\glm-local.env",
  [string]$ForkyDir = "$env:USERPROFILE\dev\forky",
  [string]$SkillDir = "$env:USERPROFILE\.claude\skills\claude-code-maas-hybrid-router",
  [string]$PlanModel = "claude-fable-5",
  [string]$ClassifierModel = "claude-sonnet-4-6",
  [int]$Port = 3458
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
  throw "Env file not found: $EnvFile"
}
if (-not (Test-Path $ForkyDir)) {
  throw "forky was not found at $ForkyDir"
}

$vars = @{}
Get-Content $EnvFile | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) { return }
  $idx = $line.IndexOf("=")
  if ($idx -lt 1) { return }
  $vars[$line.Substring(0, $idx)] = $line.Substring($idx + 1)
}

foreach ($name in @("GLM_API_BASE", "GLM_MODEL_NAME", "GLM_API_KEY")) {
  if (-not $vars[$name]) { throw "$name is missing from $EnvFile" }
}

$credPath = "$env:USERPROFILE\.claude\.credentials.json"
if (-not (Test-Path $credPath)) {
  throw "Claude OAuth credentials were not found at $credPath. Run: claude /login"
}

$execBaseUrl = $vars["GLM_API_BASE"] -replace "/chat/completions/?$", ""
$execModel = $vars["GLM_MODEL_NAME"]
$execKey = $vars["GLM_API_KEY"]

$envPath = Join-Path $ForkyDir ".env"
$envText = @"
EXEC_BASE_URL=$execBaseUrl
EXEC_API_KEY=$execKey
EXEC_MODEL=$execModel
FORKY_OPUS_MODEL=$PlanModel
FORKY_PLAN_MODEL=$PlanModel
FORKY_VISION_MODEL=$PlanModel
FORKY_CLASSIFIER_MODEL=$ClassifierModel
PORT=$Port
HOST=127.0.0.1
FORKY_CREDENTIALS_FILE=$credPath
"@
Set-Content -Path $envPath -Value $envText -Encoding UTF8

$localBin = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Force $localBin | Out-Null
$wrapper = Join-Path $localBin "claude-forky.cmd"
$wrapperText = @"
@echo off
set ANTHROPIC_BASE_URL=http://127.0.0.1:$Port
set ANTHROPIC_MODEL=$ClassifierModel
set CLAUDE_CODE_AUTO_COMPACT_WINDOW=180000
set CLAUDE_CODE_DISABLE_MOUSE_CLICKS=1
set ANTHROPIC_AUTH_TOKEN=
set ANTHROPIC_API_KEY=
claude %*
"@
Set-Content -Path $wrapper -Value $wrapperText -Encoding ASCII

$hookSource = Join-Path $SkillDir "scripts\forky-hook.ps1"
$hookTarget = Join-Path $ForkyDir "bin\forky-hook.ps1"
if (-not (Test-Path $hookSource)) {
  throw "forky-hook.ps1 not found at $hookSource"
}
Copy-Item -Path $hookSource -Destination $hookTarget -Force

$settingsPath = "$env:USERPROFILE\.claude\settings.json"
New-Item -ItemType Directory -Force (Split-Path -Parent $settingsPath) | Out-Null
if (Test-Path $settingsPath) {
  $settings = Get-Content -Raw $settingsPath | ConvertFrom-Json
} else {
  $settings = [pscustomobject]@{}
}

if (-not $settings.PSObject.Properties["hooks"]) {
  $settings | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{})
}

$hookCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$hookTarget`""

function Add-Hook($Settings, $EventName, $Matcher) {
  $hooksObj = $Settings.hooks
  if (-not $hooksObj.PSObject.Properties[$EventName]) {
    $hooksObj | Add-Member -NotePropertyName $EventName -NotePropertyValue @()
  }
  $existing = @($hooksObj.$EventName)
  foreach ($entry in $existing) {
    foreach ($h in @($entry.hooks)) {
      if ($h.command -eq $hookCommand) { return }
    }
  }
  $newEntry = [ordered]@{ hooks = @([ordered]@{ type = "command"; command = $hookCommand }) }
  if ($Matcher) { $newEntry.matcher = $Matcher }
  $hooksObj.$EventName = @($existing + [pscustomobject]$newEntry)
}

Add-Hook $settings "UserPromptSubmit" $null
Add-Hook $settings "PostToolUse" "ExitPlanMode"

$settings | ConvertTo-Json -Depth 50 | Set-Content -Path $settingsPath -Encoding UTF8

Write-Host "Wrote forky env: $envPath"
Write-Host "Wrote wrapper: $wrapper"
Write-Host "Merged hooks into: $settingsPath"
Write-Host "Execution backend: $execBaseUrl / $execModel"
Write-Host "Plan model: $PlanModel"
