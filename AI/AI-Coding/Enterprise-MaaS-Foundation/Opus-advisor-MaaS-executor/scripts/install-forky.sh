#!/usr/bin/env bash
# install-forky.sh — clone forky, install deps, ensure the vision-routing branch exists.
# Safe to re-run (idempotent). Does NOT configure or start the service.
set -euo pipefail

FORKY_REPO="${FORKY_REPO:-https://github.com/vladharl/forky.git}"
FORKY_DIR="${FORKY_DIR:-$HOME/dev/forky}"
VISION_BRANCH="${FORKY_VISION_BRANCH:-forky-vision-routing}"
BUN_BIN="${BUN_BIN:-$HOME/.bun/bin/bun}"
SKILL_DIR="$HOME/.claude/skills/Opus-advisor-MaaS-executor"

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

# --- ensure vision-routing branch --------------------------------------------
# The vision patch may already be on main (merged upstream). If so, we still
# create the branch as a marker + upgrade-safe anchor. If it's not on main,
# we apply assets/route-vision.patch.
VISION_PATCH="$HOME/.claude/skills/Opus-advisor-MaaS-executor/assets/route-vision.patch"

has_vision_code() {
  grep -q '"vision"' src/route.ts 2>/dev/null
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

log "forky installed at $FORKY_DIR (branch: $VISION_BRANCH)"
log "next: run scripts/configure-forky.sh"
