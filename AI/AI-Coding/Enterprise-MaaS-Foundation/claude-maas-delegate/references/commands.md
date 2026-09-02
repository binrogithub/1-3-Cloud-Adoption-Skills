# Operations

Commands and troubleshooting for the Claude-MaaS delegation Skill. The host
agent retains its own provider and authentication; Claude-MaaS alone uses the
configured Anthropic-compatible endpoint.

## Delegate a bounded task

```sh
printf '%s' "$brief_json" | maas-delegate run \
  --agent cursor --conversation-id "$NATIVE_ID" --workspace "$PWD"
```

Send the JSON brief on stdin, never as a command argument. The `task_type` must
be a valid enum value (see [brief-contract.md](brief-contract.md)). The
`acceptance` field is a pure shell command that exits 0 on success. Inspect the
structured result, then locally verify the acceptance evidence.

## Task-scoped tool authorization

Set `DELEGATE_ALLOWED_TOOLS` on the `maas-delegate` side of the pipe — never on
`printf`, never `IS_SANDBOX`, never `--dangerously-skip-permissions`:

```sh
# Read-only (review, repo_summary):
printf '%s' "$brief_json" | DELEGATE_ALLOWED_TOOLS='Read,Bash,Glob,Grep' \
  maas-delegate run --agent cursor --conversation-id "$NATIVE_ID" --workspace "$PWD"

# Implementation (code_generation, bug_fix, refactor):
printf '%s' "$brief_json" | DELEGATE_ALLOWED_TOOLS='Read,Write,Edit,Bash,Glob,Grep' \
  maas-delegate run --agent cursor --conversation-id "$NATIVE_ID" --workspace "$PWD"
```

## Session lifecycle

```sh
maas-delegate session new  --agent cursor --conversation-id "$ID" --workspace "$PWD"
maas-delegate session status --handle "$HANDLE"
maas-delegate session close --handle "$HANDLE"
maas-delegate session gc --older-than-days 30
maas-delegate doctor
```

One host conversation maps to one Claude session. Different conversations get
different sessions. Concurrent prompts through one handle are rejected as
`session_busy`, not interleaved.

## Result status values

- `success` — task completed.
- `session_busy` — another prompt owns the handle; wait or use separate work.
- `session_conflict` — handle belongs to another host or workspace.
- `needs_escalation` / `invalid_brief` / `unsupported_capability` — return
  control to the host agent. After two failures, keep the task local.

## Timeout behavior

Per-attempt timeouts are adaptive: 900 s minimum, `max_turns × 120` s scaled,
7200 s maximum. A caller may pass `--timeout` to override. Active background
work is not killed at the 600-second mark.

## Classification

Delegate only bounded execution: implementation, testing, bug fix, mechanical
refactor, CI repair, documentation. Keep architecture, security, payment,
incidents, complex diagnosis, and failed-twice work local. See
[routing-policy.md](routing-policy.md).

For full operations details, see [OPERATIONS.md](OPERATIONS.md).
