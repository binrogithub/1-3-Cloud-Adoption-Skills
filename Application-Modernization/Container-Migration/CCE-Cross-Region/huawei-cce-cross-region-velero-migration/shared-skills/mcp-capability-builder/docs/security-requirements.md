# Security Requirements for Generated MCPs

## Mandatory Checks

1. No hardcoded credentials in source code
2. No 0.0.0.0/0 access patterns
3. Write operations require explicit_approval parameter
4. Secret redaction in all output/report tools
5. .env.example provided (never .env with real values)
6. .gitignore includes .env, node_modules/, etc.
7. No terraform.tfstate in deliverables
8. No API response JSONs with real data

## Review Checklist

- [ ] No AK/SK in code
- [ ] No passwords in code
- [ ] No tokens in code
- [ ] No real IP addresses in examples
- [ ] No real project IDs in examples
- [ ] No real bucket names in examples
- [ ] Write tools have explicit_approval
- [ ] Reports redact secrets
- [ ] .env.example is sanitized
- [ ] .gitignore is comprehensive
