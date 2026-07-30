# Playwright Version Policy

## Current State

Using @playwright/mcp@0.0.78 (pinned).

## Package Name

@playwright/mcp

## Pinned Version

0.0.78

## Reason for Pinning

- Ensures reproducible DRS console automation behavior
- Prevents breaking changes from @latest affecting fragile selectors
- Version 0.0.78 is the latest available and has been validated in the environment

## Update Policy

- Review npm view @playwright/mcp version quarterly
- Test new version in isolated environment before updating pin
- Update this document and mcp-registry.yaml simultaneously
- Never use @latest in production configurations

## Status

PINNED
