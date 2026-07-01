param(
  [string]$ForkyDir = "$env:USERPROFILE\dev\forky"
)

$ErrorActionPreference = "Stop"
$routePath = Join-Path $ForkyDir "src\route.ts"
if (-not (Test-Path $routePath)) {
  throw "route.ts not found at $routePath"
}

$src = Get-Content -Raw $routePath
if ($src -match "FORKY_WINDOWS_VISION_PATCH") {
  Write-Host "Windows routing patch already present."
  exit 0
}

$src = $src -replace 'const PLAN_MODE_MODEL = "claude-opus-4-7";', 'const PLAN_MODE_MODEL = process.env.FORKY_PLAN_MODEL ?? process.env.FORKY_OPUS_MODEL ?? "claude-opus-4-7";'

$helper = @'

// FORKY_WINDOWS_VISION_PATCH: route image-capable requests to OAuth.
const VISION_MODEL = process.env.FORKY_VISION_MODEL ?? process.env.FORKY_OPUS_MODEL ?? PLAN_MODE_MODEL;

function hasImageContent(x: unknown): boolean {
  if (Array.isArray(x)) return x.some(hasImageContent);
  if (!x || typeof x !== "object") return false;
  const obj = x as Record<string, unknown>;
  if (obj.type === "image" || obj.type === "image_url") return true;
  if (typeof obj.media_type === "string" && obj.media_type.startsWith("image/")) return true;
  return Object.values(obj).some(hasImageContent);
}
'@

$src = $src -replace '(function looksLikeClassifierRequest\()', ($helper + "`nfunction looksLikeClassifierRequest(")

$needle = 'if (/^claude-opus/i.test(model)) {'
$insert = @'
  if (hasImageContent(body)) {
    return { provider: "anthropic-oauth", rewriteModel: VISION_MODEL, reason: "opus" };
  }
'@
$src = $src.Replace($needle, $insert + "`n  " + $needle)

Set-Content -Path $routePath -Value $src -Encoding UTF8
Write-Host "Applied Windows routing patch to $routePath"
