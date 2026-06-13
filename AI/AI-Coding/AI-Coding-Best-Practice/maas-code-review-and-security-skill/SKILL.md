---
name: maas-code-review-and-security-skill
description: Use this skill when running structured code review or security audit on code changes, especially before merge or deployment. TRIGGER when the user needs code review with findings, security vulnerability scan, OWASP classification, secret detection, dependency audit, or evidence-based review report for compliance.
---

# MaaS Code Review and Security Skill

## Overview

Code review and security audit are separate but related. Review focuses on correctness, style, and maintainability. Audit focuses on vulnerabilities, secrets, and compliance. Both require evidence-based findings, not opinions. MaaS-backed agents perform the analysis; humans make the decisions.

## When to Use

| Situation | Route |
|-----------|-------|
| Pre-merge code review | Run full review + security audit |
| Security-only scan | Run `scripts/run-security-audit.sh` |
| Review-only (no security) | Run `scripts/run-review.sh --no-security` |
| Dependency vulnerability check | Run audit with `--scope=dependencies` |
| Secret detection | Run audit with `--scope=secrets` |
| Compliance report needed | Run audit, then `scripts/format-findings.sh --format=compliance` |

**When NOT to use:**
- Automated linting (use `maas-ai-coding-quality-skill` Gate 1 instead)
- Style-only feedback (use linter, not human-scale review)
- Trivial changes (< 5 lines, no logic change)

## Core Pattern

```
Code Changes (git diff)
  -> MaaS-backed code-reviewer agent (correctness, style, maintainability)
  -> MaaS-backed security-auditor agent (OWASP, secrets, dependencies)
  -> Merge findings, deduplicate, classify severity
  -> Produce evidence-based report
  -> Human makes approve/reject decision
```

## Agent Personas

### code-reviewer

Focus: correctness, style, test coverage, maintainability.
Reference: [../shared/agents/code-reviewer.yaml](../shared/agents/code-reviewer.yaml)

Five-axis review:
1. **Correctness**: Does the code do what it claims?
2. **Readability**: Can a new team member understand this?
3. **Architecture**: Does this change fit the existing design?
4. **Security**: Are there vulnerabilities? (shallow check; deep audit is security-auditor)
5. **Performance**: Are there regressions?

### security-auditor

Focus: OWASP Top 10, secret detection, input validation, auth.
Reference: [../shared/agents/security-auditor.yaml](../shared/agents/security-auditor.yaml)

These are **separate agents**. The code-reviewer does not perform deep security analysis. The security-auditor does not comment on style.

## Anti-Rationalization Table

See [../shared/references/anti-rationalization-table.md](../shared/references/anti-rationalization-table.md) for universal entries. Skill-specific:

| Excuse | Rebuttal |
|--------|----------|
| "This code has been working for years" | Working is not the same as secure. Age increases attack surface. |
| "The vulnerability requires internal network access" | Lateral movement is real. Defense in depth is mandatory. |
| "We'll fix security issues after the feature ships" | Ship-then-fix never fixes. Security is a gate, not a backlog item. |
| "The dependency is only used in dev" | Dev dependencies run in CI. CI has production credentials. |
| "A code review would slow us down" | A production incident slows you down more. Review is cheaper than remediation. |
| "The finding severity is debatable" | When in doubt, round up. False positives are cheap; false negatives are catastrophic. |

## Review Checklist

See [references/review-checklist.md](references/review-checklist.md) for the full checklist. Summary:

- **Correctness**: Does the code do what it claims? Are edge cases handled?
- **Error handling**: Are errors caught, logged, and propagated correctly?
- **Test coverage**: Are new paths tested? Are tests derived from spec, not implementation?
- **Style**: Does it conform to project standards? (Linter should catch this; review catches what linter can't)
- **Documentation**: Are public APIs documented? Are ADRs updated?

## Security Audit Methodology

See [references/security-audit-methodology.md](references/security-audit-methodology.md) for the full methodology. Summary:

1. Identify attack surface (inputs, outputs, network, storage)
2. Classify each input by trust level
3. Trace data flow from untrusted inputs to sensitive operations
4. Check authentication and authorization at each boundary
5. Scan for secrets (API keys, tokens, passwords)
6. Audit dependencies for known vulnerabilities
7. Classify findings by OWASP category and severity
8. Produce evidence for each finding

## Finding Format

Every finding must include all fields:

```json
{
  "id": "F-001",
  "file": "src/auth/handler.py",
  "line": 42,
  "severity": "high",
  "category": "OWASP-A07",
  "title": "Hardcoded API key in auth handler",
  "description": "MaaS API key is hardcoded instead of read from environment variable",
  "evidence": "Line 42: API_KEY = 'sk-...'",
  "remediation": "Replace with os.environ['MAAS_API_KEY'] and use env file with 0640 permissions",
  "persona": "security-auditor"
}
```

Severity levels: `critical` > `high` > `medium` > `low` > `info`

## Quick Reference

| Action | Command |
|--------|---------|
| Full review + audit | `scripts/run-review.sh --with-security` |
| Review only | `scripts/run-review.sh` |
| Security audit only | `scripts/run-security-audit.sh` |
| Secret detection | `scripts/run-security-audit.sh --scope=secrets` |
| Dependency audit | `scripts/run-security-audit.sh --scope=dependencies` |
| Format findings | `scripts/format-findings.sh --format=markdown` |

## Implementation

1. Identify changed files (`git diff --name-only`)
2. Run code-reviewer persona on changed files via MaaS
3. Run security-auditor persona on changed files via MaaS
4. Merge and deduplicate findings
5. Classify by severity
6. Block merge if any critical/high finding exists
7. Produce report in configured format (markdown, JSON, SARIF, compliance)

## Verification Exit Criteria

- [ ] Review produced findings for every changed file
- [ ] Every finding has all required fields (id, file, line, severity, category, evidence, remediation)
- [ ] No finding has severity >= block_severity without blocking merge
- [ ] Security audit actually ran (evidence: non-empty findings list or explicit "no findings" with scan confirmation)
- [ ] Report is in the configured format
- [ ] Findings are deduplicated (no duplicate id/file/line combos)

## Common Mistakes

- Running review and audit as a single agent call (separation of concerns)
- Accepting "no findings" without evidence that the scan actually ran
- Classifying all findings as "low" to avoid blocking merge
- Not scanning dependencies because "they're trusted"
- Reviewing only changed lines without context (review the diff with surrounding context)
- Not redacting secrets in findings that are shared outside the team
- Running the same review on unchanged code (wastes MaaS tokens)

## Cross-Skill References

- Quality gates from [maas-ai-coding-quality-skill](../maas-ai-coding-quality-skill/) trigger this skill's security audit at Gate 4
- Test generation from [maas-spec-plan-build-test-skill](../maas-spec-plan-build-test-skill/) is recommended when review finds untested code
- Legacy code audit uses [maas-legacy-code-migration-skill](../maas-legacy-code-migration-skill/) for COBOL/Java-specific patterns
- Security checklist: [../shared/references/security-checklist.md](../shared/references/security-checklist.md)
- Anti-rationalization table: [../shared/references/anti-rationalization-table.md](../shared/references/anti-rationalization-table.md)
