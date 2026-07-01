param(
  [string]$ForkyDir = "$env:USERPROFILE\dev\forky"
)

$ErrorActionPreference = "Stop"
$routePath = Join-Path $ForkyDir "src\route.ts"
$anthropicPath = Join-Path $ForkyDir "src\anthropic.ts"
if (-not (Test-Path $routePath)) {
  throw "route.ts not found at $routePath"
}
if (-not (Test-Path $anthropicPath)) {
  throw "anthropic.ts not found at $anthropicPath"
}

$src = Get-Content -Raw $routePath
if ($src -match "FORKY_WINDOWS_VISION_PATCH") {
  Write-Host "Windows routing patch already present."
} else {

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
}

$anthropic = Get-Content -Raw $anthropicPath
if ($anthropic -match "FORKY_WINDOWS_CACHE_TTL_PATCH") {
  Write-Host "Windows cache TTL patch already present."
  exit 0
}

$oldPrepared = '  const prepared = addCachingMarkers(normalizeCacheBustingTokens(stripUnsupportedFields(injectSystemBlock(body))));'
$newPrepared = @'
  const prepared = normalizeCacheControlTtlOrder(
    addCachingMarkers(normalizeCacheBustingTokens(stripUnsupportedFields(injectSystemBlock(body)))),
  );
'@
if ($anthropic.Contains($oldPrepared)) {
  $anthropic = $anthropic.Replace($oldPrepared, $newPrepared.TrimEnd())
} elseif (-not $anthropic.Contains('const prepared = normalizeCacheControlTtlOrder(')) {
  throw "Could not find forwardOAuth prepared line in $anthropicPath"
}

$normalizer = @'
// FORKY_WINDOWS_CACHE_TTL_PATCH: keep Anthropic cache_control TTLs ordered.
function isCacheRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeCacheControlTtlOrder(body: AnthropicBody): AnthropicBody {
  let sawFiveMinuteTtl = false;
  let changed = false;

  const normalizeBlock = (block: unknown): unknown => {
    if (!isCacheRecord(block) || !isCacheRecord(block.cache_control)) return block;
    const cacheControl = block.cache_control;
    if (cacheControl.type !== "ephemeral") return block;

    const ttl = cacheControl.ttl;
    if (ttl === "1h") {
      if (!sawFiveMinuteTtl) return block;
      changed = true;
      return { ...block, cache_control: { ...cacheControl, ttl: "5m" } };
    }

    if (ttl == null || ttl === "5m") {
      sawFiveMinuteTtl = true;
    }
    return block;
  };

  const out: AnthropicBody = { ...body };

  const tools = (out as { tools?: Array<unknown> }).tools;
  if (Array.isArray(tools)) {
    const normalized = tools.map(normalizeBlock);
    if (normalized.some((block, i) => block !== tools[i])) {
      (out as { tools?: Array<unknown> }).tools = normalized;
    }
  }

  if (Array.isArray(out.system)) {
    const normalized = out.system.map(normalizeBlock) as typeof out.system;
    if (normalized.some((block, i) => block !== out.system![i])) {
      out.system = normalized;
    }
  }

  const messages = (out as { messages?: Array<Record<string, unknown>> }).messages;
  if (Array.isArray(messages)) {
    const normalizedMessages = messages.map((message) => {
      const content = message.content;
      if (!Array.isArray(content)) return message;
      const normalizedContent = content.map(normalizeBlock);
      if (!normalizedContent.some((block, i) => block !== content[i])) return message;
      return { ...message, content: normalizedContent };
    });
    if (normalizedMessages.some((message, i) => message !== messages[i])) {
      (out as { messages?: Array<Record<string, unknown>> }).messages = normalizedMessages;
    }
  }

  return changed ? out : body;
}

'@
if ($anthropic -notmatch "function normalizeCacheControlTtlOrder") {
  $marker = "`n/**`n * Same as forwardOAuth"
  if (-not $anthropic.Contains($marker)) {
    throw "Could not find insertion marker in $anthropicPath"
  }
  $anthropic = $anthropic.Replace($marker, "`n$normalizer$marker")
}

Set-Content -Path $anthropicPath -Value $anthropic -Encoding UTF8
Write-Host "Applied Windows cache TTL patch to $anthropicPath"
