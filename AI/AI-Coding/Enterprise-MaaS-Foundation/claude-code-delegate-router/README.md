# Claude Code Direct MaaS Delegate Router

A task-level delegate router for Claude Code that connects directly to Huawei
Cloud MaaS via the native Anthropic Messages API. **No LiteLLM, no Claude Code
Router (CCR), no Sidecar, no model fallback chain.** A single loopback-only
protocol adapter (`adapter/`) translates Anthropic↔MaaS for `claude-maas`; it
is not a general HTTP proxy or runtime router.

## Two commands

```text
claude       -> official Claude Code OAuth -> Anthropic
claude-maas  -> official Claude Code CLI -> loopback adapter -> Huawei MaaS -> glm-5.2
```

The word "router" means **task-level delegation**, not an HTTP router. The
system never silently switches provider within a session. A single
loopback-only adapter (`adapter/server.js`) translates the Anthropic Messages
API to the MaaS OpenAI-compatible endpoint for `claude-maas`; it binds to
`127.0.0.1` only and has no routing decisions.

## Quick start (one command)

```bash
# Install the complete stack — adapter, systemd service, client config, launchers.
# The MaaS key is read from stdin (never argv). The MaaS chat URL is mandatory.
printf '%s\n' "$HUAWEI_MAAS_API_KEY" \
  | sudo bash scripts/bootstrap.sh \
      --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
```

This installs:

| Layer | Where | What |
| --- | --- | --- |
| Adapter env | `/etc/claude-code-proxy/maas.env` (root:root 0600) | Real MaaS key + URL + model |
| Client key | `/etc/claude-code-proxy/client.key` (root:root 0600) | Per-install random key the client must present |
| systemd unit | `/etc/systemd/system/claude-code-maas-proxy.service` | Loopback adapter service (sandboxed) |
| Adapter code | `/opt/claude-code-maas-proxy/` | `server.js` + `lifecycle.js` |
| Client config | `~/.config/claude-maas/` (user 0600) | Client key copy + loopback URL |
| Launchers | `~/.local/bin/` | `claude-maas`, `claude-select`, `delegate`, `workflow` |

The real MaaS key lives only in the root-owned env file. The client holds a
per-install random client key; the adapter verifies it (constant-time) and
injects the real upstream key itself. Requests without the client key are
rejected with 401 — anonymous local processes cannot spend the MaaS key.
The key never enters the user's home directory, argv, or logs.

### Prerequisites

- Linux with systemd
- root or sudo access
- Node.js ≥ 22 on PATH
- The official `claude` CLI on PATH
- Python ≥ 3.7 for the install-time canary (runtime is 3.6-safe; CentOS 8:
  `dnf install python39` + `--python /usr/bin/python3.9`)

### With Exa web search (optional)

```bash
# Exa key on stdin line 2, MaaS key on line 1.
printf '%s\n%s\n' "$HUAWEI_MAAS_API_KEY" "$EXA_API_KEY" \
  | sudo bash scripts/bootstrap.sh \
      --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions \
      --with-exa
```

### Step-by-step (what bootstrap does)

1. Reads the MaaS key from stdin (line 1; line 2 if `--with-exa`).
2. Writes `/etc/claude-code-proxy/maas.env` (root:root, 0600) with the real key,
   URL, and model.
3. Writes the systemd unit and runs `systemctl daemon-reload`.
4. Deploys `adapter/server.js` + `adapter/lifecycle.js` to `/opt/claude-code-maas-proxy/`
   (via `adapter/deploy.sh`, which verifies SHA-256 and saves rollback copies).
5. Enables and starts the service.
6. Installs the client config (`~/.config/claude-maas/`) with the per-install
   client key and `anthropic_base_url=http://127.0.0.1:3000` (via
   `client/claude-maas-setup.sh`).
7. Optionally installs Exa (`--with-exa`).
8. **Verifies** (hard gate): polls local `/status`, checks the launcher is on
   PATH, and runs an upstream MaaS canary. If any check fails, bootstrap exits
   with code **4** (distinct from 3 = install step failure) and prints rollback
   guidance. Pass `--no-verify-live` to skip the upstream canary for offline
   installs, or `--skip-verify` to skip the entire gate.

### Bootstrap exit codes

| Code | Meaning |
| --- | --- |
| 0 | Install + verify succeeded |
| 2 | Missing dependency (node, systemctl) **or** write-protection refusal (existing config port differs — pass `--force`) |
| 3 | Install step failed (env file, deploy, client config) |
| 4 | Install completed but verify failed (adapter not reachable, launcher not on PATH, or upstream canary failed) |

### Additional flags

| Flag | Purpose |
| --- | --- |
| `--config-dir PATH` | Override client config dir (default `~/.config/claude-maas`; for isolation / multi-profile) |
| `--force` | Overwrite existing client config even if the base-url port differs (write protection is on by default) |
| `--verify-live` / `--no-verify-live` | Control upstream canary (default: on; off for offline installs) |
| `--user USER` | Target user for client-side install (takes priority over `$SUDO_USER`) |

Re-running is idempotent. See `docs/PRD_UNIFIED_INSTALL_V1.md` for the full
contract, `docs/PRD_UNIFIED_INSTALL_V2_CLOSURE.md` for the V2 verify hardening,
and `docs/OPERATIONS.md` for the step-by-step playbook with
troubleshooting and a manual fallback.

## Modes

### Mode A — OAuth Orchestrator

When logged into Anthropic, plain `claude` is the planner and orchestrator.
Bounded execution work (code generation, tests, docs, CI fixes, refactors,
batch workflows) is delegated to `claude-maas` via `delegate` or `workflow`.
Premium, visual, security, architecture, and complex-debugging work stays in
the OAuth session. See `assets/orchestrator-policy.md` for the full taxonomy.

After bootstrap, install the advisory routing policy:

```bash
./scripts/configure-policy.sh
```

### Mode B — MaaS-only

When not logged into Anthropic, invoke `claude-maas` directly. No
`claude /login` required. Every model request goes to Huawei MaaS `glm-5.2`.

## Image limitation

GLM-5.2 on MaaS does not support image input (returns HTTP 400). This project
does **not** fake vision capability or reroute images to another provider:

- **OAuth mode**: image tasks stay in the OAuth `claude` session, which has
  native vision.
- **MaaS-only mode**: image requests return a clear
  `unsupported_capability:image` result.

## No Sidecar / no runtime router

This is a product invariant, enforced by the architecture contract test and
the prohibited-dependency scanner at every release:

- No LiteLLM, no `@musistudio/claude-code-router` / CCR, no OpenRouter.
- No Vision / Premium / Tool-Repair Sidecar.
- No model fallback chain (no GLM-5.1, no cross-provider fallback).
- No runtime SSE / `[DONE]` / thinking / forced-tool repair middleware.
- `fallback` is always `false` in the audit log.

**Narrow exception — one loopback-only protocol adapter.** The project owns
exactly one loopback-only Node adapter (`adapter/server.js` +
`adapter/lifecycle.js`) that translates the Anthropic Messages API to the
Huawei MaaS OpenAI-compatible endpoint for `claude-maas`. It binds to
`127.0.0.1` only (verified at startup, refuses non-loopback), serves a single
model (`glm-5.2`), has no routing decisions, no fallback, and no gateway
dependencies. It is **not** a Sidecar, model router, or HTTP proxy in the
banned sense. See `docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md`
for the authorizing PRD and `adapter/` for the source.

A general runtime HTTP router, second listener, or Sidecar requires a **new
approved PRD**.

## Key rotation

```bash
# Re-run bootstrap with the new key — idempotent, atomically rewrites the env file.
printf '%s\n' "$NEW_HUAWEI_MAAS_API_KEY" \
  | sudo bash scripts/bootstrap.sh \
      --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
```

Rotation is idempotent (atomic temp-file + rename, 0600 preserved, service
restarted). Rotate after any interactive-channel key exposure. See
`docs/SECURITY.md`.

To rotate the **client key** (the one the local client presents to the
adapter): delete `/etc/claude-code-proxy/client.key` and re-run bootstrap —
a fresh random key is generated and re-issued to the client in the same run.

## Exa web search (claude-maas only, isolated)

`claude-maas` can search the web and fetch pages through the official Exa
remote HTTP MCP. Exa is **isolated to the MaaS-only profile** — plain `claude`
never loads it.

- Endpoint: `https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa`
- Server name: `exa-search` (user-scope MCP in `~/.claude-maas/.claude.json`).
- Tools: exactly `web_search_exa` and `web_fetch_exa` (no advanced/agent/deprecated).
- Key: stored at `~/.config/claude-maas/exa-api-key` (mode 0600), never in JSON.
- Auth: a `headersHelper` (`scripts/exa-headers-helper.py`) emits the
  `x-api-key` header at connect time; the key never enters static config.

```bash
# Install / rotate the Exa key (key via stdin, never argv)
printf '%s\n' "$EXA_API_KEY" | ./scripts/configure-exa.sh

# Retire the legacy plain-Claude Exa config (dry-run first, then apply)
./scripts/migrate-exa.sh --dry-run
./scripts/migrate-exa.sh --apply

# Verify (offline gates + live search/fetch canary)
make verify-exa-offline
printf '%s\n' "$EXA_API_KEY" | make verify-exa-live

# Uninstall (default retains the key; --purge also deletes it)
./scripts/uninstall-exa.sh
./scripts/uninstall-exa.sh --purge
```

After migrating off the old plain-Claude Exa key, **rotate it** in the Exa
console — the old key was exposed in plaintext settings/backups. See
`docs/PRD_EXA_SEARCH_V1.md` for the full contract.

## Uninstall

```bash
./scripts/uninstall.sh            # remove wrappers/hooks, keep key + audit
./scripts/uninstall.sh --purge    # also remove ~/.claude-maas and audit
```

See `docs/OPERATIONS.md` for migration from claude-glm/LiteLLM, incident
response, and 429 governance.

## Verification

```bash
make verify-offline   # prohibited-dependency scan + full test suite
printf '%s\n' "$HUAWEI_MAAS_API_KEY" | make verify-live   # live MaaS canary + E2E
```

`verify-live` runs 8 gates, including `auth-enforcement` (an anonymous
messages request against the deployed adapter must be rejected with 401).

## Project layout

```text
adapter/         loopback protocol adapter (server.js, lifecycle.js, deploy/rollback)
client/          launchers and installer (claude-maas, claude-select, setup)
scripts/         bootstrap, delegate, workflow, verify, migrate, uninstall, policy
assets/          JSON schemas and the orchestrator policy document
tests/           pytest suite, SSE fixtures, live probe, E2E probe
docs/            PRD, design, implementation plan, operations, security
```

See `docs/PRD.md` for full product requirements and
`docs/PRD_UNIFIED_INSTALL_V1.md` for the unified installer contract.