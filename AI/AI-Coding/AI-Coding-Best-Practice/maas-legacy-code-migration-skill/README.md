# MaaS Legacy Code Migration Skill

## Architecture

```
Legacy Codebase
  -> analyze-legacy.sh (MaaS glm-5.1, ~15k tokens/file)
  -> Characterization tests (MaaS glm-5.1, ~8k tokens/test)
  -> plan-migration.sh (MaaS glm-5.1, ~13k tokens)
  -> Batch loop:
       -> run-batch-transform.sh (MaaS glm-5.1, ~25k tokens/file)
       -> verify-behavior-preservation.sh
       -> PR -> CI -> Human Review -> Merge
  -> Final behavior verification
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
maas-legacy-code-migration-skill/
  SKILL.md                              # Skill definition
  README.md                             # This file
  references/
    legacy-patterns.md                  # Common legacy code patterns
    migration-methodology.md            # Step-by-step methodology
    batch-transform-pattern.md          # Reviewable batch pattern
    behavior-preservation.md            # Characterization test methodology
    language-specific/
      java-migration.md                 # Java version/framework migration
      cobol-migration.md                # COBOL-to-modern translation
      dotnet-migration.md               # .NET framework migration
  scripts/
    analyze-legacy.sh                   # MaaS agent reads code, produces understanding doc
    plan-migration.sh                   # MaaS agent plans migration batches
    run-batch-transform.sh              # MaaS agent transforms a batch
    verify-behavior-preservation.sh     # Run characterization tests, compare before/after
  agents/
    openai.yaml                         # Agent interface
  assets/
    config/
      migration-config.json             # Batch size, languages, test frameworks
```

## API Key Safety Rules

- Never print, persist, or commit real MaaS API keys
- Use `replace-with-your-maas-api-key` placeholder in all example files
- Store real keys in `.env` files with `0600` or `0640` permissions
- **Additional**: Legacy code may contain hardcoded credentials. Flag and redact these in migration artifacts. Do not copy credentials to the new codebase.

## Configuration

Edit `assets/config/migration-config.json` to customize:

- `batch_size`: Files per migration batch (default: 10)
- `languages`: Supported languages for migration (default: java, cobol, dotnet)
- `characterization_test_frameworks`: Test framework per language
- `stop_on_batch_failure`: Stop migration when a batch fails (default: true)
- `require_human_review`: Require human review per batch (default: true)
- `degrees_of_freedom`: Freedom level for transformations (default: low)

## Validation

1. Run `scripts/analyze-legacy.sh --language=java` on a sample legacy project
2. Verify understanding document is produced
3. Write characterization tests and verify they pass on the original code
4. Run `scripts/plan-migration.sh` and verify batch groupings are sensible
5. Run one batch and verify characterization tests still pass

## MaaS Token Consumption

- Analysis phase: ~15k tokens per file analyzed
- Characterization test generation: ~8k tokens per test
- Migration planning: ~13k tokens per plan
- Batch transformation: ~25k tokens per file transformed
- Behavior verification: local (0 MaaS tokens)
- One batch (10 files): ~300k total tokens
- **This is the second-highest token-consuming skill; batch sizing must account for rate limits**
