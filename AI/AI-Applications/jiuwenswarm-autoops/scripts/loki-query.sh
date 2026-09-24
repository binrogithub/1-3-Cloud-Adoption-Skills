#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: loki-query.sh --service NAME [--since-minutes 1..1440] [--limit 1..200]

Reads LOKI_BASE_URL and optional LOKI_TENANT_ID / LOKI_BEARER_TOKEN from the
process environment. It constructs a fixed, read-only Loki query_range request.
EOF
}

service=""
since_minutes=15
limit=100
start_ns=""
end_ns=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --service) service="${2:-}"; shift 2 ;;
    --since-minutes) since_minutes="${2:-}"; shift 2 ;;
    --limit) limit="${2:-}"; shift 2 ;;
    --start-ns) start_ns="${2:-}"; shift 2 ;;
    --end-ns) end_ns="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

: "${LOKI_BASE_URL:?Set LOKI_BASE_URL in the process environment.}"
service_label="${LOKI_SERVICE_LABEL:-service}"
timeout_seconds="${LOKI_TIMEOUT_SECONDS:-15}"
python_executable="${AUTOOPS_PYTHON_EXECUTABLE:-python3}"

[[ "$service" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$ ]] || {
  printf 'invalid service name; use 1-63 letters, digits, dot, underscore, or hyphen\n' >&2; exit 2;
}
[[ "$service_label" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
  printf 'invalid LOKI_SERVICE_LABEL\n' >&2; exit 2;
}
max_window_minutes="${AUTOOPS_OBSERVABILITY_MAX_WINDOW_MINUTES:-1440}"
[[ "$max_window_minutes" =~ ^[0-9]+$ ]] && (( max_window_minutes >= 1 && max_window_minutes <= 10080 )) || {
  printf 'AUTOOPS_OBSERVABILITY_MAX_WINDOW_MINUTES must be an integer from 1 through 10080\n' >&2; exit 2;
}
[[ "$since_minutes" =~ ^[0-9]+$ ]] && (( since_minutes >= 1 && since_minutes <= max_window_minutes )) || {
  printf 'since-minutes must be an integer from 1 through %s\n' "$max_window_minutes" >&2; exit 2;
}
if [[ -n "$start_ns" || -n "$end_ns" ]]; then
  [[ "$start_ns" =~ ^[0-9]+$ && "$end_ns" =~ ^[0-9]+$ && "$end_ns" -gt "$start_ns" ]] || {
    printf 'start-ns and end-ns must be increasing integer nanosecond timestamps\n' >&2; exit 2;
  }
  requested_start_ns="$start_ns"
  requested_end_ns="$end_ns"
  effective_since_minutes="$(( (requested_end_ns - requested_start_ns) / 60000000000 ))"
else
  read -r requested_start_ns requested_end_ns < <("$python_executable" - "$since_minutes" <<'PY'
import sys
import time

end = time.time_ns()
start = end - int(sys.argv[1]) * 60 * 1_000_000_000
print(start, end)
PY
  )
  effective_since_minutes="$since_minutes"
fi
[[ "$limit" =~ ^[0-9]+$ ]] && (( limit >= 1 && limit <= 200 )) || {
  printf 'limit must be an integer from 1 through 200\n' >&2; exit 2;
}
[[ "$timeout_seconds" =~ ^[0-9]+$ ]] && (( timeout_seconds >= 1 && timeout_seconds <= 60 )) || {
  printf 'LOKI_TIMEOUT_SECONDS must be an integer from 1 through 60\n' >&2; exit 2;
}
[[ "$LOKI_BASE_URL" =~ ^https?://[^[:space:]]+$ ]] || {
  printf 'LOKI_BASE_URL must be an HTTP(S) URL\n' >&2; exit 2;
}

for command_name in curl; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'missing required command: %s\n' "$command_name" >&2; exit 1;
  }
done
if [[ "$python_executable" == */* ]]; then
  [[ -x "$python_executable" ]] || {
    printf 'missing executable: %s\n' "$python_executable" >&2; exit 1;
  }
else
  command -v "$python_executable" >/dev/null 2>&1 || {
    printf 'missing required command: %s\n' "$python_executable" >&2; exit 1;
  }
fi

work_dir="$(mktemp -d)"
trap 'rm -rf -- "$work_dir"' EXIT
response_file="$work_dir/loki-response.json"
query="{${service_label}=\"${service}\"} |~ \"(?i)(error|exception|fatal|panic|failed)\""
curl_args=(
  --silent --show-error --fail
  --connect-timeout 5 --max-time "$timeout_seconds"
  --get --output "$response_file"
  --data-urlencode "query=$query"
  --data-urlencode "start=$requested_start_ns"
  --data-urlencode "end=$requested_end_ns"
  --data-urlencode "limit=$limit"
  "${LOKI_BASE_URL%/}/loki/api/v1/query_range"
)
if [[ -n "${LOKI_TENANT_ID:-}" ]]; then
  curl_args=(--header "X-Scope-OrgID: ${LOKI_TENANT_ID}" "${curl_args[@]}")
fi
if [[ -n "${LOKI_BEARER_TOKEN:-}" ]]; then
  curl_args=(--header "Authorization: Bearer ${LOKI_BEARER_TOKEN}" "${curl_args[@]}")
fi
curl "${curl_args[@]}"

LOKI_RESPONSE_FILE="$response_file" LOKI_QUERY="$query" LOKI_START_NS="$requested_start_ns" LOKI_END_NS="$requested_end_ns" LOKI_SERVICE="$service" LOKI_SINCE_MINUTES="$effective_since_minutes" LOKI_LIMIT="$limit" "$python_executable" - <<'PY'
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

credential = re.compile(r'(?i)\b(authorization|x-api-key|api[_-]?key|token|password|passwd|secret)\b\s*([:=])\s*(?:bearer\s+)?([^\s,;"\']+)')

def redact(line):
    return credential.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", line)

def iso_from_ns(value):
    return datetime.fromtimestamp(value / 1_000_000_000, timezone.utc).isoformat().replace('+00:00', 'Z')

with open(os.environ['LOKI_RESPONSE_FILE'], encoding='utf-8') as stream:
    payload = json.load(stream)
if payload.get('status') != 'success':
    raise SystemExit('Loki returned an unsuccessful response')
data = payload.get('data')
if not isinstance(data, dict) or data.get('resultType') != 'streams' or not isinstance(data.get('result'), list):
    raise SystemExit('Loki returned an unexpected query_range response')

entries = []
for item in data['result']:
    for value in item.get('values', []):
        if isinstance(value, list) and len(value) >= 2:
            entries.append({'timestamp_ns': str(value[0]), 'line': redact(str(value[1]))})
query = os.environ['LOKI_QUERY']
observed_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
latest_timestamp_ns = max((int(entry['timestamp_ns']) for entry in entries), default=None)
oldest_timestamp_ns = min((int(entry['timestamp_ns']) for entry in entries), default=None)
freshness_seconds = None if latest_timestamp_ns is None else max(0, time.time_ns() - latest_timestamp_ns) / 1_000_000_000
limit = int(os.environ['LOKI_LIMIT'])
query_start_ns = os.environ['LOKI_START_NS']
query_end_ns = os.environ['LOKI_END_NS']
truncated = len(entries) >= limit
query_ref = 'loki-' + hashlib.sha256(query.encode()).hexdigest()[:16]
result = {
    'source': 'loki',
    'status': 'empty' if not entries else 'ok',
    'query_ref': query_ref,
    'evidence_ref': query_ref,
    'start_ns': query_start_ns,
    'end_ns': query_end_ns,
    'entry_count': len(entries),
    # A successful empty filtered stream does not prove application health.
    'coverage_status': 'source_queried' if not entries else ('partial' if truncated else 'observed'),
    'source_health': 'ready',
    'source_status': 'ready',
    'observed_at': observed_at,
    'freshness_seconds': freshness_seconds,
    'freshness': {
        'oldest_observed': None if oldest_timestamp_ns is None else iso_from_ns(oldest_timestamp_ns),
        'newest_observed': None if latest_timestamp_ns is None else iso_from_ns(latest_timestamp_ns),
        'lag_seconds': freshness_seconds,
    },
    'covered_window': {'start_ns': query_start_ns, 'end_ns': query_end_ns},
    'truncated': truncated,
    'pagination_complete': not truncated,
    'truncation': {
        'status': 'possible' if truncated else 'complete',
        'limit': limit,
    },
    'service': os.environ['LOKI_SERVICE'],
    'since_minutes': int(os.environ['LOKI_SINCE_MINUTES']),
    'limit': int(os.environ['LOKI_LIMIT']),
    'requested_window': {'since_minutes': int(os.environ['LOKI_SINCE_MINUTES'])},
    'effective_window': {'start_ns': query_start_ns, 'end_ns': query_end_ns},
    'entries': entries,
}
print(json.dumps(result, ensure_ascii=False))
PY
