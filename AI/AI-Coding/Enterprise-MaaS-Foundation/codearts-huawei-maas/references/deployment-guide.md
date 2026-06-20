# Deployment Guide

## Contents

- Scope and inputs
- Automated installation
- What the installer creates and patches
- Manual verification
- `--yolo` behavior
- Common command examples

## Scope

This guide installs Huawei CodeArts CLI 26.5.6 on macOS arm64 and creates a separate `codearts-litellm` entry point that sends OpenAI-compatible requests to a LiteLLM gateway. The original `codearts_kernel` is preserved. All binary edits are made only to `codearts_litellm_kernel`.

## Inputs

- CodeArts DMG:
  `https://codearts-agent-obs-cdn.huaweicloud.com/codearts/cli_tui/latest/codearts-26.5.6-darwin-arm64.dmg`
- LiteLLM gateway root URL, for example:
  `http://YOUR_LITELLM_HOST:4000`
- LiteLLM virtual key:
  provide through `--virtual-key`, `$LITELLM_VIRTUAL_KEY`, or macOS Keychain service `codearts-litellm`, account `virtual-key`.

Do not store real virtual keys in the skill, a repository, a terminal transcript, or screenshots.

## Automated Installation

```bash
~/.codex/skills/codearts-huawei-maas/scripts/setup_codearts_litellm.sh \
  --litellm-base-url "http://YOUR_LITELLM_HOST:4000" \
  --virtual-key "sk-REPLACE_WITH_USER_KEY"
```

If the key is already in Keychain:

```bash
security add-generic-password -U -s codearts-litellm -a virtual-key -w "sk-REPLACE_WITH_USER_KEY"
~/.codex/skills/codearts-huawei-maas/scripts/setup_codearts_litellm.sh \
  --litellm-base-url "http://YOUR_LITELLM_HOST:4000"
```

## What the Installer Does

1. Downloads the DMG to `~/Downloads/codearts-26.5.6-darwin-arm64.dmg` when missing.
2. Mounts the DMG and copies the CodeArts executable to `~/Applications/codearts/codearts_kernel`.
3. Copies `codearts_kernel` to `codearts_litellm_kernel`.
4. Patches the copy:
   - `@ai-sdk/inferhub-provider` to `@ai-sdk/openai-compatible`.
   - Default plugin language from `zh-cn` to `en-us`.
   - English-only language prompts to "English by default; Chinese, Spanish, or Brazilian Portuguese when requested."
   - Removes the "skip login, use CODEARTS_CLI_AK/CODEARTS_CLI_SK" startup notice.
5. Re-signs `codearts_litellm_kernel` with `codesign --force --sign -`.
6. Creates a local HTTP proxy on `127.0.0.1:4001` that:
   - strips CodeArts' Huawei-style authorization header,
   - injects `Authorization: Bearer <LiteLLM virtual key>`,
   - forwards to the LiteLLM gateway.
7. Creates CodeArts config and model cache.
8. Creates the `codearts-litellm` wrapper with session-scoped `--yolo`.

## Manual Verification

Run:

```bash
~/.codeartsdoer/Installers/codearts-litellm --version
~/.codeartsdoer/Installers/codearts-litellm models
~/.codeartsdoer/Installers/codearts-litellm run -m huaweicloud-maas/glm-5.1 "Answer in one word: ready"
~/.codeartsdoer/Installers/codearts-litellm run -m huaweicloud-maas/glm-5.1 "用中文回答，只输出两个字：可以"
```

Expected:

- Version: `26.5.6`
- Models include:
  - `huaweicloud-maas/glm-5.1`
  - `huaweicloud-maas/claude-opus-4-6`
  - `huaweicloud-maas/deepseek-v4-pro`
  - `huaweicloud-maas/deepseek-v4-flash`
  - `huaweicloud-maas/deepseek-v3.2`
- English prompt returns English.
- Chinese prompt can return Chinese.

## --yolo Behavior

`codearts-litellm --yolo` is implemented in the wrapper. It removes `--yolo` before invoking the CodeArts kernel, so CodeArts does not need native support for that flag.

During that process only, it writes:

```json
{"bash_mode":"always_allow"}
```

and sets all CodeArts tool permissions to `allow`, plus:

```json
{"network_policy":"allow_all"}
```

The wrapper backs up previous permission files and restores them on process exit. Normal `codearts-litellm` runs should remain in the default `sandbox` mode.

## Common Command Examples

```bash
# TUI
codearts-litellm

# TUI with session-scoped permission bypass
codearts-litellm --yolo

# Non-interactive prompt
codearts-litellm run -m huaweicloud-maas/glm-5.1 "Answer in one word: ready"

# Put --yolo anywhere; the wrapper consumes it
codearts-litellm run --yolo -m huaweicloud-maas/glm-5.1 "Create the file demo.txt"
```
