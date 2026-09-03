# Operations

Commands, troubleshooting, and maintenance for the Claude-MaaS Universal
Delegate Router. `claude-maas` direct-connects to the MaaS Anthropic endpoint —
no adapter, no systemd, no loopback proxy.

## Commands

### `claude-maas` — isolated launcher

```bash
claude-maas                 # interactive session against the MaaS model
claude-maas -p "goal"       # headless single prompt
claude-maas resolve-binary  # print canonical CLI path + SHA-256 digest (no key loaded)
claude-maas --version       # passthrough (no --model inserted)
claude-maas doctor          # passthrough
claude-maas mcp             # passthrough
```

The launcher injects `--model <configured-model>` for interactive/`-p` use and
suppresses it for `--version`, `doctor`, and `mcp`.

### `maas-delegate` — session-aware delegation

```bash
# Run a bounded task (JSON brief on stdin). Reuses or creates a session.
printf '%s' "$brief_json" | maas-delegate run \
  --agent cursor --conversation-id "$NATIVE_ID" --workspace "$PWD"

# Task-scoped tools — set DELEGATE_ALLOWED_TOOLS on the maas-delegate side:
# Read-only (review, repo_summary):
printf '%s' "$brief_json" | DELEGATE_ALLOWED_TOOLS='Read,Bash,Glob,Grep' \
  maas-delegate run --agent cursor --conversation-id "$NATIVE_ID" --workspace "$PWD"
# Implementation (code_generation, bug_fix, refactor):
printf '%s' "$brief_json" | DELEGATE_ALLOWED_TOOLS='Read,Write,Edit,Bash,Glob,Grep' \
  maas-delegate run --agent cursor --conversation-id "$NATIVE_ID" --workspace "$PWD"

# Use an explicit handle instead of a conversation ID:
printf '%s' "$brief_json" | maas-delegate run \
  --agent cursor --handle "$HANDLE" --workspace "$PWD"

# Session lifecycle:
maas-delegate session new  --agent cursor --conversation-id "$NATIVE_ID" --workspace "$PWD"
maas-delegate session status --handle "$HANDLE"
maas-delegate session close --handle "$HANDLE"
maas-delegate session gc --older-than-days 30

# Health check:
maas-delegate doctor
```

The `task_type` must be a valid enum value: `code_generation`,
`unit_test_generation`, `bug_fix`, `refactor`, `docs`, `review`, `ci_fix`,
`format_migration`, `repo_summary`, `batch`, `suborchestrate` (`image` is
rejected). The `acceptance` field is a pure shell command that exits 0 on
success. Never use `IS_SANDBOX` or `--dangerously-skip-permissions`.

Every command prints exactly one JSON object. Key fields: `status`,
`delegation_handle`, `claude_session_id`, `session_reused`. Status values:
`success`, `session_busy`, `session_conflict`, `invalid_brief`,
`client_missing`, `needs_escalation`, `budget_exhausted`, `capacity_error`,
`unsupported_capability`.

- `session_busy` — another prompt owns the handle; wait or use separate work.
- `session_conflict` — the handle belongs to another host or workspace; do not
  bypass it.
- `needs_escalation` / `invalid_brief` / `unsupported_capability` — return
  control to the host agent. After a task has failed twice, keep it local.

### `delegate` — single-task delegation

Accepts a JSON brief on stdin (or `--file`), validates it, runs one bounded
`claude-maas -p` invocation, executes the brief's `acceptance` command, and
writes a redacted audit record. `max_attempts` is clamped to 1..2 and
`max_turns` to 1..64; the caller cannot raise these.

### `workflow` — fan-out runner

```bash
printf '%s' "$manifest_json" | workflow fanout        # parallel bounded workers
printf '%s' "$manifest_json" | workflow suborchestrate # single bounded invocation
```

`fanout` runs each item in an isolated delegate worker with hard-capped
concurrency (default 3, max 8). Item scopes must be pairwise disjoint. If
`failed/total > 0.30` the run aborts with `reclassify_premium`.

## Interpreting "Waiting for API response"

`Waiting for API response` in `claude-maas` means Claude Code has not yet
received visible text or tool content — it does **not** alone prove the API is
disconnected. The configured model may spend a long time in implicit reasoning
before the first visible delta. A long wait is expected for reasoning-heavy
tasks; continue waiting or cancel if you choose.

### Timeout behavior (source-backed)

There is no fixed 60/180/600-second request limit and no `MAAS_*` timeout
environment variable in the executable runtime scripts. Per-attempt timeouts
are adaptive and bounded:

| Component | Default | Effective timeout |
| --- | ---: | --- |
| `maas-delegate run` | `--timeout 0` (automatic) | `adaptive_timeout` in `delegate` |
| `delegate` (timeout = 0) | automatic | `min(7200, max(900, max_turns × 120))` seconds |
| `workflow` fanout items | `DEFAULT_ITEM_TIMEOUT` | 1800 seconds per item |

When `maas-delegate` is invoked with its default `--timeout 0`, `delegate`
computes an adaptive budget: **900 seconds minimum**, `max_turns × 120` seconds
scaled by the brief's turn count, and **7200 seconds (2 hours) maximum**. A
caller may pass an explicit `--timeout` to override this with a fixed value.

### Print-mode background-work ceiling

`claude-maas` exports two child-environment flags that prevent Claude Code's own
print-mode timer from cutting off active background work:

- `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` — suppresses the optional background
  terminal-title request that would select a helper model the MaaS endpoint does
  not expose.
- `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` — removes Claude Code's print-mode
  600-second wait ceiling.

With the ceiling removed, active background work (e.g. a running workflow) is
allowed to finish instead of being killed at the 600-second mark. Background work
itself remains enabled.

## Upstream switching

Switching the configured upstream is a client configuration change. Re-run the
bundled installer with the replacement endpoint, model, and key; no service
restart is needed.

```bash
printf '%s\n' "$KEY" | ./scripts/install.sh --non-interactive \
    --api-url https://open.bigmodel.cn/api/paas/v4/anthropic --model glm-5.3
```

The self-contained package maintains one active MaaS configuration per user.
Separate concurrent upstream profiles are not part of this release package.

## Zhipu 429 mitigation

On the Zhipu BigModel upstream, consecutive requests trip the account rate limit
routinely (~80s to recover). This is an account-tier property, not a code defect.

- `claude-maas` passes upstream `429` through to the client as-is, so Claude
  Code can back off rather than treat it as an outage.
- For headless tasks, the auto-continue supervisor waits 100s before resuming on
  stream-protocol errors. **Note:** 429 is not yet a supervised trigger (planned
  pending marker stability confirmation).
- Prefer the MaaS-backed profile for batch/fan-out workloads.

## Rollback / uninstall

```bash
./scripts/uninstall.sh            # remove wrappers/hooks/skills, keep key + audit
./scripts/uninstall.sh --purge    # also remove ~/.claude-maas and audit data
```

Default mode removes only project-owned items and retains the key and audit.
`--purge` is explicit-only. Uninstall never removes Claude Code itself, OAuth
tokens, user hooks, MCP, themes, or preferences. It also cleans up legacy
adapter artifacts (systemd service, `/opt/claude-code-maas-proxy/`, env files)
from prior installs. Running twice is a no-op.

## Modes

### Mode A: OAuth Orchestrator

Logged into Anthropic via `claude`. Plain `claude` plans and orchestrates;
bounded execution is delegated to `claude-maas` through `delegate` or `workflow`.
Premium, visual, security, architecture, and complex-debugging work stays in the
OAuth session.

### Mode B: MaaS-only

Invoke `claude-maas` directly. No `claude /login` required. Every model request
goes to the configured MaaS model. Image input returns `unsupported_capability`
— it is never silently rerouted.
