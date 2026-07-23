# install-msi.ps1 — MSI Batch Installer (PowerShell)
# Installs all .msi files in a directory (or specific files) silently via msiexec.
#
# Usage:
#   .\install-msi.ps1                                    # Install all .msi in current dir
#   .\install-msi.ps1 -Path "C:\Packages"                # Install all .msi in C:\Packages
#   .\install-msi.ps1 -Path "app1.msi","app2.msi"        # Install specific files
#   .\install-msi.ps1 -UiMode basic                      # Basic UI (progress bar)
#   .\install-msi.ps1 -Properties @{ACCEPT_EULA='1'}     # Pass MSI properties
#   .\install-msi.ps1 -ContinueOnError:$false            # Stop on first failure

param(
    [string[]]$Path = (Get-Location).Path,
    [string]$UiMode = 'silent',
    [switch]$NoReboot = $true,
    [string]$LogDir = "$env:TEMP\msi-install-logs",
    [hashtable]$Properties,
    [bool]$ContinueOnError = $true
)

# ── Helper: Decode msiexec exit code ────────────────────────────────────
function Get-MsiExitMessage {
    param([int]$Code)
    switch ($Code) {
           0 { 'Success' }
        1602 { 'User cancelled' }
        1603 { 'Fatal error (check permissions / locked files)' }
        1604 { 'Installation suspended, incomplete' }
        1605 { 'Action only valid for installed products' }
        1606 { 'Feature ID not registered' }
        1607 { 'Component ID not registered' }
        1608 { 'Unknown property' }
        1609 { 'Handle in an invalid state' }
        1610 { 'Configuration data corrupt' }
        1611 { 'Product qualifier not present' }
        1612 { 'Installation source unavailable' }
        1613 { 'Installation version too old' }
        1614 { 'Product is not installed' }
        1615 { 'SQL query syntax invalid' }
        1616 { 'Record field does not exist' }
        1618 { 'Another installation is already running' }
        1625 { 'System policy blocks installation' }
        1638 { 'Different version already installed' }
        3010 { 'Success - reboot required' }
        default { "Unknown error code: $Code" }
    }
}

# ── Helper: Check if exit code is success ───────────────────────────────
function Test-MsiSuccess {
    param([int]$Code)
    return ($Code -eq 0 -or $Code -eq 3010)
}

# ── Helper: Build UI flag ───────────────────────────────────────────────
function Get-UiFlag {
    param([string]$Mode)
    switch ($Mode) {
        'silent' { '/qn' }
        'basic'  { '/qb' }
        'full'   { '' }
        default  { '/qn' }
    }
}

# ── Helper: Build properties string ─────────────────────────────────────
function Build-PropertiesString {
    param([hashtable]$Props)
    if (-not $Props) { return '' }
    $str = ''
    foreach ($key in $Props.Keys) {
        $val = $Props[$key]
        $str += " $key=`"$val`""
    }
    return $str
}

# ── Resolve MSI files ──────────────────────────────────────────────────
$msiFiles = @()

foreach ($p in $Path) {
    if (Test-Path $p -PathType Container) {
        $msiFiles += Get-ChildItem -Path $p -Filter '*.msi' -File | Sort-Object Name
    } elseif (Test-Path $p -PathType Leaf) {
        $msiFiles += Get-Item $p
    } else {
        Write-Host "  [WARN] Path not found: $p" -ForegroundColor Yellow
    }
}

if ($msiFiles.Count -eq 0) {
    Write-Host "No .msi files found." -ForegroundColor Red
    exit 1
}

# ── Prepare log directory ──────────────────────────────────────────────
if (-not (Test-Path $LogDir)) {
    New-Item -Path $LogDir -ItemType Directory -Force | Out-Null
}

# ── Build flags ────────────────────────────────────────────────────────
$uiFlag       = Get-UiFlag -Mode $UiMode
$noRebootFlag = if ($NoReboot) { '/norestart' } else { '' }
$propStr      = Build-PropertiesString -Props $Properties

# ── Header ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "  MSI Batch Installer (PowerShell)" -ForegroundColor Cyan
Write-Host "  Files   : $($msiFiles.Count)" -ForegroundColor Cyan
Write-Host "  UI mode : $UiMode" -ForegroundColor Cyan
Write-Host "  Log dir : $LogDir" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""

# ── Install loop ───────────────────────────────────────────────────────
$results = @()
$index   = 0

foreach ($file in $msiFiles) {
    $index++
    $name    = $file.Name
    $msiPath = $file.FullName

    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $baseName  = [System.IO.Path]::GetFileNameWithoutExtension($name)
    $safeName  = $baseName -replace '[^\w\-]', '_'
    $logPath   = Join-Path $LogDir "${safeName}_${timestamp}.log"

    Write-Host "[$index/$($msiFiles.Count)] Installing: $name" -ForegroundColor Yellow
    Write-Host "       Log: $logPath" -ForegroundColor DarkGray

    $argList = "/i `"$msiPath`" $uiFlag $noRebootFlag /L*V `"$logPath`"$propStr"

    $proc = Start-Process -FilePath 'msiexec.exe' -ArgumentList $argList -Wait -PassThru -NoNewWindow

    $msg    = Get-MsiExitMessage -Code $proc.ExitCode
    $success = Test-MsiSuccess -Code $proc.ExitCode

    if ($success) {
        Write-Host "       Result: $msg ($($proc.ExitCode))" -ForegroundColor Green
    } else {
        Write-Host "       Result: $msg ($($proc.ExitCode))" -ForegroundColor Red
    }

    $results += [pscustomobject]@{
        File     = $name
        ExitCode = $proc.ExitCode
        Message  = $msg
        Success  = $success
        LogPath  = $logPath
    }

    if (-not $success -and -not $ContinueOnError) {
        Write-Host ""
        Write-Host "  [!] Stopping - continue_on_error is false." -ForegroundColor Red
        break
    }
}

# ── Summary ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "  Summary" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan

$results | Format-Table -Property File, ExitCode, Message, Success -AutoSize

$successCount = ($results | Where-Object { $_.Success }).Count
$failedCount  = ($results | Where-Object { -not $_.Success }).Count

Write-Host ""
$color = if ($failedCount -eq 0) { 'Green' } else { 'Yellow' }
Write-Host "  Total: $($results.Count)  |  Success: $successCount  |  Failed: $failedCount" -ForegroundColor $color
Write-Host "  Logs:  $LogDir" -ForegroundColor DarkGray
Write-Host ""

if ($failedCount -gt 0) { exit 1 } else { exit 0 }
