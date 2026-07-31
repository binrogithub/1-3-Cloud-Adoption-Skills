# Launch install-msi.ps1 elevated and capture output to a file
$scriptPath = "C:\Users\j84418460\Documents\AI\scripts\msi-installer\install-msi.ps1"
$msiDir = "D:\j84418460\Documents\Huawei\Projects\VDI Migration using AI Video\Test Installer"
$outputFile = "C:\Users\j84418460\Documents\AI\scripts\msi-installer\elevated-output.txt"

# Remove old output
if (Test-Path $outputFile) { Remove-Item $outputFile -Force }

Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "& { & '$scriptPath' -Path '$msiDir' -UiMode silent *>&1 | Out-File -FilePath '$outputFile' -Encoding UTF8; exit `$LASTEXITCODE }"
) -Verb RunAs -Wait

# Show the captured output
if (Test-Path $outputFile) {
    Get-Content $outputFile
} else {
    Write-Host "No output file found - UAC may have been denied."
}
