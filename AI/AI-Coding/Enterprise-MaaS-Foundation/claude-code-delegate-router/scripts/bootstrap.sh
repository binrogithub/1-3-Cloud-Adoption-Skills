#!/usr/bin/env bash
# bootstrap.sh — unified installer for the Claude Code Direct MaaS Delegate Router.
#
# Installs the complete stack from a fresh machine in one command:
#
#   root side:  /etc/claude-code-proxy/maas.env (real key, 0600 root:root)
#               /etc/systemd/system/<service>   (systemd unit)
#               /opt/claude-code-maas-proxy/    (adapter artifacts)
#               systemctl enable --now + restart
#   user side:  ~/.config/claude-maas/          (dummy key + loopback config)
#               ~/.local/bin/                   (launcher symlinks)
#   optional:   Exa web search (--with-exa)
#
# Credential topology: the real MaaS key lives in the root-owned env file. The
# claude-maas client holds a dummy "maas-local-proxy" key; the adapter injects
# the real key via getAuthKey() fallthrough. The real key never enters the
# user's home directory, argv, stdout, or logs.
#
# Usage:
#   printf '%s\n' "$HUAWEI_MAAS_API_KEY" \
#     | sudo bash scripts/bootstrap.sh \
#         --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
#
#   # With Exa (key on stdin line 2):
#   printf '%s\n%s\n' "$HUAWEI_MAAS_API_KEY" "$EXA_API_KEY" \
#     | sudo bash scripts/bootstrap.sh --maas-url <URL> --with-exa
#
# PRD: docs/PRD_UNIFIED_INSTALL_V1.md
set -euo pipefail

###############################################################################
# Defaults
###############################################################################

DEFAULT_MODEL="glm-5.2"
DEFAULT_PORT="3000"
DEFAULT_ENV_FILE="/etc/claude-code-proxy/maas.env"
DEFAULT_DEST="/opt/claude-code-maas-proxy"
DEFAULT_SERVICE="claude-code-maas-proxy.service"
DUMMY_CLIENT_KEY="maas-local-proxy"

OPT_MAAS_URL=""
OPT_MODEL="$DEFAULT_MODEL"
OPT_PORT="$DEFAULT_PORT"
OPT_WITH_EXA="no"
OPT_ENV_FILE="$DEFAULT_ENV_FILE"
OPT_DEST="$DEFAULT_DEST"
OPT_SERVICE="$DEFAULT_SERVICE"
OPT_SKIP_SYSTEMD="no"
OPT_SKIP_VERIFY="no"
OPT_DRY_RUN="no"
OPT_USER=""
OPT_CONFIG_DIR=""
OPT_VERIFY_LIVE="yes"
OPT_FORCE="no"

# Internal flag for the re-execed root phase.
_ROOT_PHASE="no"

###############################################################################
# Helpers
###############################################################################

die() {
    # Print a safe error message (never the key) to stderr and exit.
    echo "bootstrap: $*" >&2
    exit 1
}

die_code() {
    local code="$1"; shift
    echo "bootstrap: $*" >&2
    exit "$code"
}

###############################################################################
# Resolve project root
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

###############################################################################
# Parse flags
###############################################################################

while [[ $# -gt 0 ]]; do
    case "$1" in
        --maas-url)
            [[ $# -ge 2 ]] || die "--maas-url requires a value"
            OPT_MAAS_URL="$2"; shift 2 ;;
        --maas-url=*)
            OPT_MAAS_URL="${1#--maas-url=}"; shift ;;
        --model)
            [[ $# -ge 2 ]] || die "--model requires a value"
            OPT_MODEL="$2"; shift 2 ;;
        --model=*)
            OPT_MODEL="${1#--model=}"; shift ;;
        --port)
            [[ $# -ge 2 ]] || die "--port requires a value"
            OPT_PORT="$2"; shift 2 ;;
        --port=*)
            OPT_PORT="${1#--port=}"; shift ;;
        --with-exa)
            OPT_WITH_EXA="yes"; shift ;;
        --env-file)
            [[ $# -ge 2 ]] || die "--env-file requires a value"
            OPT_ENV_FILE="$2"; shift 2 ;;
        --env-file=*)
            OPT_ENV_FILE="${1#--env-file=}"; shift ;;
        --dest)
            [[ $# -ge 2 ]] || die "--dest requires a value"
            OPT_DEST="$2"; shift 2 ;;
        --dest=*)
            OPT_DEST="${1#--dest=}"; shift ;;
        --service)
            [[ $# -ge 2 ]] || die "--service requires a value"
            OPT_SERVICE="$2"; shift 2 ;;
        --service=*)
            OPT_SERVICE="${1#--service=}"; shift ;;
        --skip-systemd)
            OPT_SKIP_SYSTEMD="yes"; shift ;;
        --skip-verify)
            OPT_SKIP_VERIFY="yes"; shift ;;
        --dry-run)
            OPT_DRY_RUN="yes"; shift ;;
        --user)
            [[ $# -ge 2 ]] || die "--user requires a value"
            OPT_USER="$2"; shift 2 ;;
        --user=*)
            OPT_USER="${1#--user=}"; shift ;;
        --config-dir)
            [[ $# -ge 2 ]] || die "--config-dir requires a value"
            OPT_CONFIG_DIR="$2"; shift 2 ;;
        --config-dir=*)
            OPT_CONFIG_DIR="${1#--config-dir=}"; shift ;;
        --force)
            OPT_FORCE="yes"; shift ;;
        --verify-live)
            OPT_VERIFY_LIVE="yes"; shift ;;
        --no-verify-live)
            OPT_VERIFY_LIVE="no"; shift ;;
        --root-phase)
            _ROOT_PHASE="yes"; shift ;;
        --help|-h)
            cat <<'USAGE'
bootstrap.sh — unified installer for the Direct MaaS Delegate Router

Usage:
  printf '%s\n' "$KEY" | sudo bash scripts/bootstrap.sh --maas-url <URL> [options]

Mandatory:
  --maas-url URL    Full MaaS chat-completions URL (HTTPS, path has chat/completions)

Optional:
  --model MODEL     Model id (default: glm-5.2)
  --port PORT       Adapter loopback port (default: 3000)
  --with-exa        Also install Exa web search (reads Exa key from stdin line 2)
  --env-file PATH   Env file path (default: /etc/claude-code-proxy/maas.env)
  --dest PATH       Adapter artifact dir (default: /opt/claude-code-maas-proxy)
  --service NAME    systemd unit name (default: claude-code-maas-proxy.service)
  --skip-systemd    Skip daemon-reload/enable/start (testing / non-systemd)
  --skip-verify     Skip post-install verify (WARNING: no verification performed)
  --dry-run         Print actions, write nothing
  --user USER       Target user for client-side install (default: $SUDO_USER)
  --config-dir PATH Client config dir (default: ~/.config/claude-maas)
  --force           Overwrite existing client config even if port differs
  --verify-live     Enable upstream canary in verify (default: on)
  --no-verify-live  Skip upstream canary (offline installs; prints "upstream not verified")
  --help            Show this help

stdin:
  line 1: MaaS API key (mandatory)
  line 2: Exa API key (only if --with-exa)
USAGE
            exit 0 ;;
        *)
            die "unknown option: $1 (use --help)" ;;
    esac
done

###############################################################################
# Validate flags
###############################################################################

[[ -n "$OPT_MAAS_URL" ]] || die "--maas-url is required (the full MaaS chat-completions URL)"
[[ -n "$OPT_MODEL" ]] || die "--model must not be empty"
[[ "$OPT_PORT" =~ ^[0-9]+$ ]] || die "--port must be a positive integer (got: $OPT_PORT)"

# Validate the MaaS URL: must be HTTPS (or localhost/127.0.0.1), and the path
# must contain chat/completions to catch typos.
#
# Run python3 with set -e temporarily disabled so we can capture the exit code
# and emit our own die() message with the correct exit code (PRD §4.4).
_URL_ERR=""
set +e
python3 - "$OPT_MAAS_URL" <<'PYEOF'
import sys
from urllib.parse import urlparse

url = sys.argv[1]
parsed = urlparse(url)
scheme = (parsed.scheme or "").lower()
host = (parsed.hostname or "").lower()

if not scheme:
    sys.stderr.write("--maas-url missing scheme\n"); sys.exit(1)
if scheme != "https" and host not in ("localhost", "127.0.0.1"):
    sys.stderr.write(f"--maas-url must use HTTPS (got {scheme}); non-HTTPS only for localhost\n"); sys.exit(1)
if not host:
    sys.stderr.write("--maas-url must have a host\n"); sys.exit(1)
if "chat/completions" not in (parsed.path or ""):
    sys.stderr.write("--maas-url path must contain 'chat/completions'\n"); sys.exit(1)
PYEOF
_URL_RC=$?
set -e
if [[ $_URL_RC -ne 0 ]]; then
    die "invalid --maas-url: $OPT_MAAS_URL (see messages above)"
fi

# Check dependencies.
command -v node >/dev/null 2>&1 || die_code 2 "node not found on PATH (need Node >= 22)"
if [[ "$OPT_SKIP_SYSTEMD" == "no" ]]; then
    command -v systemctl >/dev/null 2>&1 || die_code 2 "systemctl not found on PATH (use --skip-systemd for non-systemd)"
fi

###############################################################################
# Sudo dispatch: if not root, re-exec via sudo (stdin is preserved).
###############################################################################

if [[ "$_ROOT_PHASE" == "no" && "$(id -u)" -ne 0 ]]; then
    # We are not root. Re-exec ourselves via sudo, passing all original flags.
    # stdin (the key) is inherited across sudo by default.
    exec sudo bash "$0" --root-phase "$@"
fi

###############################################################################
# Determine the target user for the client-side install.
###############################################################################

# Explicit --user flag takes priority over SUDO_USER (PRD V2 G3).
# Priority: --user > SUDO_USER > current user.
if [[ -n "$OPT_USER" ]]; then
    TARGET_USER="$OPT_USER"
elif [[ -n "${SUDO_USER:-}" ]]; then
    TARGET_USER="$SUDO_USER"
elif [[ "$(id -u)" -eq 0 && "$_ROOT_PHASE" == "yes" ]]; then
    # Running as root without sudo and no --user: error to avoid $HOME=/root.
    die "running as root without sudo; pass --user <username> to set the client-side target user"
else
    TARGET_USER="$(id -un)"
fi

# Resolve the target user's home directory.
if [[ "$TARGET_USER" == "$(id -un)" ]]; then
    TARGET_HOME="${HOME:-}"
else
    TARGET_HOME="$(getent passwd "$TARGET_USER" 2>/dev/null | cut -d: -f6 || true)"
    [[ -n "$TARGET_HOME" ]] || die "cannot resolve home directory for user: $TARGET_USER"
fi

###############################################################################
# Read keys from stdin
#
# Line 1: MaaS API key (mandatory, non-empty, single line).
# Line 2: Exa API key (only if --with-exa).
###############################################################################

MAAS_KEY=""
EXA_KEY=""

IFS= read -r MAAS_KEY || true
MAAS_KEY="${MAAS_KEY%$'\r'}"

if [[ ! "$MAAS_KEY" =~ [^[:space:]] ]]; then
    die "MaaS API key must not be empty or whitespace-only (read from stdin line 1)"
fi

if [[ "$OPT_WITH_EXA" == "yes" ]]; then
    IFS= read -r EXA_KEY || true
    EXA_KEY="${EXA_KEY%$'\r'}"
    if [[ ! "$EXA_KEY" =~ [^[:space:]] ]]; then
        die "Exa API key must not be empty or whitespace-only (read from stdin line 2, required with --with-exa)"
    fi
fi

# Reject extra lines on stdin (catches accidental multiline paste of the MaaS key).
if [[ "$OPT_WITH_EXA" == "no" ]]; then
    IFS= read -r _EXTRA_LINE || true
    if [[ -n "$_EXTRA_LINE" ]]; then
        die "unexpected extra input on stdin (MaaS key must be a single line; use --with-exa for a second key)"
    fi
    unset _EXTRA_LINE
fi

###############################################################################
# Resolve the effective client config directory.
###############################################################################

if [[ -n "$OPT_CONFIG_DIR" ]]; then
    EFFECTIVE_CONFIG_DIR="$OPT_CONFIG_DIR"
else
    EFFECTIVE_CONFIG_DIR="$TARGET_HOME/.config/claude-maas"
fi

# G7 safety / D1 write protection: if the target config dir already has a
# config.json pointing at a different port, surface it. In --dry-run, print
# the old vs new value. In a real run, claude-maas-setup.sh will refuse
# (exit 2) unless --force is passed; bootstrap surfaces that as exit 2.
if [[ -f "$EFFECTIVE_CONFIG_DIR/config.json" ]]; then
    _EXISTING_URL=""
    _EXISTING_URL="$(python3 - "$EFFECTIVE_CONFIG_DIR/config.json" <<'PYEOF' 2>/dev/null || true
import json, sys
try:
    with open(sys.argv[1]) as f:
        print(json.load(f).get("anthropic_base_url", ""))
except Exception:
    pass
PYEOF
    )" || true
    _EXISTING_PORT=""
    _EXISTING_PORT="$(python3 - "$_EXISTING_URL" <<'PYEOF' 2>/dev/null || true
import sys, re
m = re.search(r":(\d+)(?:/|$)", sys.argv[1])
if m:
    print(m.group(1))
PYEOF
    )" || true
    if [[ -n "$_EXISTING_PORT" && "$_EXISTING_PORT" != "$OPT_PORT" ]]; then
        if [[ "$OPT_DRY_RUN" == "yes" ]]; then
            echo "  existing config: $EFFECTIVE_CONFIG_DIR/config.json" >&2
            echo "    old base-url:  $_EXISTING_URL (port $_EXISTING_PORT)" >&2
            echo "    new base-url:  http://127.0.0.1:$OPT_PORT (port $OPT_PORT)" >&2
            if [[ "$OPT_FORCE" == "no" ]]; then
                echo "    ACTION: will be REFUSED (port mismatch — pass --force to overwrite)" >&2
            else
                echo "    ACTION: will be OVERWRITTEN (--force)" >&2
            fi
        else
            echo "bootstrap: existing client config at $EFFECTIVE_CONFIG_DIR points at port $_EXISTING_PORT, new port is $OPT_PORT" >&2
        fi
    fi
    unset _EXISTING_URL _EXISTING_PORT
fi

###############################################################################
# Dry-run: print what would be done, write nothing.
###############################################################################

if [[ "$OPT_DRY_RUN" == "yes" ]]; then
    echo "bootstrap: --dry-run — no files will be written"
    echo "  env file:       $OPT_ENV_FILE (root:root 0600)"
    echo "  env contents:   CLAUDE_CODE_PROXY_API_KEY=<${#MAAS_KEY} chars>"
    echo "                  ANTHROPIC_PROXY_BASE_URL=$OPT_MAAS_URL"
    echo "                  COMPLETION_MODEL=$OPT_MODEL"
    echo "                  PROXY_HOST=127.0.0.1"
    echo "                  PROXY_PORT=$OPT_PORT"
    echo "                  DEBUG=false"
    echo "  systemd unit:   /etc/systemd/system/$OPT_SERVICE"
    echo "  adapter dest:   $OPT_DEST"
    echo "  client user:    $TARGET_USER (home: $TARGET_HOME)"
    echo "  client config:  $EFFECTIVE_CONFIG_DIR/config.json (base-url http://127.0.0.1:$OPT_PORT)"
    echo "  client key:     $DUMMY_CLIENT_KEY (dummy)"
    if [[ "$OPT_WITH_EXA" == "yes" ]]; then
        echo "  exa:            install to $TARGET_HOME/.config/claude-maas/exa-api-key"
    else
        echo "  exa:            skipped"
    fi
    echo "bootstrap: --dry-run complete"
    exit 0
fi

###############################################################################
# ROOT PHASE: write env file, systemd unit, deploy adapter artifacts.
###############################################################################

echo "bootstrap: root phase — env file, systemd unit, adapter artifacts"

# --- Write the env file atomically (0600 root:root) ---

ENV_DIR="$(dirname "$OPT_ENV_FILE")"
mkdir -p "$ENV_DIR"

ENV_TMP=$(mktemp "${ENV_DIR}/.maas.env.tmp.XXXXXX") || die "failed to create temp file for env"
trap 'rm -f "$ENV_TMP"' EXIT

{
    printf 'CLAUDE_CODE_PROXY_API_KEY=%s\n' "$MAAS_KEY"
    printf 'ANTHROPIC_PROXY_BASE_URL=%s\n' "$OPT_MAAS_URL"
    printf 'COMPLETION_MODEL=%s\n' "$OPT_MODEL"
    printf 'PROXY_HOST=127.0.0.1\n'
    printf 'PROXY_PORT=%s\n' "$OPT_PORT"
    printf 'DEBUG=false\n'
} >"$ENV_TMP"

chmod 600 "$ENV_TMP"
chown root:root "$ENV_TMP" 2>/dev/null || true
mv "$ENV_TMP" "$OPT_ENV_FILE"
chmod 600 "$OPT_ENV_FILE"
chown root:root "$OPT_ENV_FILE" 2>/dev/null || true
trap - EXIT

echo "bootstrap: env file written to $OPT_ENV_FILE (0600)"

# --- Ensure the adapter artifact directory exists ---

mkdir -p "$OPT_DEST"

# --- Write the systemd unit (idempotent: overwrite if different) ---

if [[ "$OPT_SKIP_SYSTEMD" == "no" ]]; then
    UNIT_DIR="/etc/systemd/system"
    mkdir -p "$UNIT_DIR"
    UNIT_FILE="$UNIT_DIR/$OPT_SERVICE"

    # Build the unit content. ExecStart uses the real node path and the dest.
    NODE_BIN="$(command -v node)"
    UNIT_CONTENT="$(cat <<UNITEOF
[Unit]
Description=Claude Code MaaS Direct Proxy (Anthropic -> Huawei MaaS)
After=network.target

[Service]
Type=simple
WorkingDirectory=$OPT_DEST
ExecStart=$NODE_BIN $OPT_DEST/server.js
Restart=always
RestartSec=3
EnvironmentFile=$OPT_ENV_FILE

[Install]
WantedBy=multi-user.target
UNITEOF
)"

    # Write only if the content differs (idempotent).
    _NEEDS_WRITE="yes"
    if [[ -f "$UNIT_FILE" ]]; then
        if [[ "$UNIT_CONTENT" == "$(cat "$UNIT_FILE")" ]]; then
            _NEEDS_WRITE="no"
        fi
    fi
    if [[ "$_NEEDS_WRITE" == "yes" ]]; then
        printf '%s\n' "$UNIT_CONTENT" >"$UNIT_FILE"
        chmod 644 "$UNIT_FILE"
        chown root:root "$UNIT_FILE" 2>/dev/null || true
        echo "bootstrap: systemd unit written to $UNIT_FILE"
    else
        echo "bootstrap: systemd unit already up to date"
    fi

    systemctl daemon-reload
    echo "bootstrap: systemctl daemon-reload ok"
fi

# --- Deploy adapter artifacts (reuses adapter/deploy.sh) ---

echo "bootstrap: deploying adapter artifacts via adapter/deploy.sh"

DEPLOY_ENV=(
    "ADAPTER_DEST_DIR=$OPT_DEST"
    "ADAPTER_SERVICE=$OPT_SERVICE"
)

# Run deploy.sh with the env overrides. If --skip-systemd, deploy.sh will still
# try systemctl cat; that's fine — it just skips restart if the unit isn't found.
env "${DEPLOY_ENV[@]}" bash "$PROJECT_ROOT/adapter/deploy.sh" \
    || die_code 3 "adapter/deploy.sh failed"

# --- Enable and start the service ---

if [[ "$OPT_SKIP_SYSTEMD" == "no" ]]; then
    systemctl enable "$OPT_SERVICE" 2>/dev/null || true
    systemctl restart "$OPT_SERVICE"
    echo "bootstrap: service restarted"
    if ! systemctl is-active "$OPT_SERVICE" >/dev/null 2>&1; then
        die_code 3 "service failed to start: $OPT_SERVICE"
    fi
    echo "bootstrap: service active"
fi

###############################################################################
# USER PHASE: install client config + launchers as the target user.
###############################################################################

echo "bootstrap: user phase — client config + launchers (user: $TARGET_USER)"

SETUP_SCRIPT="$PROJECT_ROOT/client/claude-maas-setup.sh"
EXA_SCRIPT="$PROJECT_ROOT/scripts/configure-exa.sh"

# Helper: run a command as the target user with the correct HOME.
run_as_target() {
    if [[ "$TARGET_USER" == "$(id -un)" ]]; then
        # Already the target user — run directly.
        "$@"
    else
        # Drop privileges via sudo -u with HOME set.
        sudo -u "$TARGET_USER" env HOME="$TARGET_HOME" "$@"
    fi
}

# Install the client-side config with the DUMMY key and loopback URL.
# The real key never reaches claude-maas-setup.sh.
# Pass --config-dir if the user specified one (for isolation / multi-profile).
SETUP_ARGS=(
    --base-url "http://127.0.0.1:$OPT_PORT"
    --model "$OPT_MODEL"
)
if [[ -n "$OPT_CONFIG_DIR" ]]; then
    SETUP_ARGS+=(--config-dir "$EFFECTIVE_CONFIG_DIR")
fi
if [[ "$OPT_FORCE" == "yes" ]]; then
    SETUP_ARGS+=(--force)
fi

# Run claude-maas-setup.sh. A write-protection refusal (exit 2) is surfaced
# distinctly so the caller knows to pass --force rather than seeing a generic
# "install failed" (PRD CLIENT_CONFIG_PROTECTION §2 D1).
_SETUP_RC=0
printf '%s\n' "$DUMMY_CLIENT_KEY" | run_as_target bash "$SETUP_SCRIPT" \
    "${SETUP_ARGS[@]}" \
    || _SETUP_RC=$?
if [[ $_SETUP_RC -eq 2 ]]; then
    die_code 2 "claude-maas-setup.sh refused to overwrite (port mismatch — pass --force)"
elif [[ $_SETUP_RC -ne 0 ]]; then
    die_code 3 "claude-maas-setup.sh failed (exit $_SETUP_RC)"
fi

echo "bootstrap: client config installed to $EFFECTIVE_CONFIG_DIR/"

# --- Optional: Exa ---

if [[ "$OPT_WITH_EXA" == "yes" ]]; then
    echo "bootstrap: installing Exa (user: $TARGET_USER)"
    EXA_ARGS=()
    if [[ -n "$OPT_CONFIG_DIR" ]]; then
        EXA_ARGS+=(--config-dir "$EFFECTIVE_CONFIG_DIR")
    fi
    printf '%s\n' "$EXA_KEY" | run_as_target bash "$EXA_SCRIPT" \
        "${EXA_ARGS[@]}" \
        || die_code 3 "configure-exa.sh failed"
    echo "bootstrap: Exa installed to $EFFECTIVE_CONFIG_DIR/exa-api-key"
fi

###############################################################################
# Verify — hard gate (PRD V2 G1, G2, G4)
#
# Three stages, any failure → exit code 4 (distinct from 3 = install failure):
#   1. Local /status with bounded polling (>=10s) to absorb service startup.
#   2. Launcher PATH check — claude-maas must be on the target user's PATH.
#   3. Upstream canary — real MaaS request via live_maas_probe (if --verify-live).
#
# --skip-verify bypasses the entire gate (for testing / non-systemd).
###############################################################################

VERIFY_OK="yes"

if [[ "$OPT_SKIP_VERIFY" == "no" ]]; then
    echo "bootstrap: verify — hard gate"

    # --- Stage 1: local /status with bounded polling (G4, R2) ---
    #
    # Poll /status with 0.5s intervals until it responds or the 15s deadline
    # is reached.  Use SECONDS for real wall-clock measurement (not iteration
    # count) so the actual wait matches the deadline.

    _STATUS_OK="no"
    _POLL_DEADLINE=15  # seconds (PRD V3 R2: >=15s)
    _POLL_ELAPSED=0
    if command -v curl >/dev/null 2>&1; then
        _POLL_START=$SECONDS
        while true; do
            if curl -sf "http://127.0.0.1:$OPT_PORT/status" >/dev/null 2>&1; then
                _STATUS_OK="yes"
                break
            fi
            _POLL_ELAPSED=$((SECONDS - _POLL_START))
            if [[ "$_POLL_ELAPSED" -ge "$_POLL_DEADLINE" ]]; then
                break
            fi
            sleep 0.5
        done
        _POLL_ELAPSED=$((SECONDS - _POLL_START))
    fi

    if [[ "$_STATUS_OK" == "yes" ]]; then
        echo "bootstrap: verify: adapter /status ok (port $OPT_PORT)"
    else
        echo "bootstrap: verify: FAIL — adapter /status not reachable on port $OPT_PORT after ${_POLL_ELAPSED}s" >&2
        echo "bootstrap:   check: systemctl status $OPT_SERVICE" >&2
        echo "bootstrap:   logs:  journalctl -u $OPT_SERVICE -n 50" >&2
        VERIFY_OK="no"
    fi

    # --- Stage 2: launcher PATH check (G2) ---

    _LAUNCHER_DIR="$TARGET_HOME/.local/bin"
    _LAUNCHER_PATH="$_LAUNCHER_DIR/claude-maas"

    if [[ ! -e "$_LAUNCHER_PATH" ]]; then
        echo "bootstrap: verify: FAIL — launcher not installed at $_LAUNCHER_PATH" >&2
        VERIFY_OK="no"
    else
        # Check if ~/.local/bin is on the target user's PATH.
        # We simulate the target user's login PATH by checking getent + common defaults.
        _TARGET_PATH=""
        if [[ "$TARGET_USER" == "$(id -un)" ]]; then
            _TARGET_PATH="${PATH:-}"
        else
            # Get the target user's default PATH from their shell environment.
            _TARGET_PATH="$(sudo -u "$TARGET_USER" env HOME="$TARGET_HOME" bash -lc 'echo "$PATH"' 2>/dev/null || true)"
        fi

        _PATH_HAS_LOCAL_BIN="no"
        case ":$_TARGET_PATH:" in
            *":$_LAUNCHER_DIR:"*) _PATH_HAS_LOCAL_BIN="yes" ;;
        esac

        if [[ "$_PATH_HAS_LOCAL_BIN" == "no" ]]; then
            echo "bootstrap: verify: FAIL — $_LAUNCHER_DIR is not on $TARGET_USER's PATH" >&2
            echo "bootstrap:   the launcher claude-maas is installed but will not be found by the user." >&2
            echo "bootstrap:   fix: add this line to the user's shell profile (~/.bashrc or ~/.zshrc):" >&2
            echo "bootstrap:        export PATH=\"\$HOME/.local/bin:\$PATH\"" >&2
            VERIFY_OK="no"
        else
            echo "bootstrap: verify: launcher on PATH ok"
        fi
    fi

    # --- Stage 3: upstream canary (G1) — only if --verify-live ---

    if [[ "$OPT_VERIFY_LIVE" == "yes" ]]; then
        echo "bootstrap: verify: upstream canary (live MaaS request)"
        # Allow tests to override the probe path via env var (mutation testing).
        _CANARY_PROBE="${BOOTSTRAP_CANARY_PROBE:-$PROJECT_ROOT/tests/live_maas_probe.py}"
        if [[ -f "$_CANARY_PROBE" ]]; then
            _CANARY_RC=0
            printf '%s\n' "$MAAS_KEY" | python3 "$_CANARY_PROBE" \
                --probe text \
                --base-url "http://127.0.0.1:$OPT_PORT" \
                >/dev/null 2>&1 || _CANARY_RC=$?
            if [[ $_CANARY_RC -eq 0 ]]; then
                echo "bootstrap: verify: upstream canary ok"
            else
                echo "bootstrap: verify: FAIL — upstream canary failed (exit $_CANARY_RC)" >&2
                echo "bootstrap:   the adapter is running but MaaS rejected the request." >&2
                echo "bootstrap:   check: key validity, URL correctness, and MaaS service status." >&2
                echo "bootstrap:   probe: printf '%s\n' \"\$KEY\" | python3 tests/live_maas_probe.py --probe text --base-url http://127.0.0.1:$OPT_PORT" >&2
                VERIFY_OK="no"
            fi
        else
            echo "bootstrap: verify: WARNING — live_maas_probe.py not found, skipping upstream canary" >&2
        fi
    else
        echo "bootstrap: verify: upstream canary SKIPPED (--no-verify-live; upstream not verified)" >&2
    fi

    # --- Stage 4: launcher entry (D2) — only if --verify-live and prior stages ok ---
    #
    # PRD CLIENT_CONFIG_PROTECTION §2 D2: verify through the claude-maas
    # launcher, not just the protocol port. The launcher reads
    # ~/.config/claude-maas/config.json — if the config is wrong, this fails.
    # Skip if prior stages already failed (no point testing the launcher if
    # the adapter isn't even reachable).

    if [[ "$OPT_VERIFY_LIVE" == "yes" && "$VERIFY_OK" == "yes" ]]; then
        echo "bootstrap: verify: launcher entry (claude-maas real turn)"
        _LAUNCHER_PROBE="$PROJECT_ROOT/tests/claude_maas_launcher_probe.sh"
        if [[ -f "$_LAUNCHER_PROBE" && -x "$_LAUNCHER_PROBE" ]]; then
            _LAUNCHER_RC=0
            run_as_target bash "$_LAUNCHER_PROBE" >/dev/null 2>&1 || _LAUNCHER_RC=$?
            if [[ $_LAUNCHER_RC -eq 0 ]]; then
                echo "bootstrap: verify: launcher entry ok"
            else
                echo "bootstrap: verify: FAIL — launcher entry failed (exit $_LAUNCHER_RC)" >&2
                echo "bootstrap:   the claude-maas launcher could not complete a real turn." >&2
                echo "bootstrap:   check: ~/.config/claude-maas/config.json" >&2
                VERIFY_OK="no"
            fi
        else
            echo "bootstrap: verify: WARNING — launcher probe not found, skipping launcher entry" >&2
        fi
    fi

    # --- Verify verdict ---

    if [[ "$VERIFY_OK" != "yes" ]]; then
        echo "" >&2
        echo "bootstrap: INSTALL COMPLETED BUT VERIFY FAILED (exit code 4)" >&2
        echo "bootstrap: the adapter and client config were written, but verification did not pass." >&2
        echo "bootstrap: rollback: bash $PROJECT_ROOT/adapter/rollback.sh" >&2
        echo "bootstrap: status:   systemctl status $OPT_SERVICE" >&2
        die_code 4 "verify failed — see messages above"
    fi

    echo "bootstrap: verify: all gates passed"
fi

###############################################################################
# Success — key-free summary
###############################################################################

echo ""
echo "bootstrap: complete"
echo "  adapter:  http://127.0.0.1:$OPT_PORT -> $OPT_MAAS_URL (model: $OPT_MODEL)"
echo "  service:  $OPT_SERVICE"
echo "  env:      $OPT_ENV_FILE"
echo "  client:   $EFFECTIVE_CONFIG_DIR (user: $TARGET_USER)"
if [[ "$OPT_WITH_EXA" == "yes" ]]; then
    echo "  exa:      installed"
fi
if [[ "$OPT_SKIP_VERIFY" == "yes" ]]; then
    echo "  verify:   SKIPPED (--skip-verify)"
elif [[ "$OPT_VERIFY_LIVE" == "no" ]]; then
    echo "  verify:   local ok, upstream not verified (--no-verify-live)"
fi
echo ""
echo "  Next: claude-maas --version   # verify the client launcher works"
echo "  Mode A (OAuth orchestrator): ./scripts/configure-policy.sh"
