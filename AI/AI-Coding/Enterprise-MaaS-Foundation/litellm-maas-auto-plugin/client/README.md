# Claude Code Client Setup (GLM-5.2 via LiteLLM)

This directory installs an **isolated GLM-5.2 launcher** (`claude-litellm`) that
starts a native Claude Code session pointed at a LiteLLM gateway. Native
Claude (`claude`) is never modified — the two modes are fully separate.

```
claude        → native Claude Code (OAuth/subscription/API key, untouched)
claude-litellm    → native Claude Code + isolated GLM-5.2 profile via LiteLLM
```

`claude-glm-5.2` is the one public GLM model group. Native Claude model names
(`default`, `opus`, `sonnet`, `haiku`) are NOT remapped to GLM.

## Prerequisites

- Claude Code installed (`claude --version`)
- `curl` and `python3` available
- Network access to the gateway (`http://<gateway-host>:4000`)
- A LiteLLM virtual API key for this client (restricted to `claude-glm-5.2`)

## Quick start

```bash
# Install the isolated GLM launcher (key from stdin or CLAUDE_LITELLM_KEY env)
echo "sk-your-virtual-key" | ./claude-litellm-setup.sh --base-url http://<gateway-host>:4000

# Verify the installation
./claude-litellm-setup.sh --verify

# Start a GLM session
claude-litellm [normal Claude Code arguments]
```

The gateway key is read from stdin or the `CLAUDE_LITELLM_KEY` environment
variable — it is NEVER accepted as a command-line argument. On the gateway
host itself, `--base-url` can be omitted (defaults to `http://127.0.0.1:4000`).

## What the setup writes

1. `~/.config/claude-litellm/env` (mode `0600`) — the isolated GLM profile:

   | Variable | Value | Purpose |
   |---|---|---|
   | `ANTHROPIC_BASE_URL` | gateway URL | route GLM session calls to LiteLLM |
   | `ANTHROPIC_API_KEY` | your virtual key | gateway authentication |
   | `ANTHROPIC_MODEL` | `claude-glm-5.2` | the fixed GLM model (not user-selectable) |

2. `~/.local/bin/claude-litellm` — the launcher (resolves the native `claude`
   binary by file identity, sets GLM env vars only in the child process,
   preserves the parent environment).

3. `~/.local/bin/claude-select` — the selector (`native` / `glm` / `status`).

4. `~/.config/claude-litellm/manifest.json` (mode `0600`) — ownership manifest with
   SHA-256 hashes for uninstall and verification.

**What the manifest protects:** the user's own configuration from accidental
loss during uninstall. It is an installer ownership record, not a runtime
authorization token — the `claude-litellm` launcher never reads it, and deleting
it does not stop a session from launching. The symlink, mode, owner, and
hash checks ensure `--uninstall` removes only files this installer wrote, not
user-modified or unrelated files.

This setup does NOT modify `~/.claude/settings.json`, `~/.claude.json`, or any
shell profile. Native Claude is untouched.

## Verification

```bash
./claude-litellm-setup.sh --verify
```

Checks: profile exists with mode `0600`, profile model is `claude-glm-5.2`,
launcher installed, manifest hashes match, endpoint healthy, key authenticates
against `claude-glm-5.2`, and all internal models (both Vision models, Premium,
GLM fallback) return `401`/`403` (not `200`, `500`, or timeout).

## Uninstall

```bash
./claude-litellm-setup.sh --uninstall
```

Removes only integration-owned files (verified by manifest hash). User-modified
files are preserved (hash mismatch). Never `rm -rf`s the config directory.
Native Claude settings are not touched.

## Migrating from the old global-remapping setup

If you previously used `configure-claude-code.sh` (which wrote global model
mappings into `~/.claude/settings.json`), migrate to the isolated flow:

```bash
# Preview what would be removed (model mappings auto-removed; legacy
# URL/credentials require exact ownership evidence).
./claude-litellm-migrate.sh --dry-run

# Compute the full 64-char SHA-256 of the old gateway key, then apply.
FP=$(printf '%s' "$OLD_GATEWAY_KEY" | sha256sum | cut -d' ' -f1)
./claude-litellm-migrate.sh --apply \
  --old-base-url http://127.0.0.1:4000 \
  --old-key-fingerprint "$FP"
```

The migration removes ONLY values proven to belong to the old integration:
the LiteLLM base URL, old gateway credential, and `opus`/`sonnet`/`haiku` →
GLM model mappings. It preserves unrelated env keys, OAuth state, themes, MCP
configuration, and user preferences. It does NOT delete the entire `env`
object. Repeated `--apply` is a no-op.

## Selector

```bash
claude-select native [args]   # native Claude (untouched)
claude-select glm [args]      # GLM-5.2 through LiteLLM
claude-select status          # show config + endpoint
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `claude-select status` reports launcher missing | `~/.local/bin` not on PATH | add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile |
| connection refused / timeout | wrong `--base-url`; port 4000 not reachable | check URL; gateway admin opens security group for your IP |
| `401 key_model_access_denied` | key not allowed for `claude-glm-5.2` | admin: key ACL must include `claude-glm-5.2` |
| internal model accessible in `--verify` | key ACL too permissive | admin: restrict the client key to `claude-glm-5.2` only |
| `--verify` reports ACL failure with `500`/`000` | endpoint error or timeout misread as "blocked" | check gateway health; `--verify` now requires `401`/`403` |

## Deprecated: configure-claude-code.sh

`configure-claude-code.sh` is deprecated. It no longer writes global model
mappings. If invoked, it dispatches to `claude-litellm-migrate.sh --dry-run` to
guide migration to the isolated flow. Do not use it for new installations —
use `claude-litellm-setup.sh` instead.
