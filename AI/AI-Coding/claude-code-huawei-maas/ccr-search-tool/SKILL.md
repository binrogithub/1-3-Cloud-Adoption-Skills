---
name: ccr-search-tool
description: Configure Claude Code Router and LiteLLM so Claude Code search prompts and WebSearch tool requests are routed through LiteLLM /v1/responses search tools.
---

# CCR LiteLLM Search Tool

Use this skill when Claude Code under CCR needs current web search, such as `搜索今天的新闻`, but the request is falling back to local Fetch/WebFetch or hanging on LiteLLM streaming.

## What To Configure

Claude Code emits Anthropic-style tool intent. CCR must send search-intent requests to LiteLLM in OpenAI Responses shape, and LiteLLM must have a configured search tool plus web-search interception.

The expected flow is:

```text
Claude Code WebSearch intent
  -> CCR transformer maps WebSearch to litellm_web_search
  -> CCR provider URL uses /v1/responses
  -> request sets use_chat_completions_api=true
  -> LiteLLM websearch_interception calls configured search_tools provider
```

## Quick Path

From the `claude-code-huawei-maas` directory:

```bash
python3 ccr-search-tool/scripts/configure-ccr-litellm-search.py --dry-run
python3 ccr-search-tool/scripts/configure-ccr-litellm-search.py --apply
```

Then restart CCR and LiteLLM if the script reports changes:

```bash
ccr restart
cd /root/LiteLLM && docker compose up -d litellm
```

## Required LiteLLM Config

LiteLLM needs both `websearch_interception` and at least one `search_tools` entry. Example:

```yaml
litellm_settings:
  callbacks:
    - "prometheus"
    - "websearch_interception"
    - custom_callbacks.my_prometheus_logger
  websearch_interception_params:
    enabled_providers: ["openai"]
    search_tool_name: "exa-search"
  search_tools:
    - search_tool_name: "exa-search"
      litellm_params:
        search_provider: "exa_ai"
        api_key: "os.environ/EXA_API_KEY"
```

Use environment references for keys. Do not write provider keys directly into the repo or print them in diagnostics.

## Required CCR Behavior

The script installs a CCR transformer named `claude-websearch-to-responses`. It does three things:

- Converts Claude `WebSearch` tools to an OpenAI-compatible function tool named `litellm_web_search`.
- Forces search-intent requests through the LiteLLM Responses path by setting `use_chat_completions_api=true`.
- Filters local URL fetch tools for search prompts so Claude Code routes the query through LiteLLM search instead of calling Fetch/WebFetch directly.

The provider endpoint should be `/v1/responses`, not `/v1/chat/completions`.

## Validation

Run a direct LiteLLM check:

```bash
curl -sS http://127.0.0.1:4000/v1/responses \
  -H 'Authorization: Bearer sk-your-litellm-key' \
  -H 'Content-Type: application/json' \
  -d '{"model":"openai/your-model","input":"搜索今天的新闻","tools":[{"type":"function","function":{"name":"litellm_web_search","description":"Search the web","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}}],"use_chat_completions_api":true}'
```

Then test through Claude Code:

```text
搜索今天的新闻
```

A healthy path should show a search tool call routed to LiteLLM, not Claude Code local `Fetch(https://news.google.com)` followed by `Invalid tool parameters`.

## Troubleshooting

If Claude Code calls local Fetch/WebFetch, the CCR transformer is not installed, not in the provider transformer chain, or the prompt was not classified as search intent.

If the model writes `web_search(...)` as plain text, LiteLLM did not receive a valid tool schema or `websearch_interception` is not active.

If streaming stops after `message_stop` or times out, LiteLLM may be returning non-async Responses objects in a streaming path. Patch or upgrade the LiteLLM proxy streaming path so single Responses objects are wrapped as async events.

If the query works directly against LiteLLM but not via Claude Code, inspect CCR request logs first. The common mismatch is CCR still targeting `/v1/chat/completions` or missing `use_chat_completions_api=true` on `/v1/responses`.