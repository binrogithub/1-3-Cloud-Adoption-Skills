#!/usr/bin/env bash
set -euo pipefail

SQLSERVER_CONTAINER="${SQLSERVER_CONTAINER:-sqlserver-demo}"
BABELFISH_CONTAINER="${BABELFISH_CONTAINER:-babelfish-demo}"

env -u LD_LIBRARY_PATH docker rm -f "$SQLSERVER_CONTAINER" "$BABELFISH_CONTAINER" >/dev/null 2>&1 || true
echo "Stopped demo containers."
