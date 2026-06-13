# MaaS Code Review and Security Skill

## Architecture

```
Git diff (changed files)
  -> code-reviewer agent (MaaS glm-5.1, ~3k input tokens/file)
  -> security-auditor agent (MaaS glm-5.1, ~4k input tokens/file)
  -> Merge + classify findings
  -> Report (markdown, JSON, SARIF, or compliance format)
  -> Human approve/reject
```

## Default MaaS Configuration

| Setting | Value |
|---------|-------|
| Base URL | `https://api-ap-southeast-1.modelarts-maas.com/openai/v1` |
| Model | `glm-5.1` |
| Context Tokens | 190,000 |
| Max Output Tokens | 32,768 |

## Files

```
maas-code-review-and-security-skill/
  SKILL.md                              # Skill definition
  README.md                             # This file
  references/
    review-checklist.md                 # Code review checklist
    security-audit-methodology.md       # Step-by-step security audit process
    finding-format.md                   # JSON schema for findings
    owasp-maas-mapping.md              # OWASP Top 10 to MaaS risk mapping
  scripts/
    run-review.sh                       # Orchestrates code-reviewer persona
    run-security-audit.sh              # Orchestrates security-auditor persona
    format-findings.sh                  # Convert JSON findings to report formats
  agents/
    openai.yaml                         # Agent interface
  assets/
    config/
      review-config.json               # Severity thresholds, excluded paths, report format
```

## API Key Safety Rules

- Never print, persist, or commit real MaaS API keys
- Use `replace-with-your-maas-api-key` placeholder in all example files
- Store real keys in `.env` files with `0600` or `0640` permissions
- **Additional**: Security findings may contain code snippets with secrets. Redact secrets in reports shared outside the team.

## Configuration

Edit `assets/config/review-config.json` to customize:

- `block_on_severity`: Severity level that blocks merge (default: "high")
- `excluded_paths`: Paths to skip during review (default: vendor/, node_modules/, .git/)
- `owasp_categories`: OWASP categories to check (default: all 10)
- `report_format`: Output format (markdown, json, sarif, compliance)
- `max_findings_per_file`: Limit findings per file to prevent flooding

## Validation

1. Run `scripts/run-review.sh --with-security` on a test repository with known findings
2. Verify all known findings are detected
3. Verify findings include all required fields
4. Verify merge is blocked on critical/high findings
5. Verify report is in the configured format

## MaaS Token Consumption

- Code review: ~5k tokens per file analyzed
- Security audit: ~7k tokens per file analyzed
- Secret detection: local (0 MaaS tokens)
- Dependency audit: ~2k tokens per dependency
- Full review + audit (10 files): ~80k total tokens
