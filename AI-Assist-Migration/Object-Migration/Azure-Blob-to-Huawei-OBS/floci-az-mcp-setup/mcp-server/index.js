#!/usr/bin/env node

const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require("@modelcontextprotocol/sdk/types.js");

const ENDPOINT = process.env.FLOCI_AZ_ENDPOINT || "http://localhost:4577";
const SUBSCRIPTION_ID =
  process.env.AZ_SUBSCRIPTION_ID || "00000000-0000-0000-0000-000000000001";
const STORAGE_ACCOUNT = process.env.AZ_STORAGE_ACCOUNT || "devstoreaccount1";
const STORAGE_KEY =
  process.env.AZ_STORAGE_KEY ||
  "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMh0==";

async function azFetch(method, path, body, headers) {
  const url = `${ENDPOINT}${path}`;
  const opts = {
    method,
    headers: { "Content-Type": "application/json", ...(headers || {}) },
  };
  if (body && method !== "GET" && method !== "HEAD") {
    opts.body = typeof body === "string" ? body : JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = text;
  }
  return { status: res.status, data };
}

function textResult(content) {
  return {
    content: [
      {
        type: "text",
        text: typeof content === "string" ? content : JSON.stringify(content, null, 2),
      },
    ],
  };
}

function errResult(msg) {
  return textResult({ error: msg });
}

const TOOLS = [
  {
    name: "az_call",
    description:
      "Generic Azure REST API call against floci-az. Works for any of the 20 emulated services.",
    inputSchema: {
      type: "object",
      properties: {
        method: { type: "string", enum: ["GET", "PUT", "POST", "PATCH", "DELETE"], description: "HTTP method" },
        path: { type: "string", description: "URL path (e.g. /subscriptions/.../resourceGroups?api-version=2021-04-01)" },
        body: { type: "object", description: "Request body (JSON)" },
      },
      required: ["method", "path"],
    },
  },
  {
    name: "az_subscriptions_list",
    description: "List all Azure subscriptions in floci-az.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "az_resourcegroups_list",
    description: "List all resource groups in the default subscription.",
    inputSchema: {
      type: "object",
      properties: {
        subscriptionId: { type: "string", description: "Subscription ID (defaults to floci-az default)" },
      },
    },
  },
  {
    name: "az_resourcegroups_create",
    description: "Create a resource group.",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", description: "Resource group name" },
        location: { type: "string", description: "Azure region (e.g. eastus)", default: "eastus" },
        subscriptionId: { type: "string" },
      },
      required: ["name"],
    },
  },
  {
    name: "az_resourcegroups_delete",
    description: "Delete a resource group.",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", description: "Resource group name" },
        subscriptionId: { type: "string" },
      },
      required: ["name"],
    },
  },
  {
    name: "az_resources_list",
    description: "List resources in a resource group, optionally filtered by provider and resource type.",
    inputSchema: {
      type: "object",
      properties: {
        resourceGroup: { type: "string", description: "Resource group name" },
        provider: { type: "string", description: "Resource provider namespace (e.g. Microsoft.Storage)" },
        resourceType: { type: "string", description: "Resource type (e.g. storageAccounts)" },
        subscriptionId: { type: "string" },
      },
      required: ["resourceGroup"],
    },
  },
  {
    name: "az_storage_containers_list",
    description: "List all blob containers in the default storage account (devstoreaccount1).",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "az_storage_container_create",
    description: "Create a blob container in the default storage account.",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string", description: "Container name" } },
      required: ["name"],
    },
  },
  {
    name: "az_storage_container_delete",
    description: "Delete a blob container.",
    inputSchema: {
      type: "object",
      properties: { name: { type: "string", description: "Container name" } },
      required: ["name"],
    },
  },
  {
    name: "az_storage_blobs_list",
    description: "List blobs in a container.",
    inputSchema: {
      type: "object",
      properties: { container: { type: "string", description: "Container name" } },
      required: ["container"],
    },
  },
  {
    name: "az_storage_blob_upload",
    description: "Upload a text blob to a container.",
    inputSchema: {
      type: "object",
      properties: {
        container: { type: "string", description: "Container name" },
        blob: { type: "string", description: "Blob name" },
        content: { type: "string", description: "Blob content (text)" },
      },
      required: ["container", "blob", "content"],
    },
  },
  {
    name: "az_storage_blob_download",
    description: "Download a blob's content as text.",
    inputSchema: {
      type: "object",
      properties: {
        container: { type: "string", description: "Container name" },
        blob: { type: "string", description: "Blob name" },
      },
      required: ["container", "blob"],
    },
  },
];

const server = new Server(
  { name: "floci-az-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const sub = args?.subscriptionId || SUBSCRIPTION_ID;

  try {
    switch (name) {
      case "az_call": {
        const { method, path, body } = args;
        const res = await azFetch(method, path, body);
        return textResult(res.data);
      }

      case "az_subscriptions_list": {
        const res = await azFetch("GET", "/subscriptions");
        return textResult(res.data);
      }

      case "az_resourcegroups_list": {
        const res = await azFetch(
          "GET",
          `/subscriptions/${sub}/resourceGroups?api-version=2021-04-01`
        );
        return textResult(res.data);
      }

      case "az_resourcegroups_create": {
        const { name: rgName, location } = args;
        const res = await azFetch(
          "PUT",
          `/subscriptions/${sub}/resourceGroups/${rgName}?api-version=2021-04-01`,
          { location: location || "eastus" }
        );
        return textResult(res.data);
      }

      case "az_resourcegroups_delete": {
        const { name: rgName } = args;
        const res = await azFetch(
          "DELETE",
          `/subscriptions/${sub}/resourceGroups/${rgName}?api-version=2021-04-01`
        );
        return textResult({ deleted: true, name: rgName, status: res.status });
      }

      case "az_resources_list": {
        const { resourceGroup, provider, resourceType } = args;
        let path = `/subscriptions/${sub}/resourceGroups/${resourceGroup}/resources?api-version=2021-04-01`;
        if (provider && resourceType) {
          path = `/subscriptions/${sub}/resourceGroups/${resourceGroup}/providers/${provider}/${resourceType}?api-version=2021-04-01`;
        } else if (provider) {
          path = `/subscriptions/${sub}/resourceGroups/${resourceGroup}/providers/${provider}?api-version=2021-04-01`;
        }
        const res = await azFetch("GET", path);
        return textResult(res.data);
      }

      case "az_storage_containers_list": {
        const res = await azFetch(
          "GET",
          `/${STORAGE_ACCOUNT}/?comp=list`
        );
        return textResult(res.data);
      }

      case "az_storage_container_create": {
        const { name: cName } = args;
        const res = await azFetch(
          "PUT",
          `/${STORAGE_ACCOUNT}/${cName}?restype=container`
        );
        return textResult({ created: true, name: cName, status: res.status });
      }

      case "az_storage_container_delete": {
        const { name: cName } = args;
        const res = await azFetch(
          "DELETE",
          `/${STORAGE_ACCOUNT}/${cName}?restype=container`
        );
        return textResult({ deleted: true, name: cName, status: res.status });
      }

      case "az_storage_blobs_list": {
        const { container } = args;
        const res = await azFetch(
          "GET",
          `/${STORAGE_ACCOUNT}/${container}?restype=container&comp=list`
        );
        return textResult(res.data);
      }

      case "az_storage_blob_upload": {
        const { container, blob, content } = args;
        const res = await azFetch(
          "PUT",
          `/${STORAGE_ACCOUNT}/${container}/${blob}`,
          content,
          { "x-ms-blob-type": "BlockBlob", "Content-Type": "text/plain" }
        );
        return textResult({ uploaded: true, container, blob, status: res.status });
      }

      case "az_storage_blob_download": {
        const { container, blob } = args;
        const res = await azFetch(
          "GET",
          `/${STORAGE_ACCOUNT}/${container}/${blob}`
        );
        return textResult(res.data);
      }

      default:
        return errResult(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return errResult(`Error: ${error.message}`);
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
