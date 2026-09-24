# developable-secondary Specification

## Purpose
The build always stands on at least one real composed template page,
with a broader template material basis.

## Requirements

### Requirement: the pick is a developable template

The deterministic pick and the degraded fallback SHALL prefer
candidates whose example.html is developable (at least three section
blocks or 20KB); when no unflagged developable candidate exists the
fallback SHALL still take a developable one over an undevelopable
stub.

#### Scenario: nominal

- **WHEN the top-scored candidate is a poster-shaped stub and a real
  composed page stands behind it**
- **THEN the pick SHALL be the composed page**

### Requirement: runner-up templates materialize as secondary slots

design-materialize SHALL support a secondary slot under
design-material/secondary/<template>/ with manifest slot=secondary,
and the design flow SHALL materialize the shortlist's next two
distinct runner-ups there.

#### Scenario: nominal

- **WHEN the design flow runs with a five-entry shortlist**
- **THEN the main template plus the two distinct runner-ups SHALL be
  materialized**
