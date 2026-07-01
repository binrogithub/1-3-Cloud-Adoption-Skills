param(
  [string]$ForkyDir = "$env:USERPROFILE\dev\forky"
)

$ErrorActionPreference = "Stop"
$logDir = "$env:USERPROFILE\.forky"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "server.log"
$errLog = Join-Path $logDir "server.err.log"
$runner = Join-Path $PSScriptRoot "run-forky.ps1"

$proc = Start-Process powershell.exe `
  -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$runner`"", "-ForkyDir", "`"$ForkyDir`"") `
  -WindowStyle Hidden `
  -RedirectStandardOutput $log `
  -RedirectStandardError $errLog `
  -PassThru

Start-Sleep -Seconds 2
Write-Host "Started forky process $($proc.Id). Log: $log"
Write-Host "Error log: $errLog"
