# scripts/01_discover_msi.ps1 — Discover .msi files in target directory
# Reads MSI_DIR from env or config, lists all .msi files, writes discovery report

param(
    [string]$BaseDir = (Split-Path -Parent $PSScriptRoot)
)

# Load libraries
. "$BaseDir\lib\msi_utils.ps1"
. "$BaseDir\lib\report_utils.ps1"

# Load .env if it exists
$envPath = "$BaseDir\.env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*(.*)\s*$') {
            Set-Item -Path "env:$($Matches[1].Trim())" -Value $Matches[2].Trim()
        }
    }
}

Print-StepHeader -StepNumber "01" -StepName "Discover MSI Files"

# --- Determine target directory ---
$msiDir = $env:MSI_DIR
if (-not $msiDir) {
    $msiDir = (Get-Location).Path
    Write-Host "  MSI_DIR not set - using current directory: $msiDir" -ForegroundColor Yellow
}

if (-not (Test-Path $msiDir)) {
    Write-Host "  [FAIL] Directory does not exist: $msiDir" -ForegroundColor Red
    exit 1
}

# --- Discover .msi files ---
$msiFiles = Get-ChildItem -Path $msiDir -Filter '*.msi' -File | Sort-Object Name

if ($msiFiles.Count -eq 0) {
    Write-Host "  [FAIL] No .msi files found in: $msiDir" -ForegroundColor Red
    $report = [ordered]@{
        timestamp = (Get-Date -Format 'o')
        msi_dir   = $msiDir
        count     = 0
        files     = @()
    }
    Write-JsonReport -ReportDir "$BaseDir\reports" -ReportName '01_discovery_report.json' -Data $report
    exit 1
}

# --- Display discovered files ---
Write-Host ""
Write-Host "  Found $($msiFiles.Count) .msi file(s) in: $msiDir" -ForegroundColor Green
Write-Host ""
$index = 0
$fileList = @()
foreach ($f in $msiFiles) {
    $index++
    $sizeMB = [math]::Round($f.Length / 1MB, 2)
    Write-Host "  [$index] $($f.Name)  (${sizeMB} MB)" -ForegroundColor White
    $fileList += [ordered]@{
        name    = $f.Name
        path    = $f.FullName
        size_mb = $sizeMB
    }
}

# --- Write report ---
$report = [ordered]@{
    timestamp = (Get-Date -Format 'o')
    msi_dir   = $msiDir
    count     = $msiFiles.Count
    files     = $fileList
}
$reportPath = Write-JsonReport -ReportDir "$BaseDir\reports" -ReportName '01_discovery_report.json' -Data $report

Write-Host ""
Write-Host "  Report: $reportPath" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Next: Create approval file to proceed with installation:" -ForegroundColor Yellow
Write-Host "    touch approvals\APPROVED_INSTALL" -ForegroundColor Yellow

exit 0
