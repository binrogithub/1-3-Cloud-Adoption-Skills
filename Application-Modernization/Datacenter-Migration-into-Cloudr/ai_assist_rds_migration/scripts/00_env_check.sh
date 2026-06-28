#!/bin/bash
# 00_env_check.sh - Environment variable and network connectivity check

set -euo pipefail

BASE_DIR="${MIGRATION_BASE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
REPORTS_DIR="${BASE_DIR}/reports"
LOGS_DIR="${BASE_DIR}/logs"
ENV_FILE="${BASE_DIR}/.env"

mkdir -p "${REPORTS_DIR}" "${LOGS_DIR}"

# Load .env file if exists (does not override existing env vars)
if [ -f "${ENV_FILE}" ]; then
    set -a
    while IFS='=' read -r key value; do
        key="$(echo "${key}" | xargs)"
        [[ -z "${key}" || "${key}" == \#* ]] && continue

        value="$(echo "${value}" | xargs)"
        value="${value#\"}"
        value="${value%\"}"
        value="${value#\'}"
        value="${value%\'}"

        if [ -z "${!key+x}" ]; then
            export "${key}=${value}"
        fi
    done < <(grep -E '^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}")
    set +a
fi

TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
LOG_FILE="${LOGS_DIR}/00_env_check_$(date +%Y%m%d_%H%M%S).log"
REPORT_FILE="${REPORTS_DIR}/env_check_report.json"

log() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [INFO] [00_env_check] $*" | tee -a "${LOG_FILE}"
}

log_error() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] [00_env_check] $*" | tee -a "${LOG_FILE}" >&2
}

REQUIRED_VARS=(
    HW_ACCESS_KEY
    HW_SECRET_KEY
    HW_PROJECT_ID
    HW_REGION
    SRC_DB_HOST
    SRC_DB_PORT
    SRC_DB_USER
    SRC_DB_PASSWORD
    TGT_DB_HOST
    TGT_DB_PORT
    TGT_DB_USER
    TGT_DB_PASSWORD
)

log "Checking required environment variables..."
MISSING_VARS=()
ENV_VAR_STATUS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        MISSING_VARS+=("$var")
        ENV_VAR_STATUS+=("\"$var\": \"MISSING\"")
        log_error "ENV_VAR_MISSING: $var"
    else
        ENV_VAR_STATUS+=("\"$var\": \"SET\"")
        log "Environment variable $var is set"
    fi
done

DRY_RUN="${DRY_RUN:-true}"
DRY_RUN="$(echo "${DRY_RUN}" | tr '[:upper:]' '[:lower:]')"
if [ "${DRY_RUN}" != "true" ] && [ "${DRY_RUN}" != "false" ]; then
    log_error "Invalid DRY_RUN value '${DRY_RUN}', fallback to true"
    DRY_RUN="true"
fi
ENV_VAR_STATUS+=("\"DRY_RUN\": \"SET\"")
log "DRY_RUN=${DRY_RUN}"

SKIP_DB_TCP_CHECK="${SKIP_DB_TCP_CHECK:-false}"
SKIP_DB_TCP_CHECK="$(echo "${SKIP_DB_TCP_CHECK}" | tr '[:upper:]' '[:lower:]')"
if [ "${SKIP_DB_TCP_CHECK}" != "true" ] && [ "${SKIP_DB_TCP_CHECK}" != "false" ]; then
    log_error "Invalid SKIP_DB_TCP_CHECK value '${SKIP_DB_TCP_CHECK}', fallback to false"
    SKIP_DB_TCP_CHECK="false"
fi
ENV_VAR_STATUS+=("\"SKIP_DB_TCP_CHECK\": \"SET\"")
log "SKIP_DB_TCP_CHECK=${SKIP_DB_TCP_CHECK}"

log "Checking network connectivity..."
SRC_REACHABLE="false"
SRC_PORT_OPEN="false"
TGT_REACHABLE="false"
TGT_PORT_OPEN="false"

if [ "${SKIP_DB_TCP_CHECK}" == "true" ]; then
    log "SKIP_DB_TCP_CHECK=true, skip direct TCP connectivity checks."
else
    if [ -n "${SRC_DB_HOST:-}" ] && [ -n "${SRC_DB_PORT:-}" ]; then
        log "Testing source database connectivity: ${SRC_DB_HOST}:${SRC_DB_PORT}"
        if timeout 5 bash -c "echo > /dev/tcp/${SRC_DB_HOST}/${SRC_DB_PORT}" 2>/dev/null; then
            SRC_REACHABLE="true"
            SRC_PORT_OPEN="true"
            log "Source database port is open: ${SRC_DB_HOST}:${SRC_DB_PORT}"
        else
            log_error "NETWORK_UNREACHABLE: Cannot connect to source database ${SRC_DB_HOST}:${SRC_DB_PORT}"
        fi
    else
        log_error "Cannot test source connectivity: SRC_DB_HOST or SRC_DB_PORT not set"
    fi

    if [ -n "${TGT_DB_HOST:-}" ] && [ -n "${TGT_DB_PORT:-}" ]; then
        log "Testing target database connectivity: ${TGT_DB_HOST}:${TGT_DB_PORT}"
        if timeout 5 bash -c "echo > /dev/tcp/${TGT_DB_HOST}/${TGT_DB_PORT}" 2>/dev/null; then
            TGT_REACHABLE="true"
            TGT_PORT_OPEN="true"
            log "Target database port is open: ${TGT_DB_HOST}:${TGT_DB_PORT}"
        else
            log_error "NETWORK_UNREACHABLE: Cannot connect to target database ${TGT_DB_HOST}:${TGT_DB_PORT}"
        fi
    else
        log_error "Cannot test target connectivity: TGT_DB_HOST or TGT_DB_PORT not set"
    fi
fi

ERRORS=()
WARNINGS=()

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    for var in "${MISSING_VARS[@]}"; do
        ERRORS+=("\"ENV_VAR_MISSING: $var\"")
    done
fi

if [ "${SKIP_DB_TCP_CHECK}" != "true" ]; then
    if [ "${SRC_REACHABLE}" != "true" ]; then
        ERRORS+=("\"NETWORK_UNREACHABLE: source database\"")
    fi

    if [ "${TGT_REACHABLE}" != "true" ]; then
        ERRORS+=("\"NETWORK_UNREACHABLE: target database\"")
    fi
fi

if [ ${#ERRORS[@]} -eq 0 ]; then
    OVERALL_STATUS="SUCCESS"
    log "Environment check PASSED"
else
    OVERALL_STATUS="FAILED"
    log_error "Environment check FAILED"
fi

ENV_VAR_JSON="$(IFS=,; echo "${ENV_VAR_STATUS[*]}")"
ERRORS_JSON="$(IFS=,; echo "${ERRORS[*]:-}")"
WARNINGS_JSON="$(IFS=,; echo "${WARNINGS[*]:-}")"

cat > "${REPORT_FILE}" <<ENDOFREPORT
{
  "report_name": "env_check",
  "timestamp": "${TIMESTAMP}",
  "dry_run": ${DRY_RUN},
  "stage": "env_check",
  "status": "${OVERALL_STATUS}",
  "details": {
    "env_vars": {
      ${ENV_VAR_JSON}
    },
    "network": {
      "source_reachable": ${SRC_REACHABLE},
      "target_reachable": ${TGT_REACHABLE},
      "source_port_open": ${SRC_PORT_OPEN},
      "target_port_open": ${TGT_PORT_OPEN}
    }
  },
  "errors": [${ERRORS_JSON}],
  "warnings": [${WARNINGS_JSON}]
}
ENDOFREPORT

log "Report saved to: ${REPORT_FILE}"

if [ "${OVERALL_STATUS}" != "SUCCESS" ]; then
    exit 1
fi

exit 0
