# Upstream issue draft — JiuwenSwarm 0.2.3, R-8

**Title:** `tools: []` in a role file silently means "all tools"

**Environment:** JiuwenSwarm 0.2.3, role frontmatter `tools:` key.

**Observed (source reading, not live):** the loader does
`list(tools) if tools else ["*"]`, so an empty `tools: []` grants every tool to the
sub-agent instead of none — the opposite of what a tool-less role author intends.

**Expected:** `tools: []` means zero tools, or at minimum a warning at load time.

**Workaround used by LLMWiki:** sentinel whitelist `tools: [__llmwiki_no_tools__]`
matching no real tool name (role/llmwiki.md). Runtime confirmation that the dispatched
role really had zero tools is recorded in docs/evidence/live-2026-09-24 (E2-S4).
