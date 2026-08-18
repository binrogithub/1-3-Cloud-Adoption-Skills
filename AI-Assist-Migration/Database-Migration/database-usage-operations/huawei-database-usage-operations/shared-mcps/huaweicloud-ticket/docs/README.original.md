# Huawei Cloud Ticket MCP

MCP server for creating Huawei Cloud service tickets via the console REST API.

## Setup

### 1. Bootstrap Session (one-time, or when session expires)

```bash
node bootstrap-session.cjs
```

This opens a browser. Login with your Huawei Cloud credentials (MFA only needed here).
After login, the session (cookies + CSRF token) is saved to `~/.ticket-mcp/session.json`.

**Session lasts ~8 hours.** No MFA needed for subsequent MCP calls.

### 2. Start the MCP server

```bash
node server.mjs
```

## Tools

| Tool | Description |
|------|-------------|
| `init_session` | Initialize session with cookies+cftk, or check cached session |
| `list_service_categories` | List all products/services (ECS, RDS, OBS, etc.) |
| `list_issue_categories` | List issue categories for a product |
| `get_ticket_form_schema` | Get dynamic form fields for product+issue combo |
| `list_regions` | List available regions |
| `list_severities` | List severity levels |
| `check_create_privilege` | Check if user can create tickets |
| `prepare_ticket` | Build ticket payload WITHOUT submitting |
| `create_ticket` | SUBMIT a ticket (use prepare_ticket first!) |
| `list_tickets` | List existing tickets |

## Flow: Create Ticket from Prompt

```
"I can't SSH to my ECS in la-north-2"
  → list_service_categories → ECS
  → list_issue_categories(ECS) → Remote Login
  → get_ticket_form_schema(ECS, RemoteLogin) → fields
  → LLM maps prompt to field values
  → prepare_ticket(payload) → review payload
  → create_ticket(payload) → ticket created
```

## Session Management

- **First time**: MFA required (via bootstrap-session.cjs)
- **Subsequent calls**: Session cached in `~/.ticket-mcp/session.json`
- **Session duration**: ~8 hours (console default)
- **On expiry**: Re-run `bootstrap-session.cjs` or call `init_session` with new cookies
