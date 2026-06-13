# Performance Checklist

## MaaS Latency Budget

| Operation | p50 Target | p99 Target | Timeout |
|-----------|:---:|:---:|:---:|
| Chat completion (short, <500 tokens) | < 1s | < 5s | 30s |
| Chat completion (medium, 500-2000 tokens) | < 2s | < 8s | 60s |
| Chat completion (long, >2000 tokens) | < 5s | < 15s | 120s |
| Streaming first token | < 500ms | < 2s | 10s |
| Proxy overhead (local) | < 50ms | < 100ms | 5s |

## Token Consumption Tracking

Track per-skill, per-operation token usage:

| Skill | Operation | Input Tokens | Output Tokens | Total |
|-------|-----------|:---:|:---:|:---:|
| Quality | Security gate per file | ~2k | ~4k | ~6k |
| Review+Security | Review per file | ~3k | ~2k | ~5k |
| Review+Security | Audit per file | ~4k | ~3k | ~7k |
| Spec-Plan-Build-Test | Spec phase | ~5k | ~3k | ~8k |
| Spec-Plan-Build-Test | Plan phase | ~8k | ~5k | ~13k |
| Spec-Plan-Build-Test | Build phase per file | ~15k | ~10k | ~25k |
| Spec-Plan-Build-Test | Test phase | ~10k | ~8k | ~18k |
| Legacy Migration | Analysis per file | ~10k | ~5k | ~15k |
| Legacy Migration | Transform per file | ~15k | ~10k | ~25k |

## Context Window Management

- Total context: 190,000 tokens (glm-5.1)
- Reserve for output: 32,768 tokens
- Available for input: ~157,000 tokens
- **Strategy**: If input exceeds 120k tokens, summarize older context rather than truncating
- **Never** exceed 180k input tokens (leave 10k buffer for system prompt)

## Rate Limit Compliance

- MaaS quota: 1 QPS (queries per second)
- Minimum interval between requests: 1200ms
- Maximum queue depth: 20 requests
- Retry strategy: exponential backoff with jitter
  - Base delay: 1500ms
  - Max retries: 3
  - Jitter: ±500ms
- On 429 response: queue request, retry after `Retry-After` header

## Streaming vs Non-Streaming Decision

| Scenario | Mode | Reason |
|----------|------|--------|
| Interactive chat | Streaming | User sees partial output immediately |
| Code generation | Streaming | Long outputs; early detection of hallucination |
| Batch processing | Non-streaming | Simpler error handling, full response for validation |
| Security audit | Non-streaming | Need complete response for finding classification |
| CI/CD gate | Non-streaming | Deterministic exit code based on full response |

## Evidence Requirements

Every performance measurement must include:
- Latency histogram (p50, p90, p99, max)
- Token count (input, output, total)
- Queue depth at time of request
- Retry count (if any)
- Timestamp
