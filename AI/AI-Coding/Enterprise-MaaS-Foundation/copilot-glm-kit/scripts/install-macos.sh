#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VSIX="$SKILL_DIR/assets/vsix/oai-compatible-copilot-glm-router-0.4.3.vsix"
MODEL_ID="${GLM_MODEL_ID:-glm-5.1}"
BASE_URL="${GLM_BASE_URL:-}"
WRITE_SETTINGS=0

usage() {
  printf '%s\n' \
    'Usage:' \
    '  ./scripts/install-macos.sh' \
    '  ./scripts/install-macos.sh --base-url "https://YOUR-ENDPOINT/openai/v1"' \
    '' \
    'Options:' \
    '  --base-url URL    Also merge recommended GLM/OAI settings into VS Code settings.json.' \
    '  --model ID        Model id/display name. Default: glm-5.1.' \
    '' \
    'Environment variables:' \
    '  GLM_BASE_URL      Same as --base-url.' \
    '  GLM_MODEL_ID      Same as --model.'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:-}"
      WRITE_SETTINGS=1
      shift 2
      ;;
    --model)
      MODEL_ID="${2:-glm-5.1}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ! -f "$VSIX" ]]; then
  echo "VSIX not found: $VSIX" >&2
  exit 1
fi

if command -v code >/dev/null 2>&1; then
  CODE_BIN="$(command -v code)"
elif [[ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]]; then
  CODE_BIN="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
else
  echo "Cannot find VS Code 'code' command. Install VS Code or enable Shell Command: Install 'code' command in PATH." >&2
  exit 1
fi

echo "Installing patched OAI Compatible Copilot VSIX..."
"$CODE_BIN" --install-extension "$VSIX" --force

if [[ -n "$BASE_URL" ]]; then
  WRITE_SETTINGS=1
fi

if [[ "$WRITE_SETTINGS" -eq 1 ]]; then
  if [[ -z "$BASE_URL" ]]; then
    echo "--base-url is required when writing settings." >&2
    exit 1
  fi

  SETTINGS_DIR="$HOME/Library/Application Support/Code/User"
  SETTINGS_FILE="$SETTINGS_DIR/settings.json"
  mkdir -p "$SETTINGS_DIR"
  if [[ -f "$SETTINGS_FILE" ]]; then
    cp "$SETTINGS_FILE" "$SETTINGS_FILE.bak.$(date +%Y%m%d-%H%M%S)"
  else
    printf '{}\n' > "$SETTINGS_FILE"
  fi

  node "$SCRIPT_DIR/merge-settings.mjs" "$SETTINGS_FILE" "$BASE_URL" "$MODEL_ID"
  echo "Merged GLM/OAI settings into: $SETTINGS_FILE"
else
  echo "Skipped settings merge. Re-run with --base-url to apply settings automatically."
fi

echo
echo "Installed extensions:"
"$CODE_BIN" --list-extensions --show-versions | grep -Ei 'oai-compatible-copilot|copilot' || true
echo
echo "Next step in VS Code: run 'Developer: Reload Window', then select '${MODEL_ID} OAI Compatible'."
