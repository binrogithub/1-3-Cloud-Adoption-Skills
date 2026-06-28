#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/canteen-ordering"
ENV_FILE="/etc/canteen-ordering.env"
SERVICE_NAME="canteen-ordering"
NGINX_SERVICE="nginx"
LOCAL_HEALTH_URL="http://127.0.0.1/health"
PUBLIC_HEALTH_URL=""
SKIP_PIP=0
SKIP_DB_CHECK=0
AUTO_INSTALL_MYSQL_CLIENT=0

usage() {
  cat <<'EOF'
Usage:
  sudo bash deploy/restart_after_migration.sh [options]

Options:
  --app-dir <path>              App directory (default: /opt/canteen-ordering)
  --env-file <path>             Env file path (default: /etc/canteen-ordering.env)
  --public-health-url <url>     Optional public health URL for external check
  --skip-pip                    Skip 'pip install -r requirements.txt'
  --skip-db-check               Skip MySQL connectivity test
  --install-mysql-client        Install mysql client if not present
  -h, --help                    Show this help

Examples:
  sudo bash deploy/restart_after_migration.sh
  sudo bash deploy/restart_after_migration.sh --public-health-url http://1.2.3.4/health
  sudo bash deploy/restart_after_migration.sh --skip-pip --skip-db-check
EOF
}

log() {
  echo "[INFO] $*"
}

err() {
  echo "[ERROR] $*" >&2
}

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || {
    err "Missing command: $cmd"
    exit 1
  }
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --app-dir)
        APP_DIR="$2"
        shift 2
        ;;
      --env-file)
        ENV_FILE="$2"
        shift 2
        ;;
      --public-health-url)
        PUBLIC_HEALTH_URL="$2"
        shift 2
        ;;
      --skip-pip)
        SKIP_PIP=1
        shift
        ;;
      --skip-db-check)
        SKIP_DB_CHECK=1
        shift
        ;;
      --install-mysql-client)
        AUTO_INSTALL_MYSQL_CLIENT=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        err "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
  done
}

ensure_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    err "Please run as root, e.g.: sudo bash $0"
    exit 1
  fi
}

validate_paths() {
  [[ -d "$APP_DIR" ]] || {
    err "App dir not found: $APP_DIR"
    exit 1
  }
  [[ -f "$ENV_FILE" ]] || {
    err "Env file not found: $ENV_FILE"
    exit 1
  }
  [[ -f "$APP_DIR/requirements.txt" ]] || {
    err "requirements.txt not found: $APP_DIR/requirements.txt"
    exit 1
  }
  [[ -f "$APP_DIR/scripts_init_db.py" ]] || {
    err "scripts_init_db.py not found: $APP_DIR/scripts_init_db.py"
    exit 1
  }
  [[ -x "$APP_DIR/venv/bin/python" ]] || {
    err "Python venv not found: $APP_DIR/venv/bin/python"
    exit 1
  }
}

load_env() {
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a

  local required_vars=("DB_HOST" "DB_PORT" "DB_NAME" "DB_USER" "DB_PASSWORD")
  local v
  for v in "${required_vars[@]}"; do
    if [[ -z "${!v:-}" ]]; then
      err "Missing required variable in $ENV_FILE: $v"
      exit 1
    fi
  done
}

maybe_install_mysql_client() {
  if command -v mysql >/dev/null 2>&1; then
    return 0
  fi

  if [[ "$AUTO_INSTALL_MYSQL_CLIENT" -ne 1 ]]; then
    err "mysql client is not installed. Re-run with --install-mysql-client or install manually."
    return 1
  fi

  log "Installing mysql client..."
  apt-get update
  apt-get install -y mysql-client
}

db_check() {
  if [[ "$SKIP_DB_CHECK" -eq 1 ]]; then
    log "Skipping DB connectivity check"
    return 0
  fi

  maybe_install_mysql_client || {
    err "Skip DB check with --skip-db-check if needed."
    exit 1
  }

  log "Checking DB connectivity to ${DB_HOST}:${DB_PORT}/${DB_NAME} ..."
  local mysql_ssl_args=()
  if [[ -n "${DB_SSL_CA:-}" ]]; then
    mysql_ssl_args+=("--ssl-mode=VERIFY_CA" "--ssl-ca=${DB_SSL_CA}")
  fi
  if [[ -n "${DB_SSL_CERT:-}" ]]; then
    mysql_ssl_args+=("--ssl-cert=${DB_SSL_CERT}")
  fi
  if [[ -n "${DB_SSL_KEY:-}" ]]; then
    mysql_ssl_args+=("--ssl-key=${DB_SSL_KEY}")
  fi

  mysql \
    "${mysql_ssl_args[@]}" \
    -h "$DB_HOST" \
    -P "$DB_PORT" \
    -u "$DB_USER" \
    -p"$DB_PASSWORD" \
    "$DB_NAME" \
    -e "SELECT 1;" >/dev/null
  log "DB connectivity check passed"
}

maybe_install_python_deps() {
  if [[ "$SKIP_PIP" -eq 1 ]]; then
    log "Skipping pip install"
    return 0
  fi

  log "Installing/upgrading Python dependencies..."
  "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
}

restart_services() {
  log "Running DB init (idempotent)..."
  "$APP_DIR/venv/bin/python" "$APP_DIR/scripts_init_db.py"

  log "Reloading systemd and restarting $SERVICE_NAME ..."
  systemctl daemon-reload
  systemctl restart "$SERVICE_NAME"
  systemctl is-active --quiet "$SERVICE_NAME" || {
    err "$SERVICE_NAME is not active"
    systemctl status "$SERVICE_NAME" --no-pager || true
    journalctl -u "$SERVICE_NAME" -n 120 --no-pager || true
    exit 1
  }

  log "Testing and restarting $NGINX_SERVICE ..."
  nginx -t
  systemctl restart "$NGINX_SERVICE"
  systemctl is-active --quiet "$NGINX_SERVICE" || {
    err "$NGINX_SERVICE is not active"
    systemctl status "$NGINX_SERVICE" --no-pager || true
    exit 1
  }
}

health_check() {
  local retry_count=20
  local retry_interval=2
  local i

  log "Checking local health endpoint: $LOCAL_HEALTH_URL"
  for i in $(seq 1 "$retry_count"); do
    if curl -fsS "$LOCAL_HEALTH_URL" | grep -q '"status":"ok"'; then
      log "Local health check passed"
      break
    fi
    if [[ "$i" -eq "$retry_count" ]]; then
      err "Local health check failed after ${retry_count} attempts: $LOCAL_HEALTH_URL"
      exit 1
    fi
    sleep "$retry_interval"
  done

  if [[ -n "$PUBLIC_HEALTH_URL" ]]; then
    log "Checking public health endpoint: $PUBLIC_HEALTH_URL"
    for i in $(seq 1 "$retry_count"); do
      if curl -fsS "$PUBLIC_HEALTH_URL" | grep -q '"status":"ok"'; then
        log "Public health check passed"
        break
      fi
      if [[ "$i" -eq "$retry_count" ]]; then
        err "Public health check failed after ${retry_count} attempts: $PUBLIC_HEALTH_URL"
        exit 1
      fi
      sleep "$retry_interval"
    done
  fi
}

main() {
  parse_args "$@"
  ensure_root
  require_cmd systemctl
  require_cmd nginx
  require_cmd curl

  validate_paths
  load_env
  db_check
  maybe_install_python_deps
  restart_services
  health_check

  log "Recovery and restart completed successfully."
}

main "$@"
