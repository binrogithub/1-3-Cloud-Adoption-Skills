# Launch install-msi.cmd elevated and capture output to a file
$cmdScript = "C:\Users\j84418460\Documents\AI\scripts\msi-installer\install-msi.cmd"
$msiDir = "D:\j84418460\Documents\Huawei\Projects\VDI Migration using AI Video\Test Installer"
$outputFile = "C:\Users\j84418460\Documents\AI\scripts\msi-installer\elevated-cmd-output.txt"

if (Test-Path $outputFile) { Remove-Item $outputFile -Force }

Start-Process -FilePath "cmd.exe" -ArgumentList @(
    "/c",
    "cd /d `"$msiDir`" & call `"$cmdScript`" > `"$outputFile`" 2>&1"
) -Verb RunAs -Wait

if (Test-Path $outputFile) {
    Get-Content $outputFile
} else {
    Write-Host "No output file found - UAC may have been denied."
}
