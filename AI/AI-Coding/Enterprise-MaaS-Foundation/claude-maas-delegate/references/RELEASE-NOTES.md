# Release Notes

Included capabilities, supported hosts, and known limitations for the
Claude-MaaS Universal Delegate Router. Claims are derived from the repository
source. Planned-but-unimplemented items are marked **(planned)**.

## Included capabilities (implemented)

### Direct-connect launcher

`claude-maas` injects the MaaS endpoint, Bearer token, and model into the child
process environment and `exec`s the official `claude` binary. No daemon, no
protocol conversion, no listening port. Single model (`glm-5.2`) and single
upstream per instance; `fallback` is always `false`.

### Universal agent delegation

An additive global Skill (`claude-maas-delegate`) and routing policy are
installed into supported host agents. The host keeps its own provider, model,
and authentication. Only bounded execution is delegated: implementation, testing,
bug fixes, mechanical refactors, CI repairs, documentation. Architecture,
security, payment, incidents, complex diagnosis, and failed-twice work remain
local. The host provider is never modified.

### Session-aware delegation (`maas-delegate`)

Maps one host conversation to one Claude Code session and resumes it on later
turns. SQLite-backed registry stores only SHA-256 hashes of conversation and
workspace identifiers. Per-handle `fcntl` exclusive locks prevent cross-talk.
Lifecycle commands: `session new`, `session status`, `session close`,
`session gc`, `doctor`.

### Single-task delegation (`delegate`)

JSON brief on stdin, schema-validated (stdlib only). Hard clamps:
`max_attempts` 1..2, `max_turns` 1..64. Retry policy: 401/403 terminal, 429
bounded Retry-After (max 60s), 5xx/timeout one retry. Write-op tasks require
non-empty scope. Redacted JSONL audit (mode 0600).

### Workflow fan-out (`workflow`)

`fanout` mode: isolated delegate workers via `ThreadPoolExecutor`, concurrency
hard-capped (default 3, max 8). Item scopes must be pairwise disjoint
(enforced before thread creation). Failure threshold > 30% aborts with
`reclassify_premium`. `suborchestrate` mode: single bounded invocation.
`run_id`/`item_id` path-traversal-safe.

### Auto-continue supervisor (`auto_continue.py`)

Resumes headless `claude-maas -p` on `stream protocol error` markers: 100s
delay, max 2 retries, session-stable (`--session-id` then `--resume`, never
`--continue`). Detection reads session JSONL, never greps stdout. Only
stream-protocol errors are retried; 401/400/503/client-abort are terminal.

### Exa web search (optional, isolated)

`claude-maas` can search the web via the official Exa remote HTTP MCP, isolated
to the MaaS-only profile. Exact tool allowlist `web_search_exa`, `web_fetch_exa`.
Key stored at 0600, emitted only via a `headersHelper` that fails closed on any
identity mismatch.

### Release verification

`python3 scripts/verify-skill-release.py .` verifies the manifest, exact file
set, digests, modes, and forbidden content without requiring a key or network.
The installation command runs `maas-delegate doctor` as the live, endpoint-aware
health check. Architecture contract tests enforce the no-gateway invariants.

### Safe uninstall

`uninstall.sh` default removes only project-owned items and retains key + audit;
`--purge` is explicit-only. Never removes Claude Code, OAuth tokens, user hooks,
MCP, themes, or preferences. Cleans up legacy adapter artifacts. Idempotent.

## Supported hosts

| Host | Mechanism | Notes |
| --- | --- | --- |
| Codex | Skill in `~/.codex/skills/` + policy block in `~/.codex/AGENTS.md` | Marker-delimited block |
| GitHub Copilot | Skill in `~/.agents/skills/` + policy in `~/.copilot/copilot-instructions.md` | Marker-delimited block |
| Cursor | Skill in `~/.agents/skills/` + rule in `~/.cursor/rules/claude-maas-delegate.mdc` | `alwaysApply: true` |
| OpenCode | Skill in `~/.agents/skills/` + instruction path in `~/.config/opencode/opencode.json` or `.jsonc` | Existing settings and instructions are preserved; JSONC comments are normalized on write |
| Claude Code | `claude-maas` launcher + `delegate`/`workflow` | OAuth orchestrator or MaaS-only mode |

Host detection (`detect-host.sh`) returns a hint based on env vars and PATH
probes only; it never inspects private host databases.

## Supported upstreams

| Upstream | Endpoint | Format | Measured behavior |
| --- | --- | --- | --- |
| Huawei MaaS | `https://api-ap-southeast-1.modelarts-maas.com/anthropic` | Anthropic Messages | Baseline. No rate limiting observed in normal agent use. |
| Zhipu BigModel | `https://open.bigmodel.cn/api/paas/v4/anthropic` | Anthropic Messages | Tight rate limiting: consecutive requests hit 429 quickly (~80s to recover). Emits `reasoning_content`; tool calls well-formed. |

Switching the active upstream is a config change (`--api-url`, `--model`). No
code changes or service restart.

## Known limitations

- **No image input on `glm-5.2`.** The MaaS model returns HTTP 400 for images.
  OAuth mode keeps image tasks in the `claude` session (native vision); MaaS-only
  mode returns `unsupported_capability:image`. Images are never rerouted.
- **429 not yet supervised.** The auto-continue supervisor retries only
  stream-protocol errors. 429 handling is pass-through to the client; supervised
  429 retry is **(planned)** pending marker stability confirmation in the field.
- **Zhipu 429 under agent load.** Claude Code issues rapid consecutive requests
  that trip the Zhipu account rate limit routinely. This is an account-tier
  property. Prefer the MaaS-backed profile for batch/fan-out workloads.
- **`--allowedTools` not injected by default.** The product delegation path does
  not widen the toolbox; only the live gate scripts widen it in their own process
  env.
- **Auto-continue is headless only.** The supervisor covers `-p` invocations;
  interactive TUI is out of scope.
- **POSIX hosts only.** The universal `install.sh` targets macOS, Linux, and WSL
  with Python ≥ 3.7; native Windows is out of scope.

## Planned (not yet implemented)

- Supervised 429 retry in `auto_continue.py` (pending marker stability).
- A general runtime HTTP router, listener, or Sidecar is explicitly excluded and
  would require a new approved PRD.
