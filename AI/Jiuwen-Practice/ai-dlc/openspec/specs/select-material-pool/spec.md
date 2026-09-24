# select-material-pool Specification

## Purpose
The pool holds designs, not stubs; and a session that answered is an
answer.

## Requirements

### Requirement: a named answer survives an unclosed round

When a design-select or second-opinion session's frames carry an
assistant reply naming a valid shortlist candidate, the selection
SHALL adopt that pick as judged even if the round timed out or never
formally completed; the selection SHALL record
round_incomplete_judged=true. A round that names nothing still
degrades exactly as before.

#### Scenario: nominal

- **WHEN the 90s arbiter times out but its frames name a shortlist
  path**
- **THEN the selection SHALL be method=judged for that pick with
  round_incomplete_judged=true**

### Requirement: selection candidates carry design material

_filter_candidates SHALL exclude candidates with neither example.html
nor an assets/ directory from the selection pool, and the degraded
fallback SHALL skip candidates without example.html.

#### Scenario: nominal

- **WHEN a skills/ entry is a SKILL.md-only stub**
- **THEN it SHALL be filtered from the pool and never chosen by the
  degraded fallback**
