# design-auto-inwork-key Specification

## Purpose
Deliver never re-dispatches a design the flow already carried.

## Requirements

### Requirement: designed_in_work reads the real selection schema

design_auto_due SHALL count as designed_in_work a selection carrying
chosen (the schema design-select/pick write) or a completed D1
(design_spec.all_written), regardless of surface-file sizes when D1
stands; a selection whose surface files are thin and whose D1 did not
complete SHALL fall through to the retrofit path as before.

#### Scenario: nominal

- **WHEN a select-schema selection and a completed D1 stand**
- **THEN design_auto_due SHALL return designed_in_work, not due**
