# Generated Files

## Binaries

- `~/Applications/codearts/codearts_kernel`
  - Original CodeArts kernel from the DMG.
  - Keep this untouched.
- `~/Applications/codearts/codearts_litellm_kernel`
  - Patched copy used only by `codearts-litellm`.
  - Must pass `codesign -vv`.

## Launcher and Proxy

- `~/.codeartsdoer/Installers/codearts-litellm`
  - Bash wrapper.
  - Reads the LiteLLM virtual key from `$LITELLM_VIRTUAL_KEY` or macOS Keychain.
  - Exports CodeArts environment variables.
  - Starts the local proxy if port `4001` is not listening.
  - Implements session-scoped `--yolo`.

- `~/.codeartsdoer/Installers/codearts-litellm-proxy`
  - Python HTTP proxy (`ThreadingHTTPServer`, so concurrent CodeArts requests do not block each other).
  - Listens on `127.0.0.1:4001`.
  - Forwards to the configured LiteLLM upstream URL.
  - Streams the upstream response body in chunks (close-delimited HTTP/1.0) so SSE token streaming reaches the TUI incrementally instead of buffering the whole reply.
  - Replaces CodeArts auth with `Authorization: Bearer <virtual-key>`.

## CodeArts Config

- `~/.codeartsdoer/codearts_cli.json`
  - Main provider config.
  - Uses `@ai-sdk/openai-compatible`.
  - Local provider URL is `http://127.0.0.1:4001/v1`.
  - Defines and enables both provider aliases (`enabled_providers` lists both):
    - `litellm`
    - `huaweicloud-maas`

- `~/.codeartsdoer/codeagent.json`
  - Keeps `inferhubBaseUrl` and `"language": "en-us"`.
  - The binary patch handles the actual language instruction used by the CodeAgent plugin.

- `~/.cache/codeartsdoer/models-cache.json`
  - Prevents model-list hooks from failing when CodeArts expects an InferHub-style cache.

## Permission Storage

Default:

- `~/.codeartsdoer/cli-data/storage/permission/config.json`

```json
{"bash_mode":"sandbox"}
```

- `~/.codeartsdoer/cli-data/storage/sandbox/config.json`

```json
{"network_policy":"deny_all"}
```

During `--yolo`:

- `bash_mode` becomes `always_allow`.
- all tool permissions become `allow`.
- sandbox network policy becomes `allow_all`.

After `--yolo` exits, the wrapper restores previous files.

## Keychain Secret

The virtual key is stored at:

- Service: `codearts-litellm`
- Account: `virtual-key`

Commands:

```bash
security add-generic-password -U -s codearts-litellm -a virtual-key -w "sk-REPLACE_WITH_USER_KEY"
security find-generic-password -w -s codearts-litellm -a virtual-key
```
