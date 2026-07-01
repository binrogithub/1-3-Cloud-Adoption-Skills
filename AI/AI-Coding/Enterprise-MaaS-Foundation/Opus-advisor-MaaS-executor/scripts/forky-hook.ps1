$ErrorActionPreference = "SilentlyContinue"

$flagDir = Join-Path $env:USERPROFILE ".forky"
$flag = Join-Path $flagDir "opus"
$log = Join-Path $flagDir "hook.log"
New-Item -ItemType Directory -Force $flagDir | Out-Null

$payload = [Console]::In.ReadToEnd()
"[$((Get-Date).ToUniversalTime().ToString('s'))Z] $payload" | Add-Content -Path $log -Encoding UTF8

try {
  $data = $payload | ConvertFrom-Json
} catch {
  exit 0
}

$event = $data.hook_event_name
if (-not $event) { $event = $data.hookEventName }
$mode = $data.permission_mode
if (-not $mode) { $mode = $data.permissionMode }
$session = $data.session_id
if (-not $session) { $session = $data.sessionId }
if (-not $session) { $session = "unknown" }
$tool = $data.tool_name
if (-not $tool) { $tool = $data.toolName }

function Clear-SentinelIfOwned {
  if (-not (Test-Path $flag)) { return }
  $owner = ""
  try {
    $ownerData = Get-Content -Raw $flag | ConvertFrom-Json
    $owner = $ownerData.session_id
  } catch {}
  if (-not $owner -or $owner -eq $session -or $owner -eq "unknown") {
    Remove-Item $flag -Force -ErrorAction SilentlyContinue
  }
}

function Set-Sentinel {
  $body = @{
    session_id = $session
    set_at = [int][double]::Parse((Get-Date -UFormat %s))
  } | ConvertTo-Json -Compress
  Set-Content -Path $flag -Value $body -Encoding UTF8
}

switch ($event) {
  "UserPromptSubmit" {
    if ($mode -eq "plan") { Set-Sentinel } else { Clear-SentinelIfOwned }
  }
  "PostToolUse" {
    if ($tool -eq "ExitPlanMode") { Clear-SentinelIfOwned }
  }
}

exit 0
