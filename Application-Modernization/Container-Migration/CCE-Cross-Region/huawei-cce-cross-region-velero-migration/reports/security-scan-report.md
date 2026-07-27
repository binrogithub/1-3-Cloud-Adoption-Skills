# Security Scan Report

## Date

2026-07-27

## Scan Method

Static analysis of all files in the delivery package for sensitive patterns.

## Patterns Scanned

- AK/SK patterns (HWCLOUD_ACCESS_KEY, HW_ACCESS_KEY, etc.)
- Password patterns (password, passwd, pwd)
- Token patterns (token, api_key, apiKey)
- Private key patterns (-----BEGIN PRIVATE KEY-----)
- .env files with real values
- terraform.tfstate files
- 0.0.0.0/0 CIDR patterns
- Real IP addresses (in examples/configs)
- Real project IDs
- Real bucket names
- session.json / cookies

## Findings

| Finding | Severity | Status | Notes |
|---|---|---|---|
| .env.example contains placeholders | INFO | ACCEPTABLE | Uses <YOUR_*> placeholders |
| OpenCode config uses <INSTALLATION_ROOT> | INFO | ACCEPTABLE | No real paths |
| DRS EIP examples use example IPs | INFO | ACCEPTABLE | Clearly example values |
| No .git directories found | INFO | PASS | Clean |
| No node_modules found | INFO | PASS | Clean |
| No .env with real values | INFO | PASS | Clean |
| No terraform.tfstate found | INFO | PASS | Clean |

## Result

**PASS** — No confirmed secrets or sensitive data found in the delivery package.
