---
name: maas-ai-coding-quality-skill
description: Use this skill when enforcing AI coding quality gates, linting standards, and verification checklists before code reaches review or production. TRIGGER when the user needs quality gates for AI-generated code, lint configuration for MaaS-backed projects, coverage verification, style conformance checks, or evidence-based quality exit criteria.
---

# MaaS AI Coding Quality Skill

## Overview

AI-generated code must pass the same quality gates as human-written code. This skill defines four sequential gates (lint, test, coverage, security) and enforces them as non-negotiable exit criteria. MaaS-backed agents generate code; this skill ensures that code is verified, not assumed correct.

## When to Use

| Situation | Action |
|-----------|--------|
| AI agent generated code | Run quality gate before commit |
| Pre-commit hook setup | Configure gate scripts |
| CI pipeline integration | Add gate checks to pipeline |
| Code quality baseline | Measure and document current state |
| Quality gate customization | Adjust thresholds per project |
| Coverage verification | Run `scripts/verify-coverage.sh` |
| Lint enforcement | Run `scripts/check-lint.sh` |

**When NOT to use:**
- One-off scripts that will never be committed
- Prototype/spike code explicitly marked as throwaway
- Documentation-only changes (lint + test still apply; coverage + security may be skipped)

## Core Pattern

```
AI Coding Agent (MaaS glm-5.1)
  -> generates code
  -> Gate 1: Lint (zero warnings)
  -> Gate 2: Test (all pass)
  -> Gate 3: Coverage (meets threshold)
  -> Gate 4: Security (no critical/high findings)
  -> All pass? -> allow commit/merge
  -> Any fail? -> block, report findings, require fix
```

Each gate produces evidence: command, exit code, output summary, timestamp.

## Quality Gates

### Gate 1: Lint

- **Command**: `scripts/check-lint.sh`
- **Pass condition**: Exit 0, 0 warnings
- **Evidence**: Linter output, warning count, file list
- **Runs**: Auto-detects project language, runs appropriate linter

### Gate 2: Test

- **Command**: `scripts/run-quality-gate.sh --gate=test`
- **Pass condition**: Exit 0, 0 test failures
- **Evidence**: Test output, failure list, duration
- **Runs**: Full test suite

### Gate 3: Coverage

- **Command**: `scripts/verify-coverage.sh --threshold=80`
- **Pass condition**: Exit 0, coverage >= threshold (per language)
- **Evidence**: Coverage percentage, uncovered files/lines
- **Thresholds**: Java 80%, Python 70%, Go 60%, JavaScript 70%

### Gate 4: Security

- **Command**: Delegates to `maas-code-review-and-security-skill`
- **Pass condition**: 0 critical/high findings
- **Evidence**: Security findings JSON, severity classification
- **Runs**: MaaS-backed security auditor persona

## Anti-Rationalization Table

See [../shared/references/anti-rationalization-table.md](../shared/references/anti-rationalization-table.md) for universal entries. Skill-specific:

| Excuse | Rebuttal |
|--------|----------|
| "AI-generated code doesn't need linting" | AI models reproduce training data patterns, including bad ones. Lint everything. |
| "The quality gate slows development" | Ungated code slows production. Fix time compounds with time-in-codebase. |
| "Coverage is good enough at 50%" | Each uncovered line is an unverified contract. Raise the threshold incrementally. |
| "The security gate is overkill for this change" | Every change expands the attack surface. Run the gate. |
| "I'll fix the lint warnings later" | Lint warnings are debt. Debt compounds. Fix now. |

## Quick Reference

| Gate | Command | Pass Condition |
|------|---------|----------------|
| Lint | `scripts/check-lint.sh` | exit 0, 0 warnings |
| Test | `scripts/run-quality-gate.sh --gate=test` | exit 0, 0 failures |
| Coverage | `scripts/verify-coverage.sh --threshold=80` | exit 0, coverage >= threshold |
| Security | Reference `maas-code-review-and-security-skill` | 0 critical/high |
| All | `scripts/run-quality-gate.sh --all` | all gates pass |

## Implementation

1. Configure linter for project language (see `references/lint-standards.md`)
2. Set coverage thresholds in `assets/config/quality-gates.json`
3. Run `scripts/run-quality-gate.sh --all` on current codebase
4. Fix any existing violations
5. Add gate to pre-commit hook or CI pipeline
6. Verify gate runs on every AI-generated code commit
7. Configure evidence artifact storage (JSON format, CI artifact upload)

## Verification Exit Criteria

Code does not pass the gate until ALL of:

- [ ] Lint exits 0 with 0 warnings
- [ ] Test suite exits 0 with 0 failures
- [ ] Coverage meets language-specific threshold
- [ ] Security scan has 0 critical/high findings
- [ ] Evidence artifacts exist for each gate (JSON format)
- [ ] Evidence artifacts include timestamp and command

## Common Mistakes

- Skipping the security gate because "it's just a refactor"
- Setting coverage threshold to 0 to "unblock" the pipeline
- Running gates sequentially when they could run in parallel (lint + test can be parallel; coverage depends on test)
- Not persisting evidence artifacts (gate results must be auditable)
- Accepting "no output" as "gate passed" (verify exit code explicitly)
- Running the same gate twice on unchanged code (wastes tokens; re-run only when code has changed)

## Cross-Skill References

- Security gate delegates to [maas-code-review-and-security-skill](../maas-code-review-and-security-skill/) for deep security audit
- Test gate delegates to [maas-spec-plan-build-test-skill](../maas-spec-plan-build-test-skill/) for test generation when coverage is insufficient
- Quality gate for migrated code delegates to [maas-legacy-code-migration-skill](../maas-legacy-code-migration-skill/) for behavior preservation checks
- Security checklist: [../shared/references/security-checklist.md](../shared/references/security-checklist.md)
- Testing checklist: [../shared/references/testing-checklist.md](../shared/references/testing-checklist.md)
- Anti-rationalization table: [../shared/references/anti-rationalization-table.md](../shared/references/anti-rationalization-table.md)
