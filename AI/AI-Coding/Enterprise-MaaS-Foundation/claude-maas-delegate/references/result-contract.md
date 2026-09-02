# Result Contract

Every command prints one JSON object. A successful run includes `status: "success"`, `delegation_handle`, `session_reused`, `verification`, and token metadata.

- Save `delegation_handle` if no stable host conversation ID is available.
- `session_reused: true` means the invocation resumed the same Claude session.
- `session_busy` means another prompt owns the handle; wait or use separate work.
- `session_conflict` means the handle belongs to another host or workspace; do not bypass it.
- `needs_escalation`, `invalid_brief`, and `unsupported_capability` return control to the host agent. After a task has failed twice, keep it local for diagnosis.

Use `maas-delegate session status --handle <handle>` for non-sensitive lifecycle status and `maas-delegate session close --handle <handle>` when the host conversation ends.

