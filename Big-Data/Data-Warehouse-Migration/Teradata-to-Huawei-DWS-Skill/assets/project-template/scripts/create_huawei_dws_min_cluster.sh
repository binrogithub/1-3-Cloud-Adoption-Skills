#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export CLOUD_SDK_AK="${CLOUD_SDK_AK:-${AK:-}}"
export CLOUD_SDK_SK="${CLOUD_SDK_SK:-${SK:-}}"

python3 "${SCRIPT_DIR}/create_huawei_dws_min_cluster.py" "$@"

