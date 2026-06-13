# OWASP Top 10 to MaaS Risk Mapping

## A01: Broken Access Control

**MaaS-specific risks:**
- MaaS API key grants full model access; no per-endpoint RBAC
- No per-user rate limiting; one compromised key affects entire project
- Proxy URL exposure allows unauthorized model access

**Mitigation:**
- Rotate API keys on schedule
- Use separate keys per environment (dev/staging/prod)
- Bind proxy to 127.0.0.1; never expose MaaS URL publicly

## A02: Cryptographic Failures

**MaaS-specific risks:**
- API keys transmitted over network (must use HTTPS)
- Model responses may contain PII that is stored unencrypted
- Session tokens stored in localStorage (XSS accessible)

**Mitigation:**
- Enforce HTTPS for all MaaS calls
- Redact PII before sending to MaaS
- Use HttpOnly cookies for session tokens

## A03: Injection

**MaaS-specific risks:**
- **Prompt injection**: User input embedded in system prompt without sanitization
- **SQL injection**: User input in database queries (standard risk)
- **XSS**: User input rendered in UI (standard risk)

**Mitigation:**
- Sanitize all user input before including in MaaS prompts
- Use parameterized queries for database access
- Escape output for the rendering context

## A04: Insecure Design

**MaaS-specific risks:**
- No rate limiting on MaaS calls (cost explosion risk)
- No fallback when MaaS is unavailable (availability risk)
- No circuit breaker (cascading failure risk)
- No input length limit (context window overflow)

**Mitigation:**
- Implement rate limiter (1 QPS MaaS quota)
- Implement circuit breaker with fallback response
- Set max input length before sending to MaaS
- Design for graceful degradation

## A05: Security Misconfiguration

**MaaS-specific risks:**
- Default API keys in config files committed to VCS
- Debug logging enabled in production (logs model inputs/outputs)
- Proxy running on 0.0.0.0 instead of 127.0.0.1
- CORS set to `*` for MaaS proxy

**Mitigation:**
- Use env vars for API keys; add config files to .gitignore
- Disable debug logging in production
- Bind proxy to 127.0.0.1 only
- Set CORS to specific origins only

## A06: Vulnerable Components

**MaaS-specific risks:**
- Outdated MaaS SDK with known vulnerabilities
- Outdated proxy (claude-code-router) with security patches missing
- Transitive dependency CVEs

**Mitigation:**
- Pin all dependency versions
- Run `npm audit` / `pip audit` / `trivy` before every deployment
- Subscribe to security advisories for MaaS SDK

## A07: Identification and Authentication Failures

**MaaS-specific risks:**
- Hardcoded MaaS API keys in source code
- API keys in URLs (logged by proxies and CDNs)
- No key rotation mechanism

**Mitigation:**
- Store API keys in env vars with 0640 permissions
- Never include API keys in URLs
- Rotate keys quarterly; automate rotation if possible

## A08: Software and Data Integrity Failures

**MaaS-specific risks:**
- Model output used without validation (hallucinated code, incorrect API calls)
- No schema validation on MaaS responses
- Auto-executing model-generated code without review

**Mitigation:**
- Validate all MaaS responses against expected schema
- Never auto-execute model-generated shell commands
- Require human review for model-generated code before execution

## A09: Security Logging and Monitoring Failures

**MaaS-specific risks:**
- API keys logged in plaintext
- Model inputs/outputs logged (PII exposure)
- No alerting on abnormal MaaS usage (cost spikes, rate limit violations)

**Mitigation:**
- Log key hashes, not keys
- Log metadata only (model, token count, latency); redact content
- Set up alerts for cost spikes and rate limit violations

## A10: Server-Side Request Forgery (SSRF)

**MaaS-specific risks:**
- MaaS proxy URL is configurable (internal network access)
- User-controlled URLs fetched by the application
- Cloud metadata endpoint accessible from application

**Mitigation:**
- Validate MaaS URL against allowlist
- Block requests to internal IP ranges (169.254.169.254, 10.0.0.0/8, etc.)
- Use network policies to restrict outbound connections
