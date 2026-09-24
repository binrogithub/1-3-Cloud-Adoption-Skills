#!/usr/bin/env bash
set -Eeuo pipefail

: "${RUNDECK_BASE_URL:?Set RUNDECK_BASE_URL.}"
: "${RUNDECK_API_TOKEN:?Set RUNDECK_API_TOKEN.}"
: "${RUNDECK_PROJECT:?Set RUNDECK_PROJECT.}"
: "${RUNDECK_HOST_BASIC_CHECK_JOB_ID:?Set RUNDECK_HOST_BASIC_CHECK_JOB_ID.}"
: "${RUNDECK_ANSIBLE_ENSURE_SERVICE_JOB_ID:?Set RUNDECK_ANSIBLE_ENSURE_SERVICE_JOB_ID.}"
command -v curl >/dev/null || { echo 'missing curl' >&2; exit 1; }

base="${RUNDECK_BASE_URL%/}"
[[ "$base" =~ ^https?:// ]] || { echo 'RUNDECK_BASE_URL must be HTTP(S)' >&2; exit 2; }
health="$(curl --silent --show-error --fail --connect-timeout 5 --max-time 15 "$base/api/45/system/info" -H "X-Rundeck-Auth-Token: $RUNDECK_API_TOKEN")"
project="$(curl --silent --show-error --fail --connect-timeout 5 --max-time 15 "$base/api/45/project/$RUNDECK_PROJECT" -H "X-Rundeck-Auth-Token: $RUNDECK_API_TOKEN")"
basic_job="$(curl --silent --show-error --fail --connect-timeout 5 --max-time 15 "$base/api/45/job/$RUNDECK_HOST_BASIC_CHECK_JOB_ID" -H "X-Rundeck-Auth-Token: $RUNDECK_API_TOKEN")"
ensure_job="$(curl --silent --show-error --fail --connect-timeout 5 --max-time 15 "$base/api/45/job/$RUNDECK_ANSIBLE_ENSURE_SERVICE_JOB_ID" -H "X-Rundeck-Auth-Token: $RUNDECK_API_TOKEN")"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 - "$health" "$project" "$basic_job" "$ensure_job" "$script_dir" <<'PY'
import json, os, sys
from pathlib import Path

for value in sys.argv[1:5]:
    json.loads(value)

sys.path.insert(0, sys.argv[5])
from autoops_datasource_health import probe

known = {"loki", "prometheus", "opensearch"}
def sources(name):
    values = [item.strip().lower() for item in os.environ.get(name, "").split(",") if item.strip()]
    unknown = sorted(set(values) - known)
    if unknown:
        raise SystemExit("unknown datasource in %s: %s" % (name, ",".join(unknown)))
    return list(dict.fromkeys(values))

required = sources("AUTOOPS_PREFLIGHT_REQUIRED_SOURCES")
optional = [item for item in sources("AUTOOPS_PREFLIGHT_OPTIONAL_SOURCES") if item not in required]
checks = {}
for source in required + optional:
    result = probe(source)
    prefix = source.upper()
    checks[source] = {
        "configured": result.get("configured"),
        "deployed": result.get("reachable") is True,
        "identity_valid": result.get("identity_valid"),
        "data_available": result.get("data_available", "UNKNOWN") or "UNKNOWN",
        "status": result.get("status"),
        "error_code": result.get("error_code"),
        "downloaded": (os.environ.get("AUTOOPS_%s_DOWNLOADED" % prefix) or "UNKNOWN"),
    }
failed_required = [source for source in required if checks[source]["status"] != "READY"]
failed_optional = [source for source in optional if checks[source]["status"] != "READY"]
payload = {
    "status": "BLOCKED" if failed_required else ("DEGRADED" if failed_optional else "READY"),
    "message": "E01/E02 real execution preflight ready: Rundeck health, project, host-basic-check Job, and Ansible service Job verified",
    "rundown": "downloaded -> deployed -> configured -> data_available",
    "rundeck": "READY",
    "required_sources": required,
    "optional_sources": optional,
    "datasources": checks,
    "failed_required": failed_required,
    "failed_optional": failed_optional,
}
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
if failed_required:
    raise SystemExit(3)
PY
