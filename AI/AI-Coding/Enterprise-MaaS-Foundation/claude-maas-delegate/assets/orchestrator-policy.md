<!-- BEGIN claude-maas-policy -->
## Claude-MaaS Delegate Router: OAuth Orchestration Policy

This policy defines which tasks stay in the Anthropic OAuth session (`claude`)
and which tasks delegate to `claude-maas` (Huawei MaaS `glm-5.2`). The
classification is advisory: a route-hint hook outputs a single context line
and never blocks, invokes MaaS, inspects credentials, or mutates files.

### Tasks that stay in OAuth Claude

Keep the following in the current OAuth session because they require
high-judgment reasoning, vision, or escalation authority:

- **Images, screenshots, and vision input** — MaaS `glm-5.2` does not support
  image input. Never delegate image tasks to MaaS.
- **Security, authentication, encryption, payment, PCI, and production
  incidents** — high-risk domains requiring human-grade judgment and audit
  accountability.
- **Architecture and cross-service design** — system-level decisions that
  span multiple services and have broad blast radius.
- **Complex debugging, multi-failure root cause analysis, and race
  conditions** — investigations across multiple subsystems that exceed
  single-module scope.
- **High-risk PR review, infrastructure changes, and database migration
  decisions** — irreversible or high-impact changes requiring senior review.
- **Tasks exceeding the GLM-5.2 verified context boundary** that cannot be
  decomposed into smaller subtasks.
- **Escalation after two MaaS delegation failures** — the same item must not
  be delegated a third time; it returns to the OAuth session as premium
  remainder.

### Tasks that delegate to claude-maas (glm-5.2)

Delegate the following to `claude-maas` to shift execution tokens to MaaS:

- **Ordinary code generation and single-module modification** —
  self-contained implementation tasks within one module.
- **Unit tests, documentation, and repo summary** — mechanical text
  generation with bounded scope.
- **CI fixes, mechanical refactoring, and format migration** —
  deterministic transformations with clear acceptance criteria.
- **Low-risk and medium-risk review** — routine code review that does not
  touch security, payment, or architecture.
- **Batch, loop, CI, cron, and multi-task fan-out workflows** —
  repetitive execution that benefits from MaaS token economics.

### Tie-breaking rule

**Premium signals win ties.** When a task matches both a MaaS signal and an
OAuth signal, classify it as OAuth. For example, "generate code for the
security module" is OAuth because `security` is a premium signal even though
`code generation` is a MaaS signal.

### Escalation rules

1. A delegated task that fails twice (total attempts, including retry) returns
   `needs_escalation` and must not be delegated again.
2. Workflow fan-out failure rate exceeding 30% triggers `reclassify_premium`
   — the entire workflow aborts and returns to OAuth rather than continuing
   to consume MaaS.
3. Image input detected at delegation time is rejected with
   `unsupported_capability:image` before the MaaS client is launched.

### Prohibitions

- **Never** set any `ANTHROPIC_*` environment variable in the OAuth session.
  The OAuth session uses the official Anthropic transport; MaaS environment
  injection happens only in the isolated `claude-maas` child process.
- **Never** delegate image, vision, or screenshot input to MaaS.
- **Never** force a high-risk task to MaaS based on keyword misclassification.
  The route hint is advisory; the human or orchestrator makes the final call.
- **Never** re-delegate an item that has already failed twice.
- **Never** read, replay, or proxy the Anthropic OAuth token in `claude-maas`.
- **Never** invoke LiteLLM, Claude Code Router (CCR), OpenRouter, or any HTTP
  proxy/listener. There is no model fallback chain.
- **Never** use a model other than `glm-5.2` on the MaaS endpoint in v1.

### Invariants

1. The OAuth token is held and submitted only by the official `claude` process.
2. The `claude-maas` child process never inherits or reads OAuth credentials.
3. The `claude-maas` child process never touches `~/.claude/` or shell profiles.
4. The `fallback` field in audit records is always `false`.
5. Automation, CI, and periodic tasks should call `claude-maas` directly
   rather than consuming the OAuth session.
<!-- END claude-maas-policy -->
