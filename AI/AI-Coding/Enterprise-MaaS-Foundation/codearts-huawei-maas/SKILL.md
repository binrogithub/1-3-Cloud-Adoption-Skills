---
name: codearts-huawei-maas
description: Deploy Huawei CodeArts CLI on macOS and add a codearts-litellm wrapper that connects CodeArts to an OpenAI-compatible LiteLLM gateway, including model config, local auth proxy, language behavior patches, and session-scoped --yolo support. Use when installing CodeArts from scratch, configuring CodeArts with LiteLLM or MaaS through LiteLLM, fixing codearts-litellm wrappers, or reproducing this setup on another Mac.
---

# CodeArts LiteLLM Setup

## Quick Start

Use the bundled installer when the target host is macOS arm64 and should run CodeArts 26.5.6 through LiteLLM:

```bash
~/.codex/skills/codearts-huawei-maas/scripts/setup_codearts_litellm.sh \
  --litellm-base-url "http://YOUR_LITELLM_HOST:4000" \
  --virtual-key "sk-REPLACE_WITH_USER_KEY"
```

Then verify:

```bash
~/.codeartsdoer/Installers/codearts-litellm --version
~/.codeartsdoer/Installers/codearts-litellm models
~/.codeartsdoer/Installers/codearts-litellm run -m huaweicloud-maas/glm-5.1 "Answer in one word: ready"
~/.codeartsdoer/Installers/codearts-litellm --yolo
```

Never commit or print a real LiteLLM virtual key. Store it in macOS Keychain service `codearts-litellm`, account `virtual-key`, or pass it once to the installer.

## Workflow

1. Confirm target platform:
   - macOS arm64.
   - `curl`, `hdiutil`, `python3`, `perl`, `codesign`, `security`, and `jq` available.
   - LiteLLM gateway exposes OpenAI-compatible `/v1` endpoints and has models such as `glm-5.1`.

2. Run the installer script:
   - Downloads `https://codearts-agent-obs-cdn.huaweicloud.com/codearts/cli_tui/latest/codearts-26.5.6-darwin-arm64.dmg`.
   - Installs `~/Applications/codearts/codearts_kernel`.
   - Creates patched `~/Applications/codearts/codearts_litellm_kernel`.
   - Creates `~/.codeartsdoer/Installers/codearts-litellm`.
   - Creates `~/.codeartsdoer/Installers/codearts-litellm-proxy`.
   - Writes CodeArts provider/model config and model cache.

3. Verify with the commands in the Quick Start. If a command fails, read [Troubleshooting](references/troubleshooting.md).

4. Explain `--yolo` clearly:
   - It is implemented in the wrapper, not the original CodeArts binary.
   - It is session-scoped: the wrapper backs up permissions, sets them to allow for the process, and restores them on exit.
   - It sets `bash_mode=always_allow`, all tool permissions to `allow`, and sandbox network policy to `allow_all`.

## References

- Read [Deployment Guide](references/deployment-guide.md) for manual installation details, patch rationale, expected files, and command examples.
- Read [Generated Files](references/generated-files.md) when auditing or repairing wrapper/proxy/config content.
- Read [Troubleshooting](references/troubleshooting.md) when model calls, permissions, language behavior, signing, or `--yolo` fail.

## Safety Notes

- Keep the original `codearts_kernel` untouched. Only patch the copy named `codearts_litellm_kernel`.
- Redact LiteLLM virtual keys in answers, logs, screenshots, and docs.
- Do not make `--yolo` persistent unless the user explicitly asks. The bundled wrapper restores permission files after `--yolo` exits.
