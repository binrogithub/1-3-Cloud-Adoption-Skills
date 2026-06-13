# TODO

## Production Readiness

- [x] Add `CODEX_GLM_TRACE=1` with redaction plus mock fixtures to capture real Codex `/v1/responses` tool payloads.
- [x] Implement ordinary function calling conversion between Codex Responses tools and Huawei MaaS OpenAI-compatible Chat Completions tools.
- [x] Implement tool output round-trip conversion from Codex tool results back into Huawei MaaS chat messages.
- [x] Map Codex `local_shell` and `apply_patch` response items without executing tools in the shim; Codex CLI must keep ownership of sandboxing and approvals.
- [x] Add local 1 rps queueing plus 429 retry with jitter for Huawei MaaS limits.
- [x] Update installation flow and documentation after tool calling and queueing are stable.
- [x] Add `model_catalog_json` to glm profile so Codex resolves `glm-5.1` metadata without the fallback warning.

## Done

- [x] Isolate `codex-glm` CCR state from shared `~/.claude-code-router` by using a dedicated CCR home and port.
