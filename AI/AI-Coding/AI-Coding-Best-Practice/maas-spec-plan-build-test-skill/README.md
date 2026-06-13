# MaaS Spec-Plan-Build-Test Skill

## Architecture

```
Requirements
  -> Spec (MaaS glm-5.1, ~8k tokens) -> specification.md
  -> Plan (MaaS glm-5.1, ~13k tokens) -> plan.md
  -> HUMAN APPROVAL (mandatory gate)
  -> Build (MaaS glm-5.1, ~25k tokens/file) -> code changes
  -> Quality Gate (maas-ai-coding-quality-skill)
  -> Test (MaaS glm-5.1, ~18k tokens) -> test-results.md
  -> Ship
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
maas-spec-plan-build-test-skill/
  SKILL.md                              # Skill definition
  README.md                             # This file
  references/
    spec-template.md                    # Specification document template
    plan-template.md                    # Plan document template
    build-standards.md                  # Surgical change rules
    test-standards.md                   # Test generation rules
    phase-gate-criteria.md             # Formal gate criteria per phase
  scripts/
    run-spec-phase.sh                   # Spec generation via MaaS
    run-plan-phase.sh                   # Plan generation via MaaS
    run-build-phase.sh                  # Implementation via MaaS
    run-test-phase.sh                   # Test generation + execution via MaaS
    run-full-workflow.sh               # Orchestrates all phases with gates
  agents/
    openai.yaml                         # Agent interface
  assets/
    config/
      workflow-config.json             # Phase sequence, gate strictness
```

## API Key Safety Rules

- Never print, persist, or commit real MaaS API keys
- Use `replace-with-your-maas-api-key` placeholder in all example files
- Store real keys in `.env` files with `0600` or `0640` permissions
- Add `.env` to `.gitignore`

## Configuration

Edit `assets/config/workflow-config.json` to customize:

- `phases`: Enable/disable phases (default: spec, plan, build, test)
- `gates.spec.auto`: Auto-approve spec gate (default: true)
- `gates.plan.auto`: Auto-approve plan gate (default: **false** — human review required)
- `vertical_slicing`: Enforce vertical slice discipline (default: true)
- `max_spec_iterations`: Max spec refinement rounds (default: 3)
- `max_plan_iterations`: Max plan revision rounds (default: 2)

## Validation

1. Run `scripts/run-full-workflow.sh` on a sample feature request
2. Verify all phase artifacts are produced (specification.md, plan.md, implementation.md, test-results.md)
3. Verify the plan gate requires human approval
4. Verify the build phase runs the quality gate
5. Verify the test phase reports coverage

## MaaS Token Consumption

- Spec phase: ~8k tokens per feature
- Plan phase: ~13k tokens per feature
- Build phase: ~25k tokens per file changed
- Test phase: ~18k tokens per test suite
- Full workflow (5 files): ~180k total tokens
- **This is the highest token-consuming skill; rate limit handling is critical**
