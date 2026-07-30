# scripts/00_env_check.ps1 — Environment check before MSI installation
# Validates: admin rights, msiexec, config, .env, MSI_DIR, disk space

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

Print-StepHeader -StepNumber "00" -StepName "Environment Check"

$checks = @()

# 1. Admin check
$isAdmin = Test-Administrator
$checks += [ordered]@{ Check = 'Admin rights';     Passed = $isAdmin }
if ($isAdmin) {
    Write-Host "  [PASS] Running as Administrator" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Not running as Administrator" -ForegroundColor Red
}

# 2. msiexec
$msiexec = Get-Command 'msiexec.exe' -ErrorAction SilentlyContinue
$checks += [ordered]@{ Check = 'msiexec available'; Passed = [bool]$msiexec }
if ($msiexec) {
    Write-Host "  [PASS] msiexec.exe found: $($msiexec.Source)" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] msiexec.exe not found" -ForegroundColor Red
}

# 3. Config file
$configPath = "$BaseDir\configs\install.yaml"
$configOk = Test-Path $configPath
$checks += [ordered]@{ Check = 'Config file'; Passed = $configOk }
if ($configOk) {
    Write-Host "  [PASS] Config file found" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Config file not found: $configPath" -ForegroundColor Red
}

# 4. .env file
$envOk = Test-Path $envPath
$checks += [ordered]@{ Check = '.env file'; Passed = $envOk }
if ($envOk) {
    Write-Host "  [PASS] .env file found" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] .env file not found: $envPath" -ForegroundColor Red
}

# 5. MSI_DIR
$msiDir = $env:MSI_DIR
if (-not $msiDir) { $msiDir = (Get-Location).Path }
$msiDirOk = Test-Path $msiDir
$msiCount = 0
if ($msiDirOk) {
    $msiCount = (Get-ChildItem -Path $msiDir -Filter '*.msi' -File -ErrorAction SilentlyContinue).Count
}
$checks += [ordered]@{ Check = 'MSI_DIR accessible'; Passed = ($msiDirOk -and $msiCount -gt 0) }
if ($msiDirOk -and $msiCount -gt 0) {
    Write-Host "  [PASS] MSI_DIR: $msiDir ($msiCount .msi files found)" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] MSI_DIR: $msiDir (no .msi files found)" -ForegroundColor Red
}

# 6. Disk space
$drive = Split-Path -Qualifier $msiDir
$disk = Get-PSDrive -Name $drive.Replace(':', '') -ErrorAction SilentlyContinue
$diskGb = if ($disk) { [math]::Round($disk.Free / 1GB, 2) } else { 0 }
$diskOk = $diskGb -gt 1
$checks += [ordered]@{ Check = 'Disk space >1GB'; Passed = $diskOk }
if ($diskOk) {
    Write-Host "  [PASS] Disk space on $drive $diskGb GB free" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Disk space on $drive $diskGb GB free (<1GB)" -ForegroundColor Red
}

# Summary
$allPassed = ($checks | Where-Object { -not $_.Passed }).Count -eq 0
Write-Host ""
if ($allPassed) {
    Write-Host "  Result: All checks PASSED" -ForegroundColor Green
} else {
    Write-Host "  Result: Some checks FAILED" -ForegroundColor Red
}

# Write report
$report = [ordered]@{
    timestamp = (Get-Date -Format 'o')
    all_passed = $allPassed
    checks     = $checks
}
$reportPath = Write-JsonReport -ReportDir "$BaseDir\reports" -ReportName '00_env_check_report.json' -Data $report
Write-Host "  Report: $reportPath" -ForegroundColor DarkGray

if (-not $allPassed) { exit 1 } else { exit 0 }
