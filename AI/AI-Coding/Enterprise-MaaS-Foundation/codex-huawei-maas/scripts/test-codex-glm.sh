#!/usr/bin/env bash
set -euo pipefail

if [[ -f "$HOME/.config/codex-glm/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.config/codex-glm/env"
fi

base="${CCR_BASE_URL:-http://127.0.0.1:3457}"
key="${CLAUDE_GLM_ROUTER_KEY:-${CODEX_GLM_ROUTER_KEY:-codex-glm-local}}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

command -v codex >/dev/null 2>&1 || fail "codex is not installed"
command -v codex-glm >/dev/null 2>&1 || fail "codex-glm is not in PATH"
command -v ccr >/dev/null 2>&1 || fail "ccr is not installed"

node "$script_dir/tests/test-shim-transform.js" >/dev/null || fail "shim transform tests failed"
"$script_dir/tests/test-configure-generation.sh" >/dev/null || fail "configure generation tests failed"
codex-glm --version >/dev/null || fail "codex-glm --version failed"
codex --profile glm --strict-config --help >/dev/null || fail "Codex glm profile failed strict config parse"

curl -fsS -m 3 -H "Authorization: Bearer $key" "$base/" >/dev/null || fail "CCR root health failed"

status_code="$(curl -sS -m 5 -o /tmp/codex-glm-responses-health.out -w '%{http_code}' \
  -H "Authorization: Bearer $key" \
  "$base/v1/responses" || true)"

case "$status_code" in
  200) ;;
  401) fail "CCR /v1/responses rejected local auth" ;;
  404) fail "CCR /v1/responses route is missing" ;;
  *) sed -n '1,80p' /tmp/codex-glm-responses-health.out >&2; fail "CCR /v1/responses returned HTTP $status_code" ;;
esac

echo "Basic codex-glm checks passed."
echo "Optional live smoke test:"
echo "  codex-glm exec --skip-git-repo-check --ephemeral 'Reply with OK only'"
