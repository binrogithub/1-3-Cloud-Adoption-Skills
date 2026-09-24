#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: local-journal-query.sh [--service NAME | --scope host_system]
  [--since-minutes 1..1440] [--limit 1..200]

Reads the local systemd journal for the allowlisted service unit. This is a
read-only fallback for hosts whose journal is not yet shipped to Loki.
EOF
}

service=""
scope="application"
since_minutes=15
limit=100
until=""
since_at=""
python_executable="${AUTOOPS_PYTHON_EXECUTABLE:-python3}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --service) service="${2:-}"; shift 2 ;;
    --scope) scope="${2:-}"; shift 2 ;;
    --since-minutes) since_minutes="${2:-}"; shift 2 ;;
    --limit) limit="${2:-}"; shift 2 ;;
    --until) until="${2:-}"; shift 2 ;;
    --since-at) since_at="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ "$scope" == "application" || "$scope" == "host_system" ]] || {
  printf 'scope must be application or host_system\n' >&2; exit 2;
}
if [[ "$scope" == "application" ]]; then
  [[ "$service" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$ ]] || {
    printf 'invalid service name; use 1-63 letters, digits, dot, underscore, or hyphen\n' >&2; exit 2;
  }
elif [[ -n "$service" ]]; then
  printf 'host_system scope cannot include a service selector\n' >&2; exit 2
fi
max_window_minutes="${AUTOOPS_OBSERVABILITY_MAX_WINDOW_MINUTES:-1440}"
[[ "$max_window_minutes" =~ ^[0-9]+$ ]] && (( max_window_minutes >= 1 && max_window_minutes <= 10080 )) || {
  printf 'AUTOOPS_OBSERVABILITY_MAX_WINDOW_MINUTES must be an integer from 1 through 10080\n' >&2; exit 2;
}
[[ "$since_minutes" =~ ^[0-9]+$ ]] && (( since_minutes >= 1 && since_minutes <= max_window_minutes )) || {
  printf 'since-minutes must be an integer from 1 through %s\n' "$max_window_minutes" >&2; exit 2;
}
[[ "$limit" =~ ^[0-9]+$ ]] && (( limit >= 1 && limit <= 200 )) || {
  printf 'limit must be an integer from 1 through 200\n' >&2; exit 2;
}
if [[ -n "$until" || -n "$since_at" ]]; then
  [[ -n "$until" && -n "$since_at" ]] || {
    printf 'since-at and until must be provided together\n' >&2; exit 2;
  }
  [[ "$until" =~ ^[0-9TtZz:+._-]+$ && "$since_at" =~ ^[0-9TtZz:+._-]+$ ]] || {
    printf 'since-at and until must be ISO-8601 timestamps\n' >&2; exit 2;
  }
fi
command -v journalctl >/dev/null 2>&1 || {
  printf 'missing required command: journalctl\n' >&2; exit 1;
}
if [[ "$python_executable" == */* ]]; then
  [[ -x "$python_executable" ]] || {
    printf 'missing executable: %s\n' "$python_executable" >&2; exit 1;
  }
else
  command -v "$python_executable" >/dev/null 2>&1 || {
    printf 'missing required command: %s\n' "$python_executable" >&2; exit 1;
  }
fi

raw_file="$(mktemp)"
error_file="$(mktemp)"
trap 'rm -f -- "$raw_file" "$error_file"' EXIT
# journalctl accepts a space separated UTC timestamp here, while the public
# adapter contract uses ISO-8601 values with a T and Z. Convert only at the
# command boundary and keep the contract values unchanged in the response.
journal_since="${since_at}"
journal_until="${until}"
if [[ -n "$since_at" ]]; then
  IFS=$'\t' read -r journal_since journal_until < <("$python_executable" - "$since_at" "$until" <<'PY'
from datetime import datetime, timezone
import sys

values = [datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
          for value in sys.argv[1:]]
print('\t'.join(value.strftime('%Y-%m-%d %H:%M:%S UTC') for value in values))
PY
  )
fi
# The unit and all options are separate argv entries. User input never becomes
# a shell expression or a journalctl filter.
if [[ "$scope" == "application" ]]; then
  unit="${service%.service}.service"
  journal_args=(--quiet --unit "$unit" --since "${since_minutes} minutes ago" --no-pager
    --output short-iso --reverse -n "$limit")
else
  journal_args=(--quiet --since "${since_minutes} minutes ago" --no-pager
    --output short-iso --reverse -n "$limit")
fi
if [[ -n "$since_at" ]]; then
  if [[ "$scope" == "application" ]]; then
    journal_args=(--quiet --unit "$unit" --since "$journal_since" --until "$journal_until" --no-pager
      --output short-iso --reverse -n "$limit")
  else
    journal_args=(--quiet --since "$journal_since" --until "$journal_until" --no-pager
      --output short-iso --reverse -n "$limit")
  fi
fi
set +e
journalctl "${journal_args[@]}" >"$raw_file" 2>"$error_file"
journal_status=$?
set -e
if (( journal_status != 0 )); then
  # A permission or journal backend failure is unavailable evidence. Return a
  # machine-readable error instead of allowing an empty stdout to look clean.
  "$python_executable" - "$service" "$scope" "$since_minutes" "$limit" "$since_at" "$until" <<'PY'
import json
import sys
from datetime import datetime, timezone

service, scope, since_minutes, limit, since_at, until_at = sys.argv[1:]
now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
print(json.dumps({
    'source': 'local-journal',
    'status': 'unavailable',
    'error_code': 'JOURNAL_QUERY_FAILED',
    'service': service or None,
    'scope': scope,
    'since_minutes': int(since_minutes),
    'limit': int(limit),
    'requested_window': {'since_minutes': int(since_minutes),
                         'start_iso': since_at or None, 'end_iso': until_at or None},
    'source_health': 'failed',
    'source_status': 'failed',
    'coverage_status': 'unavailable',
    'observed_at': now,
    'entries': [],
}, ensure_ascii=False))
PY
  exit "$journal_status"
fi

JOURNAL_FILE="$raw_file" SERVICE="$service" SCOPE="$scope" SINCE_MINUTES="$since_minutes" LIMIT="$limit" SINCE_AT="$since_at" UNTIL_AT="$until" "$python_executable" - <<'PY'
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

credential = re.compile(r'(?i)\b(authorization|x-api-key|api[_-]?key|token|password|passwd|secret)\b\s*([:=])\s*(?:bearer\s+)?([^\s,;"\']+)')

def redact(line):
    return credential.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", line)

def parse_timestamp(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        return None

with open(os.environ['JOURNAL_FILE'], encoding='utf-8', errors='replace') as stream:
    lines = [line.rstrip('\n') for line in stream if line.strip()]
timestamp_pattern = re.compile(r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T[^ ]+)')
entries = []
for line in lines:
    entry = {'line': redact(line)}
    match = timestamp_pattern.match(line)
    if match:
        entry['timestamp'] = match.group('timestamp')
    entries.append(entry)
service = os.environ['SERVICE'] or None
scope = os.environ['SCOPE']
query = f'journalctl --unit {service}.service' if service else 'journalctl --system'
if os.environ['SINCE_AT']:
    effective_start = os.environ['SINCE_AT']
    effective_end = os.environ['UNTIL_AT']
else:
    effective_end = datetime.now(timezone.utc)
    effective_start = effective_end - timedelta(minutes=int(os.environ['SINCE_MINUTES']))
    effective_start = effective_start.isoformat().replace('+00:00', 'Z')
    effective_end = effective_end.isoformat().replace('+00:00', 'Z')
observed_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
limit = int(os.environ['LIMIT'])
timestamps = [parse_timestamp(entry['timestamp']) for entry in entries if entry.get('timestamp')]
timestamps = [value for value in timestamps if value is not None]
query_ref = 'journal-' + hashlib.sha256(query.encode()).hexdigest()[:16]
truncated = len(entries) >= limit
result = {
    'source': 'local-journal',
    'status': 'empty' if not entries else 'ok',
    'query_ref': query_ref,
    'evidence_ref': query_ref,
    'service': service,
    'scope': scope,
    'since_minutes': int(os.environ['SINCE_MINUTES']),
    'limit': int(os.environ['LIMIT']),
    'requested_window': {'since_minutes': int(os.environ['SINCE_MINUTES'])},
    'effective_window': {
        'since_minutes': int(os.environ['SINCE_MINUTES']),
        'start_iso': effective_start,
        'end_iso': effective_end,
    },
    'entry_count': len(entries),
    # A successful empty query is not evidence that the application is healthy.
    'coverage_status': 'source_queried' if not entries else ('partial' if truncated else 'observed'),
    'source_health': 'ready',
    'source_status': 'ready',
    'observed_at': observed_at,
    'freshness_seconds': None,
    'freshness': {
        'oldest_observed': min(timestamps).isoformat().replace('+00:00', 'Z') if timestamps else None,
        'newest_observed': max(timestamps).isoformat().replace('+00:00', 'Z') if timestamps else None,
        'lag_seconds': None,
    },
    'covered_window': {'start_iso': effective_start, 'end_iso': effective_end},
    'truncated': truncated,
    'pagination_complete': not truncated,
    'truncation': {
        'status': 'possible' if truncated else 'complete',
        'limit': limit,
    },
    'entries': entries,
}
print(json.dumps(result, ensure_ascii=False))
PY
