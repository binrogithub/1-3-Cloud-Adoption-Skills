# Adapter Checklist

Use this checklist when implementing or reviewing a Claude Code to Huawei Cloud MaaS adapter.

## Required Interfaces

- Accept Anthropic-compatible `POST /v1/messages`.
- Forward to OpenAI-compatible `POST /chat/completions`.
- Support both streaming and non-streaming responses.
- Convert Anthropic `tools[].input_schema` to OpenAI `tools[].function.parameters`.
- Convert OpenAI `tool_calls` back to Anthropic `tool_use`.
- Convert tool results back into OpenAI `tool` messages.

## Streaming Tool Calls

OpenAI streaming sends `tool_calls[].function.arguments` as fragments. The adapter must accumulate them by `tool_calls[].index`.

Do not treat each fragment as a complete JSON string.

Healthy behavior:

```text
fragment 1: {
fragment 2: "file_path":
fragment 3: "/tmp/input.txt"
fragment 4: }
```

Final assembled input:

```json
{"file_path":"/tmp/input.txt"}
```

## GLM-5.1 Path Guard

If the model calls file tools with fake home paths:

```text
/home/user/...
/Users/claudedev/...
/Users/zhujinhao/...
```

and `Bash` is available, rewrite the tool call to:

```json
{
  "name": "Bash",
  "input": {
    "command": "pwd && ls",
    "description": "Check current directory and list files"
  }
}
```

Do not rewrite paths that are real project paths, `/tmp/...`, or user-provided absolute paths.

## Rate Limit Handling

Huawei Cloud MaaS deployments may be limited to approximately one request per second.

Recommended defaults:

```bash
REQUEST_MIN_INTERVAL_MS=1200
UPSTREAM_MAX_RETRIES=3
UPSTREAM_RETRY_BASE_DELAY_MS=1500
MAX_QUEUE_DEPTH=20
```

Retry only transient failures:

- `429`
- `5xx`
- network timeout

Do not retry permanent auth errors such as `401` or `403`.

## Logs And Metrics

Access logs should record metadata only:

- timestamp
- model
- stream mode
- tool counts
- upstream status
- latency
- error category

Do not log:

- prompts
- message content
- tool outputs
- Authorization headers
- API keys

Suggested metrics:

```json
{
  "requests_total": 0,
  "requests_stream_total": 0,
  "upstream_requests_total": 0,
  "upstream_retries_total": 0,
  "upstream_429_total": 0,
  "queue_rejected_total": 0,
  "completed_total": 0,
  "failed_total": 0,
  "queue_depth": 0,
  "avg_latency_ms": 0
}
```

## End-To-End Tests

Minimum tests:

1. No-tool Claude Code CLI request.
2. No-tool Agent SDK `query()`.
3. Agent SDK `Read` request.
4. Agent SDK `Bash` request.
5. Agent SDK `Edit` request in `/tmp`.
6. Agent SDK `Agent` subagent request.
7. Four parallel `query()` calls to verify queueing.
8. Service restart, then one CLI request.

Expected result:

- no 429 under normal sequential load
- no empty tool input
- no API key in logs
- access log contains metadata only
- service binds only to `127.0.0.1`
