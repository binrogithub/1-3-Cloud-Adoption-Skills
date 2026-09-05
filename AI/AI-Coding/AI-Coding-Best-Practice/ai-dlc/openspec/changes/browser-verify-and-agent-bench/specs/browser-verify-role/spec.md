## ADDED Requirements

### Requirement: browser-verify only runs through a dispatched plane session

The orchestrating `plan.py` process SHALL NOT execute Playwright directly;
page verification SHALL occur only inside a session dispatched via
`run_browser_verify_session()`.

#### Scenario: A page verification is requested

- **WHEN** `plan.py browser-verify` is invoked with applicable pages and
  an available pin
- **THEN** the only process spawned by `plan.py` itself SHALL be
  `[CLIENT, "chat", ...]` (the existing jiuwenswarm dispatch shape)
- **AND** no direct `subprocess`/`os.exec` call to a Playwright
  executable SHALL occur outside `run_browser_verify_session()`

### Requirement: The pinned Playwright MCP tree is digest-verified before dispatch

`browser_verify_pin_state()` SHALL refuse to report the pin healthy if
the installed tree's measured digest does not match the recorded pin.

#### Scenario: The pinned tree was modified after installation

- **WHEN** the tree under `AI_DLC_PLAYWRIGHT_MCP_ROOT` has changed since
  `.aidlc-pin.json` was written
- **THEN** `browser_verify_pin_state()` SHALL return `ok: false` with the
  measured and pinned digests both named
- **AND** `plan.py browser-verify` SHALL NOT dispatch a session

#### Scenario: The pin is missing entirely

- **WHEN** the pinned root exists but carries no `.aidlc-pin.json`
- **THEN** `browser_verify_pin_state()` SHALL return `ok: false` naming
  the remedy (re-run the install script)

### Requirement: An unavailable or inapplicable check never blocks the caller

#### Scenario: No named page exists in the working tree

- **WHEN** none of the `--pages` arguments resolve to a file in the
  current `--repo`
- **THEN** `plan.py browser-verify` SHALL report
  `browser_verify_state: "not_applicable"` and exit 0
- **AND** no session SHALL be dispatched

#### Scenario: The pin is unavailable

- **WHEN** `browser_verify_pin_state().ok` is `false`
- **THEN** `plan.py browser-verify` SHALL report
  `browser_verify_state: "unavailable"` and exit 0
- **AND** the caller's own task SHALL proceed unaffected

### Requirement: A completed dispatch is recorded, never inferred

#### Scenario: A dispatch completes and is judged

- **WHEN** `run_browser_verify_session()` returns a judged-complete
  result
- **THEN** the outcome SHALL be written to `state.json.browser_verify`
- **AND** one of `BROWSER_VERIFY_PASSED` / `BROWSER_VERIFY_FAILED` /
  `BROWSER_VERIFY_UNAVAILABLE` SHALL be appended to `events.jsonl`
- **AND** the recorded outcome SHALL come from the judged frames, never
  from the dispatched role's own closing summary sentence
