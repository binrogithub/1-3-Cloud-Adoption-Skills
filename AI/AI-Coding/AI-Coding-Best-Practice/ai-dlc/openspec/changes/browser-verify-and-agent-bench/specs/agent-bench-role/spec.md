## ADDED Requirements

### Requirement: agent-bench only runs through a dispatched plane session

The orchestrating `plan.py` process SHALL NOT execute Harbor directly;
benchmark runs SHALL occur only inside a session dispatched via
`run_agent_bench_session()`.

#### Scenario: A benchmark run is requested

- **WHEN** `plan.py bench` is invoked with an available pin
- **THEN** the only process spawned by `plan.py` itself SHALL be
  `[CLIENT, "chat", ...]`
- **AND** no direct `subprocess`/`os.exec` call to the Harbor executable
  SHALL occur outside `run_agent_bench_session()`

### Requirement: The pinned Harbor install is digest-verified before dispatch

#### Scenario: The pinned venv was modified after installation

- **WHEN** the tree under `AI_DLC_AGENT_BENCH_ROOT` has changed since
  `.aidlc-pin.json` was written
- **THEN** `agent_bench_pin_state()` SHALL return `ok: false` with the
  measured and pinned digests both named
- **AND** `plan.py bench` SHALL NOT dispatch a session

### Requirement: agent-bench never gates or is recorded against any change's delivery

#### Scenario: A change is being delivered

- **WHEN** `report.py deliver` computes a change's `delivered` status
- **THEN** no field derived from `plan.py bench` or
  `/var/lib/aidlc/bench-history/` SHALL be read or referenced

#### Scenario: The bench subcommand itself is invoked

- **WHEN** `plan.py bench` is called
- **THEN** it SHALL accept no `--change` argument
- **AND** it SHALL NOT read or write any path under `.ai-dlc/tasks/`

### Requirement: An unavailable pin never fails the invoking process

#### Scenario: The pin is unavailable

- **WHEN** `agent_bench_pin_state().ok` is `false`
- **THEN** `plan.py bench` SHALL report `agent_bench_state:
  "unavailable"` and exit 0
- **AND** no session SHALL be dispatched

### Requirement: A recorded result names the tool version it measured

#### Scenario: A benchmark run completes and is judged

- **WHEN** `run_agent_bench_session()` returns a judged-complete result
- **THEN** a signed record SHALL be written to
  `/var/lib/aidlc/bench-history/<timestamp>.json`
- **AND** that record SHALL include the pinned Harbor version and the
  pin's `tree_sha256`
- **AND** a record missing either of those fields SHALL NOT be treated
  as a valid completed run
