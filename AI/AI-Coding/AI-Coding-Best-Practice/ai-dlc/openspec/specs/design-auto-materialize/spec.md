# design-auto-materialize Specification

## Purpose
Standing material is the default state of every design flow, not a
driver-side improvisation.

## Requirements

### Requirement: the design flow materializes between selection and specification

The v2 design flow SHALL materialize the D0-chosen template after
selection and before specification; a materialize that refuses (the
template carries no material, or material already stands) SHALL NOT
fail the flow.

#### Scenario: nominal

- **WHEN the design flow runs select → materialize → specify →
  verify**
- **THEN the four steps SHALL execute in that order with the chosen
  template's directory name**
