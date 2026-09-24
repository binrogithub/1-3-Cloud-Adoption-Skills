# arbiter-second-opinion Specification

## Purpose
Degradation is reserved for "no conclusion exists", not "one session
failed".

## Requirements

### Requirement: a failed arbiter earns one narrow retry

When the 90s arbiter session does not complete or names no shortlist
path, cmd_design_select SHALL open exactly one 45s second-opinion
session restricted to the top-3 candidates; a shortlist path named
there SHALL produce method=judged-2nd with degraded=false, and a
second failure SHALL degrade exactly as before with the reason
naming the second opinion's failure. A successful first arbiter
SHALL NOT open a second session.

#### Scenario: nominal

- **WHEN the 90s arbiter times out and the 45s retry names a
  shortlist path**
- **THEN the selection SHALL be judged-2nd, not degraded, and carry
  second_opinion outcome=picked**

#### Scenario: both fail

- **WHEN both sessions fail**
- **THEN the selection SHALL be method=degraded with the unflagged
  fallback and the reason SHALL say the second opinion also failed**

### Requirement: the retry is auditable

The selection record SHALL carry a second_opinion object naming
whether it was attempted, its session, and its outcome.

#### Scenario: nominal

- **WHEN a selection completes**
- **THEN second_opinion.attempted SHALL be false for deterministic or
  first-try-judged picks and true with an outcome for retried ones**
