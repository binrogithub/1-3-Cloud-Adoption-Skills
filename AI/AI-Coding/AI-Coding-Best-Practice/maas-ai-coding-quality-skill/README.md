# MaaS AI Coding Quality Skill

## Architecture

```
Developer / AI Agent
  -> writes code
  -> scripts/run-quality-gate.sh --all
  -> Gate 1: Lint -> Gate 2: Test -> Gate 3: Coverage -> Gate 4: Security
  -> All pass? -> commit allowed
  -> Any fail? -> commit blocked, findings reported
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
maas-ai-coding-quality-skill/
  SKILL.md                              # This skill definition
  README.md                             # This file
  references/
    quality-gates.md                    # Gate definitions, pass/fail criteria, CI integration
    lint-standards.md                   # Per-language linter configuration templates
    verification-exit-criteria.md       # Formal "verified" definition per gate
  scripts/
    run-quality-gate.sh                 # Main orchestrator (--gate=<name> or --all)
    check-lint.sh                       # Auto-detect language, run linter, parse output
    verify-coverage.sh                  # Run coverage, compare against threshold
  agents/
    openai.yaml                         # Agent interface referencing code-reviewer persona
  assets/
    config/
      quality-gates.json                # Gate sequence, coverage thresholds, severity block level
```

## API Key Safety Rules

- Never print, persist, or commit real MaaS API keys
- Use `replace-with-your-maas-api-key` placeholder in all example files
- Store real keys in `.env` files with `0600` or `0640` permissions
- Add `.env` to `.gitignore`
- Reference keys as `$API_KEY` in scripts, never hardcode

## Configuration

Edit `assets/config/quality-gates.json` to customize:

- `gates`: Enable/disable individual gates
- `coverage_thresholds`: Set per-language coverage minimums
- `security_block_severity`: Set the severity level that blocks merge (default: "high")
- `parallel_gates`: Gates that can run concurrently (default: lint + test)

## Validation

1. Run `scripts/run-quality-gate.sh --all` on a sample project
2. Verify all four gates execute and produce evidence artifacts
3. Verify a failing gate blocks the pipeline and reports findings
4. Verify evidence artifacts are in JSON format with timestamp and command

## MaaS Token Consumption

- Local gates (lint, test, coverage): 0 MaaS tokens
- Security gate (MaaS-backed audit): ~6k tokens per file
- Full gate run (10 files, security via MaaS): ~60k total tokens
