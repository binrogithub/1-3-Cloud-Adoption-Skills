param(
  [string]$DemoRoot = "C:\Users\Matebook\Documents\Codex\2026-06-02\files-mentioned-by-the-user-databricks\outputs\huawei-dli-hudi-demo",
  [string]$Bucket = "docktest",
  [int]$SmokeTables = 1,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location $DemoRoot

$argsList = @(
  "-ExecutionPolicy", "Bypass",
  "-File", ".\scripts\15_run_notebook_auto.ps1",
  "-Engine", "mrs",
  "-Bucket", $Bucket,
  "-TransientMrsCluster",
  "-SmokeTables", $SmokeTables
)

if ($DryRun) {
  $argsList += "-DryRun"
}

& powershell @argsList
