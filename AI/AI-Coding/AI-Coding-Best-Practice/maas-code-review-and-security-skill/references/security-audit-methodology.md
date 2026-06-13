# Security Audit Methodology

## Step 1: Identify Attack Surface

Map all entry points:
- HTTP endpoints (API routes, webhooks)
- User input forms
- File uploads
- Database queries
- Command-line arguments
- Environment variables
- MaaS API calls (model input is an attack surface for prompt injection)

## Step 2: Classify Inputs by Trust Level

| Trust Level | Examples | Validation Required |
|-------------|----------|---------------------|
| Untrusted | User form input, URL parameters, file uploads | Strict sanitization, length limits, type checks |
| Semi-trusted | API responses from external services | Schema validation, content-type checks |
| Trusted | Internal config, env vars, constants | Minimal (format checks only) |

## Step 3: Trace Data Flow

For each untrusted input, trace the data path:
1. Where does it enter? (source)
2. Where is it used? (sink)
3. What transformations happen along the way?
4. Are there sanitization/validation checkpoints?
5. Does it reach a sensitive operation? (DB query, command exec, MaaS prompt)

**Flag**: Any path from untrusted source to sensitive sink without sanitization is a finding.

## Step 4: Check Auth Boundaries

For each API endpoint:
- [ ] Requires authentication?
- [ ] Authentication is enforced (not just checked)?
- [ ] Authorization is correct (principle of least privilege)?
- [ ] Session handling is secure (no session fixation, proper timeout)?
- [ ] CORS is configured correctly (not `*` for authenticated endpoints)?

## Step 5: Scan for Secrets

Search patterns:
- API keys: `sk-`, `key-`, `AKIA`, hardcoded strings > 20 chars in quotes
- Tokens: `Bearer`, `token`, `jwt`, `session`
- Passwords: `password`, `passwd`, `pwd`, `secret`
- Connection strings: `mongodb://`, `mysql://`, `postgres://`
- Private keys: `BEGIN RSA PRIVATE KEY`, `BEGIN EC PRIVATE KEY`

**Action**: Every match is a finding. Severity = critical if committed to VCS.

## Step 6: Audit Dependencies

1. List all direct and transitive dependencies
2. Check each against CVE databases (npm audit, pip audit, trivy, Snyk)
3. Classify by severity
4. Check for abandoned/deprecated packages
5. Check for license compliance

## Step 7: Classify Findings

Map each finding to OWASP Top 10 category:

| Category | Code | Examples |
|----------|------|----------|
| Broken Access Control | A01 | Missing auth check, IDOR, privilege escalation |
| Cryptographic Failures | A02 | Weak TLS, hardcoded keys, unencrypted storage |
| Injection | A03 | SQL injection, XSS, prompt injection, command injection |
| Insecure Design | A04 | Missing rate limiting, no fallback, no circuit breaker |
| Security Misconfiguration | A05 | Default credentials, debug mode, open S3 bucket |
| Vulnerable Components | A06 | Known CVEs in dependencies |
| Auth Failures | A07 | Hardcoded passwords, weak session management |
| Data Integrity Failures | A08 | No input validation, no integrity checks |
| Logging Failures | A09 | Sensitive data in logs, no audit trail |
| SSRF | A10 | User-controlled URL fetching, internal network access |

## Step 8: Produce Evidence

For each finding, collect:
- File path and line number
- Code snippet showing the vulnerability
- HTTP request/response that demonstrates the issue (if applicable)
- Remediation code example
