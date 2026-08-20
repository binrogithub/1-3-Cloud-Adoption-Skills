# Security

Direct MaaS Delegate Router — security posture and invariants.

## Credential handling

| Property | Guarantee |
| --- | --- |
| Real MaaS key storage | `/etc/claude-code-proxy/maas.env`, root:root, mode 0600 |
| Client-side key | `~/.config/claude-maas/api-key` = `maas-local-proxy` (dummy) |
| Key injection | adapter `getAuthKey()` falls through to env-file key when client sends dummy |
| Key transport to installer | stdin only (never argv) |
| Key read by adapter | env file loaded at startup (never `source`/`eval`) |
| Key in argv | never |
| Key in shell profiles | never |
| Key in user home | never (only the dummy `maas-local-proxy` lives there) |
| Key in Git | never |
| Key in logs / audit | never |
| Key in error output | never |
| Key in process title | never |
| `status` display | endpoint host + model + irreversible fingerprint only |
| `ANTHROPIC_API_KEY` in child | unset (single credential path: `ANTHROPIC_AUTH_TOKEN`) |

## Isolation invariants

1. **OAuth token** is held and submitted only by the official `claude` process.
2. **No MaaS `ANTHROPIC_*` env var** is set in an OAuth session.
3. **No OAuth credential** is readable by the `claude-maas` child.
4. **Image input** is never delegated to the MaaS endpoint (which lacks vision).
5. **High-risk tasks** are never force-delegated by keyword; the route hint is
   advisory.
6. **A failed-twice item** is never re-delegated.
7. **`fallback`** is always `false` in audit; any other value is a broken
   invariant.

## Audit redaction

Audit logs (`~/.claude-hybrid/route-audit.jsonl`, mode 0600) record only:
model name, status, token counts, latency, task/workflow IDs, and truncated
verification evidence. They never record user prompt text, tool argument text,
or credentials.

## Destructive-operation safety

- `migrate.sh` requires `--dry-run` or `--apply` explicitly; it never infers
  apply.
- `uninstall.sh` default retains key and audit; `--purge` is explicit-only.
- All modifications create a `.bak` backup first.
- Dry-run is byte-for-byte side-effect free.

## Supplier isolation

There is no LiteLLM, no Claude Code Router, no OpenRouter, no Sidecar, and no
model fallback chain. A MaaS-only failure never triggers an Anthropic or
OpenRouter request. Provider boundaries are explicit and enforced by:

- The architecture contract test (`tests/test_architecture_contract.py`).
- The prohibited-dependency scanner (`scripts/check-prohibited-dependencies.py`).
- The Sidecar/Router negative acceptance in `verify.sh`.

A single loopback-only protocol adapter (`adapter/server.js`) translates
Anthropic↔MaaS for `claude-maas`. It binds to `127.0.0.1` only (verified at
startup, refuses non-loopback), never exposes secrets in `/status` or error
responses, and is not a Sidecar or general HTTP router. See
`docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md`.

## Post-deployment key rotation

A test key was provided via an interactive channel during development. Per PRD
§11, **rotate this key after deployment acceptance** before any production use.

## What this project does NOT do

- Does not read, copy, proxy, or replay Anthropic OAuth tokens.
- Does not install npm gateway packages (LiteLLM, CCR, OpenRouter).
- Does not use pm2, docker, or a second listener. The single loopback adapter
  runs as one systemd service (the narrow exception documented above).
- Does not read or restore keys from shell history.
- Does not perform hidden provider switching of any kind.

## Exa credential isolation

The Exa API key is stored only at `~/.config/claude-maas/exa-api-key` (mode
0600, regular file, non-symlink, current-user-owned, single line). It never
enters static configuration JSON, argv, environment, Git, logs, evidence, URL
query parameters, or user-visible output. Its only output path is the
`headersHelper` (`scripts/exa-headers-helper.py`) controlled stdout consumed
directly by Claude Code.

The helper validates the MCP server identity (`exa-search`), the HTTPS endpoint
(`mcp.exa.ai/mcp`), and the exact tool allowlist before emitting the
`x-api-key` header. It fails closed on any mismatch — symlinks, wrong
ownership, broad modes, multiline values, unexpected server names, non-Exa
URLs, or tool-set drift — and never prints the key on a failure path.

The legacy plain-Claude Exa key was exposed in plaintext settings and backups.
After `migrate-exa.sh --apply`, rotate it in the Exa console. Historical
backups are not silently deleted; explicit `uninstall-exa.sh --purge` is a
separate destructive operation.