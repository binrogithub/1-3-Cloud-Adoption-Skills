# Development Standards

## Code Style

- JavaScript (ESM modules, .mjs extension)
- 2-space indentation
- UTF-8 encoding
- LF line endings

## MCP Tool Conventions

- All tools have explicit descriptions
- Read-only tools marked in description
- Write tools require explicit_approval parameter
- Secret redaction in all output/report tools
- Input validation with JSON Schema

## Testing

- Unit tests runnable without cloud credentials
- Safety tests for approval gates and CIDR checks
- Integration tests optional (require credentials)

## Documentation

- Every MCP has README.md
- Every skill has SKILL.md and README.md
- Every tool has description and input schema
- Use cases documented with runbooks
