# Credential Management

## Required Credentials

| MCP | Variables | Description |
|---|---|---|
| huaweicloud-pricing | HWCLOUD_ACCESS_KEY, HWCLOUD_SECRET_KEY, HWCLOUD_PROJECT_ID, HWCLOUD_REGION | Huawei Cloud AK/SK |
| huaweicloud-deploy | HWCLOUD_ACCESS_KEY, HWCLOUD_SECRET_KEY | Huawei Cloud AK/SK |
| huaweicloud-drs | (via Playwright session) | Console session cookies |
| huaweicloud-ticket | (via browser session) | Console session cookies + cftk |
| dataarts-deploy-agent | HWCLOUD_ACCESS_KEY, HWCLOUD_SECRET_KEY, HWCLOUD_PROJECT_ID, HWCLOUD_REGION, DLI_QUEUE | Huawei Cloud + DLI |

## Security Best Practices

1. Never store credentials in files committed to git
2. Use environment variables or secret management services
3. Rotate credentials regularly
4. Use IAM users with minimal required permissions
5. Never log or print credential values
6. Use .env.example as template, never .env with real values
