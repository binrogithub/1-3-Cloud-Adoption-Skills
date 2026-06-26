---
name: copilot-glm-kit
description: Install, verify, diagnose, and harden GitHub Copilot Chat in VS Code when GLM or another OpenAI-compatible BYOK model is used through OAI Compatible Copilot. Use when Copilot stalls, emits malformed or truncated tool calls, writes partial files, shows path drift, needs GLM model settings, needs the patched OAI Compatible Copilot VSIX installed, or needs a portable debug bundle.
---

# Copilot GLM Kit

Use this skill when a user runs GitHub Copilot Chat Agent in VS Code with GLM through OAI Compatible Copilot and file edits or tool calls are slow, malformed, truncated, or not applied.

## Triage

First separate these cases:

- **Setup problem**: OAI Compatible Copilot is not installed, the patched VSIX is not installed, `oaicopilot.models` is missing, or VS Code has not been reloaded.
- **Workspace problem**: Copilot is opened outside the real project folder, workspace trust is missing, edits are pending `Keep`/`Undo`, or the model uses absolute paths outside the workspace.
- **GLM tool-call problem**: OAI logs show very large streamed `tool_calls[].function.arguments`, `invalid_json_arguments`, completion near `4096`/`4097` tokens, or a long `create_file` that only finishes after minutes.
- **Provider-to-Copilot apply problem**: provider logs contain `glm.toolCall.emit`, but chat editing state has no file operations and target files do not change.

Do not assume GPT is selected just because helper log entries mention `gpt-*`; Copilot may use GPT helpers for chat titles or progress while the selected model is GLM.

## Install Or Repair

Use the bundled patched extension only when the user wants the kit-installed OAI Compatible Copilot extension.

macOS:

```bash
cd ~/.codex/skills/copilot-glm-kit
chmod +x scripts/install-macos.sh
./scripts/install-macos.sh --base-url "https://YOUR-ENDPOINT/openai/v1" --model "glm-5.1"
```

Windows PowerShell:

```powershell
cd "$env:USERPROFILE\.codex\skills\copilot-glm-kit"
.\scripts\install-windows.ps1 -BaseUrl "https://YOUR-ENDPOINT/openai/v1" -ModelId "glm-5.1"
```

After installation, tell the user to run `Developer: Reload Window` in VS Code and select `glm-5.1 OAI Compatible`.

If the user does not want the installer to edit settings, omit the base URL and apply `references/settings-template.json` manually after replacing endpoint and model values.

## Verify

Run:

```bash
node ~/.codex/skills/copilot-glm-kit/scripts/check-install.mjs
```

Expected signs:

- `johnny-zhao.oai-compatible-copilot@0.4.3`
- `oaicopilot.glmToolCallCompat: true`
- `oaicopilot.models` includes the GLM model id
- OAI logs exist under `~/.copilot/oaicopilot/logs`

On Windows, use:

```powershell
node "$env:USERPROFILE\.codex\skills\copilot-glm-kit\scripts\check-install.mjs"
```

## Diagnose Logs

Summarize the latest OAI Compatible logs:

```bash
node ~/.codex/skills/copilot-glm-kit/scripts/glm_toolcall_log_summary.mjs --latest
```

Use these signals:

- Growing `toolCallChunks` or `argumentChars`: the model may still be streaming; wait before retrying.
- `finishReasons` includes `tool_calls`: the model completed a tool call.
- `invalid_json_arguments`: tool-call JSON was malformed or truncated.
- `glm.toolCall.emit`: the provider emitted a tool call to Copilot; if files did not change, inspect VS Code workspace and chat editing state.

If the user needs a sharable report:

```bash
node ~/.codex/skills/copilot-glm-kit/scripts/collect_copilot_debug_bundle.mjs --workspace /path/to/workspace --out /path/to/bundle-dir
```

Warn that logs can contain prompts, local paths, endpoint URLs, and tool-call payloads.

## Patch Guidance

When the user wants to fork or audit `JohnnyZ93/oai-compatible-copilot`, read `references/provider-patch.md`.

Core patch rule: for GLM model ids, buffer streamed tool-call chunks until `finish_reason === "tool_calls"` / `stop` / `[DONE]`, then emit only if the tool name is allowed and arguments parse to a JSON object. Prefer logging dropped calls over guessing schemas.

## Safer Copilot Prompt

For GLM agent tasks, include:

```text
Only modify files inside the current VS Code workspace. Use relative paths only. Do not create absolute paths. Work in small steps: first inspect files, then update one file or one function at a time. Do not rewrite the whole app.py unless I explicitly ask.
```

For large app creation, ask Copilot to create `requirements.txt` first, then a minimal `app.py`, then incremental changes. This avoids one giant `create_file` tool call.

## Validation

Prefer objective checks:

- `code --list-extensions --show-versions | rg 'oai-compatible-copilot|copilot'`
- Inspect VS Code `settings.json` for `oaicopilot.models`, `max_completion_tokens`, and `oaicopilot.glmToolCallCompat`.
- Check target files with `stat`, `Get-Item`, or `wc -l` before and after a Copilot run.
- Parse changed Python with `python3 -c 'import ast, pathlib; ast.parse(pathlib.Path("app.py").read_text())'`.
- Run `scripts/glm_toolcall_log_summary.mjs --latest` after each attempt.
