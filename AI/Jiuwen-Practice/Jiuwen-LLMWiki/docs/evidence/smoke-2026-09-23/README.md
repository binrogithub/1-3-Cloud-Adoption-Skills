# M0 smoke-run evidence (2026-09-23, host 247)

Preserved from the pre-implementation smoke test (E15-S4, per OQ-4 the raw streams are
kept as M0 evidence, not deleted):

- `smoke-ask1.json` — the ask result JSON of the only live glue run (pre-parser-fix,
  agent mode → correctly failed closed with `role_not_dispatched`).
- `smoke-raw-code.jsonl` — raw code-mode event stream captured on 247; source of the
  event shapes replayed by `tests/fakes/jiuwenswarm` (the successful `Agent` tool_result
  with `A single object can be up to 48.8 TB [W:services/obs]`).
- `smoke-raw.jsonl` — agent-mode run showing the R-6 sub-agent crash and the main agent
  answering uncited on its own (why D-4 fail-closed exists).
- `smoke-gateway.log`, `smoke-agentserver.log`, `jiuwen-logs/` — instance logs of the run,
  including `loaded custom agent 'llmwiki' from user` (E1/E2 evidence).
- `sub_agents_identity/` — the sub-agent state folder the smoke run created in the project
  root (proof of R-10; the reason WorkingDirectory moved to `runtime/jiuwen/work`).

The runtime copies under `runtime/logs/` were the working copies; these are the archive.
