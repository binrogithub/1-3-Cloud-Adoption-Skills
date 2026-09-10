# d1-multi-page-prompt Specification

## Purpose
A multi-page proposal yields a multi-page design.

## Requirements

### Requirement: pages.md enumerates the proposal's pages

The D1 specify prompt SHALL require one `## Page: <name>` section in
design/pages.md per page the proposal names, each composed from the
shared components and tokens.

#### Scenario: nominal

- **WHEN the specify prompt is built**
- **THEN it SHALL name the `## Page: <name>` convention and require a
  section per named page**
