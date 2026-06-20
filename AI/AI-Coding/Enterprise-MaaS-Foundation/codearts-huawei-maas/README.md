# codearts-huawei-maas

Deploy the Huawei **CodeArts** CLI on macOS arm64 and add a side-by-side `codearts-litellm` command that routes CodeArts through an OpenAI-compatible **LiteLLM** gateway (e.g. Huawei Cloud MaaS behind LiteLLM).

The original `codearts_kernel` is left untouched. All changes target a patched copy, `codearts_litellm_kernel`, plus a local auth-injecting proxy and CodeArts config.

```text
codearts-litellm
  -> codearts_litellm_kernel (patched copy)
  -> local proxy http://127.0.0.1:4001/v1   (injects Authorization: Bearer <virtual-key>)
  -> LiteLLM gateway /v1
  -> glm-5.1 / claude-opus / deepseek / ...
```

## Why A Wrapper Is Needed

CodeArts ships wired to Huawei's InferHub provider, defaults to Chinese, prints a login notice, and has no `--yolo` flag. This skill:

- swaps the provider to `@ai-sdk/openai-compatible` and points it at a local proxy,
- injects the LiteLLM virtual key per-request (kept in macOS Keychain, never in config),
- patches the kernel's language rules (English by default; Chinese/Spanish/Brazilian Portuguese on request) with **equal-length, binary-safe** edits and re-signs,
- adds a session-scoped `--yolo` that relaxes permissions only for that run and restores them on exit.

## Quick Start

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

Never commit a real gateway host or virtual key. Store the key in macOS Keychain (service `codearts-litellm`, account `virtual-key`) or pass it once to the installer.

## Layout

- `SKILL.md` — trigger description, workflow, safety notes.
- `scripts/setup_codearts_litellm.sh` — automated macOS arm64 installer.
- `references/deployment-guide.md` — from-zero deployment, patch rationale, verification.
- `references/generated-files.md` — every file/config the installer produces.
- `references/troubleshooting.md` — fixes for `--yolo`, language rules, auth, signing, model list, proxy.
- `agents/openai.yaml` — UI metadata.

## Notes

- macOS arm64 only. Requires `curl`, `hdiutil`, `python3`, `perl`, `codesign`, `security`, `jq`, `lsof`.
- The local proxy is threaded and streams responses, so concurrent CodeArts requests don't block and SSE tokens reach the TUI incrementally.
- The gateway is reached over plain HTTP by default; keep it on a trusted network or front it with TLS.
