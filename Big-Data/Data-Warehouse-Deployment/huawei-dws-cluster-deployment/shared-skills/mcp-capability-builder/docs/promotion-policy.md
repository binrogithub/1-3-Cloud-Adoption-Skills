# MCP Promotion Policy

## Promotion Path

```
DRAFT → EXPERIMENTAL → READY_FOR_REVIEW → READY
```

## Promotion Criteria

### DRAFT → EXPERIMENTAL
- Tool contracts defined
- Unit tests pass
- Security review completed
- Documentation complete

### EXPERIMENTAL → READY_FOR_REVIEW
- Integration tests pass (with credentials)
- Manual testing completed
- No security findings
- Backward compatibility verified

### READY_FOR_REVIEW → READY
- Peer review completed
- Integration with OpenCode verified
- Production use case validated
- Monitoring/alerting configured (if applicable)

## Restrictions

- NEVER skip promotion steps
- NEVER auto-promote
- NEVER promote without manual review
- NEVER promote a MCP that creates uncontrolled cloud resources
