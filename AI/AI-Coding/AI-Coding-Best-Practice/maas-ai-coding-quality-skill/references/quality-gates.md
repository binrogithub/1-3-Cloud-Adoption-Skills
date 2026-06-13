# Quality Gates

## Gate Definitions

### Gate 1: Lint

**Purpose**: Enforce code style and catch common errors mechanically.

| Language | Linter | Config File |
|----------|--------|-------------|
| JavaScript/TypeScript | ESLint | `.eslintrc.js` or `eslint.config.js` |
| Java | Checkstyle | `checkstyle.xml` |
| Python | pylint / ruff | `.pylintrc` or `pyproject.toml` |
| Go | golangci-lint | `.golangci.yml` |
| Ruby | rubocop | `.rubocop.yml` |

**Pass**: Exit 0, 0 warnings, 0 errors
**Fail**: Any non-zero exit or any findings
**Evidence**: `{ "gate": "lint", "command": "...", "exit_code": 0, "warnings": 0, "errors": 0, "timestamp": "..." }`

### Gate 2: Test

**Purpose**: Verify all tests pass.

**Pass**: Exit 0, 0 failures
**Fail**: Any non-zero exit or any test failures
**Evidence**: `{ "gate": "test", "command": "...", "exit_code": 0, "failures": 0, "total": 42, "duration_s": 12.3, "timestamp": "..." }`

### Gate 3: Coverage

**Purpose**: Verify code coverage meets minimum threshold.

**Pass**: Coverage >= threshold per language
**Fail**: Coverage below threshold
**Evidence**: `{ "gate": "coverage", "command": "...", "exit_code": 0, "coverage_pct": 85.2, "threshold_pct": 80, "uncovered_files": [...], "timestamp": "..." }`

### Gate 4: Security

**Purpose**: Verify no critical or high severity security findings.

**Pass**: 0 findings with severity >= block_severity
**Fail**: Any finding with severity >= block_severity
**Evidence**: `{ "gate": "security", "command": "...", "exit_code": 0, "critical": 0, "high": 0, "medium": 2, "low": 5, "findings": [...], "timestamp": "..." }`

## CI Integration

### GitHub Actions

```yaml
- name: Quality Gate
  run: ./scripts/run-quality-gate.sh --all
  env:
    API_KEY: ${{ secrets.MAAS_API_KEY }}
```

### GitLab CI

```yaml
quality-gate:
  script: ./scripts/run-quality-gate.sh --all
  variables:
    API_KEY: $MAAS_API_KEY
```

### Pre-commit Hook

```yaml
- repo: local
  hooks:
    - id: quality-gate
      name: Quality Gate
      entry: ./scripts/run-quality-gate.sh --all
      language: system
      pass_filenames: false
```

## Gate Execution Order

1. Lint and Test can run **in parallel** (no dependencies)
2. Coverage depends on Test (must run after)
3. Security is independent but typically runs last (highest token cost)
4. Full sequence: `[lint || test] -> coverage -> security`
