---
name: maas-legacy-code-migration-skill
description: Use this skill when understanding, refactoring, or migrating legacy code especially Java, COBOL, or .NET systems. TRIGGER when the user needs legacy code analysis, behavior-preserving refactoring, batch migration with reviewable transforms, COBOL-to-modern translation, Java version migration, .NET framework upgrade, or test generation for untested legacy code.
---

# MaaS Legacy Code Migration Skill

## Overview

Legacy code migration is the highest-risk engineering activity. The code works but is not understood. Tests are absent or inadequate. The business logic is encoded in implementation, not documented. This skill provides a structured approach: understand first, then migrate in reviewable batches, then verify behavior preservation. MaaS-backed agents assist with understanding and transformation but every batch requires human review.

## When to Use

| Situation | Route |
|-----------|-------|
| Legacy code understanding | Run `scripts/analyze-legacy.sh` |
| Plan migration | Run `scripts/plan-migration.sh` |
| Execute batch migration | Run `scripts/run-batch-transform.sh` |
| Verify behavior preservation | Run `scripts/verify-behavior-preservation.sh` |
| COBOL-specific migration | Read `references/language-specific/cobol-migration.md` |
| Java version migration | Read `references/language-specific/java-migration.md` |
| .NET framework upgrade | Read `references/language-specific/dotnet-migration.md` |

**When NOT to use:**
- Greenfield development (use `maas-spec-plan-build-test-skill` instead)
- Simple dependency updates (use package manager directly)
- Code that already has comprehensive tests and is well-understood

## Core Pattern

```
Legacy Codebase (no/weak tests)
  -> [Understand] MaaS agent reads code, produces understanding document
  -> [Characterize] Pin current behavior with characterization tests
  -> [Plan] Identify migration targets, group into batches
  -> [Transform] For each batch:
       pick N files -> transform -> test -> PR -> CI -> human review -> merge
  -> [Verify] Compare before/after behavior on characterization tests
  -> [Document] Record gaps, decisions, rollback points
```

## Reviewable Batch Pattern

From awesome-codex-skills. Key principles:

- **Batch size**: 5-10 files per batch (configurable in `assets/config/migration-config.json`)
- **Each batch produces a separate PR**
- **Each PR must pass CI before the next batch starts**
- **Human reviews each batch PR**
- **If a batch fails, stop and fix before continuing** (stop-on-failure enforced)
- **Degrees of freedom**: low (legacy migration has low freedom — behavior must be preserved)
- **Done tracking**: `done.list` file records completed files; skipped on re-run

## Behavior Preservation

The critical discipline:

1. **Before migration**: Write characterization tests that pin current behavior
   - Call existing code with known inputs
   - Record outputs
   - Assert those outputs in tests
2. **After migration**: Run characterization tests against new code
   - If tests pass: behavior is preserved
   - If tests fail: migration changed behavior (investigate)
3. **If no characterization tests can be written**: Document the risk and get human sign-off

Characterization tests are NOT unit tests. They don't test "correct" behavior — they test "existing" behavior. The existing behavior IS the specification for legacy code.

## Anti-Rationalization Table

See [../shared/references/anti-rationalization-table.md](../shared/references/anti-rationalization-table.md) for universal entries. Skill-specific:

| Excuse | Rebuttal |
|--------|----------|
| "The legacy code is too complex to understand" | If you can't understand it, you can't migrate it. Understand first, always. |
| "We'll rewrite it from scratch" | Rewrites fail at the same rate as the original development, but with higher risk because the spec is the existing code. |
| "We don't need characterization tests" | Without characterization tests, you cannot prove behavior preservation. |
| "We can migrate everything in one big batch" | Big batches hide big failures. Small batches isolate problems. |
| "The COBOL is going away anyway" | "Going away" code runs production for years. Treat it as production. |
| "We'll fix the behavior differences after migration" | Behavior differences ARE bugs. Fix them before merge, not after. |
| "The batch is small enough to skip human review" | Every batch touches production code. Every batch gets reviewed. |

## Language-Specific Patterns

### Java

See [references/language-specific/java-migration.md](references/language-specific/java-migration.md) for details.

- Version migration: Java 8 -> 11 -> 17 -> 21
- Framework migration: Spring -> Spring Boot, J2EE -> Jakarta EE
- Dependency updates with compatibility checks
- Characterization tests via JUnit 5 + AssertJ

### COBOL

See [references/language-specific/cobol-migration.md](references/language-specific/cobol-migration.md) for details.

- COBOL-to-Java or COBOL-to-Python translation patterns
- COPY book resolution and data structure mapping
- CICS/DB2 interaction preservation
- Paragraph-to-method mapping
- Characterization tests via golden-file comparison

### .NET

See [references/language-specific/dotnet-migration.md](references/language-specific/dotnet-migration.md) for details.

- Framework migration: .NET Framework -> .NET 6/8
- API compatibility analysis
- Configuration migration: web.config -> appsettings.json
- Characterization tests via xUnit + FluentAssertions

## Quick Reference

| Action | Command |
|--------|---------|
| Analyze legacy code | `scripts/analyze-legacy.sh --language=<lang>` |
| Plan migration | `scripts/plan-migration.sh --analysis=<file>` |
| Run batch transform | `scripts/run-batch-transform.sh --batch-size=10` |
| Verify behavior | `scripts/verify-behavior-preservation.sh` |

## Implementation

1. Run `scripts/analyze-legacy.sh` to understand the codebase
2. Write characterization tests for critical paths
3. Run `scripts/plan-migration.sh` to identify batches
4. For each batch:
   - Transform files via MaaS agent
   - Run characterization tests
   - Create PR
   - Wait for CI + human review
   - Merge or fix
5. After all batches: run full behavior verification
6. Document gaps and remaining tech debt

## Verification Exit Criteria

- [ ] Understanding document exists for the legacy codebase
- [ ] Characterization tests exist for critical paths
- [ ] Migration plan identifies batches with file groupings
- [ ] Each batch PR has passed CI
- [ ] Each batch PR has been reviewed by human
- [ ] Characterization tests pass after migration
- [ ] Behavior differences are documented (if any)
- [ ] Gaps and remaining tech debt are documented
- [ ] Rollback points are recorded for each batch

## Common Mistakes

- Migrating without characterization tests (cannot verify behavior)
- Batch size too large (50+ files per batch hides failures)
- Not stopping on batch failure (continue-on-error is forbidden)
- Rewriting instead of transforming (preserves behavior, not aesthetics)
- Skipping human review on "simple" batches
- Not documenting migration decisions (future maintainers need context)
- Not recording rollback points
- Treating characterization test failures as "test issues" rather than "behavior changes"

## Cross-Skill References

- Quality gates from [maas-ai-coding-quality-skill](../maas-ai-coding-quality-skill/) run on each batch PR
- Code review from [maas-code-review-and-security-skill](../maas-code-review-and-security-skill/) runs on each batch PR
- Spec-Plan-Build-Test from [maas-spec-plan-build-test-skill](../maas-spec-plan-build-test-skill/) is used for new code that replaces legacy components
- Security checklist: [../shared/references/security-checklist.md](../shared/references/security-checklist.md)
- Anti-rationalization table: [../shared/references/anti-rationalization-table.md](../shared/references/anti-rationalization-table.md)
