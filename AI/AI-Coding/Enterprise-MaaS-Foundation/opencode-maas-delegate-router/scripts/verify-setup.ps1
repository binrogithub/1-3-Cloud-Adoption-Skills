# MaaS Delegate Router — Verify Global Setup
$g = 'Green'; $y = 'Yellow'; $r = 'Red'; $cyan = 'Cyan'

Write-Host ('=' * 55) -ForegroundColor $cyan
Write-Host '  MaaS Delegate Router — Global Setup Verification' -ForegroundColor $cyan
Write-Host ('=' * 55) -ForegroundColor $cyan

$configDir = "$env:USERPROFILE\.config\opencode"
$configFile = Join-Path $configDir 'opencode.json'
$agentsMd = Join-Path $configDir 'AGENTS.md'
$skillsDir = Join-Path $configDir 'skills'
$allOk = $true

# ---- 1. Config file ----
if (Test-Path $configFile) {
    $cfg = Get-Content $configFile -Raw
    $checks = @{}
    $checks['model = huawei-maas/glm-5.2']  = $cfg -match '"model".*"huawei-maas/glm-5.2"'
    $checks['model glm-5.1 in provider']     = ($cfg -match 'glm-5.1') -and ($cfg -match 'huawei-maas')
    $checks['model glm-5.2 in provider']     = ($cfg -match 'glm-5.2') -and ($cfg -match 'huawei-maas')
    $checks['agent: ds-executor']            = $cfg -match '"ds-executor"' -and ($cfg -match 'huawei-maas/glm-5.1')
    $checks['agent: ds-reviewer']            = $cfg -match '"ds-reviewer"' -and ($cfg -match 'huawei-maas/glm-5.1')
    $checks['instructions']                  = $cfg -match '"instructions"'
    $checks['skills.paths']                  = $cfg -match '"paths"'
    Write-Host ''
Write-Host '--- opencode.json ---' -ForegroundColor $cyan
    foreach ($entry in $checks.GetEnumerator()) {
        if ($entry.Value) { Write-Host ('  OK  | {0}' -f $entry.Key) -ForegroundColor $g }
        else { Write-Host ('  FAIL| {0}' -f $entry.Key) -ForegroundColor $r; $allOk = $false }
    }
} else {
    Write-Host ('  FAIL| {0} not found' -f $configFile) -ForegroundColor $r; $allOk = $false
}

# ---- 2. AGENTS.md ----
Write-Host ''
Write-Host '--- AGENTS.md ---' -ForegroundColor $cyan
if (Test-Path $agentsMd) {
    $content = Get-Content $agentsMd -Raw
    $hasPolicy = $content -match 'Hybrid Routing Policy'
    $hasPref52 = $content -match 'GLM-5.2'
    $hasExec51 = $content -match 'huawei-maas/glm-5.1'
    $hasMandatory = $content -match 'MANDATORY'
    $hasHardRules = $content -match 'HARD RULES'
    if ($hasPolicy -and $hasPref52 -and $hasExec51 -and $hasMandatory -and $hasHardRules) {
        Write-Host ('  OK  | Complete routing policy: GLM-5.2 -> GLM-5.1') -ForegroundColor $g
    } else {
        Write-Host ('  WARN| AGENTS.md incomplete') -ForegroundColor $y; $allOk = $false
    }
} else {
    Write-Host ('  FAIL| AGENTS.md not found') -ForegroundColor $r; $allOk = $false
}

# ---- 3. Skills ----
Write-Host ''
Write-Host '--- Skills ---' -ForegroundColor $cyan
$expectedSkills = @('maas-delegate-router','glm-review','glm-repo-summary','glm-test-batch')
foreach ($s in $expectedSkills) {
    $p = Join-Path $skillsDir "$s\SKILL.md"
    if (Test-Path $p) { Write-Host ('  OK  | skills/{0}/SKILL.md' -f $s) -ForegroundColor $g }
    else { Write-Host ('  FAIL| skills/{0}/SKILL.md missing' -f $s) -ForegroundColor $r; $allOk = $false }
}

# ---- 4. API Key ----
Write-Host ''
Write-Host '--- API Key ---' -ForegroundColor $cyan
$key = [System.Environment]::GetEnvironmentVariable('MAAS_API_KEY', 'User')
if ($key) { Write-Host ('  OK  | MAAS_API_KEY is set') -ForegroundColor $g }
else {
    $kp = [System.Environment]::GetEnvironmentVariable('MAAS_API_KEY', 'Process')
    if ($kp) { Write-Host ('  OK  | MAAS_API_KEY is set (session-level)') -ForegroundColor $g }
    else { Write-Host ('  WARN| MAAS_API_KEY not set') -ForegroundColor $y; $allOk = $false }
}

# ---- Summary ----
Write-Host ''
Write-Host ('=' * 55) -ForegroundColor $cyan
if ($allOk) {
    Write-Host '  ALL CHECKS PASSED' -ForegroundColor $g
    Write-Host '  GLM-5.2 (premium) -> GLM-5.1 (execution)' -ForegroundColor $g
    Write-Host '  Restart opencode to activate.' -ForegroundColor $g
    Write-Host ('=' * 55) -ForegroundColor $cyan
} else {
    Write-Host '  SOME CHECKS FAILED — review messages above' -ForegroundColor $y
    Write-Host ('=' * 55) -ForegroundColor $cyan
}
