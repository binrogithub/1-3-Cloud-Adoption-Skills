# Contributing

## Adding a New Skill

1. Copy shared/templates/SKILL_TEMPLATE.md to skills/<new-skill>/SKILL.md
2. Copy shared/templates/SKILL_README_TEMPLATE.md to skills/<new-skill>/README.md
3. Create skill.yaml and mcp-dependencies.yaml
4. Create docs/, workflows/, prompts/, examples/, tests/
5. Document all capability gaps
6. Set initial status to DRAFT or EXPERIMENTAL
7. Run validation tests
8. Submit for review

## Adding a New MCP

1. Use mcp-capability-builder skill
2. Follow the generated scaffold
3. Implement tool contracts
4. Write tests (unit + safety)
5. Security review
6. Manual review and promotion

## Branch Conventions

- main: stable release
- develop: integration
- feature/<skill-name>: new skill development
- fix/<skill-name>: bug fixes

## Versioning

SemVer (MAJOR.MINOR.PATCH)
