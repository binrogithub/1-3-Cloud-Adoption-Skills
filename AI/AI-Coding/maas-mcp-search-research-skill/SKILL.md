---
name: maas-mcp-search-research-skill
description: Use when AI coding work needs current web information, code examples, vendor or company research, documentation lookups, or multi-source technical investigation, and the preferred pattern is Huawei Cloud MaaS or another OpenAI-compatible MaaS model combined with MCP search or crawling tools.
---

# MaaS MCP Search Research Skill

Use this skill for AI coding research workflows that combine Huawei Cloud MaaS reasoning with MCP-based search, crawl, code-search, or deep-research tools.

## Overview

Preferred flow:

```text
Question or coding task
  -> break into searchable sub-questions
  -> use MCP search/crawl/code tools for fresh evidence
  -> use MaaS model for synthesis, comparison, and decision support
  -> return cited, engineering-focused conclusions
```

Default MaaS baseline:

```text
Provider: Huawei Cloud ModelArts MaaS
API style: OpenAI-compatible
Base URL: https://api-ap-southeast-1.modelarts-maas.com/openai/v1/
Model: glm-5.1
```

## When to Activate

- User needs current web information, release status, pricing, news, or vendor updates
- Searching for code examples, API documentation, SDK behavior, or migration references
- Comparing tools, frameworks, providers, or cloud services before implementation
- Researching companies, products, or people as part of engineering planning
- Validating claims with multiple fresh sources before making code or architecture decisions
- User says `search for`, `look up`, `find`, `research`, `what's the latest`, or asks for direct sources

## MaaS Requirement

Use an OpenAI-compatible MaaS model as the synthesis layer. For Huawei Cloud MaaS, the common environment pattern is:

```bash
export OPENAI_API_KEY='replace-with-your-maas-api-key'
export OPENAI_BASE_URL='https://api-ap-southeast-1.modelarts-maas.com/openai/v1/'
export OPENAI_MODEL='glm-5.1'
```

Never commit a real MaaS API key into shared skill files or agent configs.

## MCP Search Requirement

At least one MCP search or retrieval server should be available. The exact server is intentionally flexible. Typical capability groups are:

- web search for current information
- domain-filtered search for docs or vendor sites
- code search or code-context retrieval
- page crawl or content extraction
- async deep-research agents

If multiple MCP search tools are available, prefer:

1. primary-source documentation for technical claims
2. vendor or maintainer sources for product behavior
3. broad web search only to widen recall or find leads

## Core Workflow

### 1. Frame the research question

Turn the request into a small set of verifiable sub-questions:

- what changed recently
- what exact API or behavior is needed
- which sources are authoritative
- what decision the coding task depends on

### 2. Search with MCP first

Use the MCP search tool that best matches the question:

- broad web search for current status
- advanced or filtered search for official docs
- code-context search for examples and implementation patterns
- crawl or fetch for full-page extraction
- async deep-research for wide comparative topics

### 3. Use MaaS for synthesis

Use the MaaS model to:

- summarize findings without copying long passages
- compare conflicting sources
- extract engineering implications
- identify unknowns that need another search pass

### 4. Return engineering-ready output

Prefer this output shape:

- direct answer
- evidence and source links
- impact on code, architecture, or operations
- recommendation and trade-off

## Usage Patterns

### Quick Lookup

Use MCP web search to answer narrow freshness questions such as:

```text
latest Node.js 22 features
latest React Server Components guidance
```

Then use MaaS to produce a short answer with links and relevance to the task.

### Code Research

Search for code examples and docs first, then ask MaaS to extract the exact pattern needed for implementation:

```text
Python asyncio cancellation patterns
OpenAI-compatible streaming examples
GaussDB PostgreSQL driver transaction retry examples
```

### Vendor or Tool Comparison

Run multiple focused searches, ideally against official docs plus one independent source, then have MaaS compare:

```text
LiteLLM vs direct OpenAI-compatible gateway setup
Claude Code router vs local proxy for MaaS
```

### Deep Technical Investigation

For broad topics, start the async deep-research MCP job if available, continue other work, then check results and synthesize with MaaS.

## Search Discipline

- Search before concluding, especially for anything time-sensitive
- Narrow by domain when official documentation exists
- Do not trust one source when decisions affect code, security, cost, or architecture
- Distinguish observed facts from MaaS inference
- Quote sparingly and summarize in your own words

## Related Skills

- `claude-code-huawei-maas` for Claude Code routing through Huawei MaaS
- `CSS-Code-Search-MCP` for building a code-search MCP on Huawei Cloud
- `LiteLLM-Huawei-MaaS-Proxy` when MaaS access should be centralized behind a proxy
