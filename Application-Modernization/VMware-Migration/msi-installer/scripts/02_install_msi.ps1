# scripts/02_install_msi.ps1 — Install all discovered .msi files
# Requires approval file: approvals/APPROVED_INSTALL
# Reads discovery report from step 01

param(
    [string]$BaseDir = (Split-Path -Parent $PSScriptRoot)
)

# Load libraries
. "$BaseDir\lib\msi_utils.ps1"
. "$BaseDir\lib\report_utils.ps1"

Print-StepHeader -StepNumber "02" -StepName "Install MSI Packages"

# --- Check approval gate ---
$approvalFile = "$BaseDir\approvals\APPROVED_INSTALL"
if (-not (Test-Path $approvalFile)) {
    Write-Host "  [BLOCKED] Approval file not found: approvals\APPROVED_INSTALL" -ForegroundColor Red
    Write-Host "  To approve: touch approvals\APPROVED_INSTALL" -ForegroundColor Yellow
    exit 1
}
Write-Host "  [APPROVED] Installation approved by human gate" -ForegroundColor Green

# --- Read discovery report ---
$discoveryPath = "$BaseDir\reports\01_discovery_report.json"
if (-not (Test-Path $discoveryPath)) {
    Write-Host "  [FAIL] Discovery report not found. Run 01_discover_msi.ps1 first." -ForegroundColor Red
    exit 1
}
$discovery = Read-JsonReport -Path $discoveryPath
$msiFiles = $discovery.files

# --- Load config ---
$configPath = "$BaseDir\configs\install.yaml"
$uiMode       = 'silent'
$noReboot     = $true
$logDir       = "$env:TEMP\msi-install-logs"
$continue     = $true
$properties   = $null

if (Test-Path $configPath) {
    $yaml = Get-Content $configPath -Raw
    # Simple YAML parsing (avoid dependency on powershell-yaml module)
    if ($yaml -match 'ui_mode:\s*(\w+)')           { $uiMode = $Matches[1] }
    if ($yaml -match 'no_reboot:\s*(true|false)')  { $noReboot = ($Matches[1] -eq 'true') }
    if ($yaml -match 'continue_on_error:\s*(true|false)') { $continue = ($Matches[1] -eq 'true') }
    if ($yaml -match 'log_dir:\s*(\S+)') {
        $ld = $Matches[1]
        if ($ld -ne 'null') { $logDir = $ld }
    }
}

# --- Prepare log directory ---
if (-not (Test-Path $logDir)) {
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
}

# --- Check dry run ---
$dryRun = $env:DRY_RUN -eq 'true'
if ($dryRun) {
    Write-Host "  [DRY RUN] DRY_RUN=true - no actual installs will be performed" -ForegroundColor Yellow
}

# --- Header ---
Write-Host ""
Write-Host "  UI mode : $uiMode" -ForegroundColor Cyan
Write-Host "  Log dir : $logDir" -ForegroundColor Cyan
Write-Host "  Files   : $($msiFiles.Count)" -ForegroundColor Cyan
Write-Host ""

# --- Install loop ---
$results = @()
$index   = 0

foreach ($file in $msiFiles) {
    $index++
    $msiPath = $file.path
    $name    = $file.name

    $logPath = Get-TimestampedLogPath -LogDir $logDir -BaseName ([System.IO.Path]::GetFileNameWithoutExtension($name))

    Write-Host "  [$index/$($msiFiles.Count)] Installing: $name" -ForegroundColor Yellow
    Write-Host "         Log: $logPath"

    if ($dryRun) {
        Write-Host "         Result: SKIPPED (dry run)" -ForegroundColor DarkGray
        $results += [pscustomobject]@{
            File     = $name
            ExitCode = -1
            Message  = 'Skipped (dry run)'
            Success  = $true
            LogPath  = $logPath
        }
        continue
    }

    $result = Install-MsiPackage -MsiPath $msiPath -UiMode $uiMode -NoReboot:$noReboot -LogPath $logPath -Properties $properties

    if ($result.Success) {
        Write-Host "         Result: $($result.Message) ($($result.ExitCode))" -ForegroundColor Green
    } else {
        Write-Host "         Result: $($result.Message) ($($result.ExitCode))" -ForegroundColor Red
        Write-Host "         Check log: $logPath" -ForegroundColor DarkGray
    }

    $results += [pscustomobject]@{
        File     = $name
        ExitCode = $result.ExitCode
        Message  = $result.Message
        Success  = $result.Success
        LogPath  = $logPath
    }

    if (-not $result.Success -and -not $continue) {
        Write-Host ""
        Write-Host "  [!] Stopping - continue_on_error is false." -ForegroundColor Red
        break
    }
}

# --- Summary ---
Print-SummaryTable -Results $results

# --- Write report ---
$report = [ordered]@{
    timestamp = (Get-Date -Format 'o')
    ui_mode   = $uiMode
    dry_run   = $dryRun
    total     = $results.Count
    success   = ($results | Where-Object { $_.Success }).Count
    failed    = ($results | Where-Object { -not $_.Success }).Count
    results   = $results
}
$reportPath = Write-JsonReport -ReportDir "$BaseDir\reports" -ReportName '02_install_report.json' -Data $report
Write-Host "  Report: $reportPath" -ForegroundColor DarkGray

$failedCount = ($results | Where-Object { -not $_.Success }).Count
if ($failedCount -gt 0) { exit 1 } else { exit 0 }
