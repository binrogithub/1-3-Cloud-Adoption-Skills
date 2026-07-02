param(
  [string]$ForkyDir = "$env:USERPROFILE\dev\forky",
  [string]$RepoUrl = "https://github.com/vladharl/forky.git",
  [string]$ZipUrl = "https://github.com/vladharl/forky/archive/refs/heads/main.zip",
  [switch]$SkipPatch
)

$ErrorActionPreference = "Stop"

function Require-Command($Name, $Hint) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name was not found in PATH. $Hint"
  }
}

Require-Command "claude" "Install Claude Code first."
Require-Command "bun" "Install Bun for Windows, then open a new PowerShell session."

$git = Get-Command git -ErrorAction SilentlyContinue
$parent = Split-Path -Parent $ForkyDir
New-Item -ItemType Directory -Force $parent | Out-Null

if (Test-Path $ForkyDir) {
  if ($git -and (Test-Path (Join-Path $ForkyDir ".git"))) {
    Push-Location $ForkyDir
    try {
      $dirty = git status --porcelain
      if ($dirty) {
        Write-Warning "Existing forky tree has local changes; skipping git pull."
      } else {
        git pull --ff-only
      }
    } finally {
      Pop-Location
    }
  } else {
    Write-Host "Using existing $ForkyDir"
  }
} else {
  if ($git) {
    git clone $RepoUrl $ForkyDir
  } else {
    $tmp = Join-Path $env:TEMP ("forky-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Force $tmp | Out-Null
    $zip = Join-Path $tmp "forky.zip"
    Invoke-WebRequest -Uri $ZipUrl -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $src = Get-ChildItem $tmp -Directory | Where-Object { $_.Name -like "forky-*" } | Select-Object -First 1
    if (-not $src) { throw "Could not locate extracted forky source." }
    Move-Item $src.FullName $ForkyDir
  }
}

Push-Location $ForkyDir
try {
  bun install
} finally {
  Pop-Location
}

if (-not $SkipPatch) {
  & (Join-Path $PSScriptRoot "patch-forky-windows.ps1") -ForkyDir $ForkyDir
}

Write-Host "forky installed at $ForkyDir"
