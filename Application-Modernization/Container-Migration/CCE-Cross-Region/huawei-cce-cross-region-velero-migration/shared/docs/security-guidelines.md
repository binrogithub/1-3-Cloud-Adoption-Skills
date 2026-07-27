# Security Guidelines

## Key Principles

1. **Least privilege**: IAM users have only required permissions
2. **No credentials in git**: Use .gitignore and .env.example
3. **Explicit approval**: Write operations require confirmation
4. **Secret redaction**: Reports scrub AK/SK, passwords, tokens
5. **CIDR restriction**: No 0.0.0.0/0, use /32 for specific IPs
6. **Read-only default**: Tools default to read-only where possible
7. **No auto-activation**: Generated MCPs never activated automatically

## See Also

- SECURITY.md (root level)
- shared-skills/mcp-capability-builder/docs/security-requirements.md
