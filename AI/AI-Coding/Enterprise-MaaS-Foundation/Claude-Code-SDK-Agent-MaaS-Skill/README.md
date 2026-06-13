# Claude-Code-SDK-Agent-MaaS-Skill

This skill guides an AI agent or operator through configuring Claude Code and the Claude Agent SDK to use Huawei Cloud MaaS as the model backend, especially `glm-5.1`.

The target architecture is:

```text
Claude Code / Claude Agent SDK
  -> local Anthropic-compatible proxy
  -> Huawei Cloud MaaS OpenAI-compatible API
  -> glm-5.1
```

Default MaaS URL:

```text
https://api-ap-southeast-1.modelarts-maas.com/openai/v1
```

Default model:

```text
glm-5.1
```

## Files

```text
Claude-Code-SDK-Agent-MaaS-Skill/
├── SKILL.md
├── README.md
└── references/
    └── adapter-checklist.md
```

## API Key Configuration

Do not put a real API key in this README, in `SKILL.md`, in source control, or in a package archive.

Use an environment variable or a root-owned env file.

Recommended system env file:

```bash
/etc/claude-code-proxy/maas.env
```

Example content:

```bash
CLAUDE_CODE_PROXY_API_KEY=replace-with-your-maas-api-key
ANTHROPIC_PROXY_BASE_URL=https://api-ap-southeast-1.modelarts-maas.com/openai/v1
REASONING_MODEL=glm-5.1
COMPLETION_MODEL=glm-5.1
REQUEST_MIN_INTERVAL_MS=1200
UPSTREAM_TIMEOUT_MS=180000
UPSTREAM_MAX_RETRIES=3
MAX_QUEUE_DEPTH=20
```

Recommended permissions:

```bash
sudo chown root:claude-proxy /etc/claude-code-proxy/maas.env
sudo chmod 0640 /etc/claude-code-proxy/maas.env
```

For one-off local testing, you can export the key in the shell:

```bash
export MAAS_API_KEY='replace-with-your-maas-api-key'
```

When launching a proxy that expects `CLAUDE_CODE_PROXY_API_KEY`:

```bash
export CLAUDE_CODE_PROXY_API_KEY="${MAAS_API_KEY}"
```

Never echo the real key into logs or documentation.

## Claude Code Configuration

Configure Claude Code to talk to the local proxy:

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

Typical location:

```bash
~/.claude/settings.json
```

## Agent SDK Configuration

TypeScript example:

```js
import { query } from '@anthropic-ai/claude-agent-sdk';

const env = {
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
    model: 'sonnet',
    cwd: process.cwd(),
    persistSession: false,
    maxTurns: 1,
    tools: [],
    env
  }
})) {
  if (message.type === 'result') {
    console.log(message.result);
  }
}
```

## Validation

Health:

```bash
curl http://127.0.0.1:3000/
```

Metrics:

```bash
curl http://127.0.0.1:3000/metrics
```

Claude Code:

```bash
claude -p 'Reply with OK only.' --output-format json --no-session-persistence --model sonnet
```

Agent SDK:

```bash
node test-query.mjs
node test-bash.mjs
node test-subagent-tool.mjs
```

## Adaptation Issues Covered By The Skill

- Anthropic Messages API to OpenAI Chat Completions conversion
- Streaming tool-call argument assembly
- Claude Code and Agent SDK tool-call compatibility
- GLM-5.1 fake home path guessing
- Large Claude Code default tool sets
- MaaS 429 rate limits
- Upstream timeout and retry behavior
- Metadata-only access logging
- Localhost-only proxy deployment

## Packaging Safety

Before packaging or publishing this skill, scan for secrets:

```bash
rg -n "CLAUDE_CODE_PROXY_API_KEY=[A-Za-z0-9_-]{20,}|MAAS_API_KEY='[A-Za-z0-9_-]{20,}|Bearer [A-Za-z0-9._-]{20,}" .
```

Only placeholder values such as `replace-with-your-maas-api-key` should appear.
