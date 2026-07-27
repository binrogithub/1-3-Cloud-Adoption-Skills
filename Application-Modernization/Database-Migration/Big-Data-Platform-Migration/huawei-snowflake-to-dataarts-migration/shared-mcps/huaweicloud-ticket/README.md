# huaweicloud-ticket

## Purpose

MCP server for Huawei Cloud service ticket creation and management. Enables listing service categories, issue types, and form schemas, preparing ticket payloads for review, and submitting service tickets through the Huawei Cloud console ticket API.

## Scope

**Includes:**
- Service category and issue category listing
- Dynamic form schema retrieval for ticket creation
- Region and severity listing
- Ticket creation privilege checking
- Ticket payload preparation (dry-run preview)
- Ticket submission with explicit warning
- Existing ticket listing
- Session management via console cookies

**Does not include:**
- Ticket modification or closure
- Ticket comment management
- Attachment upload
- SLA monitoring or escalation

## Use cases

1. **Service ticket creation** — Create support tickets for Huawei Cloud issues [VERIFIED_FROM_CODE]
2. **Ticket form exploration** — Discover available categories, issue types, and form fields [VERIFIED_FROM_CODE]
3. **Safe ticket preparation** — Preview ticket payload before submission [VERIFIED_FROM_CODE]
4. **Session management** — Initialize and verify console session for API access [VERIFIED_FROM_CODE]

## Architecture

- **Runtime:** Node.js (ESM)
- **Entry point:** `src/server.mjs`
- **Transport:** stdio (MCP SDK)
- **Core modules:**
  - `src/server.mjs` — Main MCP server with 10 tool handlers
  - `src/ticket-api.mjs` — Huawei Cloud ticket API client
  - `src/bootstrap-session.cjs` — Session bootstrap helper
- **Dependencies:** `@modelcontextprotocol/sdk`, `axios`
- **Authentication:** Console session cookies + CSRF token (cftk)

## MCP tools exposed

| # | Tool name | Purpose | Read/Write | Risk | Approval required |
|---|-----------|---------|------------|------|-------------------|
| 1 | init_session | Initialize/verify ticket API session | write (session) | low | no |
| 2 | list_service_categories | List product/service categories | read-only | none | no |
| 3 | list_issue_categories | List issue categories for a product | read-only | none | no |
| 4 | get_ticket_form_schema | Get dynamic form fields | read-only | none | no |
| 5 | list_regions | List available regions | read-only | none | no |
| 6 | list_severities | List severity levels | read-only | none | no |
| 7 | check_create_privilege | Check ticket creation permission | read-only | none | no |
| 8 | prepare_ticket | Prepare ticket payload (dry-run) | read-only | none | no |
| 9 | create_ticket | Submit a service ticket | write | high | implicit (WARNING) |
| 10 | list_tickets | List existing tickets | read-only | none | no |

## Prerequisites

- Node.js >= 18
- Huawei Cloud console session (cookies + cftk)
- Ticket creation permission on the account

## Installation

```bash
cd mcps/huaweicloud-ticket
npm install
```

## Configuration

Session initialization requires console cookies and CSRF token from browser session. No environment variables required.

## Environment variables

No environment variables required. Session is managed via tool calls.

## Execution

```bash
node src/server.mjs
```

## Integration with OpenCode

```json
{
  "huaweicloud-ticket": {
    "type": "local",
    "enabled": true,
    "command": ["node", "<INSTALLATION_ROOT>/mcps/huaweicloud-ticket/src/server.mjs"],
    "timeout": 30000
  }
}
```

## Examples

```bash
# List service categories
# Tool: list_service_categories

# Prepare a ticket (dry-run)
# Tool: prepare_ticket
# Parameters: { product_category_id: "123", business_type_id: "456", region_id: "la-north-2", description: "Issue description" }

# Create ticket (REAL submission)
# Tool: create_ticket
# Parameters: { payload: { ... } }
```

## Tests

```bash
npm test
```

1 test file: test-session.mjs

## Security

- `create_ticket` creates a **real** service ticket — use `prepare_ticket` first [VERIFIED_FROM_CODE]
- Session cookies and cftk are sensitive — handle with care
- No AK/SK required; uses console session authentication

## Limitations

- Requires active console session (cookies expire)
- No ticket modification, closure, or comment capabilities
- No attachment support
- Session management is manual (no auto-refresh)

## Troubleshooting

- **"Session invalid"**: Re-initialize with `init_session` providing fresh cookies/cftk
- **"No create privilege"**: Verify account permissions for ticket creation
- **"Form schema empty"**: Verify product_category_id and business_type_id are valid

## Related use cases

- Incident reporting and support ticket creation
- Service category and form exploration

## Status

**READY_WITH_WARNINGS** — 10 tools implemented. `create_ticket` performs real submission. Session management requires manual cookie provisioning. 1 test file available.
