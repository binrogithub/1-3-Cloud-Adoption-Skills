---
name: claude-code-sdk-agent-maas
description: Use this skill when configuring Claude Code or the Claude Agent SDK to run through a local Anthropic Messages API compatible proxy backed by Huawei Cloud MaaS, especially for GLM-5.1 via the OpenAI-compatible MaaS endpoint. Covers setup, SDK usage, proxy validation, tool-call compatibility, rate limiting, metrics, logging, and known adaptation issues.
---

# Claude Code SDK Agent MaaS

Use this skill to help users connect Claude Code and the Claude Agent SDK to Huawei Cloud MaaS, especially the `glm-5.1` model exposed through the OpenAI-compatible MaaS API.

The expected deployment is a local backend proxy:

```text
Claude Code / Claude Agent SDK
  -> Anthropic Messages API /v1/messages
  -> local proxy on http://127.0.0.1:3000
  -> Huawei Cloud MaaS OpenAI-compatible /chat/completions
  -> glm-5.1
```

## Core Facts

- Default MaaS base URL:
  `https://api-ap-southeast-1.modelarts-maas.com/openai/v1`
- Default model:
  `glm-5.1`
- Never print, persist in docs, commit, or package a real API key.
- Use placeholders such as `replace-with-your-maas-api-key`.
- Claude Code itself does not need to be modified. Configure it to use a local proxy through environment settings.
- The proxy must translate Anthropic Messages API requests into OpenAI Chat Completions requests and translate the response back.

## Recommended Claude Code Settings

When configuring Claude Code, use:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3000",
    "ANTHROPIC_AUTH_TOKEN": "maas-local-proxy",
    "API_TIMEOUT_MS": "3000000",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.1",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.1",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1"
  }
}
```

Typical user settings path:

```bash
~/.claude/settings.json
```

## Required Proxy Environment

Use an env file outside source control, usually:

```bash
/etc/claude-code-proxy/maas.env
```

Recommended fields:

```bash
CLAUDE_CODE_PROXY_API_KEY=replace-with-your-maas-api-key
ANTHROPIC_PROXY_BASE_URL=https://api-ap-southeast-1.modelarts-maas.com/openai/v1
REASONING_MODEL=glm-5.1
COMPLETION_MODEL=glm-5.1
REASONING_MAX_TOKENS=4096
COMPLETION_MAX_TOKENS=2048
DEBUG=false
REQUEST_MIN_INTERVAL_MS=1200
UPSTREAM_TIMEOUT_MS=180000
UPSTREAM_MAX_RETRIES=3
UPSTREAM_RETRY_BASE_DELAY_MS=1500
MAX_QUEUE_DEPTH=20
ACCESS_LOG_PATH=/var/lib/claude-code-maas-proxy/access.jsonl
```

Permissions:

```bash
chown root:claude-proxy /etc/claude-code-proxy/maas.env
chmod 0640 /etc/claude-code-proxy/maas.env
```

## SDK Usage Pattern

Use the TypeScript Agent SDK with explicit env values:

```js
import { query } from '@anthropic-ai/claude-agent-sdk';

const maasEnv = {
  ...process.env,
  ANTHROPIC_BASE_URL: 'http://127.0.0.1:3000',
  ANTHROPIC_AUTH_TOKEN: 'maas-local-proxy',
  ANTHROPIC_DEFAULT_HAIKU_MODEL: 'glm-5.1',
  ANTHROPIC_DEFAULT_SONNET_MODEL: 'glm-5.1',
  ANTHROPIC_DEFAULT_OPUS_MODEL: 'glm-5.1',
  API_TIMEOUT_MS: '3000000'
};

for await (const message of query({
  prompt: 'Reply with OK only.',
  options: {
    cwd: process.cwd(),
    model: 'sonnet',
    persistSession: false,
    maxTurns: 1,
    tools: [],
    env: maasEnv
  }
})) {
  if (message.type === 'result') {
    console.log(message.result);
  }
}
```

## Validation Workflow

Run checks in this order:

1. Proxy health:

   ```bash
   curl http://127.0.0.1:3000/
   ```

2. Proxy metrics:

   ```bash
   curl http://127.0.0.1:3000/metrics
   ```

3. Claude Code CLI:

   ```bash
   claude -p 'Reply with OK only.' --output-format json --no-session-persistence --model sonnet
   ```

4. Agent SDK no-tool query.

5. Agent SDK tool query with a restricted tool set, for example `Read`, `Bash`, or `Edit`.

6. Agent SDK subagent query with `Agent`.

7. Concurrency test with several parallel `query()` calls, then inspect:

   ```bash
   curl http://127.0.0.1:3000/metrics
   ```

Expected healthy metrics:

- `failed_total` remains `0`
- `upstream_429_total` remains `0` under normal load
- `queue_depth` returns to `0`
- `last_error` is `null`

## Known Adaptation Issues And Fixes

### Streaming Tool Arguments

OpenAI-compatible streaming tool call arguments arrive as incremental fragments. A proxy must concatenate those fragments before emitting Anthropic `input_json_delta` or the tool input can become `{}`.

If `Read`, `Edit`, or `Bash` tool inputs arrive empty, inspect the proxy streaming conversion first.

### GLM-5.1 Path Guessing

GLM-5.1 can invent paths such as:

```text
/home/user/...
/Users/claudedev/...
/Users/zhujinhao/...
```

Mitigations:

- Inject path guidance into the system prompt.
- Add the current working directory to file tool descriptions when known.
- If a fake home path is detected and `Bash` is available, rewrite the attempted file tool call to:

  ```json
  {
    "name": "Bash",
    "input": {
      "command": "pwd && ls",
      "description": "Check current directory and list files"
    }
  }
  ```

Then let the next model turn use the real cwd.

### Claude Code Default Tool Count

Claude Code can send a large default tool set, often around 20+ tools. This is normal.

Access logs should distinguish:

- `tools_original_count`
- `tools_forwarded_count`
- `tools_filtered_count`
- `tools_profile`

Suggested profiles:

- `none`
- `restricted`
- `claude_code_default`

### MaaS Rate Limit

If Huawei Cloud MaaS returns 429, use a queue and a minimum interval:

```bash
REQUEST_MIN_INTERVAL_MS=1200
UPSTREAM_MAX_RETRIES=3
UPSTREAM_RETRY_BASE_DELAY_MS=1500
MAX_QUEUE_DEPTH=20
```

For a strict 1 QPS MaaS quota, do not run many Agent SDK subagents in parallel without queueing.

### JSON Schema Output

Do not assume `outputFormat: { type: 'json_schema' }` is reliable through this model/proxy chain unless it has been tested in the target environment. Prefer plain text or application-side JSON validation with repair.

## Production Service Shape

Preferred runtime:

- Node.js HTTP service
- systemd-managed
- bind only to `127.0.0.1`
- non-root user such as `claude-proxy`
- read-only install dir
- writable state dir only
- metadata-only access log

Useful paths:

```bash
/opt/claude-code-maas-proxy/
/etc/claude-code-proxy/maas.env
/etc/systemd/system/claude-code-maas-proxy.service
/var/lib/claude-code-maas-proxy/access.jsonl
/etc/logrotate.d/claude-code-maas-proxy
```

## Security Rules

- Do not include a real API key in README files, tarballs, screenshots, logs, or committed config.
- Document API key configuration using placeholders only.
- Store the real key only in an env file or secret manager.
- Keep the local proxy bound to `127.0.0.1` unless there is a clear reason to expose it.
- The access log must be metadata-only. Do not log prompts, messages, tool outputs, or Authorization headers.
