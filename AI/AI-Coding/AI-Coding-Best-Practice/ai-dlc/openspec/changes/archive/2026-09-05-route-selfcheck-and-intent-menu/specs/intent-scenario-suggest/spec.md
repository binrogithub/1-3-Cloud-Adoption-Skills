## ADDED Requirements

### Requirement: `plan.py suggest` lists candidate routes without choosing one

Given free text and a repo, `plan.py suggest` SHALL return a ranked list of
at most 4 candidate automation routes, each with a rationale and a first
command, and SHALL NOT execute, select, or record any of them.

#### Scenario: Text matches a single candidate strongly

- **WHEN** the input text and repo state strongly match one candidate's
  trigger signal (e.g., text names a deploy/production action)
- **THEN** that candidate SHALL appear first in the returned list
- **AND** the list SHALL contain at most 4 entries total

#### Scenario: Text matches nothing recognizable

- **WHEN** every candidate scores zero against the input
- **THEN** `plan.py suggest` SHALL return an empty candidate list
- **AND** SHALL include a fallback message pointing at `plan.py next`'s
  default judgment
- **AND** SHALL NOT fabricate a non-empty answer

#### Scenario: `--change` is supplied

- **WHEN** `--change <id>` is given and that change's `state.json` already
  records a decision relevant to a candidate (e.g., an existing
  `design_selection`)
- **THEN** that candidate's rationale SHALL reference the existing decision
  rather than proposing it as if new

### Requirement: `suggest` never has side effects

- **WHEN** `plan.py suggest` runs, regardless of input or outcome
- **THEN** no file under `.ai-dlc/`, `state.json`, or `events.jsonl` SHALL
  be created or modified
- **AND** no session, dispatch, or subprocess to the gateway SHALL be
  opened

#### Scenario: Gateway is unreachable

- **WHEN** the configured dispatch gateway is unreachable
- **THEN** `plan.py suggest` SHALL still return a candidate list computed
  from local state alone
- **AND** unreachability MAY itself appear as a rationale for a candidate
  (e.g., recommending `inline_quick_fix` over `planned_full_pipeline`) but
  SHALL NOT cause the command to fail
