param(
  [string]$Output = "$PSScriptRoot\glm-local.env",
  [string]$ApiBase = "https://api.modelarts-maas.com/v2/chat/completions",
  [string]$Model = "glm-5.2"
)

$ErrorActionPreference = "Stop"

if ($ApiBase -match "/chat/completions/?$") {
  $ApiBase = $ApiBase -replace "/chat/completions/?$", ""
}

Write-Host "Huawei MaaS GLM configuration"
Write-Host "API base: $ApiBase"
Write-Host "Model: $Model"

$secure = Read-Host "Huawei MaaS API Key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if (-not $apiKey) {
  throw "API key is required."
}

$bytes = New-Object byte[] 24
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try {
  $rng.GetBytes($bytes)
} finally {
  $rng.Dispose()
}
$liteLLMKey = "sk-local-" + [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")

$content = @(
  "# Local secret config for LiteLLM + Huawei MaaS GLM. Do not commit.",
  "GLM_API_BASE=$ApiBase",
  "GLM_MODEL_NAME=$Model",
  "GLM_API_KEY=$apiKey",
  "LITELLM_CCR_KEY=$liteLLMKey"
) -join "`n"

Set-Content -Path $Output -Value $content -Encoding UTF8
Write-Host "Wrote $Output"
Write-Host "Generated local LiteLLM key: $liteLLMKey"
