# process-integrity Specification

## Purpose
A changed requirement starts a changed conversation; a write the disk
never saw is named, not silenced; a delivery answers for its own
lines, not its file's history.

## Requirements

### Requirement: a rewritten requirement resets the design session

design-specify SHALL hash the task's proposal and, when it differs
from the recorded design_spec.requirement_sha, dispatch under a
generation-suffixed session name with a prompt demanding a complete
rewrite; the state SHALL record requirement_sha and generation.

#### Scenario: nominal

- **WHEN the proposal text changes between specify runs**
- **THEN the next session runs at generation N+1 with a REWRITE
  prompt and the record carries the new hash**

### Requirement: unlanded writes are named

After the settle window the artifact checks SHALL cross-check the
session frames' write/edit targets against the disk; expected paths
that were write-attempted yet missing SHALL be recorded as
unlanded_writes in state and output.

#### Scenario: nominal

- **WHEN the frames carry a write to pages.md that never landed**
- **THEN the record names it and the outcome stays inconclusive**

### Requirement: ruff verdicts are changed-line scoped

The execution gate's ruff verdict SHALL count only diagnostics on
lines the change touched (diff base..HEAD), reporting the rest as
baseline_debt_ignored; AI_DLC_EXEC_RUFF_WHOLEFILE=1 SHALL restore
whole-file verdicts.

#### Scenario: nominal

- **WHEN a touched file carries pre-existing debt on untouched lines
  and the changed lines are clean**
- **THEN ruff passes with baseline_debt_ignored counted**
