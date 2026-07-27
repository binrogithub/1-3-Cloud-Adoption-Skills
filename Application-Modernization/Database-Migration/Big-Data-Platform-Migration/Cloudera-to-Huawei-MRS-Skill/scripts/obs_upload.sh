#!/usr/bin/env bash
# OBS Upload Script
#
# Uploads Parquet data directories to Huawei Cloud OBS using obsutil.
# Must be run on an MRS Master node where obsutil is installed.
#
# Usage:
#   ./obs_upload.sh \
#     --bucket <bucket_name> \
#     --prefix <project_prefix> \
#     --local_dir /local/path/finance_dw \
#     --tables "dim_branch dim_product fact_transaction"

set -euo pipefail

BUCKET=""
PREFIX=""
LOCAL_DIR=""
TABLES=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket)    BUCKET="$2"; shift 2 ;;
    --prefix)    PREFIX="$2"; shift 2 ;;
    --local_dir) LOCAL_DIR="$2"; shift 2 ;;
    --tables)    TABLES="$2"; shift 2 ;;
    *)           echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [[ -z "${BUCKET}" || -z "${PREFIX}" || -z "${LOCAL_DIR}" || -z "${TABLES}" ]]; then
  echo "Usage: $0 --bucket <b> --prefix <p> --local_dir <d> --tables <t1 t2 ...>"
  exit 1
fi

for table in ${TABLES}; do
  echo "Uploading ${table}..."
  obsutil cp "${LOCAL_DIR}/${table}" "obs://${BUCKET}/${PREFIX}/finance_dw/${table}" \
    -flat -r -f -j=4 -p=4
  echo "  Done: ${table}"
done

echo "All tables uploaded to obs://${BUCKET}/${PREFIX}/finance_dw/"
