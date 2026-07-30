import { writeFile, unlink } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import axios from "axios";

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema
} from "@modelcontextprotocol/sdk/types.js";

import { signHuaweiRequest } from "./huawei-signer.mjs";
import {
  listPricingTemplates,
  explainRequiredTemplate,
  estimateArchitectureCostDraft,
  normalizeArchitectureComponents,
  renderProductInfosFromTemplate
} from "./template-tools.mjs";

const execFileAsync = promisify(execFile);

const server = new Server(
  {
    name: "huaweicloud-pricing",
    version: "0.2.0"
  },
  {
    capabilities: {
      tools: {}
    }
  }
);

function envStatus(name) {
  return process.env[name] && process.env[name].length > 0 ? "SET" : "MISSING";
}

function requireEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function resolveRegion(args = {}) {
  return (
    args.region ||
    process.env.HUAWEI_DEFAULT_REGION ||
    "la-north-2"
  );
}

function resolveProjectId(args = {}) {
  return (
    args.project_id ||
    process.env.HUAWEI_PROJECT_ID
  );
}

function resolveProjectIdForRegion(region) {
  const mappingRaw = process.env.HUAWEI_PROJECT_IDS_BY_REGION;

  if (mappingRaw) {
    let mapping;
    try {
      mapping = JSON.parse(mappingRaw);
    } catch {
      return {
        error: "configuration_error",
        message: "HUAWEI_PROJECT_IDS_BY_REGION contains invalid JSON"
      };
    }

    if (mapping && typeof mapping === "object" && !Array.isArray(mapping) && mapping[region]) {
      return { project_id: String(mapping[region]) };
    }
  }

  const defaultRegion = process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
  const legacyProjectId = process.env.HUAWEI_PROJECT_ID;

  if (legacyProjectId && region === defaultRegion) {
    return { project_id: legacyProjectId };
  }

  return {
    error: "configuration_error",
    message: `No project_id configured for region ${region}`
  };
}


function extractPeriodAmounts(data) {
  const officialResult = data.official_website_rating_result || {};
  const discountResults = data.optional_discount_rating_results || [];

  const amount = officialResult.official_website_amount ?? null;
  const official_website_amount = officialResult.official_website_amount ?? null;
  const discount_amount = discountResults.length > 0
    ? (discountResults[0].official_website_amount ?? null)
    : null;
  const currency = data.currency || null;

  return { amount, official_website_amount, discount_amount, currency };
}


async function callHuaweiPricingApi({ apiPath, args }) {
  const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
  const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_api_helper.py";

  const region = resolveRegion(args);
  const projectId = resolveProjectId(args);

  if (!projectId) {
    throw new Error("project_id is required. Provide project_id or configure HUAWEI_PROJECT_ID.");
  }

  const productInfos = args.product_infos;

  if (!Array.isArray(productInfos) || productInfos.length === 0) {
    throw new Error("product_infos must be a non-empty array.");
  }

  let operation = null;

  if (apiPath === "/v2/bills/ratings/on-demand-resources") {
    operation = "on-demand-price";
  } else if (apiPath === "/v2/bills/ratings/period-resources/subscribe-rate") {
    operation = "period-price";
  } else {
    throw new Error(`Unsupported pricing apiPath: ${apiPath}`);
  }

  const tmpFile = `/tmp/huaweicloud-product-infos-${Date.now()}-${Math.random().toString(16).slice(2)}.json`;

  try {
    await writeFile(tmpFile, JSON.stringify(productInfos, null, 2), { mode: 0o600 });

    const cliArgs = [
      helper,
      operation,
      "--product-infos-file",
      tmpFile,
      "--project-id",
      projectId
    ];

    if (operation === "on-demand-price") {
      cliArgs.push("--inquiry-precision", String(args.inquiry_precision ?? 1));
    }

    const { stdout, stderr } = await execFileAsync(
      pythonBin,
      cliArgs,
      {
        timeout: args.timeout_ms || 30000,
        maxBuffer: 10 * 1024 * 1024
      }
    );

    if (stderr && stderr.trim().length > 0) {
      return {
        request: {
          api_path: apiPath,
          region,
          project_id: projectId,
          product_infos_count: productInfos.length
        },
        warning: "Python pricing helper wrote to stderr",
        stderr,
        data: {}
      };
    }

    const parsed = JSON.parse(stdout);

    return {
      request: {
        api_path: apiPath,
        region,
        project_id: projectId,
        product_infos_count: productInfos.length
      },
      helper_result: parsed
    };
  } finally {
    try {
      await unlink(tmpFile);
    } catch {
      // ignore cleanup errors
    }
  }
}


function buildQueryString(params = {}) {
  const query = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    query.set(key, String(value));
  }

  const qs = query.toString();
  return qs ? `?${qs}` : "";
}


async function callHuaweiCatalogApi({ apiPath, args = {} }) {
  const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
  const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

  const query = args.query || {};
  let operation = null;

  if (apiPath === "/v2/products/service-types") {
    operation = "service-types";
  } else if (apiPath === "/v2/products/resource-types") {
    operation = "resource-types";
  } else if (apiPath === "/v2/products/service-resources") {
    operation = "service-resources";
  } else if (apiPath === "/v2/products/usage-types") {
    operation = "usage-types";
  } else if (apiPath === "/v2/bases/measurements") {
    operation = "measurements";
  } else {
    throw new Error(`Unsupported catalog apiPath: ${apiPath}`);
  }

  const cliArgs = [
    helper,
    operation,
    "--limit",
    String(query.limit ?? 100),
    "--offset",
    String(query.offset ?? 0)
  ];

  if (operation === "service-resources") {
    if (!query.service_type_code) {
      throw new Error("service_type_code is required for service-resources");
    }

    cliArgs.push("--service-type-code", String(query.service_type_code));
  }

  if (operation === "usage-types") {
    if (query.service_type_code) {
      cliArgs.push("--service-type-code", String(query.service_type_code));
    }

    if (query.resource_type_code) {
      cliArgs.push("--resource-type-code", String(query.resource_type_code));
    }
  }

  const { stdout, stderr } = await execFileAsync(
    pythonBin,
    cliArgs,
    {
      timeout: args.timeout_ms || 30000,
      maxBuffer: 10 * 1024 * 1024
    }
  );

  if (stderr && stderr.trim().length > 0) {
    return {
      http_status: null,
      warning: "Python helper wrote to stderr",
      stderr,
      data: {}
    };
  }

  return JSON.parse(stdout);
}


server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "QueryCloudServiceTypes",
        description: "Query Huawei Cloud product catalog cloud service types using BSS/OCE API. Read-only.",
        inputSchema: {
          type: "object",
          properties: {
            limit: {
              type: "integer",
              description: "Number of records to return.",
              default: 100
            },
            offset: {
              type: "integer",
              description: "Pagination offset.",
              default: 0
            },
            service_type_code: {
              type: "string",
              description: "Optional service type code filter if supported."
            },
            service_type_name: {
              type: "string",
              description: "Optional service type name filter if supported."
            },
            x_language: {
              type: "string",
              description: "Language header. Use en_US for English.",
              default: "en_US"
            }
          },
          required: []
        }
      },
      {
        name: "QueryResourceTypes",
        description: "Query Huawei Cloud product catalog resource types using BSS/OCE API. Read-only.",
        inputSchema: {
          type: "object",
          properties: {
            limit: {
              type: "integer",
              description: "Number of records to return.",
              default: 100
            },
            offset: {
              type: "integer",
              description: "Pagination offset.",
              default: 0
            },
            x_language: {
              type: "string",
              description: "Language header. Use en_US for English.",
              default: "en_US"
            }
          },
          required: []
        }
      },
      {
        name: "QueryServiceResources",
        description: "Query Huawei Cloud resource types associated with a cloud service type. Read-only.",
        inputSchema: {
          type: "object",
          properties: {
            service_type_code: {
              type: "string",
              description: "Cloud service type code, for example hws.service.type.obs."
            },
            limit: {
              type: "integer",
              description: "Number of records to return.",
              default: 100
            },
            offset: {
              type: "integer",
              description: "Pagination offset.",
              default: 0
            },
            x_language: {
              type: "string",
              description: "Language header. Use en_US for English.",
              default: "en_US"
            }
          },
          required: ["service_type_code"]
        }
      },
      {
        name: "QueryUsageTypes",
        description: "Query Huawei Cloud product catalog usage types using BSS/OCE API. Read-only.",
        inputSchema: {
          type: "object",
          properties: {
            limit: {
              type: "integer",
              description: "Number of records to return.",
              default: 100
            },
            offset: {
              type: "integer",
              description: "Pagination offset.",
              default: 0
            },
            service_type_code: {
              type: "string",
              description: "Optional cloud service type code filter, for example hws.service.type.ebs."
            },
            resource_type_code: {
              type: "string",
              description: "Optional resource type code filter, for example hws.resource.type.volume."
            },
            x_language: {
              type: "string",
              description: "Language header. Use en_US for English.",
              default: "en_US"
            }
          },
          required: []
        }
      },
      {
        name: "QueryMeasurementUnits",
        description: "Query Huawei Cloud catalog measurement units using BSS/OCE API. Read-only.",
        inputSchema: {
          type: "object",
          properties: {
            limit: {
              type: "integer",
              description: "Number of records to return.",
              default: 100
            },
            offset: {
              type: "integer",
              description: "Pagination offset.",
              default: 0
            },
            x_language: {
              type: "string",
              description: "Language header. Use en_US for English.",
              default: "en_US"
            }
          },
          required: []
        }
      },
      {
        name: "QueryElbFlavors",
        description: "Query ELB dedicated load balancer flavors/specs available in a region using the ELB v3 API. Read-only. Does not list existing load balancers.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            x_language: {
              type: "string",
              description: "Language header. Use en_US for English.",
              default: "en_US"
            }
          },
          required: []
        }
      },
      {
        name: "QueryElbAvailabilityZones",
        description: "Query ELB availability zones in a region using the ELB v3 API. Read-only. Confirms regional availability and supported AZs.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            x_language: {
              type: "string",
              description: "Language header. Use en_US for English.",
              default: "en_US"
            }
          },
          required: []
        }
      },
      {
        name: "QueryRdsFlavors",
        description: "Query RDS MySQL flavors/specs available in a region using the RDS v3 API. Read-only. Does not list existing DB instances.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            rds_version: {
              type: "string",
              description: "RDS MySQL version, for example 8.0.",
              default: "8.0"
            },
            timeout_ms: {
              type: "integer",
              description: "Timeout in milliseconds.",
              default: 30000
            }
          },
          required: []
        }
      },
      {
        name: "QueryRdsStorageTypes",
        description: "Query RDS MySQL storage types available in a region using the RDS v3 API. Read-only. Does not list existing DB instances.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            rds_version: {
              type: "string",
              description: "RDS MySQL version, for example 8.0.",
              default: "8.0"
            },
            ha_mode: {
              type: "string",
              description: "RDS HA mode, for example single or ha.",
              default: "single"
            },
            timeout_ms: {
              type: "integer",
              description: "Timeout in milliseconds.",
              default: 30000
            }
          },
          required: []
        }
      },
      {
        name: "QueryEcsFlavors",
        description: "Query ECS flavors/specs available in a region using the ECS v1 API. Read-only. Does not list existing servers.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            availability_zone: {
              type: "string",
              description: "Optional availability zone to filter flavors, for example la-north-2a."
            },
            timeout_ms: {
              type: "integer",
              description: "Timeout in milliseconds.",
              default: 30000
            }
          },
          required: []
        }
      },
      {
        name: "QueryEvsVolumeTypes",
        description: "Query EVS volume types available in a region using the EVS v2 API. Read-only. Does not list existing volumes.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            availability_zone: {
              type: "string",
              description: "Optional availability zone to filter volume types locally, for example la-north-2a."
            },
            volume_type: {
              type: "string",
              description: "Optional volume type name to filter locally, for example SSD, GPSSD, ESSD."
            },
            timeout_ms: {
              type: "integer",
              description: "Timeout in milliseconds.",
              default: 30000
            }
          },
          required: []
        }
      },
      {
        name: "PricingHealthCheck",
        description: "Validate local Huawei Cloud pricing MCP configuration. Does not call Huawei Cloud APIs.",
        inputSchema: {
          type: "object",
          properties: {},
          required: []
        }
      },
      {
        name: "ListPricingTemplates",
        description: "List local Huawei Cloud pricing templates available for architecture cost estimation. Does not call Huawei Cloud APIs.",
        inputSchema: {
          type: "object",
          properties: {
            service: {
              type: "string",
              description: "Optional service filter, for example ecs, evs, eip, elb, rds, obs."
            },
            region: {
              type: "string",
              description: "Optional Huawei Cloud region filter, for example la-north-2."
            }
          },
          required: []
        }
      },
      {
        name: "ExplainRequiredTemplate",
        description: "Explain what is required to create or complete a pricing template with product_infos. Does not call Huawei Cloud APIs.",
        inputSchema: {
          type: "object",
          properties: {
            service: {
              type: "string",
              description: "Optional target service, for example ecs, evs, rds, obs."
            },
            region: {
              type: "string",
              description: "Optional target region, for example la-north-2."
            }
          },
          required: []
        }
      },
      {
        name: "EstimateArchitectureCostDraft",
        description: "Create a draft architecture cost mapping from requested components to local pricing templates. Does not call Huawei Cloud pricing APIs yet.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            components: {
              type: "array",
              description: "Architecture components to map to pricing templates.",
              items: {
                type: "object",
                properties: {
                  service: {
                    type: "string",
                    description: "Huawei Cloud service, for example ecs, evs, eip, elb, rds, obs."
                  },
                  template_id: {
                    type: "string",
                    description: "Template ID from pricing-templates.json, for example evs-ssd-gb-payg."
                  },
                  quantity: {
                    type: "integer",
                    description: "Number of resources/components.",
                    default: 1
                  },
                  parameters: {
                    type: "object",
                    description: "Variable parameters for the selected template. Examples: monthly_hours, system_disk_gb, size_gb, bandwidth_mbps, storage_gb.",
                    additionalProperties: true,
                    properties: {
                      monthly_hours: {
                        type: "number",
                        description: "Monthly usage hours, commonly 730."
                      },
                      system_disk_gb: {
                        type: "number",
                        description: "ECS system disk size in GB."
                      },
                      size_gb: {
                        type: "number",
                        description: "EVS disk size in GB."
                      },
                      bandwidth_mbps: {
                        type: "number",
                        description: "EIP bandwidth in Mbps."
                      },
                      storage_gb: {
                        type: "number",
                        description: "Storage size in GB for RDS/OBS or similar services."
                      }
                    }
                  }
                },
                required: ["service", "template_id"]
              }
            }
          },
          required: ["components"]
        }
      },
      {
        name: "EstimateArchitectureOnDemandPrice",
        description: "Estimate on-demand pricing for an architecture composed of multiple local pricing templates. Calculates real prices for ready templates and reports incomplete templates. Read-only.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region, for example la-north-2."
            },
            components: {
              type: "array",
              description: "Architecture components to estimate.",
              items: {
                type: "object",
                properties: {
                  service: {
                    type: "string",
                    description: "Service name, for example evs, eip, ecs, rds, obs."
                  },
                  template_id: {
                    type: "string",
                    description: "Template ID from pricing-templates.json."
                  },
                  quantity: {
                    type: "integer",
                    description: "Number of resources.",
                    default: 1
                  },
                  parameters: {
                    type: "object",
                    description: "Variable parameters for the template.",
                    additionalProperties: true
                  },
                  availability_zone: {
                    type: "string",
                    description: "Availability zone for this component's validation. Overrides default_availability_zone."
                  },
                  preferred_flavor: {
                    type: "string",
                    description: "Preferred flavor ID for validation. Overrides derivation from resource_spec."
                  }
                },
                required: ["service", "template_id"]
              }
            },
            project_id: {
              type: "string",
              description: "Optional Huawei Cloud project ID. If omitted, HUAWEI_PROJECT_ID is used."
            },
            inquiry_precision: {
              type: "integer",
              description: "0 default precision, 1 high precision.",
              default: 1
            },
            validate_availability: {
              type: "boolean",
              description: "If true, validate ECS flavor availability (abandon/sellout) before pricing. Invalid ECS components are excluded from pricing.",
              default: false
            },
            default_availability_zone: {
              type: "string",
              description: "Default availability zone for ECS validation when component-level availability_zone is not specified, for example la-north-2a."
            },
            include_unavailable_reference_pricing: {
              type: "boolean",
              description: "If true and validate_availability=true, blocked ECS components may be priced for reference only. They remain not recommended for deployment and are not included in monthly_total.",
              default: false
            }
          },
          required: ["components"]
        }
      },
      {
        name: "EstimateTemplateOnDemandPrice",
        description: "Render product_infos from a local pricing template and query Huawei Cloud on-demand pricing. Read-only. Does not create, buy, or modify resources.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region, for example la-north-2."
            },
            service: {
              type: "string",
              description: "Service name, for example evs, eip, ecs, rds, obs."
            },
            template_id: {
              type: "string",
              description: "Template ID from pricing-templates.json, for example evs-ssd-gb-payg."
            },
            quantity: {
              type: "integer",
              description: "Number of resources/components.",
              default: 1
            },
            parameters: {
              type: "object",
              description: "Variable parameters such as size_gb, bandwidth_mbps, storage_gb, monthly_hours, system_disk_gb.",
              additionalProperties: true
            },
            project_id: {
              type: "string",
              description: "Optional Huawei Cloud project ID. If omitted, HUAWEI_PROJECT_ID is used."
            },
            inquiry_precision: {
              type: "integer",
              description: "0 default precision, 1 high precision.",
              default: 1
            }
          },
          required: ["service", "template_id"]
        }
      },
      {
        name: "EstimateTemplatePeriodPrice",
        description: "Render product_infos from a local pricing template and query Huawei Cloud yearly/monthly subscription pricing. Read-only. Does not create, buy, or modify resources.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region, for example la-north-2."
            },
            service: {
              type: "string",
              description: "Service name, for example hss, cfw, ecs, rds."
            },
            template_id: {
              type: "string",
              description: "Template ID from pricing-templates.json with billing_mode=period, for example hss-host-protection-period."
            },
            quantity: {
              type: "integer",
              description: "Number of resources/components.",
              default: 1
            },
            parameters: {
              type: "object",
              description: "Variable parameters such as quantity, hss_resource_spec, period_type, period_num, monthly_hours.",
              additionalProperties: true
            },
            project_id: {
              type: "string",
              description: "Optional Huawei Cloud project ID. If omitted, HUAWEI_PROJECT_ID is used."
            }
          },
          required: ["service", "template_id"]
        }
      },
      {
        name: "EstimateArchitecturePeriodPrice",
        description: "Estimate period (yearly/monthly subscription) pricing for an architecture composed of multiple local pricing templates. Supports mixed on-demand and period components. Calculates real prices for ready templates. Read-only.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region, for example la-north-2."
            },
            components: {
              type: "array",
              description: "Architecture components to estimate. Each component is routed to on-demand or period API based on its template billing_mode.",
              items: {
                type: "object",
                properties: {
                  service: {
                    type: "string",
                    description: "Service name, for example hss, cbr, ecs."
                  },
                  template_id: {
                    type: "string",
                    description: "Template ID from pricing-templates.json."
                  },
                  quantity: {
                    type: "integer",
                    description: "Number of resources.",
                    default: 1
                  },
                  parameters: {
                    type: "object",
                    description: "Variable parameters for the template.",
                    additionalProperties: true
                  }
                },
                required: ["service", "template_id"]
              }
            },
            project_id: {
              type: "string",
              description: "Optional Huawei Cloud project ID. If omitted, HUAWEI_PROJECT_ID is used."
            },
            inquiry_precision: {
              type: "integer",
              description: "0 default precision, 1 high precision.",
              default: 1
            }
          },
          required: ["components"]
        }
      },
      {
        name: "QueryOnDemandPrice",
        description: "Query Huawei Cloud pay-per-use prices using the official pricing API. Read-only. Does not create, buy, or modify resources.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            project_id: {
              type: "string",
              description: "Optional project ID. If omitted, HUAWEI_PROJECT_ID is used."
            },
            inquiry_precision: {
              type: "integer",
              description: "0 default precision, 1 high precision.",
              default: 1
            },
            product_infos: {
              type: "array",
              description: "Raw Huawei Cloud product_infos array for /v2/bills/ratings/on-demand-resources.",
              items: { type: "object" }
            }
          },
          required: ["product_infos"]
        }
      },
      {
        name: "QueryPeriodPrice",
        description: "Query Huawei Cloud yearly/monthly subscription prices using the official pricing API. Read-only. Does not create, buy, or modify resources.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            project_id: {
              type: "string",
              description: "Optional project ID. If omitted, HUAWEI_PROJECT_ID is used."
            },
            product_infos: {
              type: "array",
              description: "Raw Huawei Cloud product_infos array for /v2/bills/ratings/period-resources/subscribe-rate.",
              items: { type: "object" }
            }
          },
          required: ["product_infos"]
        }
      },
      {
        name: "RenderProductInfosFromTemplate",
        description: "Render Huawei Cloud pricing product_infos from a local parametric product_infos_template and real architecture parameters. Does not call Huawei Cloud APIs.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region, for example la-north-2."
            },
            service: {
              type: "string",
              description: "Service name, for example evs, eip, ecs, rds, obs."
            },
            template_id: {
              type: "string",
              description: "Template ID from pricing-templates.json."
            },
            quantity: {
              type: "integer",
              description: "Number of resources/components.",
              default: 1
            },
            parameters: {
              type: "object",
              description: "Variable parameters such as size_gb, bandwidth_mbps, storage_gb, monthly_hours, system_disk_gb.",
              additionalProperties: true
            }
          },
          required: ["service", "template_id"]
        }
      },
      {
        name: "PricingProductInfoGuide",
        description: "Explain what product_infos are and how architects can obtain them from Huawei Cloud Price Calculator/API Explorer. Does not call Huawei Cloud APIs.",
        inputSchema: {
          type: "object",
          properties: {},
          required: []
        }
      },
      {
        name: "EvaluateEcsFlavorAvailability",
        description: "Evaluate ECS flavor availability for a given region/AZ based on vCPU/RAM requirements. Filters out abandon and sellout flavors. Returns exact matches and close alternatives. Read-only. Does not create, buy, or modify resources.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            availability_zone: {
              type: "string",
              description: "Target availability zone, for example la-north-2a."
            },
            vcpus: {
              type: "integer",
              description: "Required vCPU count."
            },
            ram_gb: {
              type: "number",
              description: "Required RAM in GB."
            },
            preferred_flavor: {
              type: "string",
              description: "Optional preferred flavor ID, for example s6.large.2."
            },
            allow_alternatives: {
              type: "boolean",
              description: "If true, return close alternatives when no exact match.",
              default: true
            },
            max_alternatives: {
              type: "integer",
              description: "Max number of alternative flavors to return.",
              default: 5
            },
            max_vcpu_multiplier: {
              type: "number",
              description: "Max vCPU multiplier for alternatives. A candidate flavor must have vcpus <= requested_vcpus * max_vcpu_multiplier.",
              default: 4
            },
            max_ram_multiplier: {
              type: "number",
              description: "Max RAM multiplier for alternatives. A candidate flavor must have ram_gb <= requested_ram_gb * max_ram_multiplier.",
              default: 4
            },
            include_oversized_candidates: {
              type: "boolean",
              description: "If true, flavors exceeding multiplier limits are returned separately in oversized_candidates, not mixed into alternatives.",
              default: false
            },
            timeout_ms: {
              type: "integer",
              description: "Timeout in milliseconds.",
              default: 30000
            }
          },
          required: ["region", "availability_zone", "vcpus", "ram_gb"]
        }
      },
      {
        name: "FindEcsFlavorCandidates",
        description: "Find ECS flavor candidates across multiple availability zones in a region. Evaluates each AZ independently and returns exact matches, alternatives, and oversized candidates per AZ. Returns a global status (OK/PARTIAL/ERROR) and structured summary. Read-only. Does not create, buy, or modify resources.",
        inputSchema: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Huawei Cloud region code, for example la-north-2."
            },
            targets: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  availability_zone: {
                    type: "string",
                    description: "Availability zone ID, for example la-north-2a."
                  },
                  preferred_flavor: {
                    type: "string",
                    description: "Optional preferred flavor ID for this AZ."
                  }
                },
                required: ["availability_zone"]
              },
              description: "Explicit list of target AZs to evaluate. No auto-discovery."
            },
            vcpus: {
              type: "integer",
              description: "Required vCPU count."
            },
            ram_gb: {
              type: "number",
              description: "Required RAM in GB."
            },
            allow_alternatives: {
              type: "boolean",
              description: "If true, return close alternatives when no exact match.",
              default: true
            },
            max_alternatives: {
              type: "integer",
              description: "Max number of alternative flavors per AZ.",
              default: 5
            },
            max_vcpu_multiplier: {
              type: "number",
              description: "Max vCPU multiplier for alternatives. A candidate flavor must have vcpus <= requested_vcpus * max_vcpu_multiplier.",
              default: 4
            },
            max_ram_multiplier: {
              type: "number",
              description: "Max RAM multiplier for alternatives. A candidate flavor must have ram_gb <= requested_ram_gb * max_ram_multiplier.",
              default: 4
            },
            include_oversized_candidates: {
              type: "boolean",
              description: "If true, flavors exceeding multiplier limits are returned separately in oversized_candidates per AZ.",
              default: false
            },
            max_oversized_candidates: {
              type: "integer",
              description: "Max number of oversized candidates per AZ, sorted by resource_jump_score ascending.",
              default: 5
            },
            timeout_ms: {
              type: "integer",
              description: "Timeout in milliseconds per AZ query.",
              default: 30000
            }
          },
          required: ["region", "targets", "vcpus", "ram_gb"]
        }
      }
    ]
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args = {} } = request.params;

  if (name === "QueryCloudServiceTypes") {
    const query = {
      limit: args.limit ?? 100,
      offset: args.offset ?? 0
    };

    if (args.service_type_code) query.service_type_code = args.service_type_code;
    if (args.service_type_name) query.service_type_name = args.service_type_name;

    const result = await callHuaweiCatalogApi({
      apiPath: "/v2/products/service-types",
      args: {
        query,
        x_language: args.x_language || "en_US",
        timeout_ms: args.timeout_ms
      }
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryCloudServiceTypes",
            read_only: true,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryResourceTypes") {
    const result = await callHuaweiCatalogApi({
      apiPath: "/v2/products/resource-types",
      args: {
        query: {
          limit: args.limit ?? 100,
          offset: args.offset ?? 0
        },
        x_language: args.x_language || "en_US",
        timeout_ms: args.timeout_ms
      }
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryResourceTypes",
            read_only: true,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryServiceResources") {
    if (!args.service_type_code) {
      throw new Error("service_type_code is required");
    }

    const result = await callHuaweiCatalogApi({
      apiPath: "/v2/products/service-resources",
      args: {
        query: {
          service_type_code: args.service_type_code,
          limit: args.limit ?? 100,
          offset: args.offset ?? 0
        },
        x_language: args.x_language || "en_US",
        timeout_ms: args.timeout_ms
      }
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryServiceResources",
            read_only: true,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryUsageTypes") {
    const result = await callHuaweiCatalogApi({
      apiPath: "/v2/products/usage-types",
      args: {
        query: {
          limit: args.limit ?? 100,
          offset: args.offset ?? 0,
          service_type_code: args.service_type_code,
          resource_type_code: args.resource_type_code
        },
        x_language: args.x_language || "en_US",
        timeout_ms: args.timeout_ms
      }
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryUsageTypes",
            read_only: true,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryMeasurementUnits") {
    const result = await callHuaweiCatalogApi({
      apiPath: "/v2/bases/measurements",
      args: {
        query: {
          limit: args.limit ?? 100,
          offset: args.offset ?? 0
        },
        x_language: args.x_language || "en_US",
        timeout_ms: args.timeout_ms
      }
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryMeasurementUnits",
            read_only: true,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryElbFlavors") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const resolvedProject = resolveProjectIdForRegion(region);

    if (resolvedProject.error) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryElbFlavors",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: resolvedProject.error,
              message: resolvedProject.message
            }, null, 2)
          }
        ]
      };
    }

    const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
    const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

    const cliArgs = [helper, "elb-flavors"];

    const { stdout, stderr } = await execFileAsync(
      pythonBin,
      cliArgs,
      {
        timeout: args.timeout_ms || 30000,
        maxBuffer: 10 * 1024 * 1024,
        env: { ...process.env, HUAWEI_DEFAULT_REGION: region, HUAWEI_PROJECT_ID: resolvedProject.project_id }
      }
    );

    if (stderr && stderr.trim().length > 0) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryElbFlavors",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              error: "Python helper wrote to stderr",
              stderr
            }, null, 2)
          }
        ]
      };
    }

    const result = JSON.parse(stdout);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryElbFlavors",
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryElbAvailabilityZones") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const resolvedProject = resolveProjectIdForRegion(region);

    if (resolvedProject.error) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryElbAvailabilityZones",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: resolvedProject.error,
              message: resolvedProject.message
            }, null, 2)
          }
        ]
      };
    }

    const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
    const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

    const cliArgs = [helper, "elb-availability-zones"];

    const { stdout, stderr } = await execFileAsync(
      pythonBin,
      cliArgs,
      {
        timeout: args.timeout_ms || 30000,
        maxBuffer: 10 * 1024 * 1024,
        env: { ...process.env, HUAWEI_DEFAULT_REGION: region, HUAWEI_PROJECT_ID: resolvedProject.project_id }
      }
    );

    if (stderr && stderr.trim().length > 0) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryElbAvailabilityZones",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              error: "Python helper wrote to stderr",
              stderr
            }, null, 2)
          }
        ]
      };
    }

    const result = JSON.parse(stdout);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryElbAvailabilityZones",
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryRdsFlavors") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const resolvedProject = resolveProjectIdForRegion(region);

    if (resolvedProject.error) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryRdsFlavors",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: resolvedProject.error,
              message: resolvedProject.message
            }, null, 2)
          }
        ]
      };
    }

    const rdsVersion = args.rds_version || "8.0";
    const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
    const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

    const cliArgs = [helper, "rds-flavors", "--rds-version", rdsVersion];

    const { stdout, stderr } = await execFileAsync(
      pythonBin,
      cliArgs,
      {
        timeout: args.timeout_ms || 30000,
        maxBuffer: 20 * 1024 * 1024,
        env: { ...process.env, HUAWEI_DEFAULT_REGION: region, HUAWEI_PROJECT_ID: resolvedProject.project_id }
      }
    );

    if (stderr && stderr.trim().length > 0) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryRdsFlavors",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: "Python helper wrote to stderr",
              stderr
            }, null, 2)
          }
        ]
      };
    }

    const result = JSON.parse(stdout);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryRdsFlavors",
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryRdsStorageTypes") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const resolvedProject = resolveProjectIdForRegion(region);

    if (resolvedProject.error) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryRdsStorageTypes",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: resolvedProject.error,
              message: resolvedProject.message
            }, null, 2)
          }
        ]
      };
    }

    const rdsVersion = args.rds_version || "8.0";
    const haMode = args.ha_mode || "single";
    const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
    const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

    const cliArgs = [helper, "rds-storage-types", "--rds-version", rdsVersion, "--ha-mode", haMode];

    const { stdout, stderr } = await execFileAsync(
      pythonBin,
      cliArgs,
      {
        timeout: args.timeout_ms || 30000,
        maxBuffer: 20 * 1024 * 1024,
        env: { ...process.env, HUAWEI_DEFAULT_REGION: region, HUAWEI_PROJECT_ID: resolvedProject.project_id }
      }
    );

    if (stderr && stderr.trim().length > 0) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryRdsStorageTypes",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: "Python helper wrote to stderr",
              stderr
            }, null, 2)
          }
        ]
      };
    }

    const result = JSON.parse(stdout);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryRdsStorageTypes",
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryEcsFlavors") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const resolvedProject = resolveProjectIdForRegion(region);

    if (resolvedProject.error) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryEcsFlavors",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: resolvedProject.error,
              message: resolvedProject.message
            }, null, 2)
          }
        ]
      };
    }

    const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
    const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

    const cliArgs = [helper, "ecs-flavors"];

    if (args.availability_zone) {
      cliArgs.push("--availability-zone", args.availability_zone);
    }

    const { stdout, stderr } = await execFileAsync(
      pythonBin,
      cliArgs,
      {
        timeout: args.timeout_ms || 30000,
        maxBuffer: 20 * 1024 * 1024,
        env: { ...process.env, HUAWEI_DEFAULT_REGION: region, HUAWEI_PROJECT_ID: resolvedProject.project_id }
      }
    );

    if (stderr && stderr.trim().length > 0) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryEcsFlavors",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              error: "Python helper wrote to stderr",
              stderr
            }, null, 2)
          }
        ]
      };
    }

    const result = JSON.parse(stdout);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryEcsFlavors",
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryEvsVolumeTypes") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const resolvedProject = resolveProjectIdForRegion(region);

    if (resolvedProject.error) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryEvsVolumeTypes",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: resolvedProject.error,
              message: resolvedProject.message
            }, null, 2)
          }
        ]
      };
    }

    const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
    const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

    const cliArgs = [helper, "evs-volume-types"];

    if (args.availability_zone) {
      cliArgs.push("--availability-zone", args.availability_zone);
    }

    if (args.volume_type) {
      cliArgs.push("--volume-type", args.volume_type);
    }

    const { stdout, stderr } = await execFileAsync(
      pythonBin,
      cliArgs,
      {
        timeout: args.timeout_ms || 30000,
        maxBuffer: 20 * 1024 * 1024,
        env: { ...process.env, HUAWEI_DEFAULT_REGION: region, HUAWEI_PROJECT_ID: resolvedProject.project_id }
      }
    );

    if (stderr && stderr.trim().length > 0) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "QueryEvsVolumeTypes",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              error: "Python helper wrote to stderr",
              stderr
            }, null, 2)
          }
        ]
      };
    }

    const result = JSON.parse(stdout);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryEvsVolumeTypes",
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "PricingHealthCheck") {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "PricingHealthCheck",
            status: "OK",
            read_only: true,
            purpose: "Huawei Cloud pricing assistant for architects",
            default_region: process.env.HUAWEI_DEFAULT_REGION || null,
            project_id: process.env.HUAWEI_PROJECT_ID ? "SET" : "MISSING",
            pricing_endpoint: process.env.HUAWEI_PRICING_ENDPOINT || null,
            credentials: {
              HUAWEI_ACCESS_KEY: envStatus("HUAWEI_ACCESS_KEY"),
              HUAWEI_SECRET_KEY: envStatus("HUAWEI_SECRET_KEY")
            },
            safety: {
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false
            }
          }, null, 2)
        }
      ]
    };
  }

  if (name === "ListPricingTemplates") {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(listPricingTemplates(args), null, 2)
        }
      ]
    };
  }

  if (name === "ExplainRequiredTemplate") {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(explainRequiredTemplate(args), null, 2)
        }
      ]
    };
  }

  if (name === "EstimateArchitectureCostDraft") {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(estimateArchitectureCostDraft(args), null, 2)
        }
      ]
    };
  }

  if (name === "RenderProductInfosFromTemplate") {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(renderProductInfosFromTemplate(args), null, 2)
        }
      ]
    };
  }

  if (name === "PricingProductInfoGuide") {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "PricingProductInfoGuide",
            message: "Huawei Cloud pricing APIs require product_infos. The practical workflow is: use Huawei Cloud Price Calculator or API Explorer to obtain valid product_infos for each resource specification, then pass that array to QueryOnDemandPrice or QueryPeriodPrice.",
            on_demand_api: "/v2/bills/ratings/on-demand-resources",
            period_api: "/v2/bills/ratings/period-resources/subscribe-rate",
            notes: [
              "product_infos depends on service type, resource type, resource spec, usage type, region, duration, and quantity.",
              "This MCP does not create or purchase resources.",
              "For architect workflows, keep a catalog of validated product_infos templates for ECS, EVS, EIP, ELB, RDS, OBS, and other common services."
            ]
          }, null, 2)
        }
      ]
    };
  }

  if (name === "EstimateArchitectureOnDemandPrice") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const validateAvailability = args.validate_availability === true;
    const defaultAvailabilityZone = args.default_availability_zone || null;
    const includeUnavailableReferencePricing = args.include_unavailable_reference_pricing === true;
    const normalized = normalizeArchitectureComponents(args);
    const components = normalized.components;

    if (components.length === 0) {
      throw new Error("components must be a non-empty array");
    }

    function stripLinuxSuffix(resourceSpec) {
      if (!resourceSpec) return null;
      const knownOsSuffixes = [".linux", ".windows"];
      for (const suffix of knownOsSuffixes) {
        if (resourceSpec.endsWith(suffix)) {
          return resourceSpec.slice(0, -suffix.length);
        }
      }
      return resourceSpec;
    }

    function parseEcsTemplateHints(templateId) {
      if (!templateId) return { vcpus: null, ram_gb: null };
      const match = templateId.match(/^ecs-linux-(\d+)vcpu-(\d+)gb-/);
      if (match) {
        return { vcpus: parseInt(match[1], 10), ram_gb: parseInt(match[2], 10) };
      }
      return { vcpus: null, ram_gb: null };
    }

    function parseAzStatus(azSpec, targetAz) {
      if (!azSpec || !targetAz) return "not_available";
      const parts = azSpec.split(",");
      for (const part of parts) {
        const trimmed = part.trim();
        const match = trimmed.match(/^([^(]+)\(([^)]+)\)$/);
        if (match && match[1] === targetAz) {
          return match[2];
        }
      }
      return "not_available";
    }

    const flavorsCache = {};

    async function getEvaluatedFlavors(cacheRegion, cacheAz) {
      const cacheKey = `${cacheRegion}|${cacheAz}`;
      if (flavorsCache[cacheKey]) {
        return flavorsCache[cacheKey];
      }

      const resolvedProject = resolveProjectIdForRegion(cacheRegion);
      if (resolvedProject.error) {
        flavorsCache[cacheKey] = { error: resolvedProject.message, evaluated: null };
        return flavorsCache[cacheKey];
      }

      const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
      const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

      try {
        const cliArgs = [helper, "ecs-flavors", "--availability-zone", cacheAz];
        const { stdout, stderr } = await execFileAsync(
          pythonBin,
          cliArgs,
          {
            timeout: 30000,
            maxBuffer: 20 * 1024 * 1024,
            env: { ...process.env, HUAWEI_DEFAULT_REGION: cacheRegion, HUAWEI_PROJECT_ID: resolvedProject.project_id }
          }
        );

        if (stderr && stderr.trim().length > 0) {
          flavorsCache[cacheKey] = { error: "Python helper wrote to stderr", evaluated: null };
          return flavorsCache[cacheKey];
        }

        const parsed = JSON.parse(stdout);
        const rawFlavors = parsed.data?.flavors;

        if (!Array.isArray(rawFlavors)) {
          flavorsCache[cacheKey] = { error: "Unexpected response structure", evaluated: null };
          return flavorsCache[cacheKey];
        }

        const evaluated = rawFlavors.map((flavor) => {
          const specs = flavor.os_extra_specs || {};
          const fVcpus = parseInt(flavor.vcpus, 10);
          const ramMb = flavor.ram;
          const ramGb = ramMb / 1024;
          const operationStatus = specs["cond:operation:status"] || "unknown";
          const azStatus = parseAzStatus(specs["cond:operation:az"] || "", cacheAz);
          const recommendable = azStatus === "normal" && operationStatus === "normal";
          return {
            flavor_id: flavor.id,
            vcpus: fVcpus,
            ram_mb: ramMb,
            ram_gb: ramGb,
            generation: specs["ecs:generation"] || "",
            performancetype: specs["ecs:performancetype"] || "",
            operation_status: operationStatus,
            az_status: azStatus,
            recommendable
          };
        });

        flavorsCache[cacheKey] = { error: null, evaluated };
      } catch (error) {
        flavorsCache[cacheKey] = { error: error.message, evaluated: null };
      }

      return flavorsCache[cacheKey];
    }

    const availabilityValidationComponents = [];

    if (validateAvailability) {
      for (let i = 0; i < components.length; i++) {
        const component = components[i];
        if (component.service !== "ecs") continue;

        const az =
          component.availability_zone ||
          (component.parameters || {}).availability_zone ||
          defaultAvailabilityZone;

        if (!az) {
          availabilityValidationComponents.push({
            component_index: i,
            template_id: component.template_id,
            component_type: "ecs",
            requested: { region, availability_zone: null, vcpus: null, ram_gb: null, preferred_flavor: null, resource_spec_source: null },
            status: "insufficient_data",
            preferred_flavor_status: "not_requested",
            preferred_flavor_reason: null,
            exact_matches: [],
            alternatives: [],
            oversized_candidates: [],
            excluded_summary: { operation_abandon: 0, az_sellout: 0, az_abandon: 0, az_not_available: 0, unknown_status: 0 },
            next_action: null,
            pricing_blocked: false,
            pricing_blocked_reason: null
          });
          continue;
        }

        let preferredFlavor = component.preferred_flavor || (component.parameters || {}).preferred_flavor || null;
        let resourceSpecSource = null;

        if (!preferredFlavor) {
          const componentArgs = {
            ...component,
            region,
            project_id: args.project_id,
            inquiry_precision: args.inquiry_precision ?? 1
          };
          let renderedForSpec;
          try {
            renderedForSpec = renderProductInfosFromTemplate(componentArgs);
          } catch {
            renderedForSpec = null;
          }

          const resourceSpec = renderedForSpec?.resolved_parameters?.resource_spec ?? null;

          if (resourceSpec) {
            preferredFlavor = stripLinuxSuffix(resourceSpec);
            const inputResourceSpec = (component.parameters || {}).resource_spec;
            if (inputResourceSpec) {
              resourceSpecSource = "component_parameter";
            } else {
              resourceSpecSource = "template_default";
            }
          }
        } else {
          resourceSpecSource = "component_preferred_flavor";
        }

        const hints = parseEcsTemplateHints(component.template_id);
        const vcpus = (component.parameters || {}).vcpus ?? hints.vcpus;
        const ramGb = (component.parameters || {}).ram_gb ?? hints.ram_gb;

        if (!preferredFlavor && vcpus == null && ramGb == null) {
          availabilityValidationComponents.push({
            component_index: i,
            template_id: component.template_id,
            component_type: "ecs",
            requested: { region, availability_zone: az, vcpus: null, ram_gb: null, preferred_flavor: null, resource_spec_source: null },
            status: "insufficient_data",
            preferred_flavor_status: "not_requested",
            preferred_flavor_reason: null,
            exact_matches: [],
            alternatives: [],
            oversized_candidates: [],
            excluded_summary: { operation_abandon: 0, az_sellout: 0, az_abandon: 0, az_not_available: 0, unknown_status: 0 },
            next_action: null,
            pricing_blocked: false,
            pricing_blocked_reason: null
          });
          continue;
        }

        const cacheResult = await getEvaluatedFlavors(region, az);

        if (cacheResult.error || !cacheResult.evaluated) {
          availabilityValidationComponents.push({
            component_index: i,
            template_id: component.template_id,
            component_type: "ecs",
            requested: { region, availability_zone: az, vcpus, ram_gb: ramGb, preferred_flavor: preferredFlavor, resource_spec_source: resourceSpecSource },
            status: "discovery_error",
            preferred_flavor_status: "not_requested",
            preferred_flavor_reason: null,
            exact_matches: [],
            alternatives: [],
            oversized_candidates: [],
            excluded_summary: { operation_abandon: 0, az_sellout: 0, az_abandon: 0, az_not_available: 0, unknown_status: 0 },
            next_action: null,
            pricing_blocked: true,
            pricing_blocked_reason: "Availability discovery failed; pricing blocked for safety."
          });
          continue;
        }

        const evaluated = cacheResult.evaluated;

        const pfStatus = { value: "not_requested", reason: null, detail: null };
        if (preferredFlavor) {
          const found = evaluated.find((f) => f.flavor_id === preferredFlavor);
          if (!found) {
            pfStatus.value = "invalid_selection";
            pfStatus.reason = "Flavor not found in the region/AZ.";
          } else {
            pfStatus.detail = {
              flavor_id: found.flavor_id,
              vcpus: found.vcpus,
              ram_gb: found.ram_gb,
              operation_status: found.operation_status,
              az_status: found.az_status,
              recommendable: found.recommendable
            };
            if (found.operation_status === "abandon") {
              pfStatus.value = "invalid_selection";
              pfStatus.reason = "Flavor is marked as abandon and should not be recommended for new architectures.";
            } else if (found.az_status === "sellout") {
              pfStatus.value = "invalid_selection";
              pfStatus.reason = "Flavor is sold out in the requested AZ.";
            } else if (found.az_status === "abandon") {
              pfStatus.value = "invalid_selection";
              pfStatus.reason = "Flavor is abandoned in the requested AZ.";
            } else if (found.az_status === "not_available") {
              pfStatus.value = "invalid_selection";
              pfStatus.reason = "Flavor is not available in the requested AZ.";
            } else if (found.recommendable) {
              pfStatus.value = "valid";
              pfStatus.reason = null;
            } else {
              pfStatus.value = "invalid_selection";
              pfStatus.reason = `Flavor is not recommendable (operation_status=${found.operation_status}, az_status=${found.az_status}).`;
            }
          }
        }

        const exactMatches = evaluated.filter(
          (f) => f.recommendable && vcpus != null && ramGb != null && f.vcpus === vcpus && f.ram_gb === ramGb
        );

        let alternatives = [];
        let oversizedCandidates = [];
        if (exactMatches.length === 0 && vcpus != null && ramGb != null) {
          const maxVcpuMultiplier = 4;
          const maxRamMultiplier = 4;
          const maxVcpus = vcpus * maxVcpuMultiplier;
          const maxRamGb = ramGb * maxRamMultiplier;

          const withinBounds = evaluated.filter(
            (f) => f.recommendable && f.vcpus >= vcpus && f.ram_gb >= ramGb && f.vcpus <= maxVcpus && f.ram_gb <= maxRamGb
          );

          alternatives = withinBounds
            .map((f) => ({
              ...f,
              delta_vcpus: f.vcpus - vcpus,
              delta_ram_gb: Math.round((f.ram_gb - ramGb) * 1000) / 1000,
              resource_jump_score: (f.vcpus - vcpus) + (f.ram_gb - ramGb)
            }))
            .sort((a, b) => {
              if (a.resource_jump_score !== b.resource_jump_score) return a.resource_jump_score - b.resource_jump_score;
              if (a.delta_vcpus !== b.delta_vcpus) return a.delta_vcpus - b.delta_vcpus;
              return a.flavor_id.localeCompare(b.flavor_id);
            })
            .slice(0, 5);

          const oversized = evaluated.filter(
            (f) => f.recommendable && f.vcpus >= vcpus && f.ram_gb >= ramGb && (f.vcpus > maxVcpus || f.ram_gb > maxRamGb)
          );

          oversizedCandidates = oversized
            .map((f) => ({
              ...f,
              delta_vcpus: f.vcpus - vcpus,
              delta_ram_gb: Math.round((f.ram_gb - ramGb) * 1000) / 1000,
              resource_jump_score: (f.vcpus - vcpus) + (f.ram_gb - ramGb)
            }))
            .sort((a, b) => {
              if (a.resource_jump_score !== b.resource_jump_score) return a.resource_jump_score - b.resource_jump_score;
              if (a.delta_vcpus !== b.delta_vcpus) return a.delta_vcpus - b.delta_vcpus;
              return a.flavor_id.localeCompare(b.flavor_id);
            });
        }

        const excludedSummary = {
          operation_abandon: evaluated.filter((f) => f.operation_status === "abandon").length,
          az_sellout: evaluated.filter((f) => f.operation_status !== "abandon" && f.az_status === "sellout").length,
          az_abandon: evaluated.filter((f) => f.operation_status !== "abandon" && f.az_status === "abandon").length,
          az_not_available: evaluated.filter((f) => f.operation_status !== "abandon" && f.az_status === "not_available").length,
          unknown_status: evaluated.filter((f) => f.operation_status === "unknown" || (f.operation_status !== "abandon" && f.operation_status !== "normal" && f.operation_status !== "unknown")).length
        };

        const totalRecommendable = evaluated.filter((f) => f.recommendable).length;

        let componentStatus;
        if (exactMatches.length > 0) {
          componentStatus = "available";
        } else if (pfStatus.value === "invalid_selection") {
          componentStatus = "invalid_selection";
        } else if (alternatives.length > 0) {
          componentStatus = "alternatives_available";
        } else if (totalRecommendable === 0) {
          componentStatus = "unavailable";
        } else {
          componentStatus = "no_exact_match";
        }

        let nextAction = null;
        if (componentStatus === "available") {
          nextAction = null;
        } else if (componentStatus === "alternatives_available") {
          nextAction = "architect_selection_required";
        } else if (componentStatus === "invalid_selection" && alternatives.length > 0) {
          nextAction = "architect_selection_required";
        } else if (componentStatus === "invalid_selection" && oversizedCandidates.length > 0) {
          nextAction = "review_capacity_or_region";
        } else if (componentStatus === "invalid_selection") {
          nextAction = "review_capacity_or_region";
        } else if (componentStatus === "no_exact_match" && alternatives.length > 0) {
          nextAction = "architect_selection_required";
        } else if (componentStatus === "no_exact_match") {
          nextAction = "review_capacity_or_region";
        } else if (componentStatus === "unavailable") {
          nextAction = "review_capacity_or_region";
        }

        let pricingBlocked = false;
        let pricingBlockedReason = null;

        if (pfStatus.value === "invalid_selection") {
          pricingBlocked = true;
          pricingBlockedReason = `Preferred flavor is invalid: ${pfStatus.reason}`;
        } else if (componentStatus === "unavailable") {
          pricingBlocked = true;
          pricingBlockedReason = "No recommendable ECS flavors available in this AZ.";
        } else if (componentStatus === "no_exact_match" && pfStatus.value !== "valid") {
          pricingBlocked = true;
          pricingBlockedReason = "No exact match found and no valid preferred flavor.";
        } else if (componentStatus === "alternatives_available" && pfStatus.value !== "valid") {
          pricingBlocked = true;
          pricingBlockedReason = "Alternatives exist but no valid preferred flavor selected.";
        } else if (componentStatus === "discovery_error") {
          pricingBlocked = true;
          pricingBlockedReason = "Availability discovery failed; pricing blocked for safety.";
        }

        availabilityValidationComponents.push({
          component_index: i,
          template_id: component.template_id,
          component_type: "ecs",
          requested: { region, availability_zone: az, vcpus, ram_gb: ramGb, preferred_flavor: preferredFlavor, resource_spec_source: resourceSpecSource },
          status: componentStatus,
          preferred_flavor_status: pfStatus.value,
          preferred_flavor_reason: pfStatus.reason,
          exact_matches: exactMatches,
          alternatives,
          oversized_candidates: oversizedCandidates,
          excluded_summary: excludedSummary,
          next_action: nextAction,
          pricing_blocked: pricingBlocked,
          pricing_blocked_reason: pricingBlockedReason
        });
      }
    }

    let overallAvailStatus = null;
    if (validateAvailability && availabilityValidationComponents.length > 0) {
      const statuses = availabilityValidationComponents.map((c) => c.status);
      if (statuses.some((s) => s === "discovery_error")) {
        overallAvailStatus = "discovery_error";
      } else if (statuses.every((s) => s === "available")) {
        overallAvailStatus = "available";
      } else if (statuses.every((s) => s === "invalid_selection" || s === "unavailable")) {
        overallAvailStatus = "unavailable";
      } else if (
        statuses.some((s) => s === "available" || s === "alternatives_available" || s === "no_exact_match") &&
        statuses.some((s) => s === "invalid_selection" || s === "unavailable")
      ) {
        overallAvailStatus = "partially_available";
      } else if (statuses.some((s) => s === "insufficient_data")) {
        overallAvailStatus = "validation_warnings";
      } else {
        overallAvailStatus = "validation_warnings";
      }
    } else if (validateAvailability) {
      overallAvailStatus = "available";
    }

    const ecsBlockedIndices = new Set();
    if (validateAvailability) {
      for (const vc of availabilityValidationComponents) {
        if (vc.pricing_blocked) {
          ecsBlockedIndices.add(vc.component_index);
        }
      }
    }

    const pricedComponents = [];
    const pendingComponents = [];
    const failedComponents = [];
    const availabilityBlockedComponents = [];

    let monthlyTotal = 0;
    let annualSimpleTotal = 0;
    let currency = null;

    const componentPricingMap = [];

    for (let compIdx = 0; compIdx < components.length; compIdx++) {
      const component = components[compIdx];

      if (validateAvailability && component.service === "ecs" && ecsBlockedIndices.has(compIdx)) {
        const vc = availabilityValidationComponents.find((v) => v.component_index === compIdx);
        availabilityBlockedComponents.push({
          service: component.service,
          template_id: component.template_id,
          quantity: component.quantity || 1,
          parameters: component.parameters || {},
          availability_status: vc ? vc.status : null,
          availability_reason: vc ? vc.pricing_blocked_reason : null
        });
        componentPricingMap.push({
          status: "blocked",
          pricedIndex: null,
          template_id: component.template_id,
          service: component.service,
          parameters: component.parameters || {},
          component_index: compIdx,
          network_type: (component.parameters || {}).network_type ?? component.network_type ?? null
        });
        continue;
      }

      const componentArgs = {
        ...component,
        region,
        project_id: args.project_id,
        inquiry_precision: args.inquiry_precision ?? 1
      };

      const rendered = renderProductInfosFromTemplate(componentArgs);

      if (rendered.status !== "OK") {
        pendingComponents.push({
          service: component.service,
          template_id: component.template_id,
          quantity: component.quantity || 1,
          parameters: component.parameters || {},
          render_status: rendered.status,
          reason: rendered.message || "Template is not ready for real pricing",
          rendered
        });
        componentPricingMap.push({
          status: "pending",
          pricedIndex: null,
          template_id: component.template_id,
          service: component.service,
          parameters: component.parameters || {},
          component_index: compIdx,
          network_type: (component.parameters || {}).network_type ?? component.network_type ?? null
        });
        continue;
      }

      try {
        const pricingResult = await callHuaweiPricingApi({
          apiPath: "/v2/bills/ratings/on-demand-resources",
          args: {
            ...componentArgs,
            product_infos: rendered.product_infos,
            inquiry_precision: args.inquiry_precision ?? 1
          }
        });

        const helperData = pricingResult.helper_result || {};
        const data = helperData.data || {};

        const apiAmount = data.amount ?? 0;
        const officialApiAmount = data.official_website_amount ?? null;
        const discountApiAmount = data.discount_amount ?? null;

        const monthlyHours = Number(
          rendered.resolved_parameters?.monthly_hours ??
          componentArgs.parameters?.monthly_hours ??
          0
        );

        const hasDurationUsage = rendered.product_infos.some((productInfo) =>
          productInfo.usage_factor === "Duration" ||
          productInfo.usage_factor === "duration" ||
          Number(productInfo.usage_measure_id) === 4
        );

        const shouldConvertHourlyToMonthly =
          apiAmount !== null &&
          monthlyHours > 0 &&
          !hasDurationUsage;

        const monthlyAmount = shouldConvertHourlyToMonthly ? apiAmount * monthlyHours : apiAmount;
        const annualSimpleAmount = monthlyAmount * 12;

        const officialMonthlyAmount =
          officialApiAmount !== null && officialApiAmount !== undefined
            ? (shouldConvertHourlyToMonthly ? officialApiAmount * monthlyHours : officialApiAmount)
            : null;

        const discountAmount =
          discountApiAmount !== null && discountApiAmount !== undefined
            ? (shouldConvertHourlyToMonthly ? discountApiAmount * monthlyHours : discountApiAmount)
            : null;

        const pricingBasis = {
          api_amount: apiAmount,
          official_api_amount: officialApiAmount,
          discount_api_amount: discountApiAmount,
          api_amount_interpretation: shouldConvertHourlyToMonthly
            ? "API amount interpreted as hourly amount and multiplied by monthly_hours because product_infos do not use Duration/hour."
            : "API amount interpreted as already covering the requested usage_value in product_infos.",
          monthly_hours: monthlyHours || null,
          has_duration_usage: hasDurationUsage,
          applied_monthly_hours_conversion: shouldConvertHourlyToMonthly
        };

        const componentCurrency = data.currency || currency;

        if (!currency && componentCurrency) {
          currency = componentCurrency;
        }

        monthlyTotal += monthlyAmount;
        annualSimpleTotal += annualSimpleAmount;

        pricedComponents.push({
          service: rendered.service,
          template_id: rendered.template_id,
          display_name: rendered.display_name,
          region: rendered.region,
          billing_mode: rendered.billing_mode,
          unit: rendered.unit,
          resolved_parameters: rendered.resolved_parameters,
          api_amount: apiAmount,
          monthly_amount: monthlyAmount,
          annual_simple_amount: annualSimpleAmount,
          official_monthly_amount: officialMonthlyAmount,
          discount_amount: discountAmount,
          currency: componentCurrency,
          pricing_basis: pricingBasis,
          product_infos: rendered.product_infos,
          raw_pricing_response: data
        });

        componentPricingMap.push({
          status: "priced",
          pricedIndex: pricedComponents.length - 1,
          template_id: rendered.template_id,
          service: rendered.service,
          parameters: component.parameters || {},
          component_index: compIdx,
          network_type: (component.parameters || {}).network_type ?? component.network_type ?? null
        });

        if (rendered.service === "elb" && rendered.template_id === "elb-shared-instance-payg" && monthlyAmount === 0) {
          const elbNetworkType = (component.parameters || {}).network_type ?? component.network_type ?? null;
          const notes = [
            "ELB v3 instance price returned by BSS/OCE is 0.00 (unexpected; elbv3.professional is a paid spec).",
            "This may indicate a regional pricing data gap or API limitation."
          ];
          if (elbNetworkType === "public") {
            notes.push("Public exposure is billed separately through EIP bandwidth.");
            notes.push("See service_cost_breakdown for the public ELB grouped cost.");
          } else if (elbNetworkType === "internal") {
            notes.push("No public EIP/bandwidth component is required for internal ELB.");
          } else {
            notes.push("No network_type was specified, so no public bandwidth grouping was inferred.");
          }
          pricedComponents[pricedComponents.length - 1].pricing_notes = notes;
        }
      } catch (error) {
        failedComponents.push({
          service: component.service,
          template_id: component.template_id,
          quantity: component.quantity || 1,
          parameters: component.parameters || {},
          error: error.message
        });
        componentPricingMap.push({
          status: "failed",
          pricedIndex: null,
          template_id: component.template_id,
          service: component.service,
          parameters: component.parameters || {},
          component_index: compIdx,
          network_type: (component.parameters || {}).network_type ?? component.network_type ?? null
        });
      }
    }

    const unavailableReferencePricedComponents = [];
    const warnings = [];
    let monthlyTotalEstimatedWithBlocked = monthlyTotal;
    let annualSimpleTotalEstimatedWithBlocked = annualSimpleTotal;
    let pricingMode = null;

    if (!validateAvailability) {
      pricingMode = "standard_pricing";
      if (includeUnavailableReferencePricing) {
        warnings.push("include_unavailable_reference_pricing has no effect when validate_availability=false.");
      }
    } else if (includeUnavailableReferencePricing && ecsBlockedIndices.size > 0) {
      pricingMode = "validated_with_reference";
      for (const compIdx of ecsBlockedIndices) {
        const component = components[compIdx];
        if (component.service !== "ecs") continue;

        const vc = availabilityValidationComponents.find((v) => v.component_index === compIdx);
        const resourceSpec = (component.parameters || {}).resource_spec || null;

        const quantity = component.quantity || 1;

        const refEntry = {
          component_index: compIdx,
          template_id: component.template_id,
          resource_spec: resourceSpec,
          quantity,
          availability_status: vc ? vc.status : null,
          availability_reason: vc ? vc.pricing_blocked_reason : null,
          pricing_status: null,
          deployment_status: "not_recommended",
          unit_monthly_reference_price: null,
          monthly_reference_total: null,
          monthly_reference_price: null,
          unit_annual_reference_price: null,
          annual_reference_total: null,
          annual_reference_price: null
        };

        try {
          const componentArgs = {
            ...component,
            region,
            project_id: args.project_id,
            inquiry_precision: args.inquiry_precision ?? 1
          };

          const rendered = renderProductInfosFromTemplate(componentArgs);

          if (rendered.status !== "OK") {
            refEntry.pricing_status = "reference_pricing_failed";
            refEntry.pricing_error = "Template could not render product_infos for reference pricing.";
            unavailableReferencePricedComponents.push(refEntry);
            continue;
          }

          const pricingResult = await callHuaweiPricingApi({
            apiPath: "/v2/bills/ratings/on-demand-resources",
            args: {
              ...componentArgs,
              product_infos: rendered.product_infos,
              inquiry_precision: args.inquiry_precision ?? 1
            }
          });

          const helperData = pricingResult.helper_result || {};
          const data = helperData.data || {};

          const apiAmount = data.amount ?? 0;

          const monthlyHours = Number(
            rendered.resolved_parameters?.monthly_hours ??
            componentArgs.parameters?.monthly_hours ??
            0
          );

          const hasDurationUsage = rendered.product_infos.some((productInfo) =>
            productInfo.usage_factor === "Duration" ||
            productInfo.usage_factor === "duration" ||
            Number(productInfo.usage_measure_id) === 4
          );

          const shouldConvertHourlyToMonthly =
            apiAmount !== null &&
            monthlyHours > 0 &&
            !hasDurationUsage;

          const monthlyAmount = shouldConvertHourlyToMonthly ? apiAmount * monthlyHours : apiAmount;
          const annualSimpleAmount = monthlyAmount * 12;

          const componentCurrency = data.currency || currency;
          if (!currency && componentCurrency) {
            currency = componentCurrency;
          }

          refEntry.pricing_status = "reference_priced";
          refEntry.unit_monthly_reference_price = quantity > 0 ? monthlyAmount / quantity : monthlyAmount;
          refEntry.monthly_reference_total = monthlyAmount;
          refEntry.monthly_reference_price = monthlyAmount;
          refEntry.unit_annual_reference_price = quantity > 0 ? annualSimpleAmount / quantity : annualSimpleAmount;
          refEntry.annual_reference_total = annualSimpleAmount;
          refEntry.annual_reference_price = annualSimpleAmount;
          refEntry.currency = componentCurrency;

          monthlyTotalEstimatedWithBlocked += monthlyAmount;
          annualSimpleTotalEstimatedWithBlocked += annualSimpleAmount;
        } catch (error) {
          refEntry.pricing_status = "reference_pricing_failed";
          refEntry.pricing_error = error.message ? error.message.replace(/AK[^ ]*|SK[^ ]*|token[^ ]*|cookie[^ ]*/gi, "[REDACTED]") : "Unknown error during reference pricing.";
        }

        unavailableReferencePricedComponents.push(refEntry);
      }

      if (unavailableReferencePricedComponents.length > 0) {
        warnings.push("Blocked components were priced for reference only. They are not recommended for deployment.");
        const hasAbandonOrSellout = unavailableReferencePricedComponents.some((ref) =>
          ref.availability_reason && (ref.availability_reason.includes("abandon") || ref.availability_reason.includes("sellout") || ref.availability_reason.includes("not available"))
        );
        if (hasAbandonOrSellout) {
          warnings.push("Reference prices for unavailable flavors may not reflect actual deployable capacity.");
        }
      }
    } else if (validateAvailability) {
      pricingMode = "validated_only";
    } else {
      pricingMode = "standard_pricing";
    }

    const monthlyTotalValidated = monthlyTotal;
    const annualSimpleTotalValidated = annualSimpleTotal;

    const serviceCostBreakdown = [];
    {
      const elbPublicEntries = componentPricingMap.filter((entry) =>
        entry.service === "elb" &&
        entry.template_id === "elb-shared-instance-payg" &&
        entry.network_type === "public" &&
        entry.status === "priced"
      );
      const eipBandwidthEntries = componentPricingMap.filter((entry) =>
        entry.service === "eip" &&
        entry.template_id === "eip-bandwidth-mbps-payg" &&
        entry.status === "priced"
      );

      if (elbPublicEntries.length === 1 && eipBandwidthEntries.length === 1) {
        const elbEntry = elbPublicEntries[0];
        const eipEntry = eipBandwidthEntries[0];
        const elbPriced = pricedComponents[elbEntry.pricedIndex];
        const eipPriced = pricedComponents[eipEntry.pricedIndex];

        const groupNotes = [];
        if (elbPriced.monthly_amount === 0) {
          groupNotes.push("ELB v3 instance price is 0.00 (unexpected; elbv3.professional is a paid spec; may indicate regional pricing data gap).");
        }
        groupNotes.push("Public exposure cost is represented by the EIP bandwidth component.");
        groupNotes.push("This group is informational and does not change monthly_total.");

        serviceCostBreakdown.push({
          group_type: "public_shared_elb",
          description: "Public Shared ELB grouped cost",
          pricing_source: "BSS/OCE",
          components: [
            {
              component_index: elbEntry.component_index,
              template_id: "elb-shared-instance-payg",
              role: "elbv3_instance",
              monthly_amount: elbPriced.monthly_amount
            },
            {
              component_index: eipEntry.component_index,
              template_id: "eip-bandwidth-mbps-payg",
              role: "public_bandwidth",
              monthly_amount: eipPriced.monthly_amount
            }
          ],
          monthly_group_total: elbPriced.monthly_amount + eipPriced.monthly_amount,
          notes: groupNotes
        });
      } else if (
        (elbPublicEntries.length >= 1 || eipBandwidthEntries.length >= 1) &&
        (elbPublicEntries.length > 1 || eipBandwidthEntries.length > 1)
      ) {
        warnings.push("Multiple ELB/EIP components found; public ELB cost grouping was not inferred automatically.");
      }
    }

    const summaryLines = [
      "Huawei Cloud architecture on-demand pricing estimate",
      `Region: ${region}`,
      `Currency: ${currency || "UNKNOWN"}`,
      `Monthly total calculated: ${monthlyTotal} ${currency || ""}`,
      `Annual simple total calculated: ${annualSimpleTotal} ${currency || ""}`,
      `Priced components: ${pricedComponents.length}`,
      `Pending components: ${pendingComponents.length}`,
      `Failed components: ${failedComponents.length}`
    ];

    if (validateAvailability) {
      summaryLines.push(`Availability blocked components: ${availabilityBlockedComponents.length}`);
    }

    if (unavailableReferencePricedComponents.length > 0) {
      summaryLines.push(`Reference-priced blocked components: ${unavailableReferencePricedComponents.length}`);
      summaryLines.push(`Monthly total estimated with blocked: ${monthlyTotalEstimatedWithBlocked} ${currency || ""}`);
    }

    summaryLines.push("Safety: read-only pricing query; no resources were created, modified, purchased, or deleted.");
    summaryLines.push("Note: annual total is monthly on-demand total multiplied by 12, not a yearly/monthly subscription quote.");

    if (validateAvailability && availabilityBlockedComponents.length > 0 && !includeUnavailableReferencePricing) {
      summaryLines.push("Run with validate_availability=false to see pricing for blocked components.");
    }

    if (validateAvailability && availabilityBlockedComponents.length > 0 && includeUnavailableReferencePricing) {
      summaryLines.push("Use include_unavailable_reference_pricing=true to get reference pricing for blocked components.");
    }

    const architectureSummaryText = summaryLines.join("\n");

    const result = {
      tool: "EstimateArchitectureOnDemandPrice",
      status: "OK",
      read_only: true,
      creates_resources: false,
      modifies_resources: false,
      deletes_resources: false,
      purchases_resources: false,
      architecture_summary_text: architectureSummaryText,
      normalization: normalized.normalization,
      pricing_mode: pricingMode,
      pricing_summary: {
        region,
        currency,
        monthly_total_calculated: monthlyTotal,
        annual_simple_total_calculated: annualSimpleTotal,
        monthly_total_validated: monthlyTotalValidated,
        annual_simple_total_validated: annualSimpleTotalValidated,
        priced_components_count: pricedComponents.length,
        pending_components_count: pendingComponents.length,
        failed_components_count: failedComponents.length
      },
      priced_components: pricedComponents,
      pending_components: pendingComponents,
      failed_components: failedComponents
    };

    if (pricingMode === "validated_with_reference") {
      result.pricing_summary.monthly_total_estimated_with_blocked = monthlyTotalEstimatedWithBlocked;
      result.pricing_summary.annual_simple_total_estimated_with_blocked = annualSimpleTotalEstimatedWithBlocked;
      result.unavailable_reference_priced_components = unavailableReferencePricedComponents;
    }

    if (warnings.length > 0) {
      result.warnings = warnings;
    }

    if (validateAvailability) {
      result.availability_validation = {
        enabled: true,
        overall_status: overallAvailStatus,
        components: availabilityValidationComponents
      };
      result.availability_blocked_components = availabilityBlockedComponents;
      result.pricing_summary.availability_blocked_components_count = availabilityBlockedComponents.length;
    }

    if (serviceCostBreakdown.length > 0) {
      result.service_cost_breakdown = serviceCostBreakdown;
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  }

  if (name === "EstimateTemplateOnDemandPrice") {
    const rendered = renderProductInfosFromTemplate(args);

    if (rendered.status !== "OK") {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "EstimateTemplateOnDemandPrice",
              status: "CANNOT_PRICE",
              reason: "Template could not render product_infos.",
              rendered
            }, null, 2)
          }
        ]
      };
    }

    if (rendered.billing_mode && rendered.billing_mode === "period") {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "EstimateTemplateOnDemandPrice",
              status: "ROUTING_ERROR",
              reason: "Template billing_mode is period. Use EstimateTemplatePeriodPrice for period templates.",
              template_id: rendered.template_id,
              billing_mode: rendered.billing_mode
            }, null, 2)
          }
        ]
      };
    }

    const pricingResult = await callHuaweiPricingApi({
      apiPath: "/v2/bills/ratings/on-demand-resources",
      args: {
        ...args,
        product_infos: rendered.product_infos,
        inquiry_precision: args.inquiry_precision ?? 1
      }
    });

    const helperData = pricingResult.helper_result || {};
    const data = helperData.data || {};

    const apiAmount = data.amount ?? null;
    const officialApiAmount = data.official_website_amount ?? null;
    const discountApiAmount = data.discount_amount ?? null;
    const currency = data.currency || null;

    const monthlyHours = Number(rendered.resolved_parameters?.monthly_hours ?? args.parameters?.monthly_hours ?? 0);

    const hasDurationUsage = rendered.product_infos.some((productInfo) =>
      productInfo.usage_factor === "Duration" || Number(productInfo.usage_measure_id) === 4
    );

    const shouldConvertHourlyToMonthly =
      apiAmount !== null &&
      monthlyHours > 0 &&
      !hasDurationUsage;

    const monthlyAmount = shouldConvertHourlyToMonthly ? apiAmount * monthlyHours : apiAmount;
    const officialMonthlyAmount =
      officialApiAmount !== null && officialApiAmount !== undefined
        ? (shouldConvertHourlyToMonthly ? officialApiAmount * monthlyHours : officialApiAmount)
        : null;

    const discountAmount =
      discountApiAmount !== null && discountApiAmount !== undefined
        ? (shouldConvertHourlyToMonthly ? discountApiAmount * monthlyHours : discountApiAmount)
        : null;

    const pricingBasis = {
      api_amount: apiAmount,
      official_api_amount: officialApiAmount,
      discount_api_amount: discountApiAmount,
      api_amount_interpretation: shouldConvertHourlyToMonthly
        ? "API amount interpreted as hourly amount and multiplied by monthly_hours because product_infos do not use Duration/hour."
        : "API amount interpreted as already covering the requested usage_value in product_infos.",
      monthly_hours: monthlyHours || null,
      has_duration_usage: hasDurationUsage,
      applied_monthly_hours_conversion: shouldConvertHourlyToMonthly
    };

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "EstimateTemplateOnDemandPrice",
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            template: {
              service: rendered.service,
              template_id: rendered.template_id,
              display_name: rendered.display_name,
              billing_mode: rendered.billing_mode,
              unit: rendered.unit,
              region: rendered.region,
              resolved_parameters: rendered.resolved_parameters
            },
            pricing_summary: {
              api_amount: apiAmount,
              monthly_amount: monthlyAmount,
              annual_simple_amount: monthlyAmount !== null ? monthlyAmount * 12 : null,
              official_monthly_amount: officialMonthlyAmount,
              discount_amount: discountAmount,
              currency,
              pricing_basis: pricingBasis
            },
            product_infos: rendered.product_infos,
            raw_pricing_response: data
          }, null, 2)
        }
      ]
    };
  }

  if (name === "EstimateTemplatePeriodPrice") {
    const rendered = renderProductInfosFromTemplate(args);

    if (rendered.status !== "OK") {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "EstimateTemplatePeriodPrice",
              status: "CANNOT_PRICE",
              reason: "Template could not render product_infos.",
              rendered
            }, null, 2)
          }
        ]
      };
    }

    if (rendered.billing_mode && rendered.billing_mode === "on_demand") {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "EstimateTemplatePeriodPrice",
              status: "ROUTING_ERROR",
              reason: "Template billing_mode is on_demand. Use EstimateTemplateOnDemandPrice for on-demand templates.",
              template_id: rendered.template_id,
              billing_mode: rendered.billing_mode
            }, null, 2)
          }
        ]
      };
    }

    const pricingResult = await callHuaweiPricingApi({
      apiPath: "/v2/bills/ratings/period-resources/subscribe-rate",
      args: {
        ...args,
        product_infos: rendered.product_infos
      }
    });

    const helperData = pricingResult.helper_result || {};
    const data = helperData.data || {};

    const periodExtracted = extractPeriodAmounts(data);
    const periodAmount = periodExtracted.amount;
    const officialPeriodAmount = periodExtracted.official_website_amount;
    const discountPeriodAmount = periodExtracted.discount_amount;
    const currency = periodExtracted.currency;

    const periodType = Number(rendered.resolved_parameters?.period_type ?? 2);
    const periodNum = Number(rendered.resolved_parameters?.period_num ?? 1);

    let monthlyAmount = null;
    if (periodAmount !== null) {
      if (periodType === 2) {
        monthlyAmount = periodAmount / periodNum;
      } else if (periodType === 3) {
        monthlyAmount = periodAmount / (periodNum * 12);
      } else {
        monthlyAmount = periodAmount;
      }
    }

    let officialMonthlyAmount = null;
    if (officialPeriodAmount !== null && officialPeriodAmount !== undefined) {
      if (periodType === 2) {
        officialMonthlyAmount = officialPeriodAmount / periodNum;
      } else if (periodType === 3) {
        officialMonthlyAmount = officialPeriodAmount / (periodNum * 12);
      } else {
        officialMonthlyAmount = officialPeriodAmount;
      }
    }

    let discountMonthlyAmount = null;
    if (discountPeriodAmount !== null && discountPeriodAmount !== undefined) {
      if (periodType === 2) {
        discountMonthlyAmount = discountPeriodAmount / periodNum;
      } else if (periodType === 3) {
        discountMonthlyAmount = discountPeriodAmount / (periodNum * 12);
      } else {
        discountMonthlyAmount = discountPeriodAmount;
      }
    }

    const periodTypeName = periodType === 2 ? "month" : periodType === 3 ? "year" : "unknown";

    const pricingBasis = {
      api_amount: periodAmount,
      official_api_amount: officialPeriodAmount,
      discount_api_amount: discountPeriodAmount,
      api_amount_interpretation: `API amount is the period subscription cost for period_num=${periodNum} ${periodTypeName}(s).`,
      billing_mode: "period",
      period_type: periodType,
      period_num: periodNum,
      period_type_name: periodTypeName,
      monthly_conversion: periodType === 2
        ? `monthly_amount = period_amount / period_num (${periodAmount} / ${periodNum} = ${monthlyAmount})`
        : periodType === 3
          ? `monthly_amount = period_amount / (period_num * 12) (${periodAmount} / (${periodNum} * 12) = ${monthlyAmount})`
          : "no conversion applied"
    };

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "EstimateTemplatePeriodPrice",
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            template: {
              service: rendered.service,
              template_id: rendered.template_id,
              display_name: rendered.display_name,
              billing_mode: rendered.billing_mode,
              unit: rendered.unit,
              region: rendered.region,
              resolved_parameters: rendered.resolved_parameters
            },
            pricing_summary: {
              period_amount: periodAmount,
              monthly_amount: monthlyAmount,
              annual_simple_amount: monthlyAmount !== null ? monthlyAmount * 12 : null,
              official_monthly_amount: officialMonthlyAmount,
              discount_monthly_amount: discountMonthlyAmount,
              currency,
              pricing_basis: pricingBasis
            },
            product_infos: rendered.product_infos,
            raw_pricing_response: data
          }, null, 2)
        }
      ]
    };
  }

  if (name === "EstimateArchitecturePeriodPrice") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const components = args.components || [];

    if (components.length === 0) {
      throw new Error("components must be a non-empty array");
    }

    const pricedComponents = [];
    const pendingComponents = [];
    const failedComponents = [];

    let monthlyTotalOnDemand = 0;
    let monthlyTotalPeriod = 0;
    let currency = null;

    for (const component of components) {
      const componentArgs = {
        ...component,
        region,
        project_id: args.project_id,
        inquiry_precision: args.inquiry_precision ?? 1
      };

      const rendered = renderProductInfosFromTemplate(componentArgs);

      if (rendered.status !== "OK") {
        pendingComponents.push({
          service: component.service,
          template_id: component.template_id,
          quantity: component.quantity || 1,
          parameters: component.parameters || {},
          render_status: rendered.status,
          reason: rendered.message || "Template is not ready for real pricing",
          rendered
        });
        continue;
      }

      const billingMode = rendered.billing_mode || "on_demand";
      let apiPath;
      if (billingMode === "period") {
        apiPath = "/v2/bills/ratings/period-resources/subscribe-rate";
      } else {
        apiPath = "/v2/bills/ratings/on-demand-resources";
      }

      try {
        const pricingResult = await callHuaweiPricingApi({
          apiPath,
          args: {
            ...componentArgs,
            product_infos: rendered.product_infos,
            inquiry_precision: args.inquiry_precision ?? 1
          }
        });

        const helperData = pricingResult.helper_result || {};
        const data = helperData.data || {};

        let apiAmount;
        let componentCurrency;

        if (billingMode === "period") {
          const periodExtracted = extractPeriodAmounts(data);
          apiAmount = periodExtracted.amount ?? 0;
          componentCurrency = periodExtracted.currency || currency;
        } else {
          apiAmount = data.amount ?? 0;
          componentCurrency = data.currency || currency;
        }

        if (!currency && componentCurrency) {
          currency = componentCurrency;
        }

        let monthlyAmount;

        if (billingMode === "period") {
          const periodType = Number(rendered.resolved_parameters?.period_type ?? 2);
          const periodNum = Number(rendered.resolved_parameters?.period_num ?? 1);

          if (periodType === 2) {
            monthlyAmount = apiAmount / periodNum;
          } else if (periodType === 3) {
            monthlyAmount = apiAmount / (periodNum * 12);
          } else {
            monthlyAmount = apiAmount;
          }

          const periodTypeName = periodType === 2 ? "month" : periodType === 3 ? "year" : "unknown";

          const periodExtracted = extractPeriodAmounts(data);
          let officialMonthlyAmount = null;
          if (periodExtracted.official_website_amount !== null) {
            if (periodType === 2) {
              officialMonthlyAmount = periodExtracted.official_website_amount / periodNum;
            } else if (periodType === 3) {
              officialMonthlyAmount = periodExtracted.official_website_amount / (periodNum * 12);
            } else {
              officialMonthlyAmount = periodExtracted.official_website_amount;
            }
          }
          let discountMonthlyAmount = null;
          if (periodExtracted.discount_amount !== null) {
            if (periodType === 2) {
              discountMonthlyAmount = periodExtracted.discount_amount / periodNum;
            } else if (periodType === 3) {
              discountMonthlyAmount = periodExtracted.discount_amount / (periodNum * 12);
            } else {
              discountMonthlyAmount = periodExtracted.discount_amount;
            }
          }

          pricedComponents.push({
            service: rendered.service,
            template_id: rendered.template_id,
            display_name: rendered.display_name,
            region: rendered.region,
            billing_mode: rendered.billing_mode,
            unit: rendered.unit,
            resolved_parameters: rendered.resolved_parameters,
            period_amount: apiAmount,
            monthly_amount: monthlyAmount,
            annual_simple_amount: monthlyAmount * 12,
            official_monthly_amount: officialMonthlyAmount,
            discount_monthly_amount: discountMonthlyAmount,
            currency: componentCurrency,
            pricing_basis: {
              api_amount: apiAmount,
              api_amount_interpretation: `API amount is the period subscription cost for period_num=${periodNum} ${periodTypeName}(s).`,
              billing_mode: "period",
              period_type: periodType,
              period_num: periodNum,
              period_type_name: periodTypeName
            },
            product_infos: rendered.product_infos,
            raw_pricing_response: data
          });

          monthlyTotalPeriod += monthlyAmount;
        } else {
          const monthlyHours = Number(
            rendered.resolved_parameters?.monthly_hours ??
            componentArgs.parameters?.monthly_hours ??
            0
          );

          const hasDurationUsage = rendered.product_infos.some((productInfo) =>
            productInfo.usage_factor === "Duration" ||
            productInfo.usage_factor === "duration" ||
            Number(productInfo.usage_measure_id) === 4
          );

          const shouldConvertHourlyToMonthly =
            apiAmount !== null &&
            monthlyHours > 0 &&
            !hasDurationUsage;

          monthlyAmount = shouldConvertHourlyToMonthly ? apiAmount * monthlyHours : apiAmount;

          pricedComponents.push({
            service: rendered.service,
            template_id: rendered.template_id,
            display_name: rendered.display_name,
            region: rendered.region,
            billing_mode: rendered.billing_mode,
            unit: rendered.unit,
            resolved_parameters: rendered.resolved_parameters,
            api_amount: apiAmount,
            monthly_amount: monthlyAmount,
            annual_simple_amount: monthlyAmount * 12,
            currency: componentCurrency,
            pricing_basis: {
              api_amount: apiAmount,
              api_amount_interpretation: shouldConvertHourlyToMonthly
                ? "API amount interpreted as hourly amount and multiplied by monthly_hours because product_infos do not use Duration/hour."
                : "API amount interpreted as already covering the requested usage_value in product_infos.",
              billing_mode: "on_demand",
              monthly_hours: monthlyHours || null,
              has_duration_usage: hasDurationUsage,
              applied_monthly_hours_conversion: shouldConvertHourlyToMonthly
            },
            product_infos: rendered.product_infos,
            raw_pricing_response: data
          });

          monthlyTotalOnDemand += monthlyAmount;
        }
      } catch (error) {
        failedComponents.push({
          service: component.service,
          template_id: component.template_id,
          quantity: component.quantity || 1,
          parameters: component.parameters || {},
          error: error.message
        });
      }
    }

    const monthlyTotal = monthlyTotalOnDemand + monthlyTotalPeriod;
    const annualSimpleTotal = monthlyTotal * 12;

    const warnings = [];
    const billingModes = [];
    if (monthlyTotalOnDemand > 0) billingModes.push("on_demand");
    if (monthlyTotalPeriod > 0) billingModes.push("period");

    if (billingModes.length > 1) {
      warnings.push("Architecture contains both on-demand and period billing. monthly_total is a normalized estimate: on-demand costs vary with usage, period costs are fixed for the subscription duration.");
    }

    const result = {
      tool: "EstimateArchitecturePeriodPrice",
      status: "OK",
      read_only: true,
      creates_resources: false,
      modifies_resources: false,
      deletes_resources: false,
      purchases_resources: false,
      pricing_summary: {
        region,
        currency,
        monthly_total: monthlyTotal,
        monthly_total_on_demand: monthlyTotalOnDemand,
        monthly_total_period: monthlyTotalPeriod,
        annual_simple_total: annualSimpleTotal,
        billing_modes: billingModes,
        priced_components_count: pricedComponents.length,
        pending_components_count: pendingComponents.length,
        failed_components_count: failedComponents.length
      },
      priced_components: pricedComponents,
      pending_components: pendingComponents,
      failed_components: failedComponents
    };

    if (warnings.length > 0) {
      result.warnings = warnings;
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  }

  if (name === "QueryOnDemandPrice") {
    const result = await callHuaweiPricingApi({
      apiPath: "/v2/bills/ratings/on-demand-resources",
      args
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryOnDemandPrice",
            read_only: true,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "QueryPeriodPrice") {
    const result = await callHuaweiPricingApi({
      apiPath: "/v2/bills/ratings/period-resources/subscribe-rate",
      args
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "QueryPeriodPrice",
            read_only: true,
            result
          }, null, 2)
        }
      ]
    };
  }

  if (name === "EvaluateEcsFlavorAvailability") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const resolvedProject = resolveProjectIdForRegion(region);

    if (resolvedProject.error) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "EvaluateEcsFlavorAvailability",
              status: "discovery_error",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: resolvedProject.error,
              message: resolvedProject.message
            }, null, 2)
          }
        ]
      };
    }

    const availabilityZone = args.availability_zone;
    const requestedVcpus = args.vcpus;
    const requestedRamGb = args.ram_gb;
    const preferredFlavor = args.preferred_flavor || null;
    const allowAlternatives = args.allow_alternatives !== false;
    const maxAlternatives = args.max_alternatives ?? 5;

    if (!availabilityZone) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "EvaluateEcsFlavorAvailability",
              status: "discovery_error",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: "availability_zone is required"
            }, null, 2)
          }
        ]
      };
    }

    if (requestedVcpus == null || requestedRamGb == null) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "EvaluateEcsFlavorAvailability",
              status: "discovery_error",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: "vcpus and ram_gb are required"
            }, null, 2)
          }
        ]
      };
    }

    const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
    const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

    let rawFlavors;
    try {
      const cliArgs = [helper, "ecs-flavors", "--availability-zone", availabilityZone];

      const { stdout, stderr } = await execFileAsync(
        pythonBin,
        cliArgs,
        {
          timeout: args.timeout_ms || 30000,
          maxBuffer: 20 * 1024 * 1024,
          env: { ...process.env, HUAWEI_DEFAULT_REGION: region, HUAWEI_PROJECT_ID: resolvedProject.project_id }
        }
      );

      if (stderr && stderr.trim().length > 0) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                tool: "EvaluateEcsFlavorAvailability",
                status: "discovery_error",
                read_only: true,
                creates_resources: false,
                modifies_resources: false,
                deletes_resources: false,
                purchases_resources: false,
                error: "Python helper wrote to stderr",
                stderr
              }, null, 2)
            }
          ]
        };
      }

      const parsed = JSON.parse(stdout);
      rawFlavors = parsed.data?.flavors;

      if (!Array.isArray(rawFlavors)) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                tool: "EvaluateEcsFlavorAvailability",
                status: "discovery_error",
                read_only: true,
                creates_resources: false,
                modifies_resources: false,
                deletes_resources: false,
                purchases_resources: false,
                error: "Unexpected response structure from ECS flavors API",
                raw_keys: Object.keys(parsed.data || {})
              }, null, 2)
            }
          ]
        };
      }
    } catch (error) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "EvaluateEcsFlavorAvailability",
              status: "discovery_error",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              error: "Failed to query ECS flavors",
              message: error.message
            }, null, 2)
          }
        ]
      };
    }

    function parseAzStatus(azSpec, targetAz) {
      if (!azSpec || !targetAz) return "not_available";
      const parts = azSpec.split(",");
      for (const part of parts) {
        const trimmed = part.trim();
        const match = trimmed.match(/^([^(]+)\(([^)]+)\)$/);
        if (match && match[1] === targetAz) {
          return match[2];
        }
      }
      return "not_available";
    }

    const evaluated = rawFlavors.map((flavor) => {
      const specs = flavor.os_extra_specs || {};
      const vcpus = parseInt(flavor.vcpus, 10);
      const ramMb = flavor.ram;
      const ramGb = ramMb / 1024;
      const operationStatus = specs["cond:operation:status"] || "unknown";
      const azStatus = parseAzStatus(specs["cond:operation:az"] || "", availabilityZone);
      const recommendable = azStatus === "normal" && operationStatus === "normal";

      return {
        flavor_id: flavor.id,
        vcpus,
        ram_mb: ramMb,
        ram_gb: ramGb,
        generation: specs["ecs:generation"] || "",
        performancetype: specs["ecs:performancetype"] || "",
        operation_status: operationStatus,
        az_status: azStatus,
        recommendable
      };
    });

    const preferredFlavorStatus = { value: "not_requested", reason: null, detail: null };
    if (preferredFlavor) {
      const found = evaluated.find((f) => f.flavor_id === preferredFlavor);
      if (!found) {
        preferredFlavorStatus.value = "invalid_selection";
        preferredFlavorStatus.reason = "Flavor not found in the region/AZ.";
      } else {
        preferredFlavorStatus.detail = {
          flavor_id: found.flavor_id,
          vcpus: found.vcpus,
          ram_gb: found.ram_gb,
          operation_status: found.operation_status,
          az_status: found.az_status,
          recommendable: found.recommendable
        };
        if (found.operation_status === "abandon") {
          preferredFlavorStatus.value = "invalid_selection";
          preferredFlavorStatus.reason = "Flavor is marked as abandon and should not be recommended for new architectures.";
        } else if (found.az_status === "sellout") {
          preferredFlavorStatus.value = "invalid_selection";
          preferredFlavorStatus.reason = "Flavor is sold out in the requested AZ.";
        } else if (found.az_status === "abandon") {
          preferredFlavorStatus.value = "invalid_selection";
          preferredFlavorStatus.reason = "Flavor is abandoned in the requested AZ.";
        } else if (found.az_status === "not_available") {
          preferredFlavorStatus.value = "invalid_selection";
          preferredFlavorStatus.reason = "Flavor is not available in the requested AZ.";
        } else if (found.recommendable) {
          preferredFlavorStatus.value = "valid";
          preferredFlavorStatus.reason = null;
        } else {
          preferredFlavorStatus.value = "invalid_selection";
          preferredFlavorStatus.reason = `Flavor is not recommendable (operation_status=${found.operation_status}, az_status=${found.az_status}).`;
        }
      }
    }

    const maxVcpuMultiplier = args.max_vcpu_multiplier ?? 4;
    const maxRamMultiplier = args.max_ram_multiplier ?? 4;
    const includeOversizedCandidates = args.include_oversized_candidates === true;

    const exactMatches = evaluated.filter(
      (f) => f.recommendable && f.vcpus === requestedVcpus && f.ram_gb === requestedRamGb
    );

    let alternatives = [];
    let oversizedCandidates = [];
    if (allowAlternatives && exactMatches.length === 0) {
      const maxVcpus = requestedVcpus * maxVcpuMultiplier;
      const maxRamGb = requestedRamGb * maxRamMultiplier;

      const withinBounds = evaluated.filter(
        (f) =>
          f.recommendable &&
          f.vcpus >= requestedVcpus && f.ram_gb >= requestedRamGb &&
          f.vcpus <= maxVcpus && f.ram_gb <= maxRamGb
      );

      alternatives = withinBounds
        .map((f) => ({
          ...f,
          delta_vcpus: f.vcpus - requestedVcpus,
          delta_ram_gb: Math.round((f.ram_gb - requestedRamGb) * 1000) / 1000,
          resource_jump_score: (f.vcpus - requestedVcpus) + (f.ram_gb - requestedRamGb)
        }))
        .sort((a, b) => {
          if (a.resource_jump_score !== b.resource_jump_score) {
            return a.resource_jump_score - b.resource_jump_score;
          }
          if (a.delta_vcpus !== b.delta_vcpus) {
            return a.delta_vcpus - b.delta_vcpus;
          }
          return a.flavor_id.localeCompare(b.flavor_id);
        })
        .slice(0, maxAlternatives);

      if (includeOversizedCandidates) {
        const oversized = evaluated.filter(
          (f) =>
            f.recommendable &&
            f.vcpus >= requestedVcpus && f.ram_gb >= requestedRamGb &&
            (f.vcpus > maxVcpus || f.ram_gb > maxRamGb)
        );

        oversizedCandidates = oversized
          .map((f) => ({
            ...f,
            delta_vcpus: f.vcpus - requestedVcpus,
            delta_ram_gb: Math.round((f.ram_gb - requestedRamGb) * 1000) / 1000,
            resource_jump_score: (f.vcpus - requestedVcpus) + (f.ram_gb - requestedRamGb)
          }))
          .sort((a, b) => {
            if (a.resource_jump_score !== b.resource_jump_score) {
              return a.resource_jump_score - b.resource_jump_score;
            }
            if (a.delta_vcpus !== b.delta_vcpus) {
              return a.delta_vcpus - b.delta_vcpus;
            }
            return a.flavor_id.localeCompare(b.flavor_id);
          });
      }
    }

    const excludedSummary = {
      operation_abandon: evaluated.filter((f) => f.operation_status === "abandon").length,
      az_sellout: evaluated.filter((f) => f.operation_status !== "abandon" && f.az_status === "sellout").length,
      az_abandon: evaluated.filter((f) => f.operation_status !== "abandon" && f.az_status === "abandon").length,
      az_not_available: evaluated.filter((f) => f.operation_status !== "abandon" && f.az_status === "not_available").length,
      unknown_status: evaluated.filter((f) => f.operation_status === "unknown" || (f.operation_status !== "abandon" && f.operation_status !== "normal" && f.operation_status !== "unknown")).length
    };

    const totalRecommendable = evaluated.filter((f) => f.recommendable).length;

    let globalStatus;
    if (exactMatches.length > 0) {
      globalStatus = "available";
    } else if (preferredFlavorStatus.value === "invalid_selection") {
      globalStatus = "invalid_selection";
    } else if (alternatives.length > 0) {
      globalStatus = "alternatives_available";
    } else if (totalRecommendable === 0) {
      globalStatus = "unavailable";
    } else {
      globalStatus = "no_exact_match";
    }

    const summaryLines = [
      `ECS Flavor Availability Evaluation for ${region}/${availabilityZone}`,
      `Requested: ${requestedVcpus} vCPU, ${requestedRamGb} GB RAM`,
      `Status: ${globalStatus}`,
      `Exact matches: ${exactMatches.length}`,
      `Alternatives: ${alternatives.length}`,
      `Oversized candidates: ${oversizedCandidates.length}`,
      `Multiplier limits: vCPU <= ${requestedVcpus * maxVcpuMultiplier}, RAM <= ${requestedRamGb * maxRamMultiplier} GB`,
      `Total flavors evaluated: ${evaluated.length}`,
      `Recommendable flavors in AZ: ${totalRecommendable}`,
      `Excluded: ${excludedSummary.operation_abandon} abandon, ${excludedSummary.az_sellout} sellout, ${excludedSummary.az_abandon} AZ-abandon, ${excludedSummary.az_not_available} AZ-not-available, ${excludedSummary.unknown_status} unknown`
    ];

    if (preferredFlavor) {
      summaryLines.push(`Preferred flavor '${preferredFlavor}': ${preferredFlavorStatus.value}${preferredFlavorStatus.reason ? " - " + preferredFlavorStatus.reason : ""}`);
    }

    if (globalStatus === "unavailable") {
      summaryLines.push("No recommendable flavors found. Consider querying another region or verifying with Huawei Cloud support for available generations.");
    }

    if (globalStatus === "available" || globalStatus === "alternatives_available" || globalStatus === "no_exact_match") {
      summaryLines.push("Use EstimateTemplateOnDemandPrice to compare costs of recommended flavors.");
    }

    if (excludedSummary.az_sellout > 0) {
      summaryLines.push(`Note: ${excludedSummary.az_sellout} flavors are sold out (transitory status, may become available later).`);
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "EvaluateEcsFlavorAvailability",
            status: globalStatus,
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            request: {
              region,
              availability_zone: availabilityZone,
              vcpus: requestedVcpus,
              ram_gb: requestedRamGb,
              preferred_flavor: preferredFlavor,
              max_vcpu_multiplier: maxVcpuMultiplier,
              max_ram_multiplier: maxRamMultiplier,
              include_oversized_candidates: includeOversizedCandidates
            },
            preferred_flavor_status: preferredFlavorStatus.value,
            preferred_flavor_reason: preferredFlavorStatus.reason,
            preferred_flavor_detail: preferredFlavorStatus.detail,
            exact_matches: exactMatches,
            alternatives,
            oversized_candidates: oversizedCandidates,
            excluded_summary: excludedSummary,
            total_flavors_evaluated: evaluated.length,
            total_recommendable_in_az: totalRecommendable,
            summary_text: summaryLines.join("\n")
          }, null, 2)
        }
      ]
    };
  }

  if (name === "FindEcsFlavorCandidates") {
    const region = args.region || process.env.HUAWEI_DEFAULT_REGION || "la-north-2";
    const resolvedProject = resolveProjectIdForRegion(region);
    const targets = args.targets || [];
    const requestedVcpus = args.vcpus;
    const requestedRamGb = args.ram_gb;
    const allowAlternatives = args.allow_alternatives !== false;
    const maxAlternatives = args.max_alternatives ?? 5;
    const maxVcpuMultiplier = args.max_vcpu_multiplier ?? 4;
    const maxRamMultiplier = args.max_ram_multiplier ?? 4;
    const includeOversizedCandidates = args.include_oversized_candidates === true;
    const maxOversizedCandidates = args.max_oversized_candidates ?? 5;

    if (!Array.isArray(targets) || targets.length === 0) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "FindEcsFlavorCandidates",
              status: "ERROR",
              read_only: true,
              error: "targets must be a non-empty array of { availability_zone, preferred_flavor? }"
            }, null, 2)
          }
        ]
      };
    }

    if (requestedVcpus == null || requestedRamGb == null) {
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "FindEcsFlavorCandidates",
              status: "ERROR",
              read_only: true,
              error: "vcpus and ram_gb are required"
            }, null, 2)
          }
        ]
      };
    }

    if (resolvedProject.error) {
      const azResults = targets.map((t) => ({
        availability_zone: t.availability_zone,
        status: "discovery_error",
        discovery_error: `${resolvedProject.error}: ${resolvedProject.message}`,
        exact_matches: [],
        alternatives: [],
        oversized_candidates: [],
        preferred_flavor_status: "not_requested",
        preferred_flavor_reason: null,
        preferred_flavor_detail: null
      }));

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              tool: "FindEcsFlavorCandidates",
              status: "ERROR",
              read_only: true,
              creates_resources: false,
              modifies_resources: false,
              deletes_resources: false,
              purchases_resources: false,
              request: {
                region,
                targets,
                vcpus: requestedVcpus,
                ram_gb: requestedRamGb
              },
              summary: {
                azs_evaluated: targets.length,
                azs_with_exact_match: 0,
                azs_with_alternatives: 0,
                azs_with_only_oversized: 0,
                azs_unavailable: 0,
                azs_with_discovery_error: targets.length,
                total_exact_matches: 0,
                total_alternatives: 0,
                total_oversized_candidates: 0
              },
              results: azResults
            }, null, 2)
          }
        ]
      };
    }

    const pythonBin = "/root/opencode-pricing-assistant/pricing-mcp/.venv/bin/python";
    const helper = "/root/opencode-pricing-assistant/pricing-mcp/pricing_catalog_helper.py";

    function parseAzStatus(azSpec, targetAz) {
      if (!azSpec || !targetAz) return "not_available";
      const parts = azSpec.split(",");
      for (const part of parts) {
        const trimmed = part.trim();
        const match = trimmed.match(/^([^(]+)\(([^)]+)\)$/);
        if (match && match[1] === targetAz) {
          return match[2];
        }
      }
      return "not_available";
    }

    function evaluateFlavors(rawFlavors, az) {
      return rawFlavors.map((flavor) => {
        const specs = flavor.os_extra_specs || {};
        const vcpus = parseInt(flavor.vcpus, 10);
        const ramMb = flavor.ram;
        const ramGb = ramMb / 1024;
        const operationStatus = specs["cond:operation:status"] || "unknown";
        const azStatus = parseAzStatus(specs["cond:operation:az"] || "", az);
        const recommendable = azStatus === "normal" && operationStatus === "normal";

        return {
          flavor_id: flavor.id,
          vcpus,
          ram_mb: ramMb,
          ram_gb: ramGb,
          generation: specs["ecs:generation"] || "",
          performancetype: specs["ecs:performancetype"] || "",
          operation_status: operationStatus,
          az_status: azStatus,
          recommendable
        };
      });
    }

    function classifyFlavors(evaluated, requestedVcpus, requestedRamGb, maxVcpuMultiplier, maxRamMultiplier) {
      const maxVcpus = requestedVcpus * maxVcpuMultiplier;
      const maxRamGb = requestedRamGb * maxRamMultiplier;

      const exactMatches = evaluated.filter(
        (f) => f.recommendable && f.vcpus === requestedVcpus && f.ram_gb === requestedRamGb
      );

      let alternatives = [];
      let oversizedCandidates = [];

      if (allowAlternatives && exactMatches.length === 0) {
        const withinBounds = evaluated.filter(
          (f) =>
            f.recommendable &&
            f.vcpus >= requestedVcpus && f.ram_gb >= requestedRamGb &&
            f.vcpus <= maxVcpus && f.ram_gb <= maxRamGb
        );

        alternatives = withinBounds
          .map((f) => ({
            ...f,
            delta_vcpus: f.vcpus - requestedVcpus,
            delta_ram_gb: Math.round((f.ram_gb - requestedRamGb) * 1000) / 1000,
            resource_jump_score: (f.vcpus - requestedVcpus) + (f.ram_gb - requestedRamGb)
          }))
          .sort((a, b) => {
            if (a.resource_jump_score !== b.resource_jump_score) return a.resource_jump_score - b.resource_jump_score;
            if (a.delta_vcpus !== b.delta_vcpus) return a.delta_vcpus - b.delta_vcpus;
            return a.flavor_id.localeCompare(b.flavor_id);
          })
          .slice(0, maxAlternatives);

        if (includeOversizedCandidates) {
          const oversized = evaluated.filter(
            (f) =>
              f.recommendable &&
              f.vcpus >= requestedVcpus && f.ram_gb >= requestedRamGb &&
              (f.vcpus > maxVcpus || f.ram_gb > maxRamGb)
          );

          oversizedCandidates = oversized
            .map((f) => ({
              ...f,
              delta_vcpus: f.vcpus - requestedVcpus,
              delta_ram_gb: Math.round((f.ram_gb - requestedRamGb) * 1000) / 1000,
              resource_jump_score: (f.vcpus - requestedVcpus) + (f.ram_gb - requestedRamGb)
            }))
            .sort((a, b) => {
              if (a.resource_jump_score !== b.resource_jump_score) return a.resource_jump_score - b.resource_jump_score;
              if (a.delta_vcpus !== b.delta_vcpus) return a.delta_vcpus - b.delta_vcpus;
              return a.flavor_id.localeCompare(b.flavor_id);
            })
            .slice(0, maxOversizedCandidates);
        }
      }

      return { exactMatches, alternatives, oversizedCandidates };
    }

    function evaluatePreferredFlavor(evaluated, preferredFlavor) {
      const result = { value: "not_requested", reason: null, detail: null };
      if (!preferredFlavor) return result;

      const found = evaluated.find((f) => f.flavor_id === preferredFlavor);
      if (!found) {
        result.value = "invalid_selection";
        result.reason = "Flavor not found in the region/AZ.";
      } else {
        result.detail = {
          flavor_id: found.flavor_id,
          vcpus: found.vcpus,
          ram_gb: found.ram_gb,
          operation_status: found.operation_status,
          az_status: found.az_status,
          recommendable: found.recommendable
        };
        if (found.operation_status === "abandon") {
          result.value = "invalid_selection";
          result.reason = "Flavor is marked as abandon and should not be recommended for new architectures.";
        } else if (found.az_status === "sellout") {
          result.value = "invalid_selection";
          result.reason = "Flavor is sold out in the requested AZ.";
        } else if (found.az_status === "abandon") {
          result.value = "invalid_selection";
          result.reason = "Flavor is abandoned in the requested AZ.";
        } else if (found.az_status === "not_available") {
          result.value = "invalid_selection";
          result.reason = "Flavor is not available in the requested AZ.";
        } else if (found.recommendable) {
          result.value = "valid";
          result.reason = null;
        } else {
          result.value = "invalid_selection";
          result.reason = `Flavor is not recommendable (operation_status=${found.operation_status}, az_status=${found.az_status}).`;
        }
      }
      return result;
    }

    const azResults = [];
    for (const target of targets) {
      const az = target.availability_zone;
      const preferredFlavor = target.preferred_flavor || null;

      let rawFlavors;
      try {
        const cliArgs = [helper, "ecs-flavors", "--availability-zone", az];
        const { stdout, stderr } = await execFileAsync(
          pythonBin,
          cliArgs,
          {
            timeout: args.timeout_ms || 30000,
            maxBuffer: 20 * 1024 * 1024,
            env: { ...process.env, HUAWEI_DEFAULT_REGION: region, HUAWEI_PROJECT_ID: resolvedProject.project_id }
          }
        );

        if (stderr && stderr.trim().length > 0) {
          azResults.push({
            availability_zone: az,
            status: "discovery_error",
            error: "Python helper wrote to stderr",
            stderr,
            exact_matches: [],
            alternatives: [],
            oversized_candidates: [],
            preferred_flavor_status: "not_requested",
            preferred_flavor_reason: null,
            preferred_flavor_detail: null
          });
          continue;
        }

        const parsed = JSON.parse(stdout);
        rawFlavors = parsed.data?.flavors;

        if (!Array.isArray(rawFlavors)) {
          azResults.push({
            availability_zone: az,
            status: "discovery_error",
            error: "Unexpected response structure from ECS flavors API",
            exact_matches: [],
            alternatives: [],
            oversized_candidates: [],
            preferred_flavor_status: "not_requested",
            preferred_flavor_reason: null,
            preferred_flavor_detail: null
          });
          continue;
        }
      } catch (error) {
        azResults.push({
          availability_zone: az,
          status: "discovery_error",
          error: "Failed to query ECS flavors",
          message: error.message,
          exact_matches: [],
          alternatives: [],
          oversized_candidates: [],
          preferred_flavor_status: "not_requested",
          preferred_flavor_reason: null,
          preferred_flavor_detail: null
        });
        continue;
      }

      const evaluated = evaluateFlavors(rawFlavors, az);
      const { exactMatches, alternatives, oversizedCandidates } = classifyFlavors(
        evaluated, requestedVcpus, requestedRamGb, maxVcpuMultiplier, maxRamMultiplier
      );
      const preferredFlavorResult = evaluatePreferredFlavor(evaluated, preferredFlavor);

      const totalRecommendable = evaluated.filter((f) => f.recommendable).length;
      let azStatus;
      if (exactMatches.length > 0) {
        azStatus = "available";
      } else if (preferredFlavorResult.value === "invalid_selection") {
        azStatus = "invalid_selection";
      } else if (alternatives.length > 0) {
        azStatus = "alternatives_available";
      } else if (totalRecommendable === 0) {
        azStatus = "unavailable";
      } else {
        azStatus = "no_exact_match";
      }

      azResults.push({
        availability_zone: az,
        status: azStatus,
        exact_matches: exactMatches,
        alternatives,
        oversized_candidates: oversizedCandidates,
        preferred_flavor_status: preferredFlavorResult.value,
        preferred_flavor_reason: preferredFlavorResult.reason,
        preferred_flavor_detail: preferredFlavorResult.detail,
        total_flavors_evaluated: evaluated.length,
        total_recommendable_in_az: totalRecommendable
      });
    }

    const azsWithExactMatch = azResults.filter((r) => r.exact_matches.length > 0).length;
    const azsWithAlternatives = azResults.filter((r) => r.exact_matches.length === 0 && r.alternatives.length > 0).length;
    const azsWithOnlyOversized = azResults.filter((r) => r.exact_matches.length === 0 && r.alternatives.length === 0 && r.oversized_candidates.length > 0).length;
    const azsUnavailable = azResults.filter((r) => r.status === "unavailable" || r.status === "no_exact_match").filter((r) => r.exact_matches.length === 0 && r.alternatives.length === 0 && r.oversized_candidates.length === 0).length;
    const azsWithDiscoveryError = azResults.filter((r) => r.status === "discovery_error").length;

    const totalExactMatches = azResults.reduce((sum, r) => sum + r.exact_matches.length, 0);
    const totalAlternatives = azResults.reduce((sum, r) => sum + r.alternatives.length, 0);
    const totalOversizedCandidates = azResults.reduce((sum, r) => sum + r.oversized_candidates.length, 0);

    let globalStatus;
    if (azsWithDiscoveryError === azResults.length) {
      globalStatus = "ERROR";
    } else if (azsWithDiscoveryError > 0 || azsUnavailable > 0) {
      globalStatus = "PARTIAL";
    } else if (azsWithExactMatch === azResults.length) {
      globalStatus = "OK";
    } else {
      globalStatus = "PARTIAL";
    }

    const summary = {
      azs_evaluated: azResults.length,
      azs_with_exact_match: azsWithExactMatch,
      azs_with_alternatives: azsWithAlternatives,
      azs_with_only_oversized: azsWithOnlyOversized,
      azs_unavailable: azsUnavailable,
      azs_with_discovery_error: azsWithDiscoveryError,
      total_exact_matches: totalExactMatches,
      total_alternatives: totalAlternatives,
      total_oversized_candidates: totalOversizedCandidates
    };

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            tool: "FindEcsFlavorCandidates",
            status: globalStatus,
            read_only: true,
            creates_resources: false,
            modifies_resources: false,
            deletes_resources: false,
            purchases_resources: false,
            request: {
              region,
              targets,
              vcpus: requestedVcpus,
              ram_gb: requestedRamGb,
              max_vcpu_multiplier: maxVcpuMultiplier,
              max_ram_multiplier: maxRamMultiplier,
              include_oversized_candidates: includeOversizedCandidates,
              max_oversized_candidates: maxOversizedCandidates
            },
            summary,
            results: azResults
          }, null, 2)
        }
      ]
    };
  }

  throw new Error(`Unknown tool: ${name}`);
});

const transport = new StdioServerTransport();
await server.connect(transport);
