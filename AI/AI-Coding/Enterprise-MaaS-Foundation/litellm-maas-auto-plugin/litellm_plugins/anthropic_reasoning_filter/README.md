# Anthropic Reasoning Filter

Response-only LiteLLM callback for Claude Code. It keeps provider thinking
enabled upstream but removes Anthropic `thinking` and `redacted_thinking`
blocks before the response reaches the client.

The filter:

- drops thinking block start/delta/signature/stop events;
- compacts remaining content indexes to `0..n`;
- preserves text, `tool_use`, usage, stop reasons, and terminal events;
- removes thinking blocks from non-streaming Messages responses;
- passes OpenAI chat-completions chunks through unchanged.

Set `ARF_HIDE_REASONING=false` to disable filtering.
