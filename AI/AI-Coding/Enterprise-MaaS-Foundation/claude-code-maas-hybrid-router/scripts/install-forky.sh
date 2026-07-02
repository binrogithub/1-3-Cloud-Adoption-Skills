#!/usr/bin/env bash
# install-forky.sh — clone forky, install deps, ensure local compatibility patches exist.
# Safe to re-run (idempotent). Does NOT configure or start the service.
set -euo pipefail

FORKY_REPO="${FORKY_REPO:-https://github.com/vladharl/forky.git}"
FORKY_DIR="${FORKY_DIR:-$HOME/dev/forky}"
VISION_BRANCH="${FORKY_VISION_BRANCH:-forky-vision-routing}"
BUN_BIN="${BUN_BIN:-$HOME/.bun/bin/bun}"
SKILL_DIR="$HOME/.claude/skills/claude-code-maas-hybrid-router"

log()  { printf '\033[1;34m[install-forky]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[install-forky] error:\033[0m %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1 ($2)"; }

# --- prerequisites -----------------------------------------------------------
need git   "install from your package manager"
need curl  "install from your package manager"
need jq    "install from your package manager (apt install jq / brew install jq)"

if [[ ! -x "$BUN_BIN" ]]; then
  if command -v bun >/dev/null 2>&1; then
    BUN_BIN="$(command -v bun)"
  else
    log "bun not found — installing via bun.sh"
    curl -fsSL https://bun.sh/install | bash || die "bun install failed"
    BUN_BIN="$HOME/.bun/bin/bun"
  fi
fi
log "bun: $("$BUN_BIN" --version)"

if ! command -v claude >/dev/null 2>&1; then
  die "claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
fi

# --- clone or update ----------------------------------------------------------
if [[ -d "$FORKY_DIR/.git" ]]; then
  log "existing repo at $FORKY_DIR — fetching updates"
  git -C "$FORKY_DIR" fetch --quiet origin
else
  log "cloning $FORKY_REPO → $FORKY_DIR"
  mkdir -p "$(dirname "$FORKY_DIR")"
  git clone --quiet "$FORKY_REPO" "$FORKY_DIR"
fi

cd "$FORKY_DIR"

# --- install deps -------------------------------------------------------------
log "bun install"
"$BUN_BIN" install --silent

# --- ensure compatibility branch ---------------------------------------------
# The local branch carries:
# - vision routing: image-bearing turns go to Opus, not GLM.
# - request role normalization: Claude Code may send system/developer roles in
#   messages; forky moves them to top-level system before validation.
# - cache TTL ordering: Anthropic rejects a 1h cache marker after a 5m marker.
VISION_PATCH="$HOME/.claude/skills/claude-code-maas-hybrid-router/assets/route-vision.patch"
NORMALIZE_PATCHER="$HOME/.claude/skills/claude-code-maas-hybrid-router/scripts/apply-request-normalize-patch.py"
CACHE_TTL_PATCHER="$HOME/.claude/skills/claude-code-maas-hybrid-router/scripts/apply-cache-ttl-order-patch.py"

has_vision_code() {
  python3 - src/route.ts <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text()
vision = src.find("if (hasImageContent(body))")
classifier = src.find("if (looksLikeClassifierRequest(model, body))")
sys.exit(0 if '"vision"' in src and vision >= 0 and classifier >= 0 and vision < classifier else 1)
PY
}

has_role_normalizer() {
  grep -q 'request.normalized_roles' src/server.ts 2>/dev/null
}

has_cache_ttl_normalizer() {
  grep -q 'normalizeCacheControlTtlOrder' src/anthropic.ts 2>/dev/null
}

has_plan_hook_fallback() {
  grep -q '\[ "$MODE" = "_" \]' bin/forky-hook 2>/dev/null
}

if git rev-parse --verify --quiet "refs/heads/$VISION_BRANCH" >/dev/null; then
  log "branch $VISION_BRANCH already exists"
else
  log "creating branch $VISION_BRANCH off main"
  git checkout --quiet main
  git pull --quiet --ff-only origin main 2>/dev/null || true
  git checkout --quiet -b "$VISION_BRANCH"
fi

git checkout --quiet "$VISION_BRANCH"

if has_vision_code; then
  log "vision-routing code present in src/route.ts"
else
  log "vision-routing code MISSING — applying patch"
  if [[ -f "$VISION_PATCH" ]]; then
    # Try real git apply first (works if a unified diff was generated)
    if git apply --check "$VISION_PATCH" 2>/dev/null; then
      git apply "$VISION_PATCH"
      git add src/route.ts
      git commit --quiet -m "route: send image-bearing requests to Opus (vision)"
      log "vision patch applied and committed"
    else
      # The patch asset is documentation-form (code blocks with instructions).
      # Fall back to applying via a Python script that makes the edits directly.
      log "unified diff did not apply — trying programmatic patch"
      python3 "$SKILL_DIR/scripts/apply-vision-patch.py" src/route.ts \
        && git add src/route.ts \
        && git commit --quiet -m "route: send image-bearing requests to Opus (vision)" \
        && log "vision patch applied via script" \
        || die "could not apply vision patch. Open $VISION_PATCH and apply the changes to src/route.ts by hand, then commit."
    fi
  else
    die "vision patch asset missing at $VISION_PATCH"
  fi
fi

if has_role_normalizer; then
  log "request-role normalization present in src/server.ts"
else
  log "request-role normalization MISSING — applying patch"
  python3 "$NORMALIZE_PATCHER" src/server.ts \
    && git add src/server.ts \
    && git commit --quiet -m "server: normalize system/developer message roles" \
    && log "request-role normalization patch applied" \
    || die "could not patch src/server.ts for system/developer message roles"
fi

if has_cache_ttl_normalizer; then
  log "cache TTL ordering normalization present in src/anthropic.ts"
else
  log "cache TTL ordering normalization MISSING — applying patch"
  python3 "$CACHE_TTL_PATCHER" src/anthropic.ts \
    && git add src/anthropic.ts \
    && git commit --quiet -m "anthropic: normalize cache TTL marker order" \
    && log "cache TTL ordering patch applied" \
    || die "could not patch src/anthropic.ts for cache TTL ordering"
fi

if has_plan_hook_fallback; then
  log "plan-mode hook fallback present in bin/forky-hook"
else
  log "plan-mode hook fallback MISSING — patching bin/forky-hook"
  python3 - bin/forky-hook <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
src = path.read_text()
old = 'if [ "$MODE" = "plan" ]; then'
new = 'if [ "$MODE" = "plan" ] || [ "$MODE" = "_" ]; then'
if old not in src:
    raise SystemExit(f"could not find hook mode condition in {path}")
path.write_text(src.replace(old, new, 1))
PY
  chmod +x bin/forky-hook
  git add bin/forky-hook
  git commit --quiet -m "hook: treat missing permission mode as plan sentinel"
  log "plan-mode hook fallback patch applied"
fi

log "building native forky executable"
"$BUN_BIN" run build >/dev/null
chmod +x bin/forky

log "forky installed at $FORKY_DIR (branch: $VISION_BRANCH)"
log "next: run scripts/configure-forky.sh"
