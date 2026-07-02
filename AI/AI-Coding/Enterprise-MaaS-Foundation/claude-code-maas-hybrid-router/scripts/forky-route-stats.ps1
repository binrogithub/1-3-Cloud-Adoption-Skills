param(
  [string]$LogPath = "$env:USERPROFILE\.forky\log\$(Get-Date -Format yyyy-MM-dd).jsonl",
  [int]$Tail = 0
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $LogPath)) {
  throw "Log file not found: $LogPath"
}

$lines = if ($Tail -gt 0) { Get-Content $LogPath -Tail $Tail } else { Get-Content $LogPath }
$events = foreach ($line in $lines) {
  if (-not $line.Trim()) { continue }
  try { $line | ConvertFrom-Json } catch {}
}

$requests = @($events | Where-Object { $_.event -eq "request" })
$responses = @($events | Where-Object { $_.event -eq "response" })
$errors = @($events | Where-Object { $_.level -eq "error" })

function Show-Group($Title, $Items, $Property) {
  Write-Host ""
  Write-Host "== $Title =="
  if (-not $Items -or $Items.Count -eq 0) {
    Write-Host "(none)"
    return
  }
  $Items |
    Group-Object $Property |
    Sort-Object Count -Descending |
    Select-Object Count, Name |
    Format-Table -AutoSize
}

Write-Host "Log: $LogPath"
Write-Host "Lines parsed: $($events.Count)"
Write-Host "Requests: $($requests.Count)"
Write-Host "Responses: $($responses.Count)"
Write-Host "Errors: $($errors.Count)"

Show-Group "Requests by actual provider" $requests "actualProvider"
Show-Group "Requests by routedVia" $requests "routedVia"
Show-Group "Responses by provider" $responses "provider"

Write-Host ""
Write-Host "== Main execution requests =="
$exec = @($requests | Where-Object { $_.routedVia -eq "execution" })
if ($exec.Count -eq 0) {
  Write-Host "(none)"
} else {
  $exec |
    Group-Object actualProvider |
    Sort-Object Count -Descending |
    Select-Object Count, Name |
    Format-Table -AutoSize
}

Write-Host ""
Write-Host "== Claude OAuth/classifier/plan requests =="
$claude = @($requests | Where-Object { $_.actualProvider -eq "anthropic-oauth" })
if ($claude.Count -eq 0) {
  Write-Host "(none)"
} else {
  $claude |
    Select-Object ts, routedVia, routedModel, toolCount |
    Format-Table -AutoSize
}

Write-Host ""
Write-Host "== Recent requests =="
$requests |
  Select-Object -Last 20 ts, routedVia, actualProvider, routedModel, toolCount |
  Format-Table -AutoSize

if ($errors.Count -gt 0) {
  Write-Host ""
  Write-Host "== Errors =="
  $errors |
    Select-Object ts, event, err, kind |
    Format-Table -AutoSize
}
