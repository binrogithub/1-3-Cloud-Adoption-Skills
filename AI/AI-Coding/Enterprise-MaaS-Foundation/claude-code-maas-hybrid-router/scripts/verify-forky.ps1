param(
  [string]$ForkyDir = "$env:USERPROFILE\dev\forky",
  [int]$Port = 3458,
  [string]$LiteLLMBaseUrl = "http://127.0.0.1:4000/v1",
  [string]$LiteLLMKey = $env:LITELLM_CCR_KEY
)

$ErrorActionPreference = "Continue"

$wrapper = "$env:USERPROFILE\.local\bin\claude-forky.cmd"
$cred = "$env:USERPROFILE\.claude\.credentials.json"
$envPath = Join-Path $ForkyDir ".env"
$log = "$env:USERPROFILE\.forky\server.log"

Write-Host "claude:" (Get-Command claude -ErrorAction SilentlyContinue).Source
Write-Host "bun:" (Get-Command bun -ErrorAction SilentlyContinue).Source
Write-Host "wrapper exists:" (Test-Path $wrapper)
Write-Host "credentials exist:" (Test-Path $cred)
Write-Host ".env exists:" (Test-Path $envPath)

try {
  $headers = @{}
  if ($LiteLLMKey) { $headers.Authorization = "Bearer $LiteLLMKey" }
  $models = Invoke-RestMethod -Uri "$LiteLLMBaseUrl/models" -Headers $headers -TimeoutSec 15
  $names = @($models.data | ForEach-Object { $_.id })
  Write-Host "LiteLLM models:" ($names -join ", ")
} catch {
  Write-Warning "LiteLLM check failed: $($_.Exception.Message)"
}

try {
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 10
  Write-Host "forky health:" ($health | ConvertTo-Json -Compress -Depth 10)
} catch {
  Write-Warning "forky health failed: $($_.Exception.Message)"
}

if (Test-Path $log) {
  Write-Host "Recent forky log:"
  Get-Content $log -Tail 40
}
