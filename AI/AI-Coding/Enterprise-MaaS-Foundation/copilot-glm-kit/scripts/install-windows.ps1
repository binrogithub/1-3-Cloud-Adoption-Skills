param(
  [string]$BaseUrl = $env:GLM_BASE_URL,
  [string]$ModelId = $(if ($env:GLM_MODEL_ID) { $env:GLM_MODEL_ID } else { "glm-5.1" })
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillDir = Split-Path -Parent $ScriptDir
$Vsix = Join-Path $SkillDir "assets\vsix\oai-compatible-copilot-glm-router-0.4.3.vsix"

if (!(Test-Path $Vsix)) {
  throw "VSIX not found: $Vsix"
}

$CodeCmd = Get-Command code -ErrorAction SilentlyContinue
if (!$CodeCmd) {
  $Candidate = Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\bin\code.cmd"
  if (Test-Path $Candidate) {
    $Code = $Candidate
  } else {
    throw "Cannot find VS Code 'code' command. Install VS Code or add code.cmd to PATH."
  }
} else {
  $Code = $CodeCmd.Source
}

Write-Host "Installing patched OAI Compatible Copilot VSIX..."
& $Code --install-extension $Vsix --force

if ($BaseUrl) {
  $SettingsDir = Join-Path $env:APPDATA "Code\User"
  $SettingsFile = Join-Path $SettingsDir "settings.json"
  New-Item -ItemType Directory -Force -Path $SettingsDir | Out-Null

  if (Test-Path $SettingsFile) {
    Copy-Item $SettingsFile "$SettingsFile.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
  } else {
    "{}" | Set-Content -Encoding UTF8 $SettingsFile
  }

  node (Join-Path $ScriptDir "merge-settings.mjs") $SettingsFile $BaseUrl $ModelId
  Write-Host "Merged GLM/OAI settings into: $SettingsFile"
} else {
  Write-Host "Skipped settings merge. Re-run with -BaseUrl 'https://YOUR-ENDPOINT/openai/v1' to apply settings automatically."
}

Write-Host ""
Write-Host "Installed extensions:"
& $Code --list-extensions --show-versions | Select-String -Pattern "oai-compatible-copilot|copilot"
Write-Host ""
Write-Host "Next step in VS Code: run 'Developer: Reload Window', then select '$ModelId OAI Compatible'."
