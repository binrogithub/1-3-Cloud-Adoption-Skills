# MaaS Token Patterns

## Token Budget Per Skill

Estimated input/output tokens for typical operations against Huawei Cloud MaaS (glm-5.1).

### Quality Skill
- Local gates (lint, test, coverage): 0 MaaS tokens
- Security gate (MaaS-backed audit): ~2k input + ~4k output per file
- Full gate run (10 files, security via MaaS): ~60k total

### Code Review + Security Skill
- Code review: ~3k input + ~2k output per file
- Security audit: ~4k input + ~3k output per file
- Secret detection: local (0 MaaS tokens)
- Dependency audit: ~1k input + ~1k output per dependency
- Full review + audit (10 files): ~80k total

### Spec-Plan-Build-Test Skill
- Spec phase: ~5k input + ~3k output per feature
- Plan phase: ~8k input + ~5k output per feature
- Build phase: ~15k input + ~10k output per file changed
- Test phase: ~10k input + ~8k output per test suite
- Full workflow (5 files): ~180k total

### Legacy Migration Skill
- Analysis phase: ~10k input + ~5k output per file
- Characterization test generation: ~5k input + ~3k output per test
- Migration planning: ~8k input + ~5k output per plan
- Batch transformation: ~15k input + ~10k output per file
- Behavior verification: local (0 MaaS tokens)
- One batch (10 files): ~300k total

## Context Window Strategy

```
Total context:  190,000 tokens (glm-5.1)
Output reserve:  32,768 tokens (max_output_tokens)
Input budget:   ~157,000 tokens
Safety buffer:   10,000 tokens (system prompt, overhead)
Effective input: ~147,000 tokens
```

### When Input Exceeds Budget

1. **Summarize** older conversation context (preserve recent + relevant)
2. **Chunk** large files (send relevant sections, not entire files)
3. **Reference** supporting documents by path (agent reads on demand)
4. **Never truncate** mid-expression or mid-function

## Rate Limit Handling

```
MaaS quota:       1 QPS
Min interval:     1200ms between requests
Max queue depth:  20 requests
Retry strategy:   exponential backoff + jitter
  Base delay:     1500ms
  Max retries:    3
  Jitter:         ±500ms
```

### Implementation Pattern

```bash
REQUEST_MIN_INTERVAL_MS=1200
MAX_QUEUE_DEPTH=20
MAX_RETRIES=3
RETRY_BASE_DELAY_MS=1500

last_request_time=0

send_request() {
  local now=$(date +%s%3N)
  local elapsed=$((now - last_request_time))
  if [ "$elapsed" -lt "$REQUEST_MIN_INTERVAL_MS" ]; then
    sleep $(( (REQUEST_MIN_INTERVAL_MS - elapsed) / 1000.0 ))
  fi
  # ... send request ...
  last_request_time=$(date +%s%3N)
}
```

## Cost Estimation Formula

```
cost_per_1k_input  = price_per_1k_input_tokens  (check MaaS pricing page)
cost_per_1k_output = price_per_1k_output_tokens (check MaaS pricing page)

total_cost = (input_tokens / 1000 * cost_per_1k_input) + (output_tokens / 1000 * cost_per_1k_output)
```

## Token Counting

- Use tiktoken-compatible tokenizer for GLM models
- Approximate: 1 token ≈ 4 characters for English, ≈ 2 characters for Chinese
- Count before sending: reject requests exceeding context budget
- Log token counts per request for cost tracking

## Streaming Token Accounting

- Streaming responses: count tokens from SSE chunks (`usage` field in final chunk)
- Non-streaming: count from `usage` field in response
- Always log: `prompt_tokens`, `completion_tokens`, `total_tokens`
