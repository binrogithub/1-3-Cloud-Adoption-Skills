# Dependencies

## MCP Dependencies

| MCP | Dependency | Version |
|---|---|---|
| huaweicloud-pricing | @modelcontextprotocol/sdk | latest |
| huaweicloud-pricing | axios | ^1.16.1 |
| huaweicloud-deploy | @modelcontextprotocol/sdk | latest |
| huaweicloud-drs | @modelcontextprotocol/sdk | ^1.12.1 |
| huaweicloud-drs | playwright | ^1.52.0 |
| huaweicloud-ticket | @modelcontextprotocol/sdk | latest |
| huaweicloud-ticket | axios | ^1.16.1 |
| dataarts-deploy-agent | @modelcontextprotocol/sdk | ^1.29.0 |
| dataarts-deploy-agent | dotenv | latest |
| dataarts-deploy-agent | js-yaml | latest |

## External Tools

| Tool | Used By | Purpose |
|---|---|---|
| Playwright/Chromium | huaweicloud-drs | DRS console automation |
| Terraform CLI | huaweicloud-deploy | Infrastructure validation |
| KooCLI | huaweicloud-drs (migration-operator) | DRS API operations |
