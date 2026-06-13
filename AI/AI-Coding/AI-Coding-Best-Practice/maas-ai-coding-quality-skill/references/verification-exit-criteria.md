# Verification Exit Criteria

## What "Verified" Means

Verified is NOT:
- "The code looks correct"
- "I tested it manually"
- "It worked on my machine"
- "The AI said it's fine"

Verified IS:
- The automated gate script exited 0
- The evidence artifact exists and is parseable
- The evidence artifact contains the required fields
- The evidence was produced after the most recent code change

## Per-Gate Exit Criteria

### Lint Gate

| Criterion | Evidence |
|-----------|----------|
| Linter exited 0 | `exit_code == 0` in evidence JSON |
| Zero warnings | `warnings == 0` in evidence JSON |
| Zero errors | `errors == 0` in evidence JSON |
| All source files checked | File count matches `git ls-files` count |

### Test Gate

| Criterion | Evidence |
|-----------|----------|
| Test runner exited 0 | `exit_code == 0` in evidence JSON |
| Zero failures | `failures == 0` in evidence JSON |
| No skipped tests without documented reason | Skipped count == 0 or each skip has issue reference |

### Coverage Gate

| Criterion | Evidence |
|-----------|----------|
| Coverage tool exited 0 | `exit_code == 0` in evidence JSON |
| Coverage >= threshold | `coverage_pct >= threshold_pct` in evidence JSON |
| Coverage measured for all source modules | Uncovered modules list is empty or acceptable |

### Security Gate

| Criterion | Evidence |
|-----------|----------|
| Security scan completed | `exit_code` is 0 or 1 (findings found) in evidence JSON |
| No critical findings | `critical == 0` in evidence JSON |
| No high findings | `high == 0` in evidence JSON |
| All findings have remediation | Each finding has non-empty `remediation` field |

## Evidence Artifact Format

```json
{
  "gate": "<gate-name>",
  "command": "<full-command>",
  "exit_code": 0,
  "timestamp": "2026-05-11T10:30:00Z",
  "duration_s": 12.3,
  "result": "pass",
  "details": {}
}
```

The `details` object contains gate-specific fields (warnings, failures, coverage_pct, findings, etc.).
