---
name: ccr-search-tool
description: Configure Claude Code Router so Claude Code search prompts and WebSearch tool requests are handled in CCR with optional search API prefetching instead of LiteLLM websearch_interception.
---

# CCR Search Tool

Use this skill when Claude Code under CCR needs current web search, such as `搜索今天的新闻`, but local `Fetch`/`WebFetch` tool calls are unreliable or GLM emits invalid tool parameters.

## What To Configure

Search should happen in CCR, before the model call. The CCR transformer detects search intent from the latest user message, optionally calls a search API such as Exa, injects source snippets into the model request, and removes Claude Code search/fetch tools so GLM does not need to produce fragile tool-call JSON.

The expected flow is:

```text
Claude Code search intent
  -> CCR transformer detects search intent
  -> CCR transformer calls a configured search API, for example Exa
  -> CCR injects search snippets and source URLs into the request
  -> CCR removes WebSearch/WebFetch/Fetch tools for that request
  -> configured MaaS/LiteLLM/model provider answers normally
```

This does not require LiteLLM `search_tools`, LiteLLM `websearch_interception`, or `/v1/responses` search tooling. The model provider URL should be left as-is.

## Quick Path

From the `claude-code-huawei-maas` directory:

```bash
python3 ccr-search-tool/scripts/configure-ccr-search.py --dry-run
python3 ccr-search-tool/scripts/configure-ccr-search.py --apply
```

Restart CCR if the script reports changes:

```bash
ccr restart
```

For live search, make one of these available to the CCR process:

```bash
export EXA_API_KEY='...'
# or
export CCR_SEARCH_API_KEY='...'
```

If no search API key is configured, the transformer still keeps `claude-glm` usable. Search-intent prompts receive an instruction that live search is unavailable, search/fetch tools are removed for that request, and normal non-search prompts continue to use the configured provider.

## Required CCR Behavior

The script installs a CCR transformer named `ccr-search-prefetch`. It does four things:

- Detects search intent only from the latest user message, ignoring `<system-reminder>` context.
- Calls Exa directly from CCR when `EXA_API_KEY` or `CCR_SEARCH_API_KEY` is configured.
- Injects compact search snippets and source URLs into the latest user message.
- Removes `WebSearch`, `WebFetch`, `Fetch`, and legacy LiteLLM search tool names from the request so GLM is not asked to call them.

The provider endpoint is not changed. Existing Huawei MaaS `/chat/completions`, LiteLLM model proxy, or other provider URLs remain untouched.

A typical transformer chain becomes:

```json
[
  ["maxtoken", {"max_tokens": 8192}],
  "cleancache",
  "ccr-search-prefetch",
  "reasoning",
  "enhancetool"
]
```

If an older `claude-websearch-to-responses` transformer is present, the script removes it from provider chains and installs `ccr-search-prefetch` instead.

## Validation

Test with live search configured:

```text
搜索今天的新闻，只列1条，并给出来源URL。
```

A healthy path should return current information with source URLs and should not show Claude Code local `Fetch(...)` or `WebFetch(...)` tool calls.

Test without a search API key by starting CCR without `EXA_API_KEY` / `CCR_SEARCH_API_KEY`, then run the same prompt. The request should complete instead of making `claude-glm` unavailable; the answer may state that live search is not configured.

## Troubleshooting

If Claude Code calls local Fetch/WebFetch, the CCR transformer is not installed, not in the provider transformer chain, or the prompt was not classified as search intent.

If search prompts say live search is unavailable, confirm the search key is visible to the CCR process, not just the shell running the setup script.

If normal non-search prompts fail after installing this transformer, inspect CCR config first. This script should not change `api_base_url`, model names, LiteLLM config, or provider credentials.

If an older LiteLLM search setup is still active, remove LiteLLM `websearch_interception` / `search_tools` separately. This skill deliberately keeps search at the CCR layer.
