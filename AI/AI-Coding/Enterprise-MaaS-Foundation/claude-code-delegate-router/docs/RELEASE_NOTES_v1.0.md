# Release Notes — v1.0

**Date:** 2026-08-21
**Branch:** `feat/direct-maas-router` → `main`
**Commits:** 40 (from `20104ae` to `0546b6c`)

## Summary

First release of the Claude Code Direct MaaS Delegate Router. This project
replaces the LiteLLM/CCR/OpenRouter proxy chain with a single loopback adapter
that translates Anthropic Messages API to Huawei MaaS OpenAI-format SSE, plus
an isolated `claude-maas` launcher that injects MaaS credentials without
touching the user's plain `claude` session.

## What's in the box

### Core adapter (`adapter/`)
- **`server.js`** — loopback HTTP server translating Anthropic ↔ OpenAI SSE.
  Stream reliability: idle/total timeouts, concurrency guard, size limits,
  cancellation, error codes, synthetic thinking blocks.
- **`lifecycle.js`** — `RequestLifecycleController` with 11-state machine,
  active watchdogs, block pairing enforcement.
- **`deploy.sh` / `rollback.sh`** — artifact deploy with SHA-256 verification
  and rollback.

### Unified installer (`scripts/bootstrap.sh`)
- One command installs the full stack: env file (root 0600), systemd unit,
  adapter artifacts, client config (dummy key + loopback URL), optional Exa.
- Credential topology: real key in `/etc/claude-code-proxy/maas.env`, client
  holds dummy `maas-local-proxy`, adapter injects real key via `getAuthKey()`.
- Write protection: refuses to clobber existing client config when port differs
  (prevents the 2026-08-20 port-38123 incident class).

### Client launcher (`client/claude-maas`)
- Isolated launcher that injects MaaS endpoint + Bearer token + glm-5.2 model
  into the child `claude` process. Never touches `~/.claude/` or shell profiles.

### Verification (`scripts/verify.sh`)
- 7 gates: config-modes, direct-api, token-only-claude-cli, tool-round-trip,
  plain-claude-isolation, prohibited-dependency-scan, launcher-entry.
- The launcher-entry gate (Gate 7) tests through the `claude-maas` launcher,
  not just the protocol port — catches config corruption that protocol probes
  miss.

### Thinking wait visibility
- When upstream sends `reasoning_content`, adapter emits synthetic thinking
  blocks with placeholder `·` deltas so Claude Code shows "thinking" UI instead
  of 20s of silence. Zero reasoning leakage.
- `MAAS_THINKING_DISABLED=1` kill switch for mutation testing.
- `/status` exposes `thinking_visibility` field (enabled/disabled).

## PRDs delivered

| PRD | Status |
| --- | --- |
| `PRD_MAAS_STREAM_WAIT_RELIABILITY_V1` | Delivered |
| `PRD_MAAS_STREAM_RELIABILITY_PRODUCTION_CLOSURE_V2` | Delivered |
| `PRD_UNIFIED_INSTALL_V1` | Delivered |
| `PRD_UNIFIED_INSTALL_V2_CLOSURE` | Delivered |
| `PRD_UNIFIED_INSTALL_V3_RELEASE_GATE` | Delivered |
| `PRD_THINKING_WAIT_VISIBILITY_V1` | Delivered |
| `PRD_THINKING_WAIT_VISIBILITY_V1_CLOSURE` | Delivered |
| `PRD_CLIENT_CONFIG_PROTECTION_V1` | Delivered |
| `PRD_EXA_SEARCH_V1` | Delivered |
| `PRD_RELEASE_CLOSURE_V1` | Delivered |

## Test results

- **652 tests pass** (offline suite)
- **Prohibited dependency scan:** clean (no LiteLLM/CCR/OpenRouter)
- **Working tree:** clean

## Security invariants

- The OAuth token is held and submitted only by the official `claude` process.
- `claude-maas` never inherits or reads OAuth credentials.
- `claude-maas` never touches `~/.claude/` or shell profiles.
- The `fallback` field in audit records is always `false`.
- No model other than `glm-5.2` on the MaaS endpoint.
- Real MaaS key never in user home, argv, stdout, stderr, or logs.

## Known limitations

- Image input not supported (glm-5.2 limitation). Rejected with
  `unsupported_capability:image` at delegation time.
- No multi-host, k8s, or non-systemd init in v1.
- Exa web search is optional (`--with-exa`).

## Install

```bash
printf '%s\n' "$HUAWEI_MAAS_API_KEY" \
  | sudo bash scripts/bootstrap.sh \
      --maas-url https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions
```

See `docs/OPERATIONS.md` for the full step-by-step playbook.

## Post-v1.0 doc fixes

- `OPERATIONS.md` key rotation: corrected stale `install.sh` reference to
  `bootstrap.sh --maas-url`.
- `OPERATIONS.md` troubleshooting: updated config-overwrite row from "prints a
  WARNING" to "REFUSES (exit 2)" to match the delivered write-protection behavior.
- `README.md` exit codes: code 2 now documents both missing-dependency and
  write-protection refusal.
- `README.md` flags table: added `--force` (was missing from the table).
- `README.md` verify-live: shows key-on-stdin (was a bare `make verify-live`).
- `PRD.md` §13.1: added a note pointing to `bootstrap.sh` as the delivered
  unified installer, keeping the original design interface as historical reference.
