# Source Discovery Report

## Date

2026-07-27

## Source Package

/root/huawei-cloud-mcp-suite-handoff

## MCPs Discovered

| MCP | Tools | Status | Source |
|---|---|---|---|
| huaweicloud-pricing | 25 | READY | handoff + source repo |
| huaweicloud-deploy | 4 | READY | handoff + source repo |
| huaweicloud-drs | 13 | READY | handoff + migration-lab |
| huaweicloud-ticket | 10 | READY | handoff + source repo |
| dataarts-deploy-agent | 6 | PARTIAL | handoff + source repo |

## Additional Sources Inspected

- /root/opencode-pricing-assistant (source repo with all MCPs)
- /root/migration-lab (DRS migration operator + demo project)
- /root/huawei-cloud-mcp-suite-handoff (existing handoff package)

## Use Cases Found

| Use Case | MCP | Status |
|---|---|---|
| CCE cross-region Velero | huaweicloud-deploy | NOT_IMPLEMENTED |
| PostgreSQL ECS to RDS DRS | huaweicloud-drs | DOCUMENTED |
| Snowflake to DataArts | dataarts-deploy-agent | PARTIAL |

## Key Findings

1. No skill convention exists in the current codebase
2. MCPs are well-documented with README and use cases
3. DRS MCP has robust safety guards (58 tests)
4. CCE/Velero migration is documented but not implemented
5. DataArts migration works for demo/POC only
6. A more advanced DRS migration-operator exists in migration-lab (15 tools, API+KooCLI)
