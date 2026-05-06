# Mainframe Modernization Workflow Reference

## Discovery Checklist

- Count COBOL programs, copybooks, JCL jobs, BMS maps, CSD definitions, assembler modules, DB2 artifacts, VSAM definitions, IMS artifacts, and MQ artifacts.
- Identify online entry points from CICS transaction/program mappings.
- Identify batch entry points from JCL `EXEC PGM=`, PROC expansion, and scheduler conventions.
- Identify common copybooks and record layouts.
- Identify external interfaces: files, queues, DB2 tables, terminals, reports, printers, APIs.
- Identify unavailable parsers or runtime tools.

## Reverse Engineering Checklist

- Draw control flow from entry point to called programs.
- Draw data flow from screen/job input through domain programs to files/tables/queues/reports.
- Extract business rules in plain language.
- Preserve user-visible messages and codes.
- Mark technical plumbing separately.
- Classify assembler modules:
  - business rule owner
  - utility
  - date/time helper
  - wait/sleep helper
  - black box

## DDD Boundary Heuristics

- Split by data ownership, business capability, and lifecycle.
- Keep invariants inside a service.
- Avoid one service per screen.
- Avoid chatty APIs that recreate COBOL paragraph-by-paragraph calls.
- Introduce integration events only where asynchronous consistency is acceptable.

## Testing Checklist

- Required field validation
- Code length and allowed value validation
- Numeric precision and rounding
- Status transitions
- Date boundaries
- Duplicate/upsert semantics
- Referential delete restrictions
- Not-found behavior
- Version conflict behavior
- Legacy error message equivalence

## Stop Conditions

Stop and report when:

- a core assembler module cannot be understood
- data layouts are ambiguous enough to affect business rules
- generated tests pass below 90%
- Java behavior cannot be shown logically equivalent to extracted legacy behavior
- required runtime tooling is missing and no reliable static fallback exists

