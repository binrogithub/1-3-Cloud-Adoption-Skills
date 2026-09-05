---
name: claude-maas-delegate
description: Use when implementation, test generation, bug fixing, refactoring, CI repair, or documentation execution can be delegated to Claude-MaaS from Codex, Copilot, Cursor, or OpenCode. Also use for installing, verifying, diagnosing, or uninstalling the Claude-MaaS delegation Skill.
---

# Claude-MaaS Delegation

Use Claude-MaaS only for bounded execution after local classification. The host agent retains its own provider, model, authentication, and reasoning role; Claude-MaaS alone uses the configured Anthropic-compatible endpoint.

## Quick start

1. **Install** — see [quickstart.md](references/quickstart.md). The key
   is read from stdin, never from argv. The host provider is never modified.
2. **Classify** — use [routing-policy.md](references/routing-policy.md). Keep
   unclear, high-risk, design, and exhausted work local.
3. **Delegate** — build the minimal [brief](references/brief-contract.md),
   send it on stdin, inspect the [result](references/result-contract.md).
4. **Operate** — see [commands.md](references/commands.md) for session
   lifecycle, status values, and timeout behavior.

## Delegate a task

```sh
printf '%s' "$brief_json" | maas-delegate run \
  --agent cursor --conversation-id "$native_conversation_id" \
  --workspace "$PWD"
```

Send the JSON [brief](references/brief-contract.md) on stdin. The `task_type`
must be one of: `code_generation`, `unit_test_generation`, `bug_fix`,
`refactor`, `docs`, `review`, `ci_fix`, `format_migration`, `repo_summary`,
`batch`, `suborchestrate` (`image` is rejected). The `acceptance` field is a
pure shell command that exits 0 on success.

## Task-scoped tools

Control the Claude-MaaS tool surface per task with `DELEGATE_ALLOWED_TOOLS` on
the `maas-delegate` side of the pipe — never on `printf`, never
`IS_SANDBOX`, never `--dangerously-skip-permissions`:

```sh
# Read-only (review, repo_summary):
printf '%s' "$brief_json" | DELEGATE_ALLOWED_TOOLS='Read,Bash,Glob,Grep' \
  maas-delegate run --agent cursor --conversation-id "$ID" --workspace "$PWD"

# Implementation (code_generation, bug_fix, refactor):
printf '%s' "$brief_json" | DELEGATE_ALLOWED_TOOLS='Read,Write,Edit,Bash,Glob,Grep' \
  maas-delegate run --agent cursor --conversation-id "$ID" --workspace "$PWD"
```

Both presets above use the bare `Bash` tool name, which grants unrestricted
shell — the `Bash` entry is not a command-level sandbox even when written
more narrowly (e.g. `Bash(git add:*)`); see
[permission-scoping.md](references/permission-scoping.md) for what
`--allowedTools` patterns actually restrict and
[SECURITY.md](references/SECURITY.md#tool-scoping-does-not-prevent-command-chaining)
for why none of them stop command chaining.

For parallel work, use separate handles or child sessions. Never run two
prompts concurrently through one handle. Save the `delegation_handle` from the
result to reuse the session on later turns. An invalid brief is rejected before
any session is acquired. When fanning a larger task out into multiple
concurrent Claude-MaaS sub-tasks, give each one `Write`/`Edit` only (no git)
and have the orchestrator perform `git add`/`git commit` itself once, after
reviewing every sub-task's output — git's index lock has no automatic retry,
so concurrent commits from separate sub-tasks are not safe.

## Verify and uninstall

```sh
python3 scripts/verify-skill-release.py .   # verify package integrity
./scripts/uninstall.sh                       # remove project items, retain key
```

## References

- [quickstart.md](references/quickstart.md) — install, flags, uninstall, verify
- [commands.md](references/commands.md) — commands, sessions, troubleshooting
- [routing-policy.md](references/routing-policy.md) — what to delegate vs keep local
- [brief-contract.md](references/brief-contract.md) — JSON brief schema
- [result-contract.md](references/result-contract.md) — structured result fields
- [ARCHITECTURE.md](references/ARCHITECTURE.md) — components and invariants
- [SECURITY.md](references/SECURITY.md) — credential handling and provider isolation
- [RELEASE-NOTES.md](references/RELEASE-NOTES.md) — capabilities and limitations
