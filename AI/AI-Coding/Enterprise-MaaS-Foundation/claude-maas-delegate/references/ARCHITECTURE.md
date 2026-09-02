# Architecture

This document describes the **implemented** components of the Claude-MaaS
Universal Delegate Router and the invariants they enforce. Claims are derived
from the repository source. Where a capability is planned but not yet
implemented, it is marked **(planned)**.

## Component map

```text
client/
  claude-maas            Isolated launcher (bash). Reads key + config, execs real claude.
  claude-maas-run        Headless run wrapper used by auto-continue.
  claude-maas-setup.sh   Writes ~/.config/<profile>/ config (key 0600, config.json 0600).
  claude-select          Profile selector.

scripts/
  install.sh             User-facing universal installer (interactive + --non-interactive).
  configure-agents.py    Installs additive Skill + policy into host agents.
  maas-delegate          Session-aware structured delegation command (Python).
  delegate               Structured single-task delegation (Python; JSON brief on stdin).
  delegate_core.py       Importable core shared by maas-delegate and workflow.
  session_registry.py    SQLite-backed session ownership (hashes only, fcntl locks).
  workflow               Fan-out runner (fanout / suborchestrate modes).
  auto_continue.py       Stream-protocol-error auto-resume supervisor.
  verify-skill-release.py  Self-contained release-package verifier.
  uninstall.sh           Precise uninstall (default retains key + audit; --purge).
  configure-exa.sh, migrate-exa.sh, uninstall-exa.sh, verify-exa.sh
                         Exa web-search lifecycle (isolated to MaaS-only profile).
  check-prohibited-dependencies.py  Prohibited-dependency scanner.

skills/claude-maas-delegate/
  SKILL.md               Additive delegation Skill installed into host agents.
  references/            routing-policy, brief-contract, result-contract.
  scripts/detect-host.sh Returns a host hint (codex/copilot/cursor/opencode/generic).

assets/                  brief-schema.json, manifest-schema.json, orchestrator-policy.md.
tests/                   pytest suite + architecture contract test + live probes.
```

## The launcher: `claude-maas`

The launcher is the only thing that stands between the user and the upstream.
Its implemented behavior (`client/claude-maas`):

1. Derives all paths from a single profile name (`CLAUDE_MAAS_PROFILE`,
   default `claude-maas`): `~/.config/<profile>/config.json`,
   `~/.config/<profile>/api-key`, `~/.<profile>/` as `CLAUDE_CONFIG_DIR`.
2. Locates the real `claude` binary on PATH, **excluding itself** by resolved
   path to avoid recursion.
3. Exposes a `resolve-binary` subcommand that prints the canonical CLI path and
   its SHA-256 digest without loading the key or making a model request.
4. Validates that the config directory and config file are not wider than 0700 /
   0600; refuses to read group/world-readable config.
5. Reads `config.json` via `python3` stdlib `json.load` for `anthropic_base_url`,
   `model`, `context_tokens`, `max_output_tokens`.
6. Reads the API key file with `IFS= read -r` (data read, never `source`/`eval`),
   requires mode exactly 0600.
7. Exports child-only environment: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`,
   `ANTHROPIC_MODEL`, and the default Opus/Sonnet/Haiku model vars all set to
   the configured model, `CLAUDE_CONFIG_DIR`, plus flags that disable the
   terminal-title background request and remove the print-mode wait ceiling.
8. Unsets `ANTHROPIC_API_KEY`, `CLAUDE_CODE_USE_BEDROCK`,
   `CLAUDE_CODE_USE_VERTEX` — exactly one auth source.
9. Inserts `--model <model>` as the first argument for interactive/`-p` use;
   suppresses it for `--version`, `doctor`, and `mcp` subcommands.
10. `exec`s the real `claude` binary. The launcher leaves the process table.

**Invariant: no service, no port, no protocol conversion.** The launcher is a
pure environment-injection wrapper followed by `exec`.

## Direct MaaS invariants

These are enforced by code and by the architecture contract test
(`tests/test_architecture_contract.py`) plus the prohibited-dependency scanner
(`scripts/check-prohibited-dependencies.py`), both run at every release:

| Invariant | Enforcement |
| --- | --- |
| No LiteLLM, CCR, OpenRouter runtime dependency | Scanner + contract test over `client/*` and `scripts/*` |
| No Sidecar / HTTP daemon / loopback listener / systemd | Architecture contract test; no listener code exists |
| No model fallback chain | `MODEL = "glm-5.2"` constant in `delegate` and `workflow`; `fallback` always `false` in audit |
| Single credential path | Launcher unsets `ANTHROPIC_API_KEY`; only `ANTHROPIC_AUTH_TOKEN` is set |
| Image input never delegated to MaaS | `delegate` rejects image briefs before launching the client |

A general runtime HTTP router, listener, or Sidecar requires a new approved PRD.

## Delegation: `delegate` and `maas-delegate`

### `delegate` — single-task delegation

Implemented behavior (`scripts/delegate`):

- Accepts a JSON brief on stdin (or `--file`), validates it against
  `assets/brief-schema.json` using a manual stdlib validator (no `jsonschema`).
- Runs a single bounded `claude-maas -p` invocation, then executes the brief's
  `acceptance` command with an explicit cwd and timeout.
- **Hard clamps:** `max_attempts` clamped to 1..2; `max_turns` clamped to 1..64.
  The caller cannot raise these.
- **Retry policy:** 401/403 fail immediately (no retry). 429 honors a bounded
  `Retry-After` (max 60s). 5xx/timeout get one retry. Total attempts never
  exceed 2.
- **Write-op guard:** empty `scope` on a write task type
  (`code_generation`, `unit_test_generation`, `bug_fix`, `refactor`, `ci_fix`,
  `format_migration`) is rejected as `invalid_brief`.
- Writes a redacted JSONL audit record (model, status, token counts, latency,
  task/workflow IDs, truncated verification evidence — never brief text, tool
  arguments, or credentials). Audit file mode 0600.
- Does **not** inject `--allowedTools` by default; only the live gate scripts
  widen the toolbox in their own process env.

### `maas-delegate` — session-aware delegation

Implemented behavior (`scripts/maas-delegate`):

- Subcommands: `run`, `session new`, `session status`, `session close`,
  `session gc`, `doctor`.
- `run` reads a JSON brief on stdin, acquires a session lease, takes a per-handle
  `fcntl` lock, calls `delegate_core.run` with the Claude session ID and resume
  flag, records the outcome, and prints one JSON object.
- `doctor` checks whether the client binary is on PATH.
- Prints exactly one structured JSON response with a shell-meaningful exit code.
- Status values include `success`, `session_busy`, `session_conflict`,
  `invalid_brief`, `client_missing`, `needs_escalation`.

## Session reuse: `session_registry.py`

Implemented behavior:

- SQLite-backed map from a host conversation to a Claude Code session, stored at
  `$XDG_STATE_HOME/claude-maas-delegate/state.sqlite` (or
  `~/.local/state/claude-maas-delegate/`). Database mode 0600, parent 0700.
- Stores **only SHA-256 hashes** of the host conversation ID and the resolved
  workspace path — never the raw conversation ID, never credentials, never
  delegated prompts.
- `acquire(owner_agent, conversation_key, workspace)`: if the
  `(owner_agent, conversation_hash)` pair exists and the workspace hash matches
  and the session is active, returns the existing Claude session ID with
  `reused=True`; otherwise creates a fresh handle (`dlg_<token>`) and a new
  UUID session ID.
- `acquire_handle(handle, ...)`: reuses an explicit handle after checking agent
  and workspace ownership; raises `SessionConflict` on mismatch.
- Per-handle `fcntl.flock` exclusive lock (`session_lock`) with a bounded timeout
  (default 30s) prevents concurrent prompts from crossing streams in one session.
  Fails closed on timeout as `SessionBusy`.
- `close` marks a handle closed (record retained); `gc` deletes closed records
  older than N days; `record_outcome` stores a non-sensitive terminal result.

**Invariant:** one host conversation maps to one Claude session; different host
conversations use different IDs. Concurrent prompts through one handle are
rejected, not interleaved.

## Workflow fan-out: `workflow`

Implemented behavior (`scripts/workflow`):

- Reads a workflow manifest (JSON stdin or `--file`), validates against
  `assets/manifest-schema.json` (manual, stdlib only).
- **`fanout` mode:** runs each item brief in an isolated delegate worker via
  `ThreadPoolExecutor` with hard-capped concurrency (default 3, max 8). Item
  scopes must be pairwise disjoint — enforced before any thread is created.
  Per-item results written to `~/.claude-hybrid/workflows/<run_id>/<item_id>.json`
  (mode 0600). Results array is in input order. If `failed/total > 0.30` the run
  aborts with status `reclassify_premium`.
- **`suborchestrate` mode:** passes the whole brief to a single bounded
  `claude-maas -p` invocation.
- `run_id`/`item_id` validated against `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` —
  path traversal into `~/.claude-hybrid/` is structurally rejected.
- Audit records `route=maas`, `model=glm-5.2`, `fallback=false`; never stores
  brief text or tool arguments.

## Auto-continue supervisor: `auto_continue.py`

Implemented behavior:

- Wraps a headless `claude-maas -p` invocation. When the session ends on the
  structured `API Error: stream protocol error` marker, waits
  `MAAS_AUTO_CONTINUE_DELAY` (default 100s) and retries with
  `--resume <same-session-id> -p "continue"`, up to
  `MAAS_AUTO_CONTINUE_MAX` (default 2) retries.
- Detection reads the session JSONL's last assistant record with
  `isApiErrorMessage === true`; it never greps stdout (the error string can
  appear in model prose).
- First attempt carries `--session-id <uuid>`; retries carry `--resume <same uuid>`.
  Never uses `--continue` (its "most recent session" semantics cross-talk under
  concurrency).
- Only stream-protocol errors are retried. 401/400/503/client-abort are terminal.
- **(planned, not yet implemented)** 429 is explicitly **not** a supervised
  trigger yet — pending marker stability confirmation in the field.
- Interactive TUI is out of scope — headless `-p` only.

## Exa web search (optional, isolated)

Implemented behavior:

- `claude-maas` can search the web via the official Exa remote HTTP MCP,
  isolated to the MaaS-only profile (plain `claude` never loads it).
- Server name `exa-search`; endpoint `https://mcp.exa.ai/mcp`; exact tool
  allowlist `web_search_exa`, `web_fetch_exa`.
- Exa key stored at `~/.config/claude-maas/exa-api-key` (0600), never in static
  JSON. A `headersHelper` (`scripts/exa-headers-helper.py`) emits the `x-api-key`
  header at connect time and fails closed on any identity/mode/URL mismatch.

## Verification gates

`scripts/verify-skill-release.py` validates the self-contained release package:
manifest/schema integrity, exact file set, SHA-256 hashes, executable modes,
and forbidden content/path patterns (secrets, absolute home paths, git metadata,
caches). The architecture contract test and prohibited-dependency scanner
enforce the no-gateway invariants at every release.
