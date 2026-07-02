param(
  [string]$ForkyDir = "$env:USERPROFILE\dev\forky"
)

$ErrorActionPreference = "Stop"

function Load-DotEnv($Path) {
  if (-not (Test-Path $Path)) { throw ".env not found at $Path" }
  Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $name = $line.Substring(0, $idx)
    $value = $line.Substring($idx + 1)
    [Environment]::SetEnvironmentVariable($name, $value, "Process")
  }
}

Load-DotEnv (Join-Path $ForkyDir ".env")
$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath"
$bun = Get-Command bun -ErrorAction SilentlyContinue
if (-not $bun) {
  throw "bun was not found in PATH. Install Bun or open a new shell after installation."
}
Set-Location $ForkyDir
& $bun.Source run src/server.ts
