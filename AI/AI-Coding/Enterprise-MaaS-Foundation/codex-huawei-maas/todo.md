# TODO — codex-glm Test Failures and Shim Improvements

## Summary

50 tests run across 6 categories. 49 passed, 1 failed, 2 hung (timeout at 45s).

| Category      | Pass | Fail | Hung |
|---------------|------|------|------|
| text          | 10   | 0    | 0    |
| shell         | 9    | 0    | 1    |
| file_create   | 10   | 0    | 0    |
| file_read     | 5    | 0    | 0    |
| file_edit     | 4    | 0    | 0    |
| multi         | 4    | 1    | 1    |
| edge          | 5    | 0    | 0    |

---

## Critical Issues

### 1. Session Hang After Tool Execution (tests 20, 43)

**Root cause:** After codex-glm finishes producing output (tool call results or text), the session remains open and waits for additional input instead of terminating. The 45s timeout (exit code 124) kills the process, but the actual work completed successfully.

**Evidence:**
- Test 20 (shell, `ls -la /root`): "the process timed out at 45 seconds (exit code 124) - codex-glm did not terminate on its own after producing results, likely keeping the session open"
- Test 43 (multi, create-then-modify): "Timed out after 45s. First step completed (wrote 'original' to /tmp/cglm-t43.txt), but second step (changing to 'modified') never executed"

**Why it happens:** The shim streams the SSE response correctly, but the Codex CLI session does not receive a clean end-of-turn signal that causes it to exit. When the upstream model returns a `stop_reason` of `end_turn` or `tool_use`, the shim emits `response.completed` and closes the stream, but the Codex CLI process may keep the interactive session alive waiting for the next user turn.

**Fix in shim (`codex-glm-ccr-responses-shim.cjs`):**
- [ ] Ensure `data: [DONE]\n\n` is always written and `raw.end()` is called promptly after `response.completed` in `streamAnthropicAsResponses()`. Verify no code path delays the `raw.end()` call.
- [ ] In `streamAnthropicAsResponses()`, add a `raw.destroySoon()` after `raw.end()` to force-close the TCP connection and signal to the Codex CLI that no more data will arrive.
- [ ] Investigate whether the `message_delta` event with `stop_reason` needs to be forwarded as a `response.output_item.done` event before `response.completed` — the current code silently discards `message_delta` (line 578-580) which may prevent the client from recognizing the turn is over.

### 2. Multi-Step Session Does Not Progress Past First Step (test 43)

**Root cause:** In multi-step `codex-glm exec` sessions, the model produces a tool call for the first step, Codex CLI executes it and sends the tool result back, but the model does not produce a second tool call or text response for the second step. The session hangs.

**Evidence:**
- Test 43: "First step completed (wrote 'original' to /tmp/cglm-t43.txt), but second step (changing to 'modified') never executed. File still contains 'original'."
- Test 45 also hit timeout but all 3 steps completed before the timeout, suggesting the issue is intermittent or depends on session timing.

**Why it happens:** After the shim converts the first tool result back into an Anthropic-format message and sends a second request to the model, the model may return an `end_turn` stop reason without making the second tool call. This could be because:
1. The model (GLM-5.1) sees the task as "done" after the first step.
2. The tool result conversion loses context that would prompt a second action.
3. The `responsesInputToMessages()` function does not preserve enough conversation history for multi-turn tool use.

**Fix in shim:**
- [ ] Review `responsesInputToMessages()` to ensure that multi-turn tool call/result cycles are properly converted into the Anthropic messages format with alternating `assistant` (tool_use) and `user` (tool_result) content blocks.
- [ ] Add tracing (via `writeTrace`) at the point where the second request is built, so we can inspect whether the conversation history includes the first tool call and its result.
- [ ] Consider adding a system prompt hint for multi-step requests: "Complete ALL steps before ending your turn. Do not stop after the first action."

---

## Non-Critical Issues (Passing but Notable)

### 3. Model Hallucination in Tool Output Summary (test 31)

**Detail:** "the model's natural language summary incorrectly described the content as 'Chunk ID: ba866e' rather than 'test21', which is a model hallucination, but the tool execution correctly read the file."

**Impact:** The tool output (exec command stdout) is correct, but the model's text summary of what it read is wrong. This is a GLM-5.1 model behavior issue, not a shim bug.

**Action:**
- [ ] Document this as a known GLM-5.1 limitation. No shim fix needed; the tool output itself is always correct.

### 4. Rate-Limit 429 Errors After Operation Completes (test 22)

**Detail:** "There were 429 rate-limit errors after the operation completed, but the file creation itself worked correctly."

**Impact:** The shim already retries 429s (see `requestJsonWithRetry`), but if the retries exhaust and the operation already succeeded on a prior attempt, the error noise is cosmetic.

**Action:**
- [ ] Consider logging 429 retries at a lower verbosity level to reduce noise in test output.
- [ ] Verify the retry logic in `requestJsonWithRetry()` properly consumes the response body before retrying (line 344: `upstream.resume()`) to avoid memory leaks.

### 5. Timeout on Session Cleanup (tests 20, 37, 45)

**Detail:** Several tests report exit code 124 (timeout) even though all work completed before the 45s mark. The timeout hits during session shutdown/cleanup.

**Impact:** Tests pass (correct output produced), but the process does not exit cleanly, which can cause resource leaks in long-running environments.

**Action:**
- [ ] Same fix as issue 1 — ensure the shim closes the SSE stream aggressively after `response.completed`.
- [ ] In the test harness, consider sending EOF to stdin of the codex-glm process to prompt clean exit, rather than relying on timeout kill.

### 6. Append Without Trailing Newline (test 34)

**Detail:** "File content changed from 'hello world' to 'helloappended' — the original file had 'hello world' without a trailing newline, so 'appended' was appended directly after 'world' on the same line"

**Impact:** This is correct shell behavior (`echo "appended" >> file` appends to the last line if no trailing newline). Not a shim bug.

**Action:**
- [ ] No fix needed. Document as expected shell behavior in test plan.

---

## Shim Code Quality TODOs

### 7. Stream Closure Robustness

- [ ] In `streamAnthropicAsResponses()`, wrap the `for await (const chunk of upstream)` loop in a try/catch/finally that always calls `raw.end()` and `raw.destroySoon()` in the finally block, even if the upstream stream errors.
- [ ] Add a `raw.setTimeout(0)` or `raw.clearTimeout()` after all SSE events are written to prevent the HTTP connection from being held open by a lingering keep-alive timer.

### 8. message_delta Stop Reason Handling

- [ ] Forward `message_delta` with `stop_reason` as a meaningful SSE event. Currently (line 578-580), the `message_delta` event is silently consumed and discarded. The stop reason should be reflected in the `response.completed` event's status field, and potentially emitted as a separate `response.output_item.done` event for the text message item.

### 9. apply_patch System Prompt Fallback

- [ ] The current system prompt hint (line 263) tells the model not to use `apply_patch`, but the `extractPatchesFromText()` function (line 398-413) still tries to parse patch patterns from freeform text output. If the model ignores the hint and outputs a patch in text, the shim converts it to a `custom_tool_call` — verify this fallback path works correctly with GLM-5.1, and if it does not, consider removing `extractPatchesFromText()` to avoid false-positive patch detection.

### 10. Conversation History for Multi-Turn

- [ ] In `responsesInputToMessages()`, verify that the order of messages matches what the Anthropic API expects: strict alternating `user`/`assistant` roles. If two consecutive tool results appear, insert a synthetic assistant message between them.
- [ ] Add a unit test in `test-shim-transform.js` that covers a multi-turn conversation with tool calls and tool results to catch regressions.

---

## Priority Order

1. **Issue 1 + 5 + 7 + 8** — Session hang / stream closure (affects 2 tests, potential resource leak)
2. **Issue 2 + 10** — Multi-step session progression (affects 1 test, functional failure)
3. **Issue 9** — Patch fallback correctness (defense in depth)
4. **Issue 3** — Model hallucination documentation (cosmetic)
5. **Issue 4** — Rate-limit logging (cosmetic)
6. **Issue 6** — Append behavior documentation (cosmetic)
