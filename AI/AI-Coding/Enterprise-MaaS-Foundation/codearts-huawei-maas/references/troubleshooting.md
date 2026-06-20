# Troubleshooting

## Contents

- `ARGS[@]: unbound variable`
- `unknown option: --yolo`
- Language rules still forcing English
- Startup login notice
- Authentication and model-list failures
- Signing, proxy, and permission restore issues

## `ARGS[@]: unbound variable`

Cause: Bash 3.2 with `set -u` errors when an empty array is expanded. This happens when `codearts-litellm --yolo` consumes the only argument.

Fix: use a wrapper that checks `if [ "${#ARGS[@]}" -eq 0 ]` before expanding `"${ARGS[@]}"`. The bundled installer writes this safe wrapper.

## `unknown option: --yolo`

Cause: `--yolo` reached the CodeArts kernel. CodeArts 26.5.6 does not have a native `--yolo` flag.

Fix: ensure the user is running the wrapper at `~/.codeartsdoer/Installers/codearts-litellm`, not `codearts_litellm_kernel` directly. The wrapper removes `--yolo` before launching the kernel.

## Model Replies Still Say "ONLY in English"

Cause: CodeArts has two language layers:

1. `LanguageHelper.generateSystemReminderInstruction(language = "zh-cn")`
2. `Model Language Rule: You MUST respond ONLY in English...`

Patching only the system reminder is not enough. Patch both strings in `codearts_litellm_kernel`, then re-sign.

Verify:

```bash
strings ~/Applications/codearts/codearts_litellm_kernel | \
  rg 'ONLY in English|Use English by default|Chinese, Spanish'
```

There should be no active `ONLY in English` string for the `en-us` branch.

## Startup Shows "Skipping Login..." Message

Cause: CodeArts prints a `T7.info(...)` message when `CODEARTS_CLI_AK` and `CODEARTS_CLI_SK` are present.

Fix: replace that specific `T7.info(...)` statement with a padded `void 0;` in the patched kernel copy. Re-sign after patching.

## 401 or Authentication Errors

Checks:

```bash
security find-generic-password -w -s codearts-litellm -a virtual-key
lsof -nP -iTCP:4001 -sTCP:LISTEN
tail -100 /tmp/codearts-litellm-proxy.log
```

Common causes:

- Virtual key is missing or wrong.
- `codearts-litellm-proxy` is not running.
- The LiteLLM gateway URL is wrong.
- Gateway expects `/v1` but the configured upstream was not normalized.

## `models` Fails

Check:

```bash
jq empty ~/.codeartsdoer/codearts_cli.json
jq empty ~/.cache/codeartsdoer/models-cache.json
~/.codeartsdoer/Installers/codearts-litellm models
```

The provider config should include both `litellm` and `huaweicloud-maas` aliases using `@ai-sdk/openai-compatible`.

## `codesign` Failure

After every binary edit:

```bash
codesign --force --sign - ~/Applications/codearts/codearts_litellm_kernel
codesign -vv ~/Applications/codearts/codearts_litellm_kernel
```

Do not re-sign or patch `codearts_kernel`; use the patched copy only.

## Proxy Port Already Used

Check:

```bash
lsof -nP -iTCP:4001 -sTCP:LISTEN
```

If another process is using the port, stop it or update both:

- wrapper proxy port check,
- `codearts_cli.json` provider `baseURL`.

## Permission Did Not Restore After --yolo

Check:

```bash
cat ~/.codeartsdoer/cli-data/storage/permission/config.json
cat ~/.codeartsdoer/cli-data/storage/sandbox/config.json
```

Expected default:

```json
{"bash_mode":"sandbox"}
{"network_policy":"deny_all"}
```

If a previous wrapper crashed before restoration, restore those files manually or rerun the installer.
