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
LITELLM_DIR="${LITELLM_DEPLOY_DIR:-}"
COMPOSE_FILE=""
CONFIG_FILE=""
SERVICE="litellm"
CONTAINER="litellm_proxy"
MOUNT_PATH="/app/anthropic_stream_guard.py"
CALLBACK_NAME="anthropic_stream_guard.proxy_handler_instance"
FILTER_MOUNT="/app/anthropic_reasoning_filter.py"
FILTER_CALLBACK="anthropic_reasoning_filter.proxy_handler_instance"
ROUTER_MOUNT="/app/smart_router.py"
ROUTER_CALLBACK="smart_router.proxy_handler_instance"
ROUTER_RULES_MOUNT="/app/smart_router_rules.json"
BREAKER_MOUNT="/app/glm_loop_breaker.py"
BREAKER_CALLBACK="glm_loop_breaker.proxy_handler_instance"
# Sidecar module (PRD-glm52-mainline-sidecars): mounted as /app/sidecar.py and
# imported by smart_router. NOT a registered callback — it has no
# proxy_handler_instance. smart_router does `import sidecar` at runtime.
SIDECAR_MOUNT="/app/sidecar.py"
# Tool Argument Guard (PRD-tool-argument-guard): mounted as
# /app/tool_argument_guard.py and imported by anthropic_stream_guard. NOT a
# registered callback — it is a library used by the stream guard and the
# non-stream success hook. Requires jsonschema (verified at startup).
TOOL_ARG_GUARD_MOUNT="/app/tool_argument_guard.py"
# Convergence modules (PRD-plugin-convergence §7): shared request context and
# LiteLLM exception adapter, mounted as /app/*.py and imported by the plugins.
REQUEST_CONTEXT_MOUNT="/app/_request_context.py"
LITELLM_ADAPTER_MOUNT="/app/_litellm_adapter.py"
# Model registry: mounted so every plugin resolves the same capability profiles.
REGISTRY_MOUNT="/app/model_registry.json"
# Persistent cache volume for caption cache + premium ledger (PRD §9, §10.3).
# Read-write (NOT :ro). Created on the host with mode 0700 if missing.
CACHE_HOST_DIR=""
CACHE_MOUNT="/app/cache"
FLAG_LINE="use_chat_completions_url_for_anthropic_messages"
NO_RESTART=0
DRY_RUN=0
UNINSTALL=0
ARTIFACT=""
SOURCE_ROOT=""  # set by bind_source_paths; disclosed in the plan block

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# ── Bind source file paths to a root directory ────────────────────────────────
# R7 §6.1: with --artifact, the root is the extraction directory; without, it
# is the working tree the script lives in. Called after artifact extraction (or
# directly if no artifact), so the bytes installed are the bytes verified.
bind_source_paths() {
  local root="$1"
  PLUGIN_FILE="$root/litellm_plugins/anthropic_stream_guard/callback.py"
  FILTER_FILE="$root/litellm_plugins/anthropic_reasoning_filter/callback.py"
  ROUTER_FILE="$root/litellm_plugins/smart_router/callback.py"
  ROUTER_RULES_FILE="$root/litellm_plugins/smart_router/smart_router_rules.json"
  BREAKER_FILE="$root/litellm_plugins/glm_loop_breaker/callback.py"
  SIDECAR_FILE="$root/litellm_plugins/sidecar/callback.py"
  TOOL_ARG_GUARD_FILE="$root/litellm_plugins/tool_argument_guard/callback.py"
  REQUEST_CONTEXT_FILE="$root/_request_context.py"
  LITELLM_ADAPTER_FILE="$root/_litellm_adapter.py"
  REGISTRY_FILE="$root/litellm_plugins/model_registry.json"
  SOURCE_ROOT="$root"
}

usage() {
  cat <<'EOF'
Usage: install-litellm-plugin.sh [options]

Options:
  --litellm-dir DIR   LiteLLM deployment dir containing docker-compose.yml.
                      Required (or set LITELLM_DEPLOY_DIR env var).
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
  --artifact PATH     Verify SHA256SUMS for this artifact before installing.
                      PATH is the litellm-auto-plugin-<ver>.tar.gz; a sibling
                      SHA256SUMS must exist. Refuses to install on mismatch.
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
    --artifact)     ARTIFACT="$2"; shift 2 ;;
    --source-root)  SOURCE_ROOT_ARG="$2"; shift 2 ;;
    -h|--help)      usage; exit 0 ;;
    *)              die "unknown option: $1" ;;
  esac
done

# --litellm-dir is required (no hardcoded default — avoids implicit assumptions).
if [[ -z "$LITELLM_DIR" ]]; then
  die "--litellm-dir is required (or set LITELLM_DEPLOY_DIR env var).
  Example: server/install-litellm-plugin.sh --litellm-dir /opt/litellm"
fi

# ── Artifact integrity + extraction (PRD-artifact-chain-closure §6.1) ─────────
# When --source-root is supplied: use that directory directly (durable release
# root, PRD §10). When --artifact is supplied without --source-root: verify
# SHA256SUMS, then EXTRACT to a temp directory and rebind source paths there.
# The bytes installed are the bytes verified — not the working tree's.
EXTRACT_DIR=""
if [[ -n "${SOURCE_ROOT_ARG:-}" ]]; then
  [[ -d "$SOURCE_ROOT_ARG" ]] || die "source root not found: $SOURCE_ROOT_ARG"
  bind_source_paths "$SOURCE_ROOT_ARG"
  echo "  source : durable release root ($SOURCE_ROOT_ARG)"
elif [[ -n "${ARTIFACT:-}" ]]; then
  [[ -f "$ARTIFACT" ]] || die "artifact not found: $ARTIFACT"
  SUMS_FILE="$(dirname "$ARTIFACT")/SHA256SUMS"
  [[ -f "$SUMS_FILE" ]] || die "SHA256SUMS not found next to artifact: $SUMS_FILE"
  echo "Verifying artifact integrity..."
  ARTIFACT_BASENAME="$(basename "$ARTIFACT")"
  EXPECTED_HASH=$(grep -E "^[0-9a-f]{64} +${ARTIFACT_BASENAME}\$" "$SUMS_FILE" | head -1 | cut -d' ' -f1)
  [[ -n "$EXPECTED_HASH" ]] || die "artifact not listed in SHA256SUMS: $ARTIFACT_BASENAME"
  ACTUAL_HASH=$(sha256sum "$ARTIFACT" | cut -d' ' -f1)
  if [[ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]]; then
    die "artifact hash mismatch — refusing to install.
  expected: $EXPECTED_HASH
  actual:   $ACTUAL_HASH"
  fi
  echo "  artifact: OK ($ARTIFACT_BASENAME, sha256 $ACTUAL_HASH)"

  # Reject non-tar / malformed archives before attempting extraction.
  if ! tar tzf "$ARTIFACT" >/dev/null 2>&1; then
    die "artifact is not a valid gzip tar archive — refusing to extract."
  fi
  # Reject archives containing absolute paths or .. traversal components.
  if tar tzf "$ARTIFACT" | grep -E '(^/|(^|/)\.\.(/|$))' >/dev/null; then
    die "artifact contains absolute or traversal paths — refusing to extract."
  fi
  # Extract to a temp directory and rebind source paths there.
  EXTRACT_DIR="$(mktemp -d)"
  trap 'rm -rf "$EXTRACT_DIR"' EXIT INT TERM
  tar xzf "$ARTIFACT" -C "$EXTRACT_DIR"
  # The archive contains a single top-level dir (litellm-auto-plugin-<ver>/).
  EXTRACT_ROOT="$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)"
  [[ -n "$EXTRACT_ROOT" ]] || die "artifact extraction produced no top-level directory."
  bind_source_paths "$EXTRACT_ROOT"
  echo "  source : extraction ($EXTRACT_ROOT)"
else
  # No artifact: install from the working tree, integrity unverified.
  bind_source_paths "$(cd "$SCRIPT_DIR/.." && pwd)"
  echo "  source : working tree (no --artifact; integrity unverified)"
fi

[[ -f "$PLUGIN_FILE" ]] || die "plugin file not found: $PLUGIN_FILE"
[[ -f "$FILTER_FILE" ]] || die "reasoning filter not found: $FILTER_FILE"
[[ -f "$BREAKER_FILE" ]] || die "loop breaker not found: $BREAKER_FILE"
[[ -f "$ROUTER_FILE" ]] || die "smart router not found: $ROUTER_FILE"
[[ -f "$ROUTER_RULES_FILE" ]] || die "smart router rules not found: $ROUTER_RULES_FILE"
[[ -f "$SIDECAR_FILE" ]] || die "sidecar module not found: $SIDECAR_FILE"
[[ -f "$TOOL_ARG_GUARD_FILE" ]] || die "tool argument guard not found: $TOOL_ARG_GUARD_FILE"
[[ -f "$REGISTRY_FILE" ]] || die "model registry not found: $REGISTRY_FILE"
COMPOSE_FILE="${COMPOSE_FILE:-$LITELLM_DIR/docker-compose.yml}"
[[ -f "$COMPOSE_FILE" ]] || die "compose file not found: $COMPOSE_FILE"
command -v python3 >/dev/null || die "python3 is required"

# Default cache host dir lives under the deployment's assets/ (PRD §15).
CACHE_HOST_DIR="${CACHE_HOST_DIR:-$LITELLM_DIR/assets/cache}"

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
echo "  source  : $SOURCE_ROOT"
echo "  plugin  : $PLUGIN_FILE -> $MOUNT_PATH"
echo "  action  : $([[ $UNINSTALL == 1 ]] && echo uninstall || echo install)$([[ $DRY_RUN == 1 ]] && echo ' (dry-run)')"
echo

ASG_MODE="$([[ $UNINSTALL == 1 ]] && echo uninstall || echo install)" \
ASG_DRY="$DRY_RUN" ASG_COMPOSE="$COMPOSE_FILE" ASG_CONFIG="$CONFIG_FILE" \
ASG_SERVICE="$SERVICE" ASG_PLUGIN="$PLUGIN_FILE" ASG_MOUNT="$MOUNT_PATH" \
ASG_CALLBACK="$CALLBACK_NAME" ASG_FLAG="$FLAG_LINE" \
ASG_FILTER_PLUGIN="$FILTER_FILE" ASG_FILTER_MOUNT="$FILTER_MOUNT" \
ASG_FILTER_CALLBACK="$FILTER_CALLBACK" ASG_ROUTER_PLUGIN="$ROUTER_FILE" \
ASG_ROUTER_MOUNT="$ROUTER_MOUNT" ASG_ROUTER_CALLBACK="$ROUTER_CALLBACK" \
ASG_ROUTER_RULES_PLUGIN="$ROUTER_RULES_FILE" \
ASG_ROUTER_RULES_MOUNT="$ROUTER_RULES_MOUNT" \
ASG_BREAKER_PLUGIN="$BREAKER_FILE" ASG_BREAKER_MOUNT="$BREAKER_MOUNT" \
ASG_BREAKER_CALLBACK="$BREAKER_CALLBACK" \
ASG_SIDECAR_PLUGIN="$SIDECAR_FILE" ASG_SIDECAR_MOUNT="$SIDECAR_MOUNT" \
ASG_TOOL_ARG_GUARD_PLUGIN="$TOOL_ARG_GUARD_FILE" ASG_TOOL_ARG_GUARD_MOUNT="$TOOL_ARG_GUARD_MOUNT" \
ASG_REQUEST_CONTEXT_PLUGIN="$REQUEST_CONTEXT_FILE" ASG_REQUEST_CONTEXT_MOUNT="$REQUEST_CONTEXT_MOUNT" \
ASG_LITELLM_ADAPTER_PLUGIN="$LITELLM_ADAPTER_FILE" ASG_LITELLM_ADAPTER_MOUNT="$LITELLM_ADAPTER_MOUNT" \
ASG_REGISTRY_PLUGIN="$REGISTRY_FILE" ASG_REGISTRY_MOUNT="$REGISTRY_MOUNT" \
ASG_CACHE_HOST="$CACHE_HOST_DIR" ASG_CACHE_MOUNT="$CACHE_MOUNT" python3 - <<'PY'
import os, re, sys, time

mode      = os.environ["ASG_MODE"]
dry       = os.environ["ASG_DRY"] == "1"
compose_f = os.environ["ASG_COMPOSE"]
config_f  = os.environ["ASG_CONFIG"]
service   = os.environ["ASG_SERVICE"]
plugin    = os.environ["ASG_PLUGIN"]
mount     = os.environ["ASG_MOUNT"]
callback  = os.environ["ASG_CALLBACK"]
filter_plugin = os.environ["ASG_FILTER_PLUGIN"]
filter_mount = os.environ["ASG_FILTER_MOUNT"]
filter_callback = os.environ["ASG_FILTER_CALLBACK"]
router_plugin = os.environ["ASG_ROUTER_PLUGIN"]
router_mount = os.environ["ASG_ROUTER_MOUNT"]
router_callback = os.environ["ASG_ROUTER_CALLBACK"]
router_rules_plugin = os.environ["ASG_ROUTER_RULES_PLUGIN"]
router_rules_mount = os.environ["ASG_ROUTER_RULES_MOUNT"]
breaker_plugin = os.environ["ASG_BREAKER_PLUGIN"]
breaker_mount = os.environ["ASG_BREAKER_MOUNT"]
breaker_callback = os.environ["ASG_BREAKER_CALLBACK"]
sidecar_plugin = os.environ["ASG_SIDECAR_PLUGIN"]
sidecar_mount = os.environ["ASG_SIDECAR_MOUNT"]
tool_arg_guard_plugin = os.environ["ASG_TOOL_ARG_GUARD_PLUGIN"]
tool_arg_guard_mount = os.environ["ASG_TOOL_ARG_GUARD_MOUNT"]
registry_plugin = os.environ["ASG_REGISTRY_PLUGIN"]
registry_mount = os.environ["ASG_REGISTRY_MOUNT"]
cache_host = os.environ["ASG_CACHE_HOST"]
cache_mount = os.environ["ASG_CACHE_MOUNT"]
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

# R11 §10: When installing from a durable release root (--source-root or
# --artifact), update existing mount source paths to point at the new root.
# This ensures the container runs the durable bytes, not a stale worktree.
_mount_updates = [
    (plugin, mount),
    (filter_plugin, filter_mount),
    (router_plugin, router_mount),
    (router_rules_plugin, router_rules_mount),
    (breaker_plugin, breaker_mount),
    (sidecar_plugin, sidecar_mount),
    (tool_arg_guard_plugin, tool_arg_guard_mount),
    (os.environ.get("ASG_REQUEST_CONTEXT_PLUGIN", ""), os.environ.get("ASG_REQUEST_CONTEXT_MOUNT", "")),
    (os.environ.get("ASG_LITELLM_ADAPTER_PLUGIN", ""), os.environ.get("ASG_LITELLM_ADAPTER_MOUNT", "")),
    (registry_plugin, registry_mount),
]
for src_path, mnt_path in _mount_updates:
    if not src_path:
        continue
    # Match any source path mounted at mnt_path and replace with src_path.
    mnt_re = re.compile(r"^(\s*-\s).+:" + re.escape(mnt_path) + r"(:ro|:rw)?\s*$", re.M)
    m = mnt_re.search(text)
    if m:
        existing_line = m.group(0)
        suffix = m.group(2) or ""
        new_line = "{}{}:{}{}".format(m.group(1), src_path, mnt_path, suffix)
        if existing_line.strip() != new_line.strip():
            text = text[:m.start()] + new_line + text[m.end():]
            print(f"  compose: updated mount source for {mnt_path}")

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

filter_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(filter_mount) + r"(:ro)?\s*$", re.M)
if mode == "install" and not filter_mount_re.search(text):
    primary_mount = re.search(r"^(\s*)-\s*.+:" + re.escape(mount) + r"(:ro)?\s*$", text, re.M)
    if not primary_mount:
        sys.exit(f"error: primary plugin mount missing while adding {filter_mount}")
    insert_at = primary_mount.end()
    text = text[:insert_at] + f"\n{primary_mount.group(1)}- {filter_plugin}:{filter_mount}:ro" + text[insert_at:]
    print("  compose: reasoning filter mount added")
elif mode == "uninstall":
    text = filter_mount_re.sub("", text)

router_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(router_mount) + r"(:ro)?\s*$", re.M)
if mode == "install" and not router_mount_re.search(text):
    filter_mount_line = re.search(r"^(\s*)-\s*.+:" + re.escape(filter_mount) + r"(:ro)?\s*$", text, re.M)
    if not filter_mount_line:
        sys.exit(f"error: reasoning filter mount missing while adding {router_mount}")
    insert_at = filter_mount_line.end()
    text = text[:insert_at] + f"\n{filter_mount_line.group(1)}- {router_plugin}:{router_mount}:ro" + text[insert_at:]
    print("  compose: smart router mount added")
elif mode == "uninstall":
    text = router_mount_re.sub("", text)

router_rules_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(router_rules_mount) + r"(:ro)?\s*$", re.M)
if mode == "install" and not router_rules_mount_re.search(text):
    router_mount_line = re.search(r"^(\s*)-\s*.+:" + re.escape(router_mount) + r"(:ro)?\s*$", text, re.M)
    if not router_mount_line:
        sys.exit(f"error: smart router mount missing while adding {router_rules_mount}")
    insert_at = router_mount_line.end()
    text = text[:insert_at] + f"\n{router_mount_line.group(1)}- {router_rules_plugin}:{router_rules_mount}:ro" + text[insert_at:]
    print("  compose: smart router rules mount added")
elif mode == "uninstall":
    text = router_rules_mount_re.sub("", text)

breaker_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(breaker_mount) + r"(:ro)?\s*$", re.M)
if mode == "install" and not breaker_mount_re.search(text):
    router_rules_line = re.search(r"^(\s*)-\s*.+:" + re.escape(router_rules_mount) + r"(:ro)?\s*$", text, re.M)
    if not router_rules_line:
        sys.exit(f"error: smart router rules mount missing while adding {breaker_mount}")
    insert_at = router_rules_line.end()
    text = text[:insert_at] + f"\n{router_rules_line.group(1)}- {breaker_plugin}:{breaker_mount}:ro" + text[insert_at:]
    print("  compose: loop breaker mount added")
elif mode == "uninstall":
    text = breaker_mount_re.sub("", text)

# Sidecar module mount (PRD-glm52-mainline-sidecars). Not a registered callback —
# smart_router imports it as a plain module. Mounted :ro like the other plugins.
sidecar_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(sidecar_mount) + r"(:ro)?\s*$", re.M)
if mode == "install" and not sidecar_mount_re.search(text):
    breaker_line = re.search(r"^(\s*)-\s*.+:" + re.escape(breaker_mount) + r"(:ro)?\s*$", text, re.M)
    if not breaker_line:
        sys.exit(f"error: loop breaker mount missing while adding {sidecar_mount}")
    insert_at = breaker_line.end()
    text = text[:insert_at] + f"\n{breaker_line.group(1)}- {sidecar_plugin}:{sidecar_mount}:ro" + text[insert_at:]
    print("  compose: sidecar module mount added")
elif mode == "uninstall":
    text = sidecar_mount_re.sub("", text)

# Tool Argument Guard mount (PRD-tool-argument-guard). Not a registered callback —
# anthropic_stream_guard imports it as a plain module. Mounted :ro.
tag_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(tool_arg_guard_mount) + r"(:ro)?\s*$", re.M)
if mode == "install" and not tag_mount_re.search(text):
    sidecar_line = re.search(r"^(\s*)-\s*.+:" + re.escape(sidecar_mount) + r"(:ro)?\s*$", text, re.M)
    if not sidecar_line:
        sys.exit(f"error: sidecar mount missing while adding {tool_arg_guard_mount}")
    insert_at = sidecar_line.end()
    text = text[:insert_at] + f"\n{sidecar_line.group(1)}- {tool_arg_guard_plugin}:{tool_arg_guard_mount}:ro" + text[insert_at:]
    print("  compose: tool argument guard mount added")
elif mode == "uninstall":
    text = tag_mount_re.sub("", text)

# Convergence modules (PRD-plugin-convergence §7): _request_context.py and
# _litellm_adapter.py, imported by the plugins. Mounted :ro after tool_arg_guard.
request_context_plugin = os.environ["ASG_REQUEST_CONTEXT_PLUGIN"]
request_context_mount = os.environ["ASG_REQUEST_CONTEXT_MOUNT"]
litellm_adapter_plugin = os.environ["ASG_LITELLM_ADAPTER_PLUGIN"]
litellm_adapter_mount = os.environ["ASG_LITELLM_ADAPTER_MOUNT"]

rc_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(request_context_mount) + r"(:ro)?\s*$", re.M)
if mode == "install" and not rc_mount_re.search(text):
    tag_line = re.search(r"^(\s*)-\s*.+:" + re.escape(tool_arg_guard_mount) + r"(:ro)?\s*$", text, re.M)
    if not tag_line:
        sys.exit(f"error: tool argument guard mount missing while adding {request_context_mount}")
    insert_at = tag_line.end()
    text = text[:insert_at] + f"\n{tag_line.group(1)}- {request_context_plugin}:{request_context_mount}:ro" + text[insert_at:]
    print("  compose: request context module mount added")
elif mode == "uninstall":
    text = rc_mount_re.sub("", text)

la_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(litellm_adapter_mount) + r"(:ro)?\s*$", re.M)
if mode == "install" and not la_mount_re.search(text):
    rc_line = re.search(r"^(\s*)-\s*.+:" + re.escape(request_context_mount) + r"(:ro)?\s*$", text, re.M)
    if not rc_line:
        sys.exit(f"error: request context mount missing while adding {litellm_adapter_mount}")
    insert_at = rc_line.end()
    text = text[:insert_at] + f"\n{rc_line.group(1)}- {litellm_adapter_plugin}:{litellm_adapter_mount}:ro" + text[insert_at:]
    print("  compose: litellm adapter module mount added")
elif mode == "uninstall":
    text = la_mount_re.sub("", text)

# Model registry mount (read by every plugin for capability profiles).
registry_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(registry_mount) + r"(:ro)?\s*$", re.M)
if mode == "install" and not registry_mount_re.search(text):
    tag_line = re.search(r"^(\s*)-\s*.+:" + re.escape(tool_arg_guard_mount) + r"(:ro)?\s*$", text, re.M)
    if not tag_line:
        sys.exit(f"error: tool argument guard mount missing while adding {registry_mount}")
    insert_at = tag_line.end()
    text = text[:insert_at] + f"\n{tag_line.group(1)}- {registry_plugin}:{registry_mount}:ro" + text[insert_at:]
    print("  compose: model registry mount added")
elif mode == "uninstall":
    text = registry_mount_re.sub("", text)

# Persistent cache volume (read-write) for caption cache + premium ledger.
# Created on the host with mode 0700 if missing (PRD §9.1, §15).
cache_mount_re = re.compile(r"^\s*-\s*.+:" + re.escape(cache_mount) + r"(:rw|:ro)?\s*$", re.M)
if mode == "install":
    import os as _os
    # PRD §7.11: dry-run must perform NO file/directory/permission mutation.
    if not dry:
        try:
            _os.makedirs(cache_host, exist_ok=True)
            _os.chmod(cache_host, 0o700)
        except OSError as exc:
            print(f"  warn: could not create cache dir {cache_host}: {exc}")
    else:
        print(f"  dry-run: would create cache dir {cache_host} (mode 0700)")
    if not cache_mount_re.search(text):
        # Anchor on the registry mount line (the last plugin mount we added).
        anchor = re.search(r"^(\s*)-\s*.+:" + re.escape(registry_mount) + r"(:ro)?\s*$", text, re.M)
        if not anchor:
            # Fall back to the breaker line if registry wasn't added this run.
            anchor = re.search(r"^(\s*)-\s*.+:" + re.escape(breaker_mount) + r"(:ro)?\s*$", text, re.M)
        if anchor:
            insert_at = anchor.end()
            text = text[:insert_at] + f"\n{anchor.group(1)}- {cache_host}:{cache_mount}:rw" + text[insert_at:]
            print(f"  compose: cache volume mount added ({cache_host} -> {cache_mount})")
        else:
            print(f"  warn: could not find an anchor mount to insert {cache_mount}; add manually")
elif mode == "uninstall":
    text = cache_mount_re.sub("", text)

# R11 §4.3: Set TOOL_ARG_GUARD_MODE=enforce in the container environment.
# The installer idempotently adds this env var to the service's environment:
# block so the tool argument guard normalizes/rejects malformed args (not
# just observes them).
if mode == "install":
    tag_env = "TOOL_ARG_GUARD_MODE"
    tag_val = "enforce"
    # Check if already present in the compose environment section.
    env_re = re.compile(r"^(\s+)TOOL_ARG_GUARD_MODE\s*:\s*\S+\s*$", re.M)
    if env_re.search(text):
        # Ensure the value is enforce (update if different).
        text = env_re.sub(r"\1TOOL_ARG_GUARD_MODE: " + tag_val, text)
        print("  compose: TOOL_ARG_GUARD_MODE set to enforce (updated)")
    else:
        # Find the environment: block under the service and insert.
        env_block = re.search(r"^(\s+)environment\s*:\s*$", text, re.M)
        if env_block:
            indent = env_block.group(1) + "  "
            insert_at = env_block.end()
            text = text[:insert_at] + f"\n{indent}{tag_env}: {tag_val}" + text[insert_at:]
            print("  compose: TOOL_ARG_GUARD_MODE=enforce added to environment")
        else:
            # No environment: block — add one after the service line.
            svc = re.search(rf"^(\s*){re.escape(service)}:\s*$", text, re.M)
            if svc:
                indent = svc.group(1) + "  "
                insert_at = svc.end()
                text = text[:insert_at] + f"\n{indent}environment:\n{indent}  {tag_env}: {tag_val}" + text[insert_at:]
                print("  compose: TOOL_ARG_GUARD_MODE=enforce added (new environment block)")
            else:
                print(f"  warn: could not find service '{service}' to add TOOL_ARG_GUARD_MODE; set it manually")
elif mode == "uninstall":
    env_re = re.compile(r"^\s*TOOL_ARG_GUARD_MODE\s*:\s*\S+\s*\n", re.M)
    text = env_re.sub("", text)

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

filter_cb_re = re.compile(r"^\s*-\s*" + re.escape(filter_callback) + r"\s*$", re.M)
if mode == "install" and not filter_cb_re.search(text):
    primary_cb = re.search(r"^(\s*)-\s*" + re.escape(callback) + r"\s*$", text, re.M)
    if not primary_cb:
        sys.exit(f"error: primary callback missing while adding {filter_callback}")
    insert_at = primary_cb.end()
    text = text[:insert_at] + f"\n{primary_cb.group(1)}- {filter_callback}" + text[insert_at:]
    print("  config : reasoning filter callback registered")
elif mode == "uninstall":
    text = filter_cb_re.sub("", text)

router_cb_re = re.compile(r"^\s*-\s*" + re.escape(router_callback) + r"\s*$", re.M)
if mode == "install" and not router_cb_re.search(text):
    filter_cb = re.search(r"^(\s*)-\s*" + re.escape(filter_callback) + r"\s*$", text, re.M)
    if not filter_cb:
        sys.exit(f"error: reasoning filter callback missing while adding {router_callback}")
    insert_at = filter_cb.end()
    text = text[:insert_at] + f"\n{filter_cb.group(1)}- {router_callback}" + text[insert_at:]
    print("  config : smart router callback registered")
elif mode == "uninstall":
    text = router_cb_re.sub("", text)

# Registered last so it sees the request after routing has chosen a model.
breaker_cb_re = re.compile(r"^\s*-\s*" + re.escape(breaker_callback) + r"\s*$", re.M)
if mode == "install" and not breaker_cb_re.search(text):
    router_cb = re.search(r"^(\s*)-\s*" + re.escape(router_callback) + r"\s*$", text, re.M)
    if not router_cb:
        sys.exit(f"error: smart router callback missing while adding {breaker_callback}")
    insert_at = router_cb.end()
    text = text[:insert_at] + f"\n{router_cb.group(1)}- {breaker_callback}" + text[insert_at:]
    print("  config : loop breaker callback registered")
elif mode == "uninstall":
    text = breaker_cb_re.sub("", text)
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
  echo "Verifying plugin import + deployment invariants inside the container ..."
  docker exec "$CONTAINER" python -c "
import sys, os, inspect
sys.path.insert(0, '/app')
from anthropic_stream_guard import proxy_handler_instance, AnthropicStreamGuard
from anthropic_reasoning_filter import proxy_handler_instance as reasoning_filter
from smart_router import proxy_handler_instance as smart_router
from glm_loop_breaker import proxy_handler_instance as loop_breaker
import sidecar
import tool_argument_guard
assert 'async_post_call_streaming_iterator_hook' in AnthropicStreamGuard.__dict__
assert inspect.iscoroutinefunction(sidecar.process_request), 'sidecar.process_request must be async'
assert tool_argument_guard.is_available(), 'tool_argument_guard requires jsonschema'
print('plugin import OK:', type(proxy_handler_instance).__name__)
print('reasoning filter import OK:', type(reasoning_filter).__name__)
print('smart router import OK:', type(smart_router).__name__)
print('loop breaker import OK:', type(loop_breaker).__name__)
print('sidecar import OK: process_request is async coroutine')
print('tool argument guard import OK: jsonschema available, mode=%s' % tool_argument_guard.MODE)
# Registry + cache invariants (PRD §15).
assert os.access('/app/model_registry.json', os.R_OK), 'MODEL_REGISTRY_FILE not readable'
assert os.path.isdir('/app/cache') and os.access('/app/cache', os.W_OK), '/app/cache not writable'
print('registry readable + cache writable OK')
# PRD §7.2: Tool Guard mode must be a known value (startup validation ran at import;
# reaching here means it passed). Enforce mode requires jsonschema (checked above).
assert tool_argument_guard.MODE in ('off', 'observe', 'enforce'), 'invalid TOOL_ARG_GUARD_MODE'
print('tool guard mode valid: %s' % tool_argument_guard.MODE)
# PRD §7.1: residency policy must be importable (defense-in-depth at egress).
assert hasattr(sidecar, 'ResidencyPolicy'), 'sidecar.ResidencyPolicy missing'
assert hasattr(sidecar, 'SidecarPolicyDenied'), 'sidecar.SidecarPolicyDenied missing'
assert sidecar.SidecarPolicyDenied.http_status == 403, 'SIDECAR_POLICY_DENIED must be 403'
print('residency policy + SIDECAR_POLICY_DENIED (403) OK')
# PRD §7.8: cross-process lock must be available (fcntl imported).
assert hasattr(sidecar.CaptionCache, 'cross_process_lock'), 'CaptionCache.cross_process_lock missing'
assert hasattr(sidecar.InterventionLedger, 'claim'), 'InterventionLedger.claim missing'
assert hasattr(sidecar.InterventionLedger, 'record_outcome'), 'InterventionLedger.record_outcome missing'
print('cross-process caption + ledger claims OK')
# PRD §7.9: typed errors carry their declared HTTP status.
assert sidecar.InvalidImageInput.http_status == 400
assert sidecar.ImageLimitExceeded.http_status == 413
assert sidecar.VisionSidecarUnavailable.http_status == 502
assert sidecar.SidecarPolicyDenied.http_status == 403
print('typed error HTTP statuses OK (400/403/413/502)')
# R-6 invariant: every emittable route target must be published in model_list.
# (The smart_router checks this at startup via MODEL_LIST_FILE; here we verify
# the registry + model_list files are present and readable.)
reg_path = os.environ.get('MODEL_REGISTRY_FILE', '/app/model_registry.json')
assert os.access(reg_path, os.R_OK), 'MODEL_REGISTRY_FILE not readable: %s' % reg_path
print('R-6 registry readable OK')
# Loopback reachability: the sidecar calls SIDECAR_BASE_URL (loopback gateway).
base = os.environ.get('SIDECAR_BASE_URL', 'http://127.0.0.1:4000')
print('SIDECAR_BASE_URL=%s (loopback reachability verified at runtime by sidecar)' % base)
# Internal sidecar key must be configured (PRD §7.11).
assert os.environ.get('SIDECAR_API_KEY'), 'SIDECAR_API_KEY not set — internal sidecar key required'
print('SIDECAR_API_KEY configured OK')
print('ALL INVARIANTS OK')
" || die "plugin import / invariant verification failed inside container"
  echo
  echo "Install complete. All deployment invariants verified."
else
  echo "Uninstall complete."
fi
