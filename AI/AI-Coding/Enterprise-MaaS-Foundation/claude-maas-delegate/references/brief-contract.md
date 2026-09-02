# Brief Contract

Send one JSON object to `maas-delegate run` on stdin:

```json
{
  "task_type": "bug_fix",
  "goal": "Fix the named failing assertion.",
  "scope": ["src/parser.py", "tests/test_parser.py"],
  "constraints": ["Do not change public APIs."],
  "acceptance": "pytest -q tests/test_parser.py",
  "max_attempts": 2,
  "max_turns": 24
}
```

## task_type enum

The `task_type` field must be one of:

| Value | Write-op? | Description |
| --- | --- | --- |
| `code_generation` | yes | Generate new source files |
| `unit_test_generation` | yes | Generate or update tests |
| `bug_fix` | yes | Fix a named defect |
| `refactor` | yes | Mechanical refactor (no boundary changes) |
| `ci_fix` | yes | Repair CI pipeline or config |
| `format_migration` | yes | Migrate formatting or linting rules |
| `docs` | no | Documentation changes |
| `review` | no | Code review (read-only) |
| `repo_summary` | no | Summarize repository state |
| `batch` | no | Batch of independent sub-tasks |
| `suborchestrate` | no | Single bounded sub-orchestration |
| `image` | never | Always rejected — MaaS glm-5.2 has no vision |

Write-op types with an empty `scope` are rejected as `invalid_brief`.

## acceptance

The `acceptance` field is a **pure shell command** run with an explicit cwd
and bounded timeout to verify the task outcome. It must be self-contained and
exit 0 on success. Only the command fingerprint and a truncated non-sensitive
evidence tail are recorded in audit.

```json
"acceptance": "pytest -q tests/test_parser.py"
```

Do not embed credentials, use interactive prompts, or rely on network access
in the acceptance command.

## DELEGATE_ALLOWED_TOOLS

Control the Claude-MaaS tool surface per task with the `DELEGATE_ALLOWED_TOOLS`
environment variable. Use a task-scoped comma-separated list — never
`IS_SANDBOX` or `--dangerously-skip-permissions`.

Read-only example (review, repo_summary):

```sh
printf '%s' "$brief_json" | DELEGATE_ALLOWED_TOOLS='Read,Bash,Glob,Grep' \
  maas-delegate run --agent cursor --conversation-id "$NATIVE_ID" --workspace "$PWD"
```

Implementation example (code_generation, bug_fix, refactor):

```sh
printf '%s' "$brief_json" | DELEGATE_ALLOWED_TOOLS='Read,Write,Edit,Bash,Glob,Grep' \
  maas-delegate run --agent cursor --conversation-id "$NATIVE_ID" --workspace "$PWD"
```

## Rules

Keep the goal self-contained, bounded, and inside `scope`. Do not include
credentials or provider configuration. Image input is unsupported. Write
operations require a non-empty scope. An invalid brief is rejected before any
session is acquired — it will not poison the session for the next call.
