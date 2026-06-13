# Security Checklist

## OWASP Top 10 (2021) with MaaS-Specific Considerations

| # | Category | MaaS Risk | Check |
|---|----------|-----------|-------|
| A01 | Broken Access Control | MaaS API key grants full model access; no per-endpoint RBAC | Verify API key scope is minimal |
| A02 | Cryptographic Failures | API keys transmitted over network; model responses may contain PII | Enforce HTTPS, redact PII before sending to MaaS |
| A03 | Injection | Prompt injection via user input passed to MaaS | Sanitize all user input before MaaS calls |
| A04 | Insecure Design | No rate limiting on MaaS calls; no fallback on model failure | Design rate limiter, circuit breaker, fallback |
| A05 | Security Misconfiguration | Default API keys in config files; debug logging enabled | Rotate keys, disable debug logs in production |
| A06 | Vulnerable Components | SDK dependencies with known CVEs; outdated proxy | Audit dependencies monthly, pin versions |
| A07 | Auth Failures | Hardcoded MaaS API keys in source code | Use env vars with 0640 file permissions |
| A08 | Data Integrity Failures | Model output used without validation; no schema check | Validate all MaaS responses against expected schema |
| A09 | Logging Failures | Sensitive data logged (API keys, model inputs/outputs) | Log metadata only; redact secrets |
| A10 | SSRF | MaaS proxy URL configurable; internal network exposure | Bind proxy to 127.0.0.1; validate MaaS URL against allowlist |

## Secret Detection Rules

- Never commit API keys, tokens, or credentials to version control
- Use `replace-with-your-maas-api-key` placeholder in all example files
- Store real keys in `.env` files with `0600` or `0640` permissions
- Add `.env` to `.gitignore`
- Scan for secrets before every commit (pre-commit hook or CI gate)

## Input Validation Requirements

- All user input sent to MaaS must be sanitized (strip control characters, limit length)
- No raw user input in system prompts (prompt injection risk)
- Validate MaaS response schema before processing
- Set `max_tokens` to limit output length

## Authentication/Authorization Patterns

- MaaS API key is the sole auth mechanism; treat it as a production secret
- Rotate API keys on a schedule (minimum quarterly)
- Use separate keys for development and production
- Log key usage for audit (key hash, not the key itself)

## Dependency Vulnerability Scanning

- Run `npm audit` / `pip audit` / `trivy` before every deployment
- Block deployment on critical or high CVEs
- Pin all dependency versions (no floating ranges in production)

## Network Security

- Bind all local proxies to `127.0.0.1` only (never `0.0.0.0`)
- Enforce HTTPS for all MaaS API calls
- Validate TLS certificates (no `rejectUnauthorized: false`)
- Use proxy allowlist for outbound connections

## Data Classification

- **Public**: Can be sent to MaaS without restriction
- **Internal**: Can be sent to MaaS with logging disabled
- **Confidential**: Must be redacted or anonymized before sending to MaaS
- **Restricted**: Must NOT be sent to MaaS under any circumstances

## Evidence Requirements

Every security finding must include:
- File path and line number
- Severity (critical / high / medium / low)
- OWASP category
- Specific evidence (code snippet, log entry, or test output)
- Remediation steps
