#!/usr/bin/env bash
set -euo pipefail

# install-litellm-plugin.sh
# Install (or uninstall) the anthropic_stream_guard plugin into a
# docker-compose based LiteLLM deployment. Idempotent; every modified file
# gets a timestamped .bak backup. No LiteLLM source code is patched.
#
# What it does:
#   1. Mounts the plugin as a single file at /app/anthropic_stream_guard.py
#      (LiteLLM's get_instance_fn resolves callbacks as <module>.py next to
#      the config file; package directories are NOT supported).
#   2. Registers `anthropic_stream_guard.proxy_handler_instance` under
#      litellm_settings.callbacks.
#   3. Ensures `use_chat_completions_url_for_anthropic_messages: true` under
#      litellm_settings (keeps /v1/messages off the OpenAI Responses API,
#      which OpenAI-compatible backends such as Huawei MaaS do not serve).
#   4. Restarts the LiteLLM service and verifies the plugin import.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LITELLM_DIR="/root/LiteLLM"
COMPOSE_FILE=""
CONFIG_FILE=""
SERVICE="litellm"
CONTAINER="litellm_proxy"
PLUGIN_FILE="$(cd "$SCRIPT_DIR/.." && pwd)/litellm_plugins/anthropic_stream_guard/callback.py"
MOUNT_PATH="/app/anthropic_stream_guard.py"
CALLBACK_NAME="anthropic_stream_guard.proxy_handler_instance"
FLAG_LINE="use_chat_completions_url_for_anthropic_messages"
NO_RESTART=0
DRY_RUN=0
UNINSTALL=0

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: install-litellm-plugin.sh [options]

Options:
  --litellm-dir DIR   LiteLLM deployment dir containing docker-compose.yml.
                      Default: /root/LiteLLM
  --compose-file F    Compose file. Default: <litellm-dir>/docker-compose.yml
  --config-file F     LiteLLM config yaml. Default: auto-detected from the
                      compose mount of /app/config.yaml, else
                      <litellm-dir>/assets/config/litellm_config.yaml
  --service NAME      Compose service name. Default: litellm
  --container NAME    Container name (for health wait / verify). Default: litellm_proxy
  --plugin-file F     Plugin source. Default: repo litellm_plugins/anthropic_stream_guard/callback.py
  --no-restart        Apply file changes but do not restart the service.
  --dry-run           Show what would change without writing.
  --uninstall         Remove the mount + callback (leaves the flag in place).
  -h, --help          Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --litellm-dir)  LITELLM_DIR="$2"; shift 2 ;;
    --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
    --config-file)  CONFIG_FILE="$2"; shift 2 ;;
    --service)      SERVICE="$2"; shift 2 ;;
    --container)    CONTAINER="$2"; shift 2 ;;
    --plugin-file)  PLUGIN_FILE="$2"; shift 2 ;;
    --no-restart)   NO_RESTART=1; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    --uninstall)    UNINSTALL=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *)              die "unknown option: $1" ;;
  esac
done

[[ -f "$PLUGIN_FILE" ]] || die "plugin file not found: $PLUGIN_FILE"
COMPOSE_FILE="${COMPOSE_FILE:-$LITELLM_DIR/docker-compose.yml}"
[[ -f "$COMPOSE_FILE" ]] || die "compose file not found: $COMPOSE_FILE"
command -v python3 >/dev/null || die "python3 is required"

if [[ -z "$CONFIG_FILE" ]]; then
  CONFIG_FILE=$(python3 - "$COMPOSE_FILE" "$LITELLM_DIR" <<'PY'
import re, sys, os
compose, base = sys.argv[1], sys.argv[2]
for line in open(compose):
    m = re.match(r"\s*-\s*(.+?):/app/config\.yaml", line)
    if m:
        p = m.group(1).strip()
        print(p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p)))
        break
else:
    print(os.path.join(base, "assets/config/litellm_config.yaml"))
PY
)
fi
[[ -f "$CONFIG_FILE" ]] || die "LiteLLM config not found: $CONFIG_FILE (pass --config-file)"

echo "Plan:"
echo "  compose : $COMPOSE_FILE (service: $SERVICE)"
echo "  config  : $CONFIG_FILE"
echo "  plugin  : $PLUGIN_FILE -> $MOUNT_PATH"
echo "  action  : $([[ $UNINSTALL == 1 ]] && echo uninstall || echo install)$([[ $DRY_RUN == 1 ]] && echo ' (dry-run)')"
echo

ASG_MODE="$([[ $UNINSTALL == 1 ]] && echo uninstall || echo install)" \
ASG_DRY="$DRY_RUN" ASG_COMPOSE="$COMPOSE_FILE" ASG_CONFIG="$CONFIG_FILE" \
ASG_SERVICE="$SERVICE" ASG_PLUGIN="$PLUGIN_FILE" ASG_MOUNT="$MOUNT_PATH" \
ASG_CALLBACK="$CALLBACK_NAME" ASG_FLAG="$FLAG_LINE" python3 - <<'PY'
import os, re, sys, time

mode      = os.environ["ASG_MODE"]
dry       = os.environ["ASG_DRY"] == "1"
compose_f = os.environ["ASG_COMPOSE"]
config_f  = os.environ["ASG_CONFIG"]
service   = os.environ["ASG_SERVICE"]
plugin    = os.environ["ASG_PLUGIN"]
mount     = os.environ["ASG_MOUNT"]
callback  = os.environ["ASG_CALLBACK"]
flag      = os.environ["ASG_FLAG"]
ts        = time.strftime("%Y%m%d%H%M%S")

def save(path, text, orig):
    if text == orig:
        return False
    if dry:
        print(f"  would modify {path}")
        return True
    backup = f"{path}.bak.{ts}"
    open(backup, "w").write(orig)
    open(path, "w").write(text)
    print(f"  modified {path} (backup: {backup})")
    return True

# ---------- docker-compose.yml ----------
orig = open(compose_f).read()
text = orig
mount_line_re = re.compile(r"^\s*-\s*.+:" + re.escape(mount) + r"(:ro)?\s*$", re.M)
volume_entry = f"{plugin}:{mount}:ro"

if mode == "install":
    if mount_line_re.search(text):
        print(f"  compose: mount already present")
    else:
        # locate the service block, then its volumes: list
        svc = re.search(rf"^(\s*){re.escape(service)}:\s*$", text, re.M)
        if not svc:
            sys.exit(f"error: service '{service}' not found in {compose_f}; add this volume manually:\n      - {volume_entry}")
        svc_indent = len(svc.group(1))
        block_start = svc.end()
        nxt = re.compile(rf"^\s{{0,{svc_indent}}}\S", re.M)
        m_end = nxt.search(text, block_start)
        block_end = m_end.start() if m_end else len(text)
        block = text[block_start:block_end]
        vol = re.search(r"^(\s*)volumes:\s*$", block, re.M)
        if not vol:
            sys.exit(f"error: no volumes: key under service '{service}'; add manually:\n      - {volume_entry}")
        item = re.compile(r"^(\s*)-\s", re.M)
        m_item = item.search(block, vol.end())
        indent = m_item.group(1) if m_item else vol.group(1) + "  "
        insert_at = block_start + vol.end()
        text = text[:insert_at] + f"\n{indent}- {volume_entry}" + text[insert_at:]
        print(f"  compose: mount added")
else:
    text2 = mount_line_re.sub("", text)
    text = re.sub(r"\n\n+", "\n\n", text2) if text2 != text else text
    print(f"  compose: mount {'removed' if text != orig else 'not present'}")
save(compose_f, text, orig)

# ---------- litellm config yaml ----------
orig = open(config_f).read()
text = orig
cb_line_re = re.compile(r"^\s*-\s*" + re.escape(callback) + r"\s*$", re.M)

lls = re.search(r"^litellm_settings:\s*$", text, re.M)
if not lls:
    sys.exit(f"error: litellm_settings: block not found in {config_f}")
lls_end_m = re.compile(r"^\S", re.M).search(text, lls.end())
lls_end = lls_end_m.start() if lls_end_m else len(text)

if mode == "install":
    if cb_line_re.search(text):
        print("  config : callback already registered")
    else:
        block = text[lls.end():lls_end]
        cbs = re.search(r"^(\s*)callbacks:\s*$", block, re.M)
        if cbs:
            # insert after the last consecutive list item of callbacks
            item_re = re.compile(r"^(\s*)-\s.*$", re.M)
            pos = cbs.end()
            indent = None
            for m in item_re.finditer(block, cbs.end()):
                # stop when indentation drops back / another key starts
                between = block[pos:m.start()]
                if re.search(r"^\s*\w[\w_]*:", between, re.M):
                    break
                indent = m.group(1); pos = m.end()
            indent = indent or cbs.group(1) + "  "
            block = block[:pos] + f"\n{indent}- {callback}" + block[pos:]
        else:
            block = f"  callbacks:\n    - {callback}\n" + block
        text = text[:lls.end()] + block + text[lls_end:]
        print("  config : callback registered")
    # ensure routing flag
    if re.search(rf"^\s*{flag}\s*:\s*true", text, re.M):
        print("  config : chat-completions routing flag already set")
    else:
        text = text[:lls.end()] + f"\n  {flag}: true  # keep /v1/messages off the unsupported Responses API" + text[lls.end():]
        print("  config : chat-completions routing flag added")
else:
    if cb_line_re.search(text):
        text = cb_line_re.sub("", text)
        text = re.sub(r"\n\n+\n", "\n\n", text)
        print("  config : callback removed")
    else:
        print("  config : callback not present")
save(config_f, text, orig)
PY

if [[ "$DRY_RUN" == "1" ]]; then
  echo; echo "Dry run complete. No files were changed."
  exit 0
fi

if [[ "$NO_RESTART" == "1" ]]; then
  echo; echo "Files updated. Restart the service to apply:  cd $LITELLM_DIR && docker compose up -d $SERVICE"
  exit 0
fi

echo
echo "Restarting service '$SERVICE' ..."
( cd "$LITELLM_DIR" && docker compose up -d "$SERVICE" >/dev/null )
# `up -d` does not recreate on config-content changes of mounted files; force restart
docker restart "$CONTAINER" >/dev/null

for i in $(seq 1 60); do
  st=$(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo unknown)
  [[ "$st" == "healthy" ]] && { echo "Container healthy."; break; }
  [[ "$i" == "60" ]] && die "container did not become healthy; check: docker logs $CONTAINER"
  sleep 2
done

if [[ "$UNINSTALL" == "0" ]]; then
  echo "Verifying plugin import inside the container ..."
  docker exec "$CONTAINER" python -c "
import sys; sys.path.insert(0, '/app')
from anthropic_stream_guard import proxy_handler_instance, AnthropicStreamGuard
assert 'async_post_call_streaming_iterator_hook' in AnthropicStreamGuard.__dict__
print('plugin import OK:', type(proxy_handler_instance).__name__)
" || die "plugin import failed inside container"
  echo
  echo "Install complete. Next steps: see server/README.md"
  echo "  - ensure a claude-* wildcard entry exists in model_list"
  echo "  - issue per-client virtual keys via /key/generate"
else
  echo "Uninstall complete."
fi
