# Huawei Cloud Migration Skills

## Purpose

Organized library of migration skills for Huawei Cloud. Each skill represents a complete migration scenario, orchestrates one or more MCPs, and clearly documents its capabilities, limitations, and gaps.

The primary functional unit is the **migration skill**, not the individual MCP.

## Architecture

```
huawei-cloud-migration-skills-handoff/
├── skills/              # Migration skills (primary unit)
├── shared-skills/       # Shared skills (mcp-capability-builder)
├── shared-mcps/         # Shared MCPs (references)
├── integrations/        # External integrations (Playwright)
├── shared/              # Shared documentation, schemas, templates
├── inventory/           # Dependency registries and matrices
└── reports/             # Analysis and validation reports
```

## Skills catalog

| Skill | Scenario | Primary MCP | Risk | Maturity |
|---|---|---|---|---|
| huawei-cce-cross-region-velero-migration | CCE cross-region with Velero | huaweicloud-deploy | High | EXPERIMENTAL |
| huawei-postgresql-ecs-to-rds-drs-cross-region | PostgreSQL ECS→RDS with DRS | huaweicloud-drs | High | READY_WITH_WARNINGS |
| huawei-snowflake-to-dataarts-migration | Snowflake→DataArts | dataarts-deploy-agent | Medium | PARTIAL |
| mcp-capability-builder | Gap analysis and MCP generation | None | Low | READY_WITH_WARNINGS |

## How a skill works

1. A skill is loaded into the agent (OpenCode/Hermes)
2. The agent reads SKILL.md for operational instructions
3. The agent reads skill.yaml for configuration
4. The agent verifies that required MCPs are available
5. The agent follows the workflow phase by phase
6. Each phase classifies its automation level
7. Capability gaps are documented and handled explicitly

## Relationship between skills and MCPs

| Skill | Pricing | Deploy | DRS | Ticket | DataArts | Playwright |
|---|---|---|---|---|---|---|
| CCE Velero | optional | **required** | - | optional | - | optional |
| PostgreSQL DRS | optional | - | **required** | optional | - | - |
| Snowflake DataArts | optional | - | - | optional | **required** | optional |
| Capability Builder | - | - | - | - | - | - |

## Capability gap workflow

1. Skill identifies a gap during a phase
2. Gap is documented with ID, phase, required capability
3. mcp-capability-builder is invoked for analysis
4. Decision: USE_EXISTING_TOOL, EXTEND_EXISTING_MCP, CREATE_NEW_MCP, MANUAL_STEP
5. If an MCP is generated: marked as DRAFT, requires manual review
6. Never activated automatically

## How to generate a missing MCP

1. Identify the real gap (not just a different name)
2. Invoke mcp-capability-builder with the gap details
3. Review the generated scaffold
4. Run local tests
5. Complete the implementation
6. Security review
7. Promote from DRAFT → EXPERIMENTAL → READY_FOR_REVIEW → READY

## Installation

See [shared/docs/installation.md](shared/docs/installation.md)

## Configuration

See [shared/docs/opencode-integration.md](shared/docs/opencode-integration.md)

## Usage with OpenCode

```bash
# Load a skill
skill huawei-postgresql-ecs-to-rds-drs-cross-region

# Follow the agent-guided workflow
```

## Usage with Hermes

Similar to OpenCode. Load the skill and follow the workflow.

## Testing

See [reports/test-report.md](reports/test-report.md)

## Security

See [SECURITY.md](SECURITY.md) and [shared/docs/security-guidelines.md](shared/docs/security-guidelines.md)

## Publishing to Git

1. Create a Git repository
2. Copy the ZIP contents to the repository
3. Verify no secrets are present (see security-scan-report.md)
4. Initial commit
5. Set up CI/CD for skill validation

## Limitations

- CCE cross-region Velero: EXPERIMENTAL (most phases are manual)
- Snowflake→DataArts: PARTIAL (demo/POC flow only)
- DRS VPN: NOT_IMPLEMENTED (public Internet only)
- DRS pricing: BLOCKED on huaweicloud-pricing MCP

## Scenario status

| Scenario | Maturity | Automated phases | Gaps |
|---|---|---|---|
| CCE cross-region Velero | EXPERIMENTAL | 0/10 | 7 |
| PostgreSQL ECS→RDS DRS | READY_WITH_WARNINGS | 4/10 | 7 |
| Snowflake→DataArts | PARTIAL | 4/10 | 6 |
