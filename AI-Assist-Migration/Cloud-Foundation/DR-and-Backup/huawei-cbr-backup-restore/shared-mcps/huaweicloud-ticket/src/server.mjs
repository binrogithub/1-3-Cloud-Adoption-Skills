import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema
} from "@modelcontextprotocol/sdk/types.js";

import {
  loadSession,
  saveSession,
  isSessionValid,
  listServiceCategories,
  listIssueCategories,
  getTicketFormSchema,
  listRegions,
  listSeverities,
  checkCreatePrivilege,
  getSignedAgreement,
  createTicket,
  listTickets,
  getGlobalToken
} from "./ticket-api.mjs";

const server = new Server(
  { name: "huaweicloud-ticket", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

const TOOL_DEFINITIONS = [
  {
    name: "init_session",
    description: "Initialize or verify the ticket API session. Provide cookies and cftk from a browser session, or check if a cached session is still valid.",
    inputSchema: {
      type: "object",
      properties: {
        cftk: { type: "string", description: "CSRF token (cftk) from console cookies" },
        cookies: { type: "string", description: "Full cookie string from browser document.cookie" },
        agency_id: { type: "string", description: "User/agency ID (from /global/token)" },
        region: { type: "string", description: "Default region code", default: "cn-east-5" },
        check_only: { type: "boolean", description: "Only check if cached session is valid", default: false }
      }
    }
  },
  {
    name: "list_service_categories",
    description: "List all available product/service categories for ticket creation (ECS, RDS, OBS, VPC, etc.)",
    inputSchema: { type: "object", properties: {} }
  },
  {
    name: "list_issue_categories",
    description: "List issue categories for a specific product (e.g., Remote Login, OS Issues for ECS)",
    inputSchema: {
      type: "object",
      properties: {
        product_category_id: { type: "string", description: "Product category ID from list_service_categories" }
      },
      required: ["product_category_id"]
    }
  },
  {
    name: "get_ticket_form_schema",
    description: "Get the dynamic form fields needed to create a ticket for a specific product+issue category combo. Returns field names, types, required status, and options for select fields.",
    inputSchema: {
      type: "object",
      properties: {
        product_category_id: { type: "string", description: "Product category ID" },
        business_type_id: { type: "string", description: "Issue category ID from list_issue_categories" },
        incident_sub_type_id: { type: "string", description: "Sub type ID: -1 for products, 1 for services like Billing/Account", default: "-1" }
      },
      required: ["product_category_id", "business_type_id"]
    }
  },
  {
    name: "list_regions",
    description: "List available Huawei Cloud regions for ticket creation",
    inputSchema: { type: "object", properties: {} }
  },
  {
    name: "list_severities",
    description: "List severity levels available for a product+issue category",
    inputSchema: {
      type: "object",
      properties: {
        product_category_id: { type: "string", description: "Product category ID" },
        business_type_id: { type: "string", description: "Issue category ID" }
      },
      required: ["product_category_id", "business_type_id"]
    }
  },
  {
    name: "check_create_privilege",
    description: "Check if the current user has permission to create service tickets",
    inputSchema: { type: "object", properties: {} }
  },
  {
    name: "prepare_ticket",
    description: "Prepare a ticket creation payload WITHOUT submitting it. Returns the full payload that would be sent to create_ticket. Use this to review/validate before actual submission.",
    inputSchema: {
      type: "object",
      properties: {
        product_category_id: { type: "string", description: "Product category ID" },
        business_type_id: { type: "string", description: "Issue category ID" },
        incident_sub_type_id: { type: "string", description: "Sub type ID (-1 or 1)", default: "-1" },
        region_id: { type: "string", description: "Region code (e.g., la-north-2, cn-east-5)" },
        description: { type: "string", description: "Problem description (plain text, will be wrapped in HTML)" },
        extends_map: { type: "object", description: "Dynamic form fields as key-value pairs (keys from get_ticket_form_schema)" },
        contact_type: { type: "string", description: "Contact types comma-separated (0=mobile, 2=email)", default: "0,2" },
        cc_email: { type: "string", description: "CC email address" }
      },
      required: ["product_category_id", "business_type_id", "region_id", "description"]
    }
  },
  {
    name: "create_ticket",
    description: "Create (SUBMIT) a service ticket. WARNING: This creates a REAL ticket. Use prepare_ticket first to review the payload. Requires explicit_approval=true to proceed.",
    inputSchema: {
      type: "object",
      properties: {
        payload: { type: "object", description: "Full ticket payload (from prepare_ticket or manually constructed)" },
        explicit_approval: { type: "boolean", description: "Must be true to create the ticket. Rejects false, missing, or non-boolean values." }
      },
      required: ["payload", "explicit_approval"]
    }
  },
  {
    name: "list_tickets",
    description: "List existing service tickets",
    inputSchema: {
      type: "object",
      properties: {
        offset: { type: "number", description: "Page offset", default: 0 },
        limit: { type: "number", description: "Page size", default: 10 }
      }
    }
  }
];

let cachedSession = null;

async function getSession() {
  if (cachedSession && isSessionValid(cachedSession)) return cachedSession;
  cachedSession = await loadSession();
  if (!cachedSession) {
    throw new Error("No active session. Call init_session first with cookies and cftk from the Huawei Cloud console.");
  }
  return cachedSession;
}

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOL_DEFINITIONS
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "init_session": {
        if (args.check_only) {
          const s = await loadSession();
          if (s && isSessionValid(s)) {
            cachedSession = s;
            const token = await getGlobalToken(s).catch(() => null);
            return {
              content: [{ type: "text", text: JSON.stringify({
                status: "valid",
                userId: s.agencyId,
                region: s.region,
                userName: token?.name,
                expiresAt: new Date(s.expiresAt).toISOString(),
                savedAt: new Date(s.savedAt).toISOString()
              }, null, 2) }]
            };
          }
          return { content: [{ type: "text", text: JSON.stringify({ status: "expired_or_missing" }, null, 2) }] };
        }

        if (!args.cftk || !args.cookies) {
          return { content: [{ type: "text", text: "Error: cftk and cookies are required for session initialization." }] };
        }

        const session = {
          cftk: args.cftk,
          cookies: args.cookies,
          agencyId: args.agency_id || "",
          region: args.region || "cn-east-5",
          expiresAt: Date.now() + 8 * 60 * 60 * 1000
        };

        const token = await getGlobalToken(session).catch(() => null);
        if (token && token.id) {
          session.agencyId = token.id;
          session.domainId = token.domainId;
          session.userName = token.name;
        }

        cachedSession = await saveSession(session);
        return {
          content: [{ type: "text", text: JSON.stringify({
            status: "initialized",
            userId: session.agencyId,
            userName: session.userName,
            domainId: session.domainId,
            region: session.region,
            expiresAt: new Date(session.expiresAt).toISOString()
          }, null, 2) }]
        };
      }

      case "list_service_categories": {
        const session = await getSession();
        const result = await listServiceCategories(session);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "list_issue_categories": {
        const session = await getSession();
        const result = await listIssueCategories(session, args.product_category_id);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "get_ticket_form_schema": {
        const session = await getSession();
        const result = await getTicketFormSchema(
          session,
          args.product_category_id,
          args.business_type_id,
          args.incident_sub_type_id || "-1"
        );
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "list_regions": {
        const session = await getSession();
        const result = await listRegions(session);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "list_severities": {
        const session = await getSession();
        const result = await listSeverities(session, args.product_category_id, args.business_type_id);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "check_create_privilege": {
        const session = await getSession();
        const result = await checkCreatePrivilege(session);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      case "prepare_ticket": {
        const session = await getSession();
        const agreement = await getSignedAgreement(session).catch(() => ({}));
        const agreementId = agreement.signed_record_id || agreement.agreement_signed_record_id;

        const descriptionHtml = `<div class="osm-rich-text"><p>${args.description}</p></div>`;

        const payload = {
          business_type_id: args.business_type_id,
          product_category_id: args.product_category_id,
          incident_sub_type_id: args.incident_sub_type_id || "-1",
          source_id: session.sourceId,
          simple_description: descriptionHtml,
          accessory_ids: [],
          region_id: args.region_id,
          extends_map: args.extends_map || {},
          extension_map: {
            contactType: args.contact_type || "0,2",
            remindCCEmail: args.cc_email || "",
            isReceiveMsgRemind: 0
          }
        };

        if (agreementId) {
          payload.agreement_signed_record_id = agreementId;
        }

        return {
          content: [{ type: "text", text: JSON.stringify({
            status: "prepared",
            note: "This payload has NOT been submitted. Use create_ticket with this payload to submit.",
            payload,
            missing_fields: !agreementId ? ["agreement_signed_record_id (agreement not signed)"] : []
          }, null, 2) }]
        };
      }

      case "create_ticket": {
        if (args.explicit_approval !== true) {
          return {
            content: [{ type: "text", text: JSON.stringify({
              error: "APPROVAL_REQUIRED",
              message: "create_ticket requires explicit_approval=true. Review the payload with prepare_ticket first, then call create_ticket with explicit_approval=true."
            }) }]
          };
        }
        if (!args.payload || typeof args.payload !== 'object') {
          return {
            content: [{ type: "text", text: JSON.stringify({
              error: "INVALID_PAYLOAD",
              message: "create_ticket requires a valid payload object. Use prepare_ticket to generate one."
            }) }]
          };
        }
        const session = await getSession();
        const result = await createTicket(session, args.payload);
        return {
          content: [{ type: "text", text: JSON.stringify({
            status: "created",
            result
          }) }]
        };
      }

      case "list_tickets": {
        const session = await getSession();
        const result = await listTickets(session, args.offset || 0, args.limit || 10);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      }

      default:
        return { content: [{ type: "text", text: `Unknown tool: ${name}` }] };
    }
  } catch (err) {
    if (err.code === "SESSION_EXPIRED") {
      return { content: [{ type: "text", text: JSON.stringify({ error: "SESSION_EXPIRED", message: "Session expired. Re-initialize with init_session." }) }] };
    }
    return { content: [{ type: "text", text: JSON.stringify({ error: err.message }) }] };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ticket-mcp server running on stdio");
}

main().catch(console.error);
