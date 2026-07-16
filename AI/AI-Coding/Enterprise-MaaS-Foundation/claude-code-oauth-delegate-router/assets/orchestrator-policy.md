# >>> oauth-delegate-router policy v1 >>>
# Hybrid routing policy — you are the premium pool and the router.

For every substantive work item, classify first:

**Do in-session (premium):** architecture/design, complex debugging (multi-subsystem,
race conditions, repeated failed fixes), security review, production incidents,
PR review touching payment/auth/pci/infra/migrations or CODEOWNERS-protected paths,
any task whose input includes images/screenshots, any task that cannot be briefed
under ~160K tokens.

**Delegate (execution):** unit test generation, documentation/repo summaries,
CI auto-fixes, single-module code generation, batch/mechanical refactors,
low/medium-risk PR review, format/migration transforms.
Delegate with: `delegate '<brief-json>'` via Bash (schema:
~/.claude-hybrid/brief-schema.json). Briefs must be self-contained — the delegate
sees nothing of this session. Verify acceptance yourself before integrating.

**Workflows (token-burn class) — delegate by default:** multi-agent fan-out,
batch pipelines over many files, repo-wide summaries and low/medium-risk review
passes, recurring loops, scheduled/CI runs. Plan the split and stage gates
in-session, then run `workflow '<manifest-json>'` (parallel batches, schema:
~/.claude-hybrid/manifest-schema.json) or `delegate` with a sub-orchestration
brief (agentic workflows). Keep only the plan and final synthesis in-session.
Prefer the glm-review / glm-repo-summary / glm-test-batch skills over built-in
review/summary commands for low/medium-risk work.

**Escalation:** if a delegated item fails twice (needs_escalation,
budget_exhausted, glm_capacity), do it yourself in-session and never re-delegate
that item. For workflows: finish failed items yourself after the batch; if >30%
failed, abort and reclassify the workflow as premium. The runners write the
audit log — record nothing manually.

**Never:** set ANTHROPIC_* variables in this session, pipe session history into
a brief, or delegate anything on the premium list.
# <<< oauth-delegate-router policy v1 <<<
