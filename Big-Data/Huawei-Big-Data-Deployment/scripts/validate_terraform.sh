#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-.}"

cd "$ROOT_DIR"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform command not found"
  exit 1
fi

terraform fmt -recursive -check
terraform init -backend=false
terraform validate

echo "Terraform validation completed successfully."
