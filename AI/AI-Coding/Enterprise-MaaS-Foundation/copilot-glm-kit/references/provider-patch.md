# Provider Patch Reference

Use this reference when a user wants to fork or patch `JohnnyZ93/oai-compatible-copilot` for GLM tool-call reliability.

## Observed Failure Pattern

Typical OAI log signs:

```json
{"tag":"openai.stream.chunk","data":{"modelId":"glm-5.1","data":"... tool_calls ... function.arguments ..."}}
{"tag":"glm.toolCall.drop","data":{"toolName":"create_file","rawArgsLength":15449,"reason":"invalid_json_arguments"}}
{"tag":"usage.capture","data":{"usage":{"completion_tokens":4097}}}
```

Interpretation:

- The selected model is GLM, not necessarily GPT, even if Copilot helper requests use `gpt-4o-mini` for titles/progress.
- GLM is attempting tool calls.
- The `function.arguments` JSON is incomplete, badly escaped, or too large.
- A default output cap around 4096 can truncate file content mid-JSON.
- A long `create_file` may be valid but slow: thousands of streamed chunks can take minutes before VS Code sees an executable tool call.
- `glm.toolCall.emit` only proves the provider handed the tool call to Copilot. If target files do not change and chat edit state has empty `operations`, the failure is after provider emission: workspace path, VS Code edit acceptance, trust, or Copilot tool handling.

## Minimal Patch

Patch the OpenAI chat-completions streaming handler, usually `src/openai/openaiApi.ts`.

Add a normalizer similar to:

```ts
class GlmToolCallCompat {
  private buffers = new Map<number, { id?: string; name?: string; args: string }>();

  append(tc: Record<string, unknown>) {
    const idx = typeof tc.index === "number" ? tc.index : 0;
    const buf = this.buffers.get(idx) ?? { args: "" };
    const func = tc.function as Record<string, unknown> | undefined;
    if (typeof tc.id === "string") buf.id = tc.id;
    if (typeof func?.name === "string") buf.name = func.name;
    if (typeof func?.arguments === "string") buf.args += func.arguments;
    this.buffers.set(idx, buf);
  }

  flush(validToolNames: Set<string>, emit: (id: string, name: string, input: Record<string, unknown>) => void) {
    for (const [idx, buf] of this.buffers) {
      if (!buf.name || !validToolNames.has(buf.name)) continue;
      const parsed = safeParseObject(buf.args);
      if (!parsed) continue;
      emit(buf.id ?? `call_${idx}`, buf.name, parsed);
    }
    this.buffers.clear();
  }
}
```

Integrate as:

- Extract allowed tool names from `convertToolsToOpenAI(options)`.
- Enable only when `modelId` or user model id includes `/glm/i` and config switch is true.
- In GLM mode, append streamed tool calls but do not call `tryEmitBufferedToolCall`.
- On `finish_reason === "tool_calls"`, `stop`, or `[DONE]`, flush the compatibility buffer.

## Conservative Validation

Emit only when all checks pass:

- `toolName` exists.
- Tool is in VS Code-provided tool list.
- arguments parse to a JSON object.
- Common tools have required fields:
  - `replace_string_in_file`: `filePath`, `oldString`, `newString`
  - `insert_edit_into_file`: `filePath`, `code`
  - `run_in_terminal`: `command`

For unknown tools such as `create_file`, do not invent schema unless you have observed the exact VS Code schema in that session. Prefer logging rather than guessing.

## Apply vs Emit Diagnosis

Use this sequence after a run:

1. Summarize OAI logs and identify the latest request id.
2. If the latest request has no `finishReasons`, it is still streaming. Wait instead of retrying.
3. If `finishReasons` includes `tool_calls` and the log has `glm.toolCall.emit`, the provider accepted the tool call.
4. Check target files with `stat`/`Get-Item`.
5. Check latest `chatEditingSessions/*/state.json`.
   - Non-empty `operations`: Copilot staged edits; user may need `Keep`, or the edit may be pending.
   - Empty `operations`: VS Code/Copilot did not apply the emitted tool call. Reopen the correct workspace and retry with relative paths and smaller edits.

## Output Limit Fix

Add explicit `oaicopilot.models`:

```json
"oaicopilot.models": [
  {
    "id": "glm-5.1",
    "displayName": "glm-5.1",
    "owned_by": "maas",
    "apiMode": "openai",
    "context_length": 128000,
    "max_completion_tokens": 16000,
    "max_tokens": 16000,
    "temperature": 0,
    "vision": false,
    "include_reasoning_in_request": false
  }
]
```

Restart/reload VS Code after changing model metadata.

## Workspace and Path Guardrail

Use prompts that forbid absolute paths:

```text
Only modify files inside the currently opened VS Code workspace. Use relative file paths like app.py and requirements.txt. Do not use /Users, C:\, Desktop, or any absolute path. If you are unsure of the workspace, list files first.
```

This matters because GLM may drift from `/Users/name/Desktop/ticket-support` to `/Users/name/support-tickets`; Copilot may ignore or fail edits outside the active workspace.

## Recommended User Prompt

For validation, avoid a huge one-shot app. Start small:

```text
只把 requirements.txt 替换成：streamlit。必须使用文件编辑工具。
```

Then:

```text
只创建一个最小 Streamlit app.py，不要 CSS，不要数据库，不超过 80 行。必须使用文件编辑工具。
```

Then attempt larger app generation.
