#!/usr/bin/env bash
set -euo pipefail

CODEARTS_VERSION="26.5.6"
DMG_URL="https://codearts-agent-obs-cdn.huaweicloud.com/codearts/cli_tui/latest/codearts-26.5.6-darwin-arm64.dmg"
LITELLM_BASE_URL="http://YOUR_LITELLM_HOST:4000"
INSTALL_DIR="$HOME/Applications/codearts"
CONFIG_DIR="$HOME/.codeartsdoer"
CACHE_DIR="$HOME/.cache/codeartsdoer"
LOCAL_PROXY_HOST="127.0.0.1"
LOCAL_PROXY_PORT="4001"
VIRTUAL_KEY="${LITELLM_VIRTUAL_KEY:-}"
FORCE_INSTALL="false"

usage() {
  cat <<'USAGE'
Usage:
  setup_codearts_litellm.sh [options]

Options:
  --litellm-base-url URL   LiteLLM gateway root or /v1 URL. Default: http://YOUR_LITELLM_HOST:4000
  --virtual-key KEY        LiteLLM virtual key. If omitted, uses $LITELLM_VIRTUAL_KEY or prompts securely.
  --install-dir DIR        CodeArts install directory. Default: ~/Applications/codearts
  --force-install          Reinstall codearts_kernel from the DMG even if it already exists.
  -h, --help               Show this help.

Creates:
  ~/.codeartsdoer/Installers/codearts-litellm
  ~/.codeartsdoer/Installers/codearts-litellm-proxy
  ~/Applications/codearts/codearts_litellm_kernel
  ~/.codeartsdoer/codearts_cli.json
  ~/.codeartsdoer/codeagent.json
  ~/.cache/codeartsdoer/models-cache.json
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --litellm-base-url)
      LITELLM_BASE_URL="${2:?missing value for --litellm-base-url}"
      shift 2
      ;;
    --virtual-key)
      VIRTUAL_KEY="${2:?missing value for --virtual-key}"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="${2:?missing value for --install-dir}"
      shift 2
      ;;
    --force-install)
      FORCE_INSTALL="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_platform() {
  if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
    echo "This installer targets macOS arm64 only." >&2
    exit 1
  fi

  need_cmd curl
  need_cmd hdiutil
  need_cmd python3
  need_cmd perl
  need_cmd codesign
  need_cmd security
  need_cmd jq
  need_cmd lsof
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

inferhub_url() {
  case "$LITELLM_BASE_URL" in
    */v1) printf '%s\n' "$LITELLM_BASE_URL" ;;
    */v1/) printf '%s\n' "${LITELLM_BASE_URL%/}" ;;
    *) printf '%s/v1\n' "${LITELLM_BASE_URL%/}" ;;
  esac
}

download_dmg() {
  local dmg_path="$HOME/Downloads/codearts-${CODEARTS_VERSION}-darwin-arm64.dmg"
  mkdir -p "$HOME/Downloads"
  if [ ! -f "$dmg_path" ]; then
    echo "Downloading CodeArts DMG to $dmg_path" >&2
    curl -L "$DMG_URL" -o "$dmg_path"
  fi
  printf '%s\n' "$dmg_path"
}

find_kernel_in_mount() {
  local mount_dir="$1"
  local candidate=""

  candidate="$(find "$mount_dir" -type f \( -name 'codearts_kernel' -o -name 'codearts' \) -perm -111 2>/dev/null | while IFS= read -r file; do
    size="$(stat -f%z "$file" 2>/dev/null || echo 0)"
    if [ "$size" -gt 50000000 ]; then
      printf '%s\n' "$file"
      break
    fi
  done)"

  if [ -z "$candidate" ]; then
    candidate="$(find "$mount_dir" -type f -name 'codearts*' 2>/dev/null | while IFS= read -r file; do
      size="$(stat -f%z "$file" 2>/dev/null || echo 0)"
      if [ "$size" -gt 50000000 ]; then
        printf '%s\n' "$file"
        break
      fi
    done)"
  fi

  printf '%s\n' "$candidate"
}

install_codearts_kernel() {
  local kernel="$INSTALL_DIR/codearts_kernel"
  if [ -x "$kernel" ] && [ "$FORCE_INSTALL" != "true" ]; then
    echo "Using existing CodeArts kernel: $kernel"
    return
  fi

  local dmg_path mount_dir source_kernel
  dmg_path="$(download_dmg)"
  mount_dir="$(mktemp -d "${TMPDIR:-/tmp}/codearts-dmg.XXXXXX")"

  echo "Mounting $dmg_path"
  hdiutil attach "$dmg_path" -nobrowse -readonly -quiet -mountpoint "$mount_dir"
  trap 'hdiutil detach "$mount_dir" -quiet >/dev/null 2>&1 || true; rm -rf "$mount_dir"' EXIT

  source_kernel="$(find_kernel_in_mount "$mount_dir")"
  if [ -z "$source_kernel" ]; then
    echo "Could not locate a CodeArts kernel executable in the DMG." >&2
    echo "Mounted at: $mount_dir" >&2
    exit 1
  fi

  mkdir -p "$INSTALL_DIR"
  cp "$source_kernel" "$kernel"
  chmod +x "$kernel"
  echo "Installed CodeArts kernel: $kernel"

  hdiutil detach "$mount_dir" -quiet >/dev/null 2>&1 || true
  rm -rf "$mount_dir"
  trap - EXIT
}

patch_litellm_kernel() {
  local source="$INSTALL_DIR/codearts_kernel"
  local target="$INSTALL_DIR/codearts_litellm_kernel"

  if [ ! -x "$source" ]; then
    echo "Missing source kernel: $source" >&2
    exit 1
  fi

  cp "$source" "$target"
  chmod +x "$target"

  # Equal-length binary-safe replacements.
  perl -0pi -e 's/\@ai-sdk\/inferhub-provider/\@ai-sdk\/openai-compatible/g' "$target"
  perl -0pi -e 's/language: "zh-cn"/language: "en-us"/g' "$target"
  perl -0pi -e 's/IMPORTANT: You must reply in English only, regardless of the language used in the user\x27s question\./IMPORTANT: Use English by default. Use Chinese, Spanish, or Brazilian Portuguese when requested.  /g' "$target"
  perl -0pi -e 's/Model Language Rule: You MUST respond ONLY in English\. This includes your response text, internal thinking, reasoning, and any explanations\. Even if the user asks in Chinese, you MUST reply in English only\./Model Language Rule: Use English by default. If the user asks for Chinese, Spanish, or Brazilian Portuguese, reply in that requested language.                                                                /g' "$target"
  perl -0pi -e '$old=q{T7.info("\\u8DF3\\u8FC7\\u767B\\u5F55\\uFF0C\\u4F7F\\u7528\\u73AF\\u5883\\u53D8\\u91CF CODEARTS_CLI_AK \\u548C CODEARTS_CLI_SK \\u6388\\u6743");}; $new=q{void 0;}; $new .= " " x (length($old)-length($new)); s/\Q$old\E/$new/g' "$target"

  codesign --force --sign - "$target" >/dev/null
  codesign -vv "$target"
}

store_virtual_key() {
  if [ -z "$VIRTUAL_KEY" ]; then
    VIRTUAL_KEY="$(security find-generic-password -w -s codearts-litellm -a virtual-key 2>/dev/null || true)"
  fi
  if [ -z "$VIRTUAL_KEY" ]; then
    printf 'LiteLLM virtual key: ' >&2
    stty -echo
    read -r VIRTUAL_KEY
    stty echo
    printf '\n' >&2
  fi
  if [ -z "$VIRTUAL_KEY" ]; then
    echo "LiteLLM virtual key is required." >&2
    exit 1
  fi
  security add-generic-password -U -s codearts-litellm -a virtual-key -w "$VIRTUAL_KEY" >/dev/null
}

write_proxy() {
  local proxy="$CONFIG_DIR/Installers/codearts-litellm-proxy"
  mkdir -p "$CONFIG_DIR/Installers"
  cat >"$proxy" <<'PY'
#!/usr/bin/env python3
import http.client
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DEFAULT_UPSTREAM = "__DEFAULT_UPSTREAM_URL__"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 4001


def virtual_key():
    key = os.environ.get("LITELLM_VIRTUAL_KEY")
    if key:
        return key
    return subprocess.check_output(
        ["security", "find-generic-password", "-w", "-s", "codearts-litellm", "-a", "virtual-key"],
        text=True,
    ).strip()


def upstream():
    raw = os.environ.get("LITELLM_UPSTREAM_URL", DEFAULT_UPSTREAM).rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError(f"Invalid LiteLLM upstream URL: {raw}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    base_path = parsed.path.rstrip("/")
    return parsed.scheme, parsed.hostname, port, base_path


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 so a body with no Content-Length is delimited by connection
    # close, which lets streaming (SSE) responses flush incrementally.
    protocol_version = "HTTP/1.0"

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        scheme, host, port, base_path = upstream()
        body = self.rfile.read(int(self.headers.get("content-length", "0") or "0"))
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "authorization"}
        }
        headers["Authorization"] = f"Bearer {virtual_key()}"
        headers["Content-Length"] = str(len(body))

        path = self.path
        if base_path and not path.startswith(base_path + "/") and path != base_path:
            path = base_path + path

        conn_cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(host, port, timeout=300)
        try:
            conn.request(self.command, path, body, headers)
            response = conn.getresponse()

            self.send_response(response.status)
            for key, value in response.getheaders():
                # Drop hop-by-hop / framing headers; we re-frame as close-delimited.
                if key.lower() not in {"transfer-encoding", "connection", "content-length", "keep-alive"}:
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()

            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except BrokenPipeError:
            pass
        finally:
            conn.close()

    def log_message(self, fmt, *args):
        return


ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler).serve_forever()
PY
  python3 - "$proxy" "$LITELLM_BASE_URL" <<'PY'
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
url = sys.argv[2].rstrip("/")
path.write_text(path.read_text().replace("__DEFAULT_UPSTREAM_URL__", url))
PY
  chmod +x "$proxy"
}

write_wrapper() {
  local wrapper="$CONFIG_DIR/Installers/codearts-litellm"
  mkdir -p "$CONFIG_DIR/Installers"
  cat >"$wrapper" <<'BASH'
#!/bin/bash
set -euo pipefail

KEYCHAIN_SERVICE="codearts-litellm"
KEYCHAIN_ACCOUNT="virtual-key"

YOLO_MODE="false"
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--yolo" ]; then
    YOLO_MODE="true"
  else
    ARGS+=("$arg")
  fi
done

PERMISSION_DIR="$HOME/.codeartsdoer/cli-data/storage/permission"
SANDBOX_DIR="$HOME/.codeartsdoer/cli-data/storage/sandbox"
YOLO_BACKUP_DIR=""

backup_yolo_config() {
  YOLO_BACKUP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/codearts-litellm-yolo.XXXXXX")"
  mkdir -p "$YOLO_BACKUP_DIR/permission" "$YOLO_BACKUP_DIR/sandbox"
  [ -f "$PERMISSION_DIR/config.json" ] && cp "$PERMISSION_DIR/config.json" "$YOLO_BACKUP_DIR/permission/config.json"
  [ -f "$PERMISSION_DIR/global.json" ] && cp "$PERMISSION_DIR/global.json" "$YOLO_BACKUP_DIR/permission/global.json"
  [ -f "$SANDBOX_DIR/config.json" ] && cp "$SANDBOX_DIR/config.json" "$YOLO_BACKUP_DIR/sandbox/config.json"
}

restore_yolo_config() {
  [ -n "$YOLO_BACKUP_DIR" ] && [ -d "$YOLO_BACKUP_DIR" ] || return
  [ -f "$YOLO_BACKUP_DIR/permission/config.json" ] && cp "$YOLO_BACKUP_DIR/permission/config.json" "$PERMISSION_DIR/config.json" || rm -f "$PERMISSION_DIR/config.json"
  [ -f "$YOLO_BACKUP_DIR/permission/global.json" ] && cp "$YOLO_BACKUP_DIR/permission/global.json" "$PERMISSION_DIR/global.json" || rm -f "$PERMISSION_DIR/global.json"
  [ -f "$YOLO_BACKUP_DIR/sandbox/config.json" ] && cp "$YOLO_BACKUP_DIR/sandbox/config.json" "$SANDBOX_DIR/config.json" || rm -f "$SANDBOX_DIR/config.json"
  rm -rf "$YOLO_BACKUP_DIR"
  YOLO_BACKUP_DIR=""
}

enable_yolo_mode() {
  mkdir -p "$PERMISSION_DIR" "$SANDBOX_DIR"
  cat >"$PERMISSION_DIR/config.json" <<'JSON'
{"bash_mode":"always_allow"}
JSON
  cat >"$PERMISSION_DIR/global.json" <<'JSON'
[
  {"permission":"read","pattern":"*","action":"allow"},
  {"permission":"grep","pattern":"*","action":"allow"},
  {"permission":"browser","pattern":"*","action":"allow"},
  {"permission":"glob","pattern":"*","action":"allow"},
  {"permission":"lsp","pattern":"*","action":"allow"},
  {"permission":"codesearch","pattern":"*","action":"allow"},
  {"permission":"edit","pattern":"*","action":"allow"},
  {"permission":"write","pattern":"*","action":"allow"},
  {"permission":"webfetch","pattern":"*","action":"allow"},
  {"permission":"websearch","pattern":"*","action":"allow"},
  {"permission":"external_directory_write","pattern":"*","action":"allow"},
  {"permission":"external_directory_read","pattern":"*","action":"allow"},
  {"permission":"dotfile","pattern":"*","action":"allow"}
]
JSON
  cat >"$SANDBOX_DIR/config.json" <<'JSON'
{"network_policy":"allow_all"}
JSON
}

if [ "$YOLO_MODE" = "true" ]; then
  backup_yolo_config
  trap restore_yolo_config EXIT INT TERM
  enable_yolo_mode
fi

if [ -z "${LITELLM_VIRTUAL_KEY:-}" ]; then
  LITELLM_VIRTUAL_KEY="$(security find-generic-password -w -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" 2>/dev/null || true)"
fi

if [ -z "${LITELLM_VIRTUAL_KEY:-}" ]; then
  echo "Missing LiteLLM virtual key. Add it with: security add-generic-password -U -s codearts-litellm -a virtual-key -w '<key>'" >&2
  exit 1
fi

export LITELLM_VIRTUAL_KEY
export LITELLM_UPSTREAM_URL="__LITELLM_UPSTREAM_URL__"
export CODEARTS_CLI_AK="${CODEARTS_CLI_AK:-Bearer ${LITELLM_VIRTUAL_KEY}}"
export CODEARTS_CLI_SK="${CODEARTS_CLI_SK:-external-maas}"

if ! lsof -nP -iTCP:4001 -sTCP:LISTEN >/dev/null 2>&1; then
  nohup "$HOME/.codeartsdoer/Installers/codearts-litellm-proxy" >/tmp/codearts-litellm-proxy.log 2>&1 &
  sleep 1
fi

SCRIPT_DIR="$HOME/Applications/codearts"
export PATH="${SCRIPT_DIR}:$PATH"
export package_tag="undefined"
export CODEAGENT_USE_MESSAGE_FEEDBACK="false"
export OMO_SEND_ANONYMOUS_TELEMETRY="0"
export SCENARIO="codeartsdoer"
export KERNEL_DATA_DIR="$HOME/.codeartsdoer/cli-data"
export KERNEL_CONFIG_DIR="$HOME/.codeartsdoer"
export OPENCODE_CHANNEL="latest"
export OPENCODE_CONFIG="$HOME/.codeartsdoer/codearts_cli.json"
export OPENCODE_CONFIG_FILE="codearts_cli.json,codearts_cli.jsonc"
export OPENCODE_MODE="tui"
export PLUGIN_ENV="hc"
export NODE_TLS_REJECT_UNAUTHORIZED="0"
export OPENCODE_DISABLE_MODELS_FETCH="1"
export OPENCODE_DISABLE_AUTOUPDATE="true"
export OPENCODE_ALWAYS_NOTIFY_UPDATE="false"

run_kernel() {
  if [ "${#ARGS[@]}" -eq 0 ]; then
    "${SCRIPT_DIR}/codearts_litellm_kernel"
  else
    "${SCRIPT_DIR}/codearts_litellm_kernel" "${ARGS[@]}"
  fi
}

if [ "$YOLO_MODE" = "true" ]; then
  run_kernel
  exit $?
fi

if [ "${#ARGS[@]}" -eq 0 ]; then
  exec "${SCRIPT_DIR}/codearts_litellm_kernel"
fi

exec "${SCRIPT_DIR}/codearts_litellm_kernel" "${ARGS[@]}"
BASH
  python3 - "$wrapper" "$LITELLM_BASE_URL" <<'PY'
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
url = sys.argv[2].rstrip("/")
path.write_text(path.read_text().replace("__LITELLM_UPSTREAM_URL__", url))
PY
  chmod +x "$wrapper"
}

write_codearts_config() {
  local local_base="http://${LOCAL_PROXY_HOST}:${LOCAL_PROXY_PORT}/v1"
  mkdir -p "$CONFIG_DIR" "$CACHE_DIR"

  python3 - "$CONFIG_DIR/codearts_cli.json" "$local_base" <<'PY'
import json
import sys
path, base = sys.argv[1], sys.argv[2]
models = {
    "glm-5.1": {"name": "GLM 5.1", "limit": {"context": 128000, "output": 16000}},
    "claude-opus-4-6": {"name": "Claude Opus 4.6", "limit": {"context": 200000, "output": 32000}},
    "deepseek-v4-pro": {"name": "DeepSeek V4 Pro", "limit": {"context": 128000, "output": 16000}},
    "deepseek-v4-flash": {"name": "DeepSeek V4 Flash", "limit": {"context": 128000, "output": 16000}},
    "deepseek-v3.2": {"name": "DeepSeek V3.2", "limit": {"context": 128000, "output": 16000}},
}
provider = {
    "npm": "@ai-sdk/openai-compatible",
    "name": "LiteLLM Gateway",
    "options": {"baseURL": base, "apiKey": "{env:LITELLM_VIRTUAL_KEY}"},
    "models": models,
}
config = {
    "$schema": "https://opencode.ai/config.json",
    "enabled_providers": ["litellm", "huaweicloud-maas"],
    "provider": {"litellm": provider, "huaweicloud-maas": provider},
}
open(path, "w").write(json.dumps(config, indent=2) + "\n")
PY

  python3 - "$CONFIG_DIR/codeagent.json" "$(inferhub_url)" <<'PY'
import json
import sys
path, inferhub = sys.argv[1], sys.argv[2]
open(path, "w").write(json.dumps({"inferhubBaseUrl": inferhub, "language": "en-us"}, indent=2) + "\n")
PY

  python3 - "$CACHE_DIR/models-cache.json" <<'PY'
import json
import sys
path = sys.argv[1]
models = {
    "glm-5.1": {"id": "GLM 5.1", "reasoning": False, "limit": {"context": 128000, "input": 128000, "output": 16000}, "enable_queue": False},
    "claude-opus-4-6": {"id": "Claude Opus 4.6", "reasoning": True, "limit": {"context": 200000, "input": 200000, "output": 32000}, "enable_queue": False},
    "deepseek-v4-pro": {"id": "DeepSeek V4 Pro", "reasoning": True, "limit": {"context": 128000, "input": 128000, "output": 16000}, "enable_queue": False},
    "deepseek-v4-flash": {"id": "DeepSeek V4 Flash", "reasoning": True, "limit": {"context": 128000, "input": 128000, "output": 16000}, "enable_queue": False},
    "deepseek-v3.2": {"id": "DeepSeek V3.2", "reasoning": True, "limit": {"context": 128000, "input": 128000, "output": 16000}, "enable_queue": False},
}
open(path, "w").write(json.dumps({"models": models, "timestamp": 1781984500000, "version": 1}, indent=2) + "\n")
PY
}

write_default_permissions() {
  mkdir -p "$CONFIG_DIR/cli-data/storage/permission" "$CONFIG_DIR/cli-data/storage/sandbox"
  cat >"$CONFIG_DIR/cli-data/storage/permission/config.json" <<'JSON'
{"bash_mode":"sandbox"}
JSON
  cat >"$CONFIG_DIR/cli-data/storage/permission/global.json" <<'JSON'
[
  {"permission":"read","pattern":"*","action":"allow"},
  {"permission":"grep","pattern":"*","action":"allow"},
  {"permission":"browser","pattern":"*","action":"ask"},
  {"permission":"glob","pattern":"*","action":"allow"},
  {"permission":"lsp","pattern":"*","action":"allow"},
  {"permission":"codesearch","pattern":"*","action":"allow"},
  {"permission":"edit","pattern":"*","action":"ask"},
  {"permission":"write","pattern":"*","action":"ask"},
  {"permission":"webfetch","pattern":"*","action":"ask"},
  {"permission":"websearch","pattern":"*","action":"allow"},
  {"permission":"external_directory_write","pattern":"*","action":"ask"},
  {"permission":"external_directory_read","pattern":"*","action":"allow"},
  {"permission":"dotfile","pattern":"*","action":"ask"}
]
JSON
  cat >"$CONFIG_DIR/cli-data/storage/sandbox/config.json" <<'JSON'
{"network_policy":"deny_all"}
JSON
}

install_user_bin() {
  local bin_dir="$HOME/.local/bin"
  mkdir -p "$bin_dir"
  ln -sf "$CONFIG_DIR/Installers/codearts-litellm" "$bin_dir/codearts-litellm"
  if ! printf '%s' ":$PATH:" | grep -q ":$bin_dir:"; then
    echo "Add this to your shell profile if codearts-litellm is not on PATH:"
    echo "  export PATH=\"$bin_dir:\$PATH\""
  fi
}

verify_install() {
  "$CONFIG_DIR/Installers/codearts-litellm" --version
  "$CONFIG_DIR/Installers/codearts-litellm" models >/dev/null
  jq empty "$CONFIG_DIR/codearts_cli.json"
  jq empty "$CONFIG_DIR/codeagent.json"
  jq empty "$CACHE_DIR/models-cache.json"
  codesign -vv "$INSTALL_DIR/codearts_litellm_kernel"
}

main() {
  require_platform
  install_codearts_kernel
  patch_litellm_kernel
  store_virtual_key
  write_proxy
  write_wrapper
  write_codearts_config
  write_default_permissions
  install_user_bin
  verify_install

  cat <<EOF

codearts-litellm is installed.

Try:
  $CONFIG_DIR/Installers/codearts-litellm models
  $CONFIG_DIR/Installers/codearts-litellm run -m huaweicloud-maas/glm-5.1 "Answer in one word: ready"
  $CONFIG_DIR/Installers/codearts-litellm --yolo
EOF
}

main "$@"
