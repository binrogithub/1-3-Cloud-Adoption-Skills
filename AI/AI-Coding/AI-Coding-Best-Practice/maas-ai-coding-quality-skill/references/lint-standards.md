# Lint Standards

## Per-Language Linter Configuration

### JavaScript / TypeScript (ESLint)

```json
{
  "extends": ["eslint:recommended"],
  "rules": {
    "no-unused-vars": "error",
    "no-console": "warn",
    "eqeqeq": "error",
    "no-eval": "error",
    "no-implied-eval": "error",
    "no-new-func": "error"
  }
}
```

### Java (Checkstyle)

Key checks:
- `AvoidStarImport`
- `EmptyBlock`
- `MissingOverride`
- `MagicNumber`
- `LineLength` (max 120)
- `MethodLength` (max 150)

### Python (ruff)

```toml
[tool.ruff]
line-length = 120
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "SIM"]
ignore = ["E501"]
```

### Go (golangci-lint)

```yaml
linters:
  enable:
    - errcheck
    - govet
    - staticcheck
    - unused
    - gosimple
    - ineffassign
    - typecheck
```

### .NET (dotnet-format + analyzers)

```xml
<Project>
  <PropertyGroup>
    <AnalysisLevel>latest</AnalysisLevel>
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
</Project>
```

## MaaS-Compatible Defaults

All linter configs enforce:
- No hardcoded secrets (custom rule or plugin)
- No `console.log` / `print` in production code
- No `TODO` without issue reference
- No `FIXME` without issue reference
- Error on unused imports
- Error on unreachable code
