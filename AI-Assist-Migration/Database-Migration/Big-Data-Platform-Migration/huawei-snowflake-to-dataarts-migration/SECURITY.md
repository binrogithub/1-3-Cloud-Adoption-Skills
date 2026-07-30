# Security

## Secret Management

- No credentials stored in the package
- .env.example provided as template (never .env with real values)
- All examples use placeholders (<YOUR_*>, <INSTALLATION_ROOT>)

## Least Privilege

- IAM users should have only required permissions per MCP
- DRS: replication permissions only
- Ticket: ticket creation permissions only
- Pricing: read-only catalog access

## Read/Write Separation

| MCP | Read-Only Tools | Write Tools | Write Requires Approval |
|---|---|---|---|
| huaweicloud-pricing | 25 | 0 | N/A |
| huaweicloud-deploy | 3 | 1 | No (local files only) |
| huaweicloud-drs | 10 | 3 | Yes (explicit_approval) |
| huaweicloud-ticket | 8 | 2 | Implicit (use prepare_ticket first) |
| dataarts-deploy-agent | 4 | 2 | Yes (confirm=true) |

## CIDR Restrictions

- DRS MCP rejects 0.0.0.0/0 and CIDRs broader than /32
- All source access plans use /32 CIDR for DRS EIP

## Generated MCP Security

- Never use real credentials
- Never call cloud services
- Never create resources
- Marked as DRAFT/EXPERIMENTAL
- Require manual review before activation
