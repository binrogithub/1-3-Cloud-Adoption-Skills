# claude-code-huawei-maas

This skill documents the Claude Code CLI usage pattern for connecting `claude` directly to Huawei Cloud MaaS through `claude-code-router`.

It is intended for operators who want the installed Claude Code CLI command to use an OpenAI-compatible ModelArts MaaS endpoint, especially `glm-5.1`, without writing a custom Anthropic-to-OpenAI proxy.

## Scope

This is for Claude Code CLI:

```text
claude CLI
  -> claude-code-router on http://127.0.0.1:3456
  -> Huawei Cloud MaaS OpenAI-compatible /chat/completions
  -> glm-5.1
```

For Claude Agent SDK or custom proxy patterns, use the separate `Claude-Code-SDK-Agent-MaaS-Skill`.

## Quick Start

```bash
export API_KEY='replace-with-your-maas-api-key'
./scripts/configure.sh
```

The script configures:

- `~/.claude-code-router/config.json`
- a `claude` wrapper that exports the router environment
- `ANTHROPIC_MODEL=glm-5.1`
- `ANTHROPIC_CUSTOM_MODEL_OPTION=glm-5.1`
- `CLAUDE_CODE_MAX_CONTEXT_TOKENS=190000`

It also runs a smoke test and expects the result to report `modelUsage.glm-5.1`.

## Files

```text
claude-code-huawei-maas/
├── README.md
├── SKILL.md
├── agents/
│   └── openai.yaml
└── scripts/
    └── configure.sh
```

## Security

Do not commit a real MaaS API key. The script writes `api_key: "$API_KEY"` into the router config so the secret remains in the runtime environment.
