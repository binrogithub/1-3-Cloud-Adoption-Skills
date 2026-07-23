# scripts/03_verify_install.ps1 — Verify installed products in registry
# Reads install report from step 02 and checks registry for each product

param(
    [string]$BaseDir = (Split-Path -Parent $PSScriptRoot)
)

# Load libraries
. "$BaseDir\lib\msi_utils.ps1"
. "$BaseDir\lib\report_utils.ps1"

Print-StepHeader -StepNumber "03" -StepName "Verify Installed Products"

# --- Read install report ---
$installPath = "$BaseDir\reports\02_install_report.json"
if (-not (Test-Path $installPath)) {
    Write-Host "  [FAIL] Install report not found. Run 02_install_msi.ps1 first." -ForegroundColor Red
    exit 1
}
$installReport = Read-JsonReport -Path $installPath

# --- Read discovery report for file names ---
$discoveryPath = "$BaseDir\reports\01_discovery_report.json"
$discovery = Read-JsonReport -Path $discoveryPath

# --- Verify each product ---
Write-Host ""
$results = @()

# Product name mapping (extract product name from MSI filename)
$productMap = @{
    '7z'        = '7-Zip'
    'blender'   = 'Blender'
    'inkscape'  = 'Inkscape'
}

foreach ($file in $discovery.files) {
    $name = $file.name
    # Try to guess product name from filename
    $searchName = $null
    foreach ($key in $productMap.Keys) {
        if ($name -match $key) {
            $searchName = $productMap[$key]
            break
        }
    }
    if (-not $searchName) {
        # Use filename without extension as search term
        $searchName = [System.IO.Path]::GetFileNameWithoutExtension($name)
    }

    Write-Host "  Checking: $name (searching for '$searchName')" -ForegroundColor Yellow

    $product = Test-ProductInstalled -ProductName $searchName
    if ($product) {
        Write-Host "    [FOUND] $($product.DisplayName) v$($product.DisplayVersion)" -ForegroundColor Green
        if ($product.InstallLocation) {
            Write-Host "           Location: $($product.InstallLocation)" -ForegroundColor DarkGray
        }
        $results += [pscustomobject]@{
            File        = $name
            SearchName  = $searchName
            Found       = $true
            DisplayName = $product.DisplayName
            Version     = $product.DisplayVersion
            Location    = $product.InstallLocation
        }
    } else {
        Write-Host "    [NOT FOUND] No registry match for '$searchName'" -ForegroundColor Red
        $results += [pscustomobject]@{
            File        = $name
            SearchName  = $searchName
            Found       = $false
            DisplayName = $null
            Version     = $null
            Location    = $null
        }
    }
}

# --- Summary ---
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "  Verification Summary" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan

$results | Format-Table -Property File, Found, DisplayName, Version -AutoSize

$foundCount   = ($results | Where-Object { $_.Found }).Count
$missingCount = ($results | Where-Object { -not $_.Found }).Count

Write-Host ""
$color = if ($missingCount -eq 0) { 'Green' } else { 'Yellow' }
Write-Host "  Total: $($results.Count)  |  Found: $foundCount  |  Missing: $missingCount" -ForegroundColor $color
Write-Host ""

# --- Write report ---
$report = [ordered]@{
    timestamp = (Get-Date -Format 'o')
    total     = $results.Count
    found     = $foundCount
    missing   = $missingCount
    results   = $results
}
$reportPath = Write-JsonReport -ReportDir "$BaseDir\reports" -ReportName '03_verify_report.json' -Data $report
Write-Host "  Report: $reportPath" -ForegroundColor DarkGray

if ($missingCount -gt 0) { exit 1 } else { exit 0 }
