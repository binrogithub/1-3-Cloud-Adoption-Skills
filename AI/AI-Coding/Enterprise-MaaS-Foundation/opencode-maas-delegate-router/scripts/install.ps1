<#
.SYNOPSIS
  Install MaaS Delegate Router — full global setup.
.DESCRIPTION
  Installs providers, agents, routing policy, and skills globally so that
  hybrid routing (GLM-5.2 premium -> GLM-5.1 execution) is the
  DEFAULT behavior in every opencode session — no need to tell the model.
.PARAMETER maasApiKey
  Huawei MaaS API key. If omitted, you must set MAAS_API_KEY env var manually.
#>
param([string]$maasApiKey)

$g = 'Green'; $y = 'Yellow'; $cyan = 'Cyan'; $r = 'Red'
$configDir = "$env:USERPROFILE\.config\opencode"
$configFile = Join-Path $configDir 'opencode.json'
$agentsMd = Join-Path $configDir 'AGENTS.md'
$skillsDir = Join-Path $configDir 'skills'
$scriptDir = Split-Path -Parent $PSScriptRoot
$policySource = Join-Path $scriptDir 'assets\orchestrator-policy.md'

Write-Host ('=' * 58) -ForegroundColor $cyan
Write-Host '  MaaS Delegate Router — Global Install' -ForegroundColor $cyan
Write-Host '  After install + restart, hybrid routing is the DEFAULT.' -ForegroundColor $cyan
Write-Host ('=' * 58) -ForegroundColor $cyan
Write-Host ('  Premium:   GLM-5.2          (orchestrator)') -ForegroundColor $g
Write-Host ('  Execution: GLM-5.1          (execution pool)') -ForegroundColor $cyan

# ---- Step 1: Create global config ----
Write-Host ''
Write-Host ('[1/4] Creating global config ...') -ForegroundColor $cyan
if (!(Test-Path $configDir)) { New-Item -ItemType Directory -Path $configDir -Force | Out-Null }

if (Test-Path $configFile) {
    $backup = $configFile + '.bak.' + (Get-Date -Format 'yyyyMMddHHmmss')
    Copy-Item -Path $configFile -Destination $backup
    Write-Host ('  -> Existing config backed up to: {0}' -f (Split-Path -Leaf $backup)) -ForegroundColor $y
}

$newConfig = @'
{
  "$schema": "https://opencode.ai/config.json",

  "model": "huawei-maas/glm-5.2",

  "instructions": ["'@ + $configDir.Replace('\','\\') + @'\\AGENTS.md"],

  "agent": {
    "ds-executor": {
      "model": "huawei-maas/glm-5.1",
      "mode": "subagent",
      "description": "Execution pool agent on GLM-5.1. Use for unit tests, docs, CI fixes, codegen, batch refactors, low/medium-risk review.",
      "permission": { "edit": "allow", "bash": "allow" }
    },
    "ds-reviewer": {
      "model": "huawei-maas/glm-5.1",
      "mode": "subagent",
      "description": "Code reviewer on GLM-5.1. Low/medium-risk PR reviews.",
      "permission": { "edit": "deny", "bash": { "git *": "allow", "*": "ask" } }
    }
  },

  "skills": {
    "paths": ["'@ + $configDir.Replace('\','\\') + @'\\skills"]
  },

  "provider": {
    "huawei-maas": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Huawei MaaS",
      "options": {
        "baseURL": "https://api-ap-southeast-1.modelarts-maas.com/openai/v1",
        "apiKey": "{env:MAAS_API_KEY}"
      },
      "models": {
        "glm-5.1": {
          "name": "GLM-5.1",
          "tool_call": true
        },
        "glm-5.2": {
          "name": "GLM-5.2",
          "tool_call": true
        }
      }
    }
  }
}
'@

Set-Content -Path $configFile -Value $newConfig
Write-Host ('  -> Created: opencode.json') -ForegroundColor $g

# ---- Step 2: Create global AGENTS.md ----
Write-Host ('[2/4] Creating global AGENTS.md policy ...') -ForegroundColor $cyan
$agentsContent = Get-Content -Raw -Path $policySource
Set-Content -Path $agentsMd -Value $agentsContent
Write-Host ('  -> Created: AGENTS.md (routing policy)') -ForegroundColor $g

# ---- Step 3: Copy skills ----
Write-Host ('[3/4] Copying skills to global directory ...') -ForegroundColor $cyan
if (!(Test-Path $skillsDir)) { New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null }
$skillSources = @(
    @{ Name = 'maas-delegate-router'; Source = Join-Path $scriptDir 'SKILL.md' },
    @{ Name = 'glm-review'; Source = Join-Path $scriptDir 'assets\skills\glm-review\SKILL.md' },
    @{ Name = 'glm-repo-summary'; Source = Join-Path $scriptDir 'assets\skills\glm-repo-summary\SKILL.md' },
    @{ Name = 'glm-test-batch'; Source = Join-Path $scriptDir 'assets\skills\glm-test-batch\SKILL.md' }
)
foreach ($skill in $skillSources) {
    if (!(Test-Path $skill.Source)) { throw "Missing skill source: $($skill.Source)" }
    $dest = Join-Path $skillsDir $skill.Name
    if (!(Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
    Copy-Item -Path $skill.Source -Destination (Join-Path $dest 'SKILL.md') -Force
    Write-Host ('  -> skills/{0}/SKILL.md' -f $skill.Name) -ForegroundColor $g
}

# ---- Step 4: Set API key ----
Write-Host ('[4/4] Setting MAAS_API_KEY ...') -ForegroundColor $cyan
if ($maasApiKey) {
    [System.Environment]::SetEnvironmentVariable('MAAS_API_KEY', $maasApiKey, 'User')
    Write-Host ('  -> MAAS_API_KEY set as user-level env-var') -ForegroundColor $g
} else {
    $existing = [System.Environment]::GetEnvironmentVariable('MAAS_API_KEY', 'User')
    if ($existing) {
        Write-Host ('  -> MAAS_API_KEY already set') -ForegroundColor $g
    } else {
        Write-Host ('  -> ACTION NEEDED: Set MAAS_API_KEY manually:') -ForegroundColor $y
        Write-Host ('     [Environment]::SetEnvironmentVariable("MAAS_API_KEY","your-key","User")') -ForegroundColor $y
    }
}

# ---- Done ----
Write-Host ''
Write-Host ('=' * 58) -ForegroundColor $cyan
Write-Host '  INSTALL COMPLETE' -ForegroundColor $g
Write-Host ('=' * 58) -ForegroundColor $cyan
Write-Host ''
Write-Host 'What was installed:' -ForegroundColor $cyan
Write-Host '  ~/.config/opencode/opencode.json    — providers + agents + skills + instructions' -ForegroundColor $g
Write-Host '  ~/.config/opencode/AGENTS.md         — routing policy (injected every session)' -ForegroundColor $g
Write-Host '  ~/.config/opencode/skills/           — 4 auto-loaded skills' -ForegroundColor $g
Write-Host ''
Write-Host 'Next steps:' -ForegroundColor $cyan
Write-Host '  1. Restart opencode' -ForegroundColor $y
Write-Host '  2. Type any task — GLM-5.2 routes automatically' -ForegroundColor $y
Write-Host '     Execution (tests, codegen, docs) -> ds-executor on GLM-5.1' -ForegroundColor $g
Write-Host '     Planning, architecture, security  -> stays in-session on GLM-5.2' -ForegroundColor $g
