# Upstream compatibility matrix

Measured behavior of the OpenAI-compatible endpoints this adapter is
deployed against. One adapter instance serves exactly ONE upstream and ONE
model (architecture invariant: single-model single-upstream per instance —
the constraint is on cardinality per instance, not on which model/upstream).

| Upstream | Endpoint | Format | Measured behavior |
| --- | --- | --- | --- |
| Huawei MaaS | `https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions` | OpenAI | Baseline. No rate limiting observed in normal agent use. |
| Zhipu BigModel | `https://open.bigmodel.cn/api/paas/v4/chat/completions` | OpenAI | **Tight rate limiting**: consecutive requests hit `429` quickly (~80s to recover). Emits `reasoning_content`; tool calls well-formed. |

## Known limitations

- **Zhipu 429 under agent load**: Claude Code issues rapid consecutive
  requests; on Zhipu this trips the account rate limit routinely. This is an
  account-tier property, not a code defect. Mitigations:
  - The adapter passes upstream `429` through to the client as-is (PRD
    UPSTREAM_PROFILE_V1 D5), so Claude Code can back off rather than treat
    it as an outage.
  - For headless tasks, the auto-continue supervisor (PRD
    RUNTIME_RESILIENCE_V1 WP-B) waits 100s before resuming on
    stream-protocol errors; note 429 is NOT yet a supervised trigger until
    marker stability is confirmed in the field.
- **`claude-glm` (local profile)**: on the Zhipu upstream, expect 429s
  during high-frequency agent tasks. Prefer the MaaS-backed profile for
  batch/fan-out workloads.

## Adding / switching an upstream

The runtime is env-driven — switching `:3000` between upstreams is a
three-variable change in `/etc/claude-code-proxy/maas.env` (`CLAUDE_CODE_PROXY_API_KEY`,
`ANTHROPIC_PROXY_BASE_URL`, `COMPLETION_MODEL`) plus a service restart. No
code changes. For a second concurrent upstream, install a separate profile:

```bash
printf '%s\n' "$KEY" | sudo bash scripts/bootstrap.sh \
    --maas-url https://open.bigmodel.cn/api/paas/v4/chat/completions \
    --model glm-5.3 --port 3100 --profile claude-glm
```

Each profile gets its own env file, adapter dir, systemd unit (identical
hardening), client config dir, and an independent client key (cross-profile
requests are rejected 401). `scripts/window-check-v12.sh` (N1-G) verifies
every such listener stays build-matched, authenticated, and hardened.
