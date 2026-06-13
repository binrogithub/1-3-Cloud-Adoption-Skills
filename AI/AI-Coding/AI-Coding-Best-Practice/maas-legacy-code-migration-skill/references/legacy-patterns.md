# Legacy Code Patterns

## Common Anti-Patterns in Legacy Codebases

### Big Ball of Mud

- No clear module boundaries
- Everything depends on everything
- Circular dependencies common
- **Migration strategy**: Identify seams (points where behavior can be isolated), create thin wrappers, migrate one seam at a time

### Copy-Paste Inheritance

- Similar code duplicated across files with minor variations
- No shared abstractions
- **Migration strategy**: Identify duplicated patterns, extract shared module, replace copies with calls, verify behavior per copy

### Magic Numbers

- Hardcoded constants scattered throughout code
- No named constants or configuration
- **Migration strategy**: Extract to named constants or configuration file, verify each extraction individually

### Global State

- Global variables, singletons, static mutable state
- Implicit dependencies between modules
- **Migration strategy**: Identify global state, make dependencies explicit (constructor injection), verify behavior after each extraction

### Implicit Dependencies

- Modules depend on other modules through side effects, not interfaces
- Order of initialization matters but is not documented
- **Migration strategy**: Map dependency graph, make dependencies explicit, introduce dependency injection

### Missing Abstractions

- Business logic mixed with I/O, UI, and infrastructure
- No separation of concerns
- **Migration strategy**: Identify business logic, extract to pure functions, verify behavior, then migrate infrastructure

### Primitive Obsession

- Business concepts represented as primitives (strings, ints) instead of types
- Validation scattered across codebase
- **Migration strategy**: Introduce value types, centralize validation, verify behavior

### Shotgut Surgery

- One change requires edits across many files
- High coupling, low cohesion
- **Migration strategy**: Refactor to localize changes (move code to where it belongs), verify after each move

## Legacy Code Reading Strategy

1. **Start with tests** (if any exist): Tests document intended behavior
2. **Read entry points first**: Main functions, API endpoints, event handlers
3. **Trace data flow**: Follow the data from input to output
4. **Identify seams**: Points where behavior can be substituted or extended
5. **Map dependency graph**: What depends on what
6. **Document as you go**: Write understanding document incrementally

## Understanding Document Template

```markdown
# Legacy Codebase Understanding

## Overview
[What this system does, in business terms]

## Architecture
[High-level architecture diagram and description]

## Entry Points
[List of main functions, API endpoints, event handlers]

## Data Flow
[How data moves through the system]

## Key Modules
[For each module: purpose, dependencies, complexity estimate]

## Seams
[Points where behavior can be isolated for testing/migration]

## Known Risks
[Areas that are particularly fragile or poorly understood]

## Characterization Test Coverage
[Which paths have characterization tests, which don't]
```
