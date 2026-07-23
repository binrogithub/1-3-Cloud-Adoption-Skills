# run-elevated-cmd.ps1 — Launch install-msi.cmd with UAC elevation
# Captures output to a file since elevated process output is not inherited.
#
# Usage:
#   .\run-elevated-cmd.ps1                                # Uses defaults
#   .\run-elevated-cmd.ps1 -MsiDir "C:\Packages"          # Specify MSI directory
#   .\run-elevated-cmd.ps1 -CmdScript "C:\Tools\install-msi.cmd"

param(
    [string]$CmdScript = "$PSScriptRoot\install-msi.cmd",
    [string]$MsiDir = (Get-Location).Path,
    [string]$OutputFile = "$env:TEMP\msi-elevated-cmd-output.txt"
)

if (Test-Path $OutputFile) { Remove-Item $OutputFile -Force }

Write-Host "Launching elevated CMD to install MSIs from: $MsiDir" -ForegroundColor Yellow
Write-Host "Output will be captured to: $OutputFile" -ForegroundColor DarkGray
Write-Host ""

Start-Process -FilePath "cmd.exe" -ArgumentList @(
    "/c",
    "cd /d `"$MsiDir`" & call `"$CmdScript`" > `"$OutputFile`" 2>&1"
) -Verb RunAs -Wait

if (Test-Path $OutputFile) {
    Write-Host "=== Elevated Output ===" -ForegroundColor Cyan
    Get-Content $OutputFile
    Write-Host "=== End Output ===" -ForegroundColor Cyan
} else {
    Write-Host "No output file found - UAC may have been denied." -ForegroundColor Red
}
