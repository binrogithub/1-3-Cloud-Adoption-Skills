# lib/report_utils.ps1 — Report generation functions
# Shared library for the MSI Batch Installer project

# --- Write a JSON report ---
function Write-JsonReport {
    param(
        [string]$ReportDir,
        [string]$ReportName,
        $Data
    )
    if (-not (Test-Path $ReportDir)) {
        New-Item -Path $ReportDir -ItemType Directory -Force | Out-Null
    }
    $path = Join-Path $ReportDir $ReportName
    $Data | ConvertTo-Json -Depth 10 | Out-File -FilePath $path -Encoding UTF8
    return $path
}

# --- Read a JSON report ---
function Read-JsonReport {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    return Get-Content $Path -Raw | ConvertFrom-Json
}

# --- Print a summary table ---
function Print-SummaryTable {
    param([array]$Results)

    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  Summary" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan

    $Results | Format-Table -Property File, ExitCode, Message, Success -AutoSize

    $successCount = ($Results | Where-Object { $_.Success }).Count
    $failedCount  = ($Results | Where-Object { -not $_.Success }).Count

    Write-Host ""
    $color = if ($failedCount -eq 0) { 'Green' } else { 'Yellow' }
    Write-Host "  Total: $($Results.Count)  |  Success: $successCount  |  Failed: $failedCount" -ForegroundColor $color
    Write-Host ""
}

# --- Write step log ---
function Write-StepLog {
    param(
        [string]$LogDir,
        [string]$StepName,
        [string]$Message
    )
    if (-not (Test-Path $LogDir)) {
        New-Item -Path $LogDir -ItemType Directory -Force | Out-Null
    }
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $logPath   = Join-Path $LogDir "${StepName}_${timestamp}.log"
    $Message | Out-File -FilePath $logPath -Encoding UTF8
    return $logPath
}

# --- Print step header ---
function Print-StepHeader {
    param(
        [string]$StepNumber,
        [string]$StepName
    )
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  Step $StepNumber : $StepName" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
}
