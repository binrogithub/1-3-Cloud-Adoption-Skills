# Security

Security posture and invariants for the Claude-MaaS Universal Delegate Router.
All claims below are derived from the repository source.

## Credential handling

| Property | Guarantee |
| --- | --- |
| MaaS key storage | `~/.config/claude-maas/api-key`, mode 0600, single line raw key |
| Key injection | `claude-maas` launcher reads the key file and exports `ANTHROPIC_AUTH_TOKEN` in the child process env |
| Key transport to installer | stdin only (never argv) |
| Key read by launcher | data read (`IFS= read -r`, never `source`/`eval`) |
| Key in argv | never |
| Key in shell profiles | never |
| Key in Git | never |
| Key in logs / audit | never |
| Key in error output | never |
| Key in process title | never |
| `status` display | endpoint host + model + irreversible fingerprint only |
| `ANTHROPIC_API_KEY` in child | unset (single credential path: `ANTHROPIC_AUTH_TOKEN`) |

The installer (`claude-maas-setup.sh`) never writes shell profiles
(`~/.bashrc`, `~/.zshrc`, …) or the plain Claude config directory (`~/.claude/`).
It only writes under `~/.config/claude-maas/` and creates `~/.local/bin` for
launcher copies/symlinks.

## Provider isolation invariants

1. **OAuth token** is held and submitted only by the official `claude` process.
2. **No MaaS `ANTHROPIC_*` env var** is set in an OAuth session.
3. **No OAuth credential** is readable by the `claude-maas` child.
4. **Image input** is never delegated to the MaaS endpoint (which lacks vision).
5. **High-risk tasks** are never force-delegated by keyword; the route hint is
   advisory.
6. **A failed-twice item** is never re-delegated.
7. **`fallback`** is always `false` in audit; any other value is a broken
   invariant.
8. **Delegation goal text** travels to `claude-maas -p` on stdin, never in argv
   (invisible to other local users via `/proc/*/cmdline`).
9. **Workflow `run_id`/`item_id`** match `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` —
   path traversal into `~/.claude-hybrid/` is structurally rejected.

## Session registry privacy

`session_registry.py` stores **only SHA-256 hashes** of the host conversation ID
and the resolved workspace path. It deliberately holds no provider credentials
and no delegated prompts. The SQLite database is mode 0600 with a 0700 parent.
Per-handle `fcntl.flock` exclusive locks prevent concurrent prompts from
crossing streams; the lock fails closed on timeout.

## Audit redaction

Audit logs (`~/.claude-hybrid/route-audit.jsonl`, mode 0600) record only: model
name, status, token counts, latency, task/workflow IDs, and truncated
verification evidence. They never record user prompt text, tool argument text,
or credentials. Workflow per-item results under
`~/.claude-hybrid/workflows/<run_id>/<item_id>.json` are likewise mode 0600.

## Destructive-operation safety

- `migrate-exa.sh` requires `--dry-run` or `--apply` explicitly; it never infers
  apply.
- `uninstall.sh` default retains key and audit; `--purge` is explicit-only.
- `configure-agents.py` refuses to overwrite an unowned skill directory unless
  `--force` is given (ownership marker file).
- All config modifications use atomic temp-file + rename, preserving 0600.
- Dry-run is byte-for-byte side-effect free.

## Supplier isolation

There is no LiteLLM, no Claude Code Router, no OpenRouter, no Sidecar, no HTTP
daemon, no listening port, and no model fallback chain. A MaaS-only failure
never triggers an Anthropic or OpenRouter request. Provider boundaries are
explicit and enforced by:

- The architecture contract test (`tests/test_architecture_contract.py`).
- The prohibited-dependency scanner (`scripts/check-prohibited-dependencies.py`).
- The Sidecar/Router negative acceptance in `verify.sh`.

## Exa credential isolation

The Exa API key is stored only at `~/.config/claude-maas/exa-api-key` (mode
0600, regular file, non-symlink, current-user-owned, single line). It never
enters static configuration JSON, argv, environment, Git, logs, evidence, URL
query parameters, or user-visible output. Its only output path is the
`headersHelper` (`scripts/exa-headers-helper.py`) controlled stdout consumed
directly by Claude Code.

The helper validates the MCP server identity (`exa-search`), the HTTPS endpoint
(`mcp.exa.ai/mcp`), and the exact tool allowlist before emitting the `x-api-key`
header. It fails closed on any mismatch — symlinks, wrong ownership, broad
modes, multiline values, unexpected server names, non-Exa URLs, or tool-set
drift — and never prints the key on a failure path.

The legacy plain-Claude Exa key was exposed in plaintext settings and backups.
After `migrate-exa.sh --apply`, rotate it in the Exa console. Historical backups
are not silently deleted; explicit `uninstall-exa.sh --purge` is a separate
destructive operation.

## Post-deployment key rotation

Re-run the installer with the new key — idempotent, atomically rewrites the
config. Rotate after any interactive-channel key exposure before any production
use.

## What this project does NOT do

- Does not read, copy, proxy, or replay Anthropic OAuth tokens.
- Does not install npm gateway packages (LiteLLM, CCR, OpenRouter).
- Does not run an HTTP daemon, listener, or protocol converter.
- Does not use systemd, pm2, docker, or any service manager.
- Does not read or restore keys from shell history.
- Does not perform hidden provider switching of any kind.
