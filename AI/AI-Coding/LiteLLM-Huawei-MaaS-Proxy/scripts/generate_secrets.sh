#!/usr/bin/env bash
# generate_secrets.sh — Generate all required secrets for .env
# Usage: ./scripts/generate_secrets.sh

set -euo pipefail

printf "══════════════════════════════════════════════════════\n"
printf "  LiteLLM Huawei MaaS Proxy — Secret Generator\n"
printf "══════════════════════════════════════════════════════\n\n"

printf "⚠️  WARNING: Never commit these values to version control.\n"
printf "    Add them to .env (gitignored) with chmod 600 .env\n\n"

MASTER_KEY="sk-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
SALT_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
GRAFANA_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

printf "Copy these into your .env file:\n\n"
printf "  LITELLM_MASTER_KEY=\"%s\"\n" "$MASTER_KEY"
printf "  LITELLM_SALT_KEY=\"%s\"\n" "$SALT_KEY"
printf "  DB_PASSWORD=\"%s\"\n" "$DB_PASSWORD"
printf "  GRAFANA_PASSWORD=\"%s\"\n" "$GRAFANA_PASSWORD"

printf "\nThen run:\n"
printf "  chmod 600 .env\n"
