<#
.SYNOPSIS
  Build a delegation brief for the ds-executor (GLM-5.1) subagent.
.PARAMETER goal
  Task goal (required)
.PARAMETER scope
  Comma-separated file scopes
.PARAMETER constraints
  Comma-separated constraints
.PARAMETER acceptance
  Verification command
#>
param(
    [Parameter(Mandatory=$true)][string]$goal,
    [string]$scope,
    [string]$constraints,
    [string]$acceptance
)

$brief = @{ goal = $goal }
if ($scope) { $brief.scope = $scope -split ',' }
if ($constraints) { $brief.constraints = $constraints -split ',' }
if ($acceptance) { $brief.acceptance = $acceptance }

$json = $brief | ConvertTo-Json -Compress
$cyan = 'Cyan'; $y = 'Yellow'
Write-Host 'Delegation brief (copy into opencode Task):' -ForegroundColor $cyan
Write-Host $json
Write-Host ''
Write-Host 'In opencode, use:' -ForegroundColor $cyan
Write-Host ('  goal: {0}' -f $goal) -ForegroundColor $y
if ($scope) { Write-Host ('  scope: [{0}]' -f ($scope -replace ',', ', ')) -ForegroundColor $y }
if ($constraints) { Write-Host ('  constraints: [{0}]' -f ($constraints -replace ',', ', ')) -ForegroundColor $y }
if ($acceptance) { Write-Host ('  acceptance: {0}' -f $acceptance) -ForegroundColor $y }
