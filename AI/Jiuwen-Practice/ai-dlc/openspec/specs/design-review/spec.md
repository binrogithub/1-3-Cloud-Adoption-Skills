# design-review Specification

## Purpose
Put a bounded adversarial round between the design artifact and the work that
follows it, so the axes a single author systematically omits are raised once,
answered once, and recorded.

## Requirements

### Requirement: The review round runs only when the design artifact ran

The round SHALL follow the design artifact and SHALL NOT run without it.

#### Scenario: The design artifact was produced

- **WHEN** the design artifact has been written and accepted into the change
- **THEN** the review round SHALL run before the phase is reported complete

#### Scenario: The design artifact was skipped

- **WHEN** the optional design artifact was skipped on its own conditions
- **THEN** the review round SHALL NOT run
- **AND** the skip SHALL be recorded as the reason no review took place

### Requirement: Each reviewer files exactly one finding and stops

A reviewer SHALL produce one finding on its own axis. It SHALL NOT produce a
second, SHALL NOT edit the design, and SHALL NOT review another axis.

#### Scenario: A reviewer completes

- **WHEN** a reviewer is dispatched for an axis
- **THEN** it SHALL write exactly one finding to its own path, naming the axis,
  the concern, where in the design it applies, and what it would change
- **AND** the product surface diff for that dispatch SHALL contain only that
  finding

#### Scenario: A reviewer files more than one finding

- **WHEN** a reviewer writes more than one finding, or writes outside its own
  path
- **THEN** the dispatch SHALL fail, naming what it wrote

#### Scenario: A reviewer has nothing to say

- **WHEN** a reviewer finds nothing on its axis
- **THEN** it SHALL record that explicitly, stating what it examined
- **AND** silence SHALL NOT be accepted in place of that record

### Requirement: The author answers every finding on the record

The author SHALL revise once, and SHALL answer each finding, accepting or
rejecting it with a reason. A finding SHALL NOT be left unanswered.

#### Scenario: Revising after review

- **WHEN** the review round completes
- **THEN** the author SHALL be dispatched once more, carrying every finding
- **AND** the revision SHALL record, for each finding, whether it was accepted
  and what changed, or rejected and why

#### Scenario: A finding is unanswered

- **WHEN** the revision does not answer a finding
- **THEN** the phase SHALL NOT be reported complete
- **AND** the unanswered finding SHALL be named

### Requirement: A finding is advice, never a delivery criterion

Findings SHALL inform the author. They SHALL NOT gate delivery, and no finding
SHALL be treated as a verdict on correctness.

#### Scenario: Delivery is decided

- **WHEN** delivery is decided for a change whose design was reviewed
- **THEN** the criteria SHALL remain the ones already in force, unchanged by any
  finding
- **AND** the review record SHALL be carried in the report as advice

#### Scenario: A finding is proposed as a gate

- **WHEN** a change would make an unresolved finding block delivery
- **THEN** it SHALL be rejected, because no correctness judgement is built here
