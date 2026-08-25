# Operations Guide

Direct MaaS Delegate Router — operations, incident response, and maintenance.

## Interpreting "Waiting for API response"

`Waiting for API response` in `claude-maas` means Claude Code has not yet
received visible text or tool content — it does **not** alone prove the API is
disconnected. GLM-5.2 may spend a long time in implicit reasoning before the
first visible delta. Use the request state to distinguish slow from stuck:

| State | Meaning | Action |
| --- | --- | --- |
| `upstream_active_hidden` | MaaS is returning reasoning; UI may still show Waiting | Continue waiting, or cancel if you choose |
| `visible_streaming` | Visible content has started flowing | Normal — wait for completion |
| `connecting` (long) | Waiting for upstream response headers | Check connect/header timeout (default 60s) |
| `idle_timeout` | Upstream went silent at the application layer | Retry — the request failed with `MAAS_IDLE_TIMEOUT` |
| `total_timeout` | Request exceeded the total wall-clock limit (default 600s) | Retry or split the task into smaller turns |

### Timeout configuration

| Boundary | Default | Env var |
| --- | ---: | --- |
| connect/header | 60s | `MAAS_CONNECT_TIMEOUT` |
| upstream idle | 180s | `MAAS_IDLE_TIMEOUT` |
| total request | 600s | `MAAS_TOTAL_TIMEOUT` |

Reasoning chunks refresh the idle timer but not the total timer. A request
that continuously receives reasoning will succeed as long as it completes within
the total timeout — it will not be killed for being "slow to show text."

### Stable error codes

| Code | Retryable | Meaning |
| --- | --- | --- |
| `MAAS_CONNECT_TIMEOUT` | yes | No response headers within connect timeout |
| `MAAS_IDLE_TIMEOUT` | yes | No upstream bytes within idle timeout |
| `MAAS_TOTAL_TIMEOUT` | yes | Exceeded total wall-clock limit |
| `MAAS_STREAM_EOF` | yes | Upstream ended without a finish reason |
| `MAAS_STREAM_PROTOCOL` | no | Unrecoverable stream structure error |
| `MAAS_CLIENT_ABORTED` | no | Client disconnected; upstream cancelled |

### Rollback

**Adapter rollback** (restore the previous adapter artifacts + restart):

```bash
bash adapter/rollback.sh
```

This restores `/opt/claude-code-maas-proxy/*.rollback` for each artifact,
verifies checksums, and restarts the service. It never touches the env file
or secrets.

**Client uninstall** (remove launchers + client config):

```bash
./scripts/uninstall.sh            # default: remove wrappers/hooks, keep key + audit
./scripts/uninstall.sh --purge    # also remove ~/.claude-maas and audit
```

The stream reliability module is a pure library (`client/stream_reliability.py`)
with no external dependencies and no HTTP listener. To roll back the Python
module, revert the commits that introduced it — no service restart, URL, or key
change is needed. The module does not modify API URL, API key, `glm-5.2`, or
1M context.

## Modes

### Mode A: OAuth Orchestrator

The user is logged into Anthropic via the official `claude`. Plain `claude`
remains the planner and orchestrator. Bounded execution work is delegated to
`claude-maas` through `delegate` or `workflow`. Premium, visual, security,
architecture, and complex-debugging work stays in the OAuth session.

### Mode B: MaaS-only

The user invokes `claude-maas` directly. No `claude /login` is required. Every
model request goes to Huawei MaaS `glm-5.2`. Image input returns a clear
`unsupported_capability` result — it is never silently rerouted.

## Install

### Unified install (recommended)

One command installs the complete stack — adapter, systemd service, client
config, and launchers — from a fresh machine:

```bash
printf '%s\n' "$HUAWEI_MAAS_API_KEY" \
  | sudo bash scripts/bootstrap.sh \
      --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
```

Prerequisites: Linux with systemd, root/sudo, Node ≥ 22, the official `claude`
CLI on PATH, **Python ≥ 3.7**.

> Python ≥ 3.7 is needed by the install-time canary probe
> (`tests/live_maas_probe.py` uses `from __future__ import annotations` and
> `dataclasses`). The runtime launcher and the installer's inline python are
> 3.6-safe — only the canary needs 3.7+. On CentOS/RHEL 8 the default
> `python3` is 3.6: `dnf install python39` (it does **not** replace the
> system `python3`) and re-run bootstrap with
> `--python /usr/bin/python3.9`. Bootstrap preflights the version before
> writing anything and fails with an explicit version message — a canary
> that cannot execute is reported as such, never as "MaaS rejected the
> request".

What bootstrap does:

| Step | Action |
| --- | --- |
| 1 | Read MaaS key from stdin (line 1; line 2 = Exa key if `--with-exa`) |
| 2 | Write `/etc/claude-code-proxy/maas.env` (root:root 0600) with real key + URL + model |
| 3 | Write the systemd unit, `systemctl daemon-reload` |
| 4 | Deploy `adapter/server.js` + `lifecycle.js` to `/opt/claude-code-maas-proxy/` (SHA-256 verified, rollback saved) |
| 5 | `systemctl enable --now` + `restart` + `is-active` check |
| 6 | Install client config (`~/.config/claude-maas/`) with dummy key + loopback URL |
| 7 | Optionally install Exa (`--with-exa`) |
| 8 | **Verify** (hard gate): poll `/status` + launcher PATH check + upstream canary. Exit 4 on failure |

The real key lives only in the root-owned env file. The client holds a dummy
`maas-local-proxy` key. Re-running is idempotent. See
`docs/PRD_UNIFIED_INSTALL_V1.md` for the full contract.

### Post-install

Bootstrap runs a hard verify gate by default (exit 4 on failure). If you skipped
it (`--skip-verify` or `--no-verify-live`), run these checks manually:

```bash
# Verify the adapter is running.
curl -s http://127.0.0.1:3000/status

# Verify the client launcher works.
claude-maas --version

# (Mode A only) Install the OAuth orchestration policy.
./scripts/configure-policy.sh

# Full release verification (live MaaS canary + Claude Code E2E).
printf '%s\n' "$HUAWEI_MAAS_API_KEY" | ./scripts/verify.sh
```

### Manual step-by-step (if bootstrap is unavailable)

If you need to install by hand, bootstrap does exactly these steps:

```bash
# 1. Write the root-owned env file (0600).
sudo install -d -m 700 /etc/claude-code-proxy
sudo bash -c 'cat > /etc/claude-code-proxy/maas.env' <<'EOF'
CLAUDE_CODE_PROXY_API_KEY=<your key>
ANTHROPIC_PROXY_BASE_URL=https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
COMPLETION_MODEL=glm-5.2
PROXY_HOST=127.0.0.1
PROXY_PORT=3000
DEBUG=false
EOF
sudo chmod 600 /etc/claude-code-proxy/maas.env

# 2. Write the systemd unit.
sudo install -d /opt/claude-code-maas-proxy
sudo tee /etc/systemd/system/claude-code-maas-proxy.service > /dev/null <<'EOF'
[Unit]
Description=Claude Code MaaS Direct Proxy (Anthropic -> Huawei MaaS)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/claude-code-maas-proxy
ExecStart=/usr/bin/node /opt/claude-code-maas-proxy/server.js
Restart=always
RestartSec=3
EnvironmentFile=/etc/claude-code-proxy/maas.env

[Install]
WantedBy=multi-user.target
EOF

# 3. Deploy adapter artifacts + reload + enable.
sudo systemctl daemon-reload
sudo bash adapter/deploy.sh
sudo systemctl enable --now claude-code-maas-proxy.service

# 4. Install client config (dummy key, loopback URL).
printf 'maas-local-proxy\n' | bash client/claude-maas-setup.sh \
  --base-url http://127.0.0.1:3000 --model glm-5.2

# 5. Verify.
curl -s http://127.0.0.1:3000/status
claude-maas --version
```

### Troubleshooting

| Symptom | Check |
| --- | --- |
| `bootstrap: service failed to start` (exit 3) | `systemctl status claude-code-maas-proxy.service` and `journalctl -u claude-code-maas-proxy.service -n 50` |
| `bootstrap: verify: FAIL` (exit 4) | Install completed but a verify gate failed — see the specific message. Rollback: `bash adapter/rollback.sh` |
| `/status not reachable` (exit 4) | Service may have crashed; check `systemctl status` and `journalctl -u <service> -n 50` |
| Launcher not on PATH (exit 4) | Add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc` or `~/.zshrc` |
| Upstream canary failed (exit 4) | Key invalid, URL wrong, or MaaS down; probe: `printf '%s\n' "$KEY" \| python3 tests/live_maas_probe.py --probe text --base-url http://127.0.0.1:3000` |
| Port 3000 in use | `ss -tlnp \| grep 3000`; use `--port 3001` and `--config-dir` to isolate |
| `--maas-url` rejected | Must be HTTPS (or localhost) and path must contain `chat/completions` |
| `claude-maas` not found | Ensure `~/.local/bin` is on PATH; bootstrap verify now checks this and exits 4 if missing |
| 401/403 from MaaS | Key invalid or revoked; rotate via bootstrap re-run |
| Config write protection (exit 2) | Bootstrap **refuses** to overwrite an existing client config when the base-url port differs (prevents test runs from clobbering production). Override with `--force`, or use `--config-dir` to install to a separate directory |

## Key rotation

```bash
printf '%s\n' "$NEW_HUAWEI_MAAS_API_KEY" \
  | sudo bash scripts/bootstrap.sh \
      --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
```

Rotation is idempotent: bootstrap atomically rewrites the env file (temp file +
rename, 0600 preserved), redeploys adapter artifacts, and restarts the service.
The client config is unchanged (same client key + loopback URL), so no `--force`
is needed. After rotation, run `./scripts/verify.sh` to confirm the new key works.

**Rotate the key after any interactive-channel exposure** (e.g. a key pasted
into a chat for testing). The deployment acceptance in this project's release
used a test key that should be rotated before production use.

### Client-key rotation (adapter auth)

`/v1/messages` requires the per-install client key (401 otherwise). To
rotate it:

```bash
sudo rm /etc/claude-code-proxy/client.key
printf '%s\n' "$HUAWEI_MAAS_API_KEY" \
  | sudo bash scripts/bootstrap.sh \
      --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
```

A fresh random key is generated and re-issued to the client in the same run.
`--legacy-auth` keeps the pre-v1.2 open behavior if an un-migrated local
client still depends on it — remove the flag once migrated.

## Uninstall

```bash
./scripts/uninstall.sh            # default: remove wrappers/hooks, keep key + audit
./scripts/uninstall.sh --purge    # explicit: also remove ~/.claude-maas and audit
```

## Local temporary profiles (e.g. claude-glm)

`client/claude-glm` is **not part of the release** (PRD
UPSTREAM_PROFILE_V1 P-B). Local-only profile wrappers live outside the
repository — e.g. `/usr/local/lib/claude-glm-local/claude-glm`, a one-line
shim: `CLAUDE_MAAS_PROFILE=claude-glm exec <repo>/client/claude-maas "$@"`.

Rules for a local profile:

- **Not in the release support matrix** — no release-notes coverage, no
  repo-tracked code (S9 stays closed: no untracked executable enters PATH
  from the repo).
- **Must meet the same security bar** as the main profile. Every backing
  listener must: match the repo build (`sha256(server.js)`), enforce
  client-key auth (anonymous and cross-profile requests → 401), and run
  under a systemd unit with the full hardening set.
  `scripts/window-check-v12.sh` (N1-G) checks all three per listener —
  a noncompliant clone fails the release gate.
- Install the backing instance with
  `bootstrap.sh --profile claude-glm --maas-url <url> --model <model> --port <p>`,
  which derives `/etc/claude-glm-proxy/`, `/opt/claude-glm-proxy/`,
  `claude-glm-proxy.service`, `~/.config/claude-glm/`, and an independent
  client key.
- Upstream behavior differences (e.g. Zhipu's tight 429 rate limiting) are
  documented in `docs/UPSTREAMS.md`.

## Auto-continue on stream protocol error (WP-B)

When a headless task dies on `API Error: stream protocol error`, the
supervisor (`scripts/auto_continue.py`) waits 100s and resumes the **same
session** with `continue`, up to 2 retries, then gives up. This automates
the single most common manual intervention (48% of historical incidents).

Env knobs:

| Var | Default | Meaning |
| --- | --- | --- |
| `MAAS_AUTO_CONTINUE` | `1` | `0` disables supervision entirely |
| `MAAS_AUTO_CONTINUE_MAX` | `2` | retry budget after the initial attempt |
| `MAAS_AUTO_CONTINUE_DELAY` | `100` | seconds to wait before each retry |

Consumers: `scripts/delegate`, `scripts/workflow`, and
`client/claude-maas-run` (ad-hoc headless tasks) — all three share the same
supervisor module; there is no second implementation.

Scope limits (by design):

- **Only stream-protocol errors retry.** 401/400/503-OVER_CAPACITY and
  client aborts are terminal — retrying them is useless or harmful.
- **429 is not covered yet**: the adapter currently masks upstream 429 as
  502 (PRD_UPSTREAM_PROFILE_V1 §D5); until that is fixed the marker is not
  reliably distinguishable.
- **Interactive TUI sessions are not supported** — the supervisor cannot
  reliably inject keystrokes into a running TUI. Headless `-p` only.
  Consequence (PRD RELEASE_V13 S3-c, known and intentional): when the
  adapter's retry chain (now 2 attempts) still cannot recover a malformed
  tool call, an **interactive** session shows the API error and needs a
  manual `continue` — there is no automatic recovery on that path. The
  observed residual after the second retry is ~0.7% of malformed-args
  events.

**Side-effect warning**: `continue` may re-run tools that already executed
earlier in the same turn. On the specific failure path covered here the
triggering tool call was never executed (the adapter degraded it before
execution — LOOP_CONTINUITY_V1 §L1-B), so the retry itself is clean at the
moment it fires; but tools completed *before* the malformed call in the same
turn can be redone. For high-side-effect tasks (publish, destructive
writes) set `MAAS_AUTO_CONTINUE=0`.

Observability: every retry decision and final outcome is appended to
`~/.claude-hybrid/auto-continue-audit.jsonl` (mode 0600) as
`{"type":"auto_continue","session_id":…,"attempt":…,"trigger":…,"outcome":…}`.
In-process counters `auto_continue_{attempted,succeeded,abandoned}` are
exposed by the module — without them you cannot tell rescue from spin.

## Release soak window (v1.2 gates)

`make window-check` evaluates the RELEASE_V12 host gates any time:

- **N1-G** — no project-derived listener besides `:3000` (guards against
  unmanaged adapter clones like the retired `claude-glm-proxy`/`server_capture`).
- **N2-G** — `:3001` capture clone stays offline, no autostart entries.
- **N4-G** — `/status` stop_reasons sum equals journald `request_end` since
  service boot (both sides reset together; fails if non-streaming logging
  drifts again).

`make window-open` stamps a 24h soak window
(`/etc/claude-code-proxy/window-v12.json`); a later `make window-check`
reports elapsed time, `request_end` volume (needs ≥200), and
`MAAS_AUTH_REJECTED` count (each must be explainable). Tag `v1.2` only when
the window has elapsed and all gates are green.

Default uninstall removes the project marker block, owned hook entry, wrapper
symlinks, and agent/skill files. It **retains** `~/.claude-maas`, the key, and
audit data, and prints their locations. `--purge` must be requested explicitly.

## Migration from claude-glm / LiteLLM

```bash
./scripts/migrate.sh --dry-run    # byte-for-byte side-effect free preview
./scripts/migrate.sh --apply      # remove owned legacy values (with backup)
```

The migrator removes **only** client-side legacy values proven by the ownership
manifest (endpoint + key fingerprint + marker ownership). It does not stop or
modify a remote LiteLLM deployment — that is a separate operational change. It
never deletes OAuth tokens, Anthropic API keys, user hooks, MCP, theme, or
preferences.

## Incident response

### MaaS endpoint protocol regression

If `verify.sh` fails on a protocol canary gate:

1. Do **not** add runtime repair middleware. The PRD explicitly prohibits
   `anthropic_stream_guard`, `anthropic_reasoning_filter`, and similar runtime
   patches.
2. Confirm the regression is repeatable with `python3 tests/live_maas_probe.py`.
3. If the defect cannot be avoided by documented Claude Code or MaaS
   configuration, open an issue and reconsider a compatibility layer via a new
   PRD (see "Revisit triggers" in the design doc).
4. Until resolved, block installation/release — the canary is a release gate.

### 429 governance

- Concurrency governor caps parallel workflow workers (default 3, hard-capped).
- Bounded `Retry-After` is honored, but a single work item has at most **two**
  total attempts.
- If 429s are sustained, reduce workflow concurrency rather than increasing
  retry counts.

### Authentication failure (401/403)

Fails immediately. No retry, no OAuth fallback. Check key rotation. The key is
never printed in error output.

**Since v1.2** a 401 from the adapter (`http://127.0.0.1:3000`) usually means
a client-key mismatch, not an upstream problem: the client's
`~/.config/claude-maas/api-key` must match `/etc/claude-code-proxy/client.key`.
Re-run bootstrap to re-issue both sides. `GET /status` shows
`client_auth: "enforced" | "legacy"` and `test_upstream` state.

### Failed delegation

- OAuth mode: after two failed attempts, the item returns
  `needs_escalation`. The orchestrator may complete it in the OAuth session and
  must not delegate it again.
- MaaS-only mode: the MaaS error is reported. Provider and model are never
  changed.

## Audit

Local JSONL audit at `~/.claude-hybrid/route-audit.jsonl` (mode 0600). Each
record contains: timestamp, task/workflow ID, route (`maas`), model
(`glm-5.2`), attempt, outcome, duration, token counts, and `fallback: false`.
It never records prompt text, tool arguments, or credentials.

`fallback` must always be `false`. Any other value indicates a broken product
invariant.

## The runtime-router rule

A general runtime HTTP router, protocol converter, or Sidecar requires a **new
approved PRD**. The architecture contract test plus dependency scanner enforce
their absence at every release.

**Narrow exception — one loopback-only adapter.** The project owns exactly one
loopback-only Node adapter (`adapter/server.js` + `adapter/lifecycle.js`) that
translates the Anthropic Messages API to the MaaS OpenAI-compatible endpoint for
`claude-maas`. It binds to `127.0.0.1` only (verified at startup), serves a
single model (`glm-5.2`), has no routing decisions, no fallback, and no gateway
dependencies. It is not a Sidecar or general HTTP router. The
`RequestLifecycleController` provides active watchdogs (connect/idle/total
timeout), cancellation, finish-aware EOF, backpressure, concurrency guard, and
sanitized `/status` observability. See
`docs/PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2.md`.

## Exa web search (claude-maas only)

Exa is isolated to the `claude-maas` profile. The key lives at
`~/.config/claude-maas/exa-api-key` (0600); the MCP definition and two tool
permissions live in `~/.claude-maas/`. Plain `claude` never loads Exa.

### Install / rotate

```bash
printf '%s\n' "$EXA_API_KEY" | ./scripts/configure-exa.sh
```

Rotation is idempotent — only the key file changes; the MCP JSON stays
byte-stable.

### Migrate off legacy plain-Claude Exa

```bash
./scripts/migrate-exa.sh --dry-run   # report only, no side effects
./scripts/migrate-exa.sh --apply     # remove the legacy shape
```

After apply, **rotate the old Exa key** in the Exa console — it was exposed in
plaintext settings and backups.

### Uninstall

```bash
./scripts/uninstall-exa.sh            # remove MCP + permissions, retain key
./scripts/uninstall-exa.sh --purge    # also delete the key file
```

### Incident response

| Scenario | Action |
| --- | --- |
| 401 / 403 | The key is invalid or revoked. Rotate via `configure-exa.sh`. No fallback. |
| 429 | Rate limited. Wait and retry; no provider switch. |
| Timeout / DNS | The tool call fails; the MaaS session remains usable. |
| Exposed key | Rotate in the Exa console, then `printf '%s\n' "$NEW" \| ./scripts/configure-exa.sh`. Historical backups are not auto-deleted; rotation invalidates them. |
| Tool drift | `verify-exa.sh` blocks release if the tool set is not exactly `web_search_exa, web_fetch_exa`. |