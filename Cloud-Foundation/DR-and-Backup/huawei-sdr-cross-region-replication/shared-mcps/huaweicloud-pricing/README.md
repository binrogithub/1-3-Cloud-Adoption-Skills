# huaweicloud-pricing

## Purpose

Local MCP server for Huawei Cloud pricing estimation and catalog queries. Enables architects to estimate costs for Huawei Cloud architectures using on-demand and period (subscription) pricing APIs, evaluate ECS flavor availability, and explore the product catalog — all without creating or modifying any cloud resources.

## Scope

**Includes:**
- Product catalog queries (service types, resource types, usage types, measurement units)
- Service-specific flavor/spec queries (ECS, EVS, RDS, ELB)
- Raw on-demand and period pricing API queries
- Template-based architecture cost estimation (on-demand and period)
- ECS flavor availability evaluation across availability zones
- Local pricing template management and rendering
- Health check and product info guide

**Does not include:**
- Any resource creation, modification, or deletion
- Any purchasing or subscription operations
- Account or billing management
- Cost analysis of existing deployed resources

## Use cases

1. **Architecture cost estimation** — Estimate monthly costs for a proposed architecture before deployment [VERIFIED_FROM_CODE]
2. **ECS flavor selection** — Find available ECS flavors matching vCPU/RAM requirements and evaluate alternatives [VERIFIED_FROM_CODE]
3. **On-demand vs period comparison** — Compare pay-per-use vs yearly/monthly subscription pricing [VERIFIED_FROM_CODE]
4. **Product catalog exploration** — Discover available services, resource types, and usage types [VERIFIED_FROM_CODE]
5. **RDS/ELB/EVS spec discovery** — Query available database flavors, load balancer specs, and volume types [VERIFIED_FROM_CODE]
6. **Multi-AZ flavor evaluation** — Find ECS flavor candidates across multiple availability zones simultaneously [VERIFIED_FROM_CODE]

## Architecture

- **Runtime:** Node.js (ESM)
- **Entry point:** `src/server.mjs`
- **Transport:** stdio (MCP SDK)
- **Core modules:**
  - `src/server.mjs` — Main MCP server with 25 tool handlers
  - `src/template-tools.mjs` — Pricing template rendering and architecture estimation
  - `src/huawei-signer.mjs` — Huawei Cloud API request signing (AK/SK v4)
  - `src/pricing_api_helper.py` — Python helper for pricing API calls
  - `src/pricing_catalog_helper.py` — Python helper for catalog exploration
  - `config/pricing-templates.example.json` — Parametric pricing templates for 20+ services
- **Dependencies:** `@modelcontextprotocol/sdk`, `axios`
- **APIs used:** BSS/OCE (pricing), ECS (flavors), EVS (volume types), RDS (flavors, storage), ELB (flavors, AZs)

## MCP tools exposed

| # | Tool name | Purpose | Read/Write | Risk | Approval required |
|---|-----------|---------|------------|------|-------------------|
| 1 | QueryCloudServiceTypes | Query product catalog cloud service types | read-only | none | no |
| 2 | QueryResourceTypes | Query product catalog resource types | read-only | none | no |
| 3 | QueryServiceResources | Query resource types for a service type | read-only | none | no |
| 4 | QueryUsageTypes | Query product catalog usage types | read-only | none | no |
| 5 | QueryMeasurementUnits | Query catalog measurement units | read-only | none | no |
| 6 | QueryElbFlavors | Query ELB dedicated load balancer flavors | read-only | none | no |
| 7 | QueryElbAvailabilityZones | Query ELB availability zones | read-only | none | no |
| 8 | QueryRdsFlavors | Query RDS MySQL flavors | read-only | none | no |
| 9 | QueryRdsStorageTypes | Query RDS MySQL storage types | read-only | none | no |
| 10 | QueryEcsFlavors | Query ECS flavors in a region | read-only | none | no |
| 11 | QueryEvsVolumeTypes | Query EVS volume types | read-only | none | no |
| 12 | PricingHealthCheck | Validate pricing MCP configuration | read-only | none | no |
| 13 | ListPricingTemplates | List local pricing templates | read-only | none | no |
| 14 | ExplainRequiredTemplate | Explain template requirements | read-only | none | no |
| 15 | EstimateArchitectureCostDraft | Draft architecture cost mapping (no API calls) | read-only | none | no |
| 16 | EstimateArchitectureOnDemandPrice | Estimate on-demand pricing for architecture | read-only | none | no |
| 17 | EstimateTemplateOnDemandPrice | Estimate on-demand price from template | read-only | none | no |
| 18 | EstimateTemplatePeriodPrice | Estimate period price from template | read-only | none | no |
| 19 | EstimateArchitecturePeriodPrice | Estimate period pricing for architecture | read-only | none | no |
| 20 | QueryOnDemandPrice | Query raw on-demand prices | read-only | none | no |
| 21 | QueryPeriodPrice | Query raw period prices | read-only | none | no |
| 22 | RenderProductInfosFromTemplate | Render product_infos from template | read-only | none | no |
| 23 | PricingProductInfoGuide | Guide on obtaining product_infos | read-only | none | no |
| 24 | EvaluateEcsFlavorAvailability | Evaluate ECS flavor availability for region/AZ | read-only | none | no |
| 25 | FindEcsFlavorCandidates | Find ECS flavors across multiple AZs | read-only | none | no |

## Prerequisites

- Node.js >= 18
- Huawei Cloud account with BSS pricing API access
- AK/SK with pricing query permissions

## Installation

```bash
cd mcps/huaweicloud-pricing
npm install
```

## Configuration

Set environment variables:

```bash
export HWCLOUD_ACCESS_KEY=<YOUR_ACCESS_KEY>
export HWCLOUD_SECRET_KEY=<YOUR_SECRET_KEY>
export HWCLOUD_PROJECT_ID=<YOUR_PROJECT_ID>
export HWCLOUD_REGION=<YOUR_REGION>
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| HWCLOUD_ACCESS_KEY | yes | Huawei Cloud Access Key |
| HWCLOUD_SECRET_KEY | yes | Huawei Cloud Secret Key |
| HWCLOUD_PROJECT_ID | no | Project ID for pricing queries |
| HWCLOUD_REGION | no | Default region |

## Execution

```bash
node src/server.mjs
```

## Integration with OpenCode

```json
{
  "huaweicloud-pricing": {
    "type": "local",
    "enabled": true,
    "command": ["node", "<INSTALLATION_ROOT>/mcps/huaweicloud-pricing/src/server.mjs"],
    "timeout": 30000
  }
}
```

## Examples

```bash
# List pricing templates
# Tool: ListPricingTemplates

# Estimate ECS on-demand cost
# Tool: EstimateTemplateOnDemandPrice
# Parameters: { service: "ecs", template_id: "ecs-general-purpose-payg", region: "la-north-2", parameters: { monthly_hours: 730, system_disk_gb: 40 } }

# Find ECS flavors
# Tool: FindEcsFlavorCandidates
# Parameters: { region: "la-north-2", targets: [{ availability_zone: "la-north-2a" }], vcpus: 4, ram_gb: 8 }
```

## Tests

```bash
# Unit tests (no credentials required)
npm run test:unit

# Integration tests (requires credentials)
RUN_LIVE_API=true npm run test:integration
```

21 test files covering CBR, CCE, CFW, DCS, DDS, ECS, ELB, EVS, HSS, LTS, NAT, SFS, VPC, VPN, WAF pricing.

## Security

- All 25 tools are **read-only** — no resources are created, modified, or deleted
- AK/SK are used only for API signing; never logged or transmitted in plaintext
- No `terraform apply` or destructive operations
- Pricing queries do not expose account billing details

## Limitations

- Pricing results depend on Huawei Cloud API availability and catalog coverage
- Template-based estimation requires pre-configured pricing templates
- ECS flavor availability can change; results are point-in-time
- Period pricing requires specific product_infos that may not be available for all services

## Troubleshooting

- **"PricingHealthCheck fails"**: Verify AK/SK and region configuration
- **"Empty results from QueryEcsFlavors"**: Region may not support the requested service; try a different region
- **"Template not found"**: Check `config/pricing-templates.example.json` for available template IDs

## Related use cases

- Architecture cost estimation before deployment
- ECS flavor selection and availability evaluation
- Multi-service cost breakdown analysis

## Status

**READY** — All 25 tools implemented and tested. Read-only classification confirmed from code analysis. 21 test files available.
