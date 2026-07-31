# run-elevated.ps1 — Launch install-msi.ps1 with UAC elevation
# Captures output to a file since elevated process output is not inherited.
#
# Usage:
#   .\run-elevated.ps1                                    # Uses defaults
#   .\run-elevated.ps1 -MsiDir "C:\Packages"              # Specify MSI directory
#   .\run-elevated.ps1 -ScriptPath "C:\Tools\install-msi.ps1"

param(
    [string]$ScriptPath = "$PSScriptRoot\install-msi.ps1",
    [string]$MsiDir = (Get-Location).Path,
    [string]$OutputFile = "$env:TEMP\msi-elevated-output.txt"
)

# Remove old output
if (Test-Path $OutputFile) { Remove-Item $OutputFile -Force }

Write-Host "Launching elevated PowerShell to install MSIs from: $MsiDir" -ForegroundColor Yellow
Write-Host "Output will be captured to: $OutputFile" -ForegroundColor DarkGray
Write-Host ""

Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "& { & '$ScriptPath' -Path '$MsiDir' *>&1 | Out-File -FilePath '$OutputFile' -Encoding UTF8; exit `$LASTEXITCODE }"
) -Verb RunAs -Wait

# Show the captured output
if (Test-Path $OutputFile) {
    Write-Host "=== Elevated Output ===" -ForegroundColor Cyan
    Get-Content $OutputFile
    Write-Host "=== End Output ===" -ForegroundColor Cyan
} else {
    Write-Host "No output file found - UAC may have been denied." -ForegroundColor Red
}
