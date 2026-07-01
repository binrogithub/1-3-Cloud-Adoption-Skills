param(
  [int]$Port = 3458
)

$ErrorActionPreference = "Stop"
$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
  Write-Host "No listener found on port $Port."
  exit 0
}

$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pidValue in $pids) {
  Write-Host "Stopping process $pidValue on port $Port"
  Stop-Process -Id $pidValue -Force
}
