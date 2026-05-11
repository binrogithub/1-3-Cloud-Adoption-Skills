param(
  [ValidateSet("Smoke", "Package", "ValidateTerraform", "PlanReplace", "ApplyReplace", "FullReplace")]
  [string]$Action = "Smoke",
  [string]$RepoRoot = "E:\codex",
  [string]$BaseUrl = "",
  [string]$VarFile = "E:\codex\.local\ai-site-deploy.tfvars",
  [string]$PlanPath = "E:\codex\.local\maas-gateway-replace.tfplan",
  [int]$WaitSeconds = 150
)

$ErrorActionPreference = "Stop"

function ConvertFrom-SecureStringToPlainText {
  param([Parameter(Mandatory = $true)][SecureString]$SecureString)
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  }
  finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

function Invoke-RepoCommand {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$Arguments = @()
  )

  Push-Location $RepoRoot
  try {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Command failed with exit code $LASTEXITCODE`: $FilePath $($Arguments -join ' ')"
    }
  }
  finally {
    Pop-Location
  }
}

function Read-LocalCredentialFiles {
  $values = @{}
  $paths = @(
    (Join-Path $RepoRoot ".local\huawei-cloud-credentials.env"),
    $VarFile
  )

  foreach ($path in $paths) {
    if (-not (Test-Path -LiteralPath $path)) {
      continue
    }

    foreach ($line in Get-Content -LiteralPath $path) {
      $trimmed = $line.Trim()
      if (-not $trimmed -or $trimmed.StartsWith("#")) {
        continue
      }

      if ($trimmed -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
        $key = $matches[1]
        $value = $matches[2].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
          $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$key] = $value
      }
    }
  }

  return $values
}

function Save-LocalCredentialEnv {
  param([Parameter(Mandatory = $true)][hashtable]$Values)

  $localDir = Join-Path $RepoRoot ".local"
  New-Item -ItemType Directory -Force -Path $localDir | Out-Null
  $envPath = Join-Path $localDir "huawei-cloud-credentials.env"
  $orderedKeys = @(
    "access_key",
    "secret_key",
    "domain_name",
    "admin_password",
    "maas_api_key",
    "gateway_admin_password",
    "virtual_user_password",
    "admin_cidr",
    "project_name"
  )

  $lines = @()
  foreach ($key in $orderedKeys) {
    if ($Values.ContainsKey($key) -and $Values[$key]) {
      $lines += "$key=$($Values[$key])"
    }
  }

  Set-Content -LiteralPath $envPath -Value $lines -Encoding UTF8
  Write-Host "credential_cache: $envPath"
}

function ConvertTo-TerraformString {
  param([AllowNull()][string]$Value)
  if ($null -eq $Value) {
    return ""
  }
  return $Value.Replace("\", "\\").Replace('"', '\"')
}

function Ensure-TerraformVarFile {
  param([Parameter(Mandatory = $true)][hashtable]$Values)

  if (Test-Path -LiteralPath $VarFile) {
    return
  }

  $localDir = Split-Path -Parent $VarFile
  New-Item -ItemType Directory -Force -Path $localDir | Out-Null

  $projectName = if ($Values["project_name"]) { $Values["project_name"] } else { "maas-finops-gateway" }
  $adminCidr = if ($Values["admin_cidr"]) { $Values["admin_cidr"] } else { "0.0.0.0/0" }

  $tfvars = @(
    'region = "la-south-2"',
    'availability_zone = "la-south-2a"',
    'ecs_cpu_core_count = 4',
    'ecs_memory_size = 8',
    ('project_name = "{0}"' -f (ConvertTo-TerraformString $projectName)),
    ('access_key = "{0}"' -f (ConvertTo-TerraformString $Values["access_key"])),
    ('secret_key = "{0}"' -f (ConvertTo-TerraformString $Values["secret_key"])),
    ('domain_name = "{0}"' -f (ConvertTo-TerraformString $Values["domain_name"])),
    ('admin_password = "{0}"' -f (ConvertTo-TerraformString $Values["admin_password"])),
    ('maas_api_key = "{0}"' -f (ConvertTo-TerraformString $Values["maas_api_key"])),
    ('gateway_admin_password = "{0}"' -f (ConvertTo-TerraformString $Values["gateway_admin_password"])),
    ('virtual_user_password = "{0}"' -f (ConvertTo-TerraformString $Values["virtual_user_password"])),
    ('admin_cidr = "{0}"' -f (ConvertTo-TerraformString $adminCidr)),
    'virtual_key_count = 50',
    'virtual_key_budget_usd = 20',
    'create_rds = false'
  )

  Set-Content -LiteralPath $VarFile -Value $tfvars -Encoding UTF8
  Write-Host "tfvars_created: $VarFile"
}

function Request-MissingCredentials {
  param(
    [Parameter(Mandatory = $true)][hashtable]$Values,
    [string[]]$Required = @()
  )

  $labels = @{
    access_key = "Huawei Cloud access_key"
    secret_key = "Huawei Cloud secret_key"
    domain_name = "Huawei Cloud IAM domain_name"
    admin_password = "ECS admin_password"
    maas_api_key = "Huawei Cloud MaaS API key"
    gateway_admin_password = "Gateway admin password"
    virtual_user_password = "Virtual-key user fixed password"
    admin_cidr = "SSH admin CIDR, for example 1.2.3.4/32"
    project_name = "Terraform project_name"
  }
  $secretKeys = @("secret_key", "admin_password", "maas_api_key", "gateway_admin_password", "virtual_user_password")
  $changed = $false

  foreach ($key in $Required) {
    if ($Values.ContainsKey($key) -and $Values[$key]) {
      continue
    }

    if ($secretKeys -contains $key) {
      $secure = Read-Host -Prompt $labels[$key] -AsSecureString
      $Values[$key] = ConvertFrom-SecureStringToPlainText -SecureString $secure
    }
    else {
      $Values[$key] = Read-Host -Prompt $labels[$key]
    }
    $changed = $true
  }

  if ($changed) {
    Save-LocalCredentialEnv -Values $Values
  }

  return $Values
}

function Get-LocalCredentials {
  param([string[]]$Required = @())

  $script = "C:\Users\l00584501\.codex\skills\huawei-cloud-credentials\scripts\get-huawei-cloud-credentials.ps1"
  $values = @{}

  if (Test-Path -LiteralPath $script) {
    $json = & powershell -NoProfile -ExecutionPolicy Bypass -File $script -Json
    if ($LASTEXITCODE -ne 0) {
      throw "Credential helper failed."
    }
    $helperValues = $json | ConvertFrom-Json
    foreach ($property in $helperValues.PSObject.Properties) {
      if ($property.Value) {
        $values[$property.Name] = $property.Value
      }
    }
  }
  else {
    Write-Host "credential_skill: not_found; using .local files and interactive prompts"
  }

  $fileValues = Read-LocalCredentialFiles
  foreach ($key in $fileValues.Keys) {
    if (-not $values.ContainsKey($key) -or -not $values[$key]) {
      $values[$key] = $fileValues[$key]
    }
  }

  return (Request-MissingCredentials -Values $values -Required $Required)
}

function Invoke-Package {
  Invoke-RepoCommand -FilePath "npm" -Arguments @("run", "package:maas-gateway")
}

function Invoke-TerraformValidate {
  Invoke-RepoCommand -FilePath "terraform" -Arguments @("-chdir=terraform\ai-hardware-config-site", "validate")
}

function Invoke-TerraformPlanReplace {
  if (-not (Test-Path -LiteralPath $VarFile)) {
    throw "Missing Terraform var file: $VarFile"
  }

  Invoke-RepoCommand -FilePath "terraform" -Arguments @(
    "-chdir=terraform\ai-hardware-config-site",
    "plan",
    "-input=false",
    "-var-file=$VarFile",
    "-replace=huaweicloud_compute_instance.site",
    "-out=$PlanPath"
  )
}

function Invoke-TerraformApplyReplace {
  if (-not (Test-Path -LiteralPath $PlanPath)) {
    throw "Missing Terraform plan: $PlanPath"
  }

  Invoke-RepoCommand -FilePath "terraform" -Arguments @(
    "-chdir=terraform\ai-hardware-config-site",
    "apply",
    "-input=false",
    $PlanPath
  )
}

function Resolve-BaseUrl {
  if ($BaseUrl) {
    return $BaseUrl.TrimEnd("/")
  }

  if ($env:MAAS_GATEWAY_BASE_URL) {
    return $env:MAAS_GATEWAY_BASE_URL.TrimEnd("/")
  }

  Push-Location $RepoRoot
  try {
    $output = & terraform -chdir=terraform\ai-hardware-config-site output -raw site_url 2>$null
    if ($LASTEXITCODE -eq 0 -and $output) {
      return $output.TrimEnd("/")
    }
  }
  finally {
    Pop-Location
  }

  throw "BaseUrl is required. Pass -BaseUrl, set MAAS_GATEWAY_BASE_URL, or run Terraform so output site_url is available."
}

function Invoke-Smoke {
  $resolvedBaseUrl = Resolve-BaseUrl
  $creds = Get-LocalCredentials
  $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

  $health = Invoke-RestMethod -Uri "$resolvedBaseUrl/api/health" -Method Get -TimeoutSec 60
  Write-Host "health: $($health.status)"

  if ($creds["gateway_admin_password"]) {
    $loginBody = @{
      username = "admin"
      password = $creds["gateway_admin_password"]
    } | ConvertTo-Json

    $login = Invoke-RestMethod -Uri "$resolvedBaseUrl/api/login" -Method Post -ContentType "application/json" -Body $loginBody -WebSession $session -TimeoutSec 60
    Write-Host "admin_login_role: $($login.role)"

    $routes = Invoke-RestMethod -Uri "$resolvedBaseUrl/api/litellm/routes" -Method Get -WebSession $session -TimeoutSec 60
    Write-Host "base_url: $($routes.baseUrl)"
    Write-Host "chat_completions_url: $($routes.chatCompletionsUrl)"
    Write-Host "models_url: $($routes.modelsUrl)"
    Write-Host "model_route_count: $($routes.modelRoutes.Count)"

    $keys = Invoke-RestMethod -Uri "$resolvedBaseUrl/api/admin/keys" -Method Get -WebSession $session -TimeoutSec 60
    Write-Host "virtual_key_count: $($keys.summary.keyCount)"
  }
  else {
    Write-Host "admin smoke skipped: gateway_admin_password missing"
  }

  $mcpBody = @{
    jsonrpc = "2.0"
    id = 1
    method = "tools/list"
    params = @{}
  } | ConvertTo-Json
  $mcp = Invoke-RestMethod -Uri "$resolvedBaseUrl/mcp" -Method Post -ContentType "application/json" -Body $mcpBody -TimeoutSec 60
  $toolNames = $mcp.result.tools | ForEach-Object { $_.name }
  Write-Host "mcp_tools: $($toolNames -join ',')"
}

switch ($Action) {
  "Package" {
    Invoke-Package
  }
  "ValidateTerraform" {
    Invoke-TerraformValidate
  }
  "PlanReplace" {
    $creds = Get-LocalCredentials -Required @("access_key", "secret_key", "domain_name", "admin_password", "maas_api_key", "gateway_admin_password", "virtual_user_password")
    Ensure-TerraformVarFile -Values $creds
    Invoke-Package
    Invoke-TerraformValidate
    Invoke-TerraformPlanReplace
  }
  "ApplyReplace" {
    Get-LocalCredentials | Out-Null
    Invoke-TerraformApplyReplace
  }
  "FullReplace" {
    $creds = Get-LocalCredentials -Required @("access_key", "secret_key", "domain_name", "admin_password", "maas_api_key", "gateway_admin_password", "virtual_user_password")
    Ensure-TerraformVarFile -Values $creds
    Invoke-Package
    Invoke-TerraformValidate
    Invoke-TerraformPlanReplace
    Invoke-TerraformApplyReplace
    Write-Host "waiting_seconds: $WaitSeconds"
    Start-Sleep -Seconds $WaitSeconds
    Invoke-Smoke
  }
  "Smoke" {
    Invoke-Smoke
  }
}
