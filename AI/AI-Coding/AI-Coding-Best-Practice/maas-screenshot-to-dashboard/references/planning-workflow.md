# Planning Workflow Reference — CCPM Integration

## PRD Template (.claude/prds/<name>.md)

```yaml
---
name: <feature-name>
description: <one-line summary>
status: backlog
created: <ISO 8601>
---
```

### Required Sections

1. **Executive Summary** — What and why in 2-3 sentences
2. **Problem Statement** — Current state vs desired state
3. **User Stories** — With acceptance criteria (AC)
4. **Functional Requirements** — One per component/feature (FR-1, FR-2, ...)
5. **Non-Functional Requirements** — Performance, accessibility, theme
6. **Success Criteria** — Measurable (e.g., similarity ≥ 85%)
7. **Constraints & Assumptions** — Tech stack, data source, scope limits
8. **Out of Scope** — Explicitly list what's NOT included
9. **Dependencies** — External data, libraries, services

## Epic Template (.claude/epics/<name>/epic.md)

```yaml
---
name: <feature-name>
status: backlog
created: <ISO 8601>
progress: 0%
prd: .claude/prds/<name>.md
---
```

### Required Sections

1. **Overview** — Technical summary
2. **Architecture Decisions** — Table of decision/choice/rationale
3. **Technical Approach** — Frontend components, backend, infrastructure
4. **Implementation Strategy** — Ordered phases
5. **Task Breakdown Preview** — Table with #/Task/Depends/Parallel/Estimate
6. **Dependencies** — External requirements
7. **Success Criteria (Technical)** — Measurable technical goals
8. **Estimated Effort** — Total hours

## Task Template (.claude/epics/<name>/NNN.md)

```yaml
---
name: <Task Title>
status: open
created: <ISO 8601>
updated: <ISO 8601>
depends_on: []
parallel: true
conflicts_with: []
---
```

### Required Sections

1. **Description** — What to implement
2. **Acceptance Criteria** — Checklist with `- [ ]`
3. **Technical Details** — Specific code patterns, files, configs
4. **Dependencies** — Which tasks must complete first
5. **Effort Estimate** — Size (XS/S/M/L/XL) + Hours

## Typical Task Breakdown for Dashboard

| # | Task | Depends | Parallel | Size |
|---|---|---|---|---|
| 001 | Theme & Layout Foundation | — | No | S |
| 002 | Mock Data & BilingualTitle | 1 | No | S |
| 003 | KPI Cards | 2 | No | S |
| 004 | Choropleth Map | 2 | Yes | M |
| 005 | Top-10 Tables | 2 | Yes | S |
| 006 | Main Line Chart | 2 | Yes | M |
| 007 | Bar Chart | 2 | Yes | S |
| 008 | Donut Chart | 2 | Yes | S |
| 009 | Horizontal Bar Chart | 2 | Yes | S |
| 010 | Dashboard Assembly & Polish | 3-9 | No | M |

**Parallelization**: Tasks 4-9 can run concurrently via Agent tool after Task 3 completes.
