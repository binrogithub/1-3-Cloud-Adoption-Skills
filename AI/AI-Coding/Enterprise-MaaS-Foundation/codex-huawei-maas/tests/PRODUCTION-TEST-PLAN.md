# Production Test Plan

## Preconditions

- `codex`, `node`, `npm`, `curl`, and `ccr` are available.
- A valid Huawei MaaS API key is exported as `API_KEY`, `MAAS_API_KEY`, or `HUAWEI_MAAS_API_KEY`.
- `~/.local/bin` is on `PATH`.

## Install

```bash
export API_KEY='replace-with-real-key'
./scripts/configure-codex-glm.sh
```

## Checks

```bash
codex --version
codex-glm --version
codex --profile glm --strict-config --help
HOME="${CODEX_GLM_CCR_HOME:-$HOME/.codex-glm/ccr-home}" ccr status
curl -fsS -H "Authorization: Bearer ${CODEX_GLM_ROUTER_KEY:-codex-glm-local}" http://127.0.0.1:3457/
./scripts/test-codex-glm.sh
```

Expected result: syntax checks, shim transform fixtures, Codex profile parsing, and CCR health checks pass.

## End-To-End

```bash
codex-glm exec --skip-git-repo-check --ephemeral "Reply with OK only"
```

Expected result: the final answer is `OK` or a short response containing only `OK`.

## Trace Fixture Capture

```bash
CODEX_GLM_TRACE=1 CODEX_GLM_TRACE_DIR=/tmp/codex-glm-traces \
  codex-glm exec --skip-git-repo-check --ephemeral "Reply with OK only"
ls -la /tmp/codex-glm-traces
```

Expected result: redacted `responses-request` and `anthropic-upstream-request` JSON files are written.

## Rollback

```bash
RESTORE_CCR=1 ./scripts/configure-codex-glm.sh
HOME="${CODEX_GLM_CCR_HOME:-$HOME/.codex-glm/ccr-home}" ccr restart
curl -i http://127.0.0.1:3457/v1/responses
```

Expected result after rollback: `/v1/responses` returns CCR route missing.
