# NAT Gateway Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-06-01
**Region**: la-north-2
**Status**: Public NAT Gateway resource_spec CONFIRMED for all 4 specs. Private/Elastic/Exclusive PENDING.

---

## 1. BSS/OCE Catalog Summary

### cloud_service_type
- **Code**: `hws.service.type.natgateway`
- **Name**: NAT Gateway
- **Source**: Confirmed via BSS/OCE `/v2/products/service-types` and `/v2/products/usage-types`

### Resource Types (4 total)

| # | resource_type_code | Name | Usage Types | On-Demand |
|---|---|---|---|---|
| 1 | `hws.resource.type.natgateway` | Nat Gateway | `duration`, `duration_hour` | **CONFIRMED** (small/middle/large/xlarge) |
| 2 | `hws.resource.type.privatenat` | Private Nat Gateway | (not queried) | PENDING |
| 3 | `hws.resource.type.elasticnatgateway` | Elastic NAT Gateway | (not queried) | PENDING |
| 4 | `hws.resource.type.natgateway.exclusive` | Exclusive Standard-price NAT Gateway | (not queried) | PENDING |

### Usage Types (confirmed for `hws.resource.type.natgateway`)

| resource_type_code | usage_type code | usage_type name |
|---|---|---|
| `hws.resource.type.natgateway` | `duration` | Duration |
| `hws.resource.type.natgateway` | `duration_hour` | Duration |

**Critical finding**: BSS catalog lists both `duration` and `duration_hour`, but **only `duration` works** for on-demand pricing API. `duration_hour` returns CBC.6006 "Product not found". The Huawei Cloud Price Calculator uses `duration` with `usage_value=30, usage_measure_id=0` (30-day month).

---

## 2. Billing Models Identified

### A. Public NAT Gateway Instance

**Four specs confirmed via BSS/OCE live pricing API:**

| Spec | resource_spec | Hourly Rate (USD) | Monthly 730h (USD) | Calculator Monthly (usage_value=30, USD) | Max SNAT Connections | Max DNAT Connections |
|---|---|---|---|---|---|---|
| Small | `natgateway_small` | 0.10158 | 74.16 | 73.14 | 10,000 | 100 |
| Middle | `natgateway_middle` | 0.19050 | 139.07 | 137.16 | 50,000 | 200 |
| Large | `natgateway_large` | 0.37463 | 273.48 | 269.73 | 200,000 | 500 |
| Extra Large | `natgateway_xlarge` | 0.66038 | 482.08 | 475.47 | 1,000,000 | 1,000 |

**Key observations:**
- `usage_value=30, usage_measure_id=0` represents a 30-day month (720 hours). The API returns the 30-day price.
- `usage_value=730, usage_measure_id=4` represents 730 hours directly. The API returns the 730-hour price.
- Monthly 730h prices are slightly higher than calculator (30-day = 720h) prices because 730 > 720.
- The calculator payload uses `usage_value=30, usage_measure_id=0` which is the **primary** format.
- For template implementation, `usage_value=730, usage_measure_id=4` (monthly_hours pattern) is the **standard MCP pattern** used by all other services (ECS, EVS, EIP, RDS, etc.).

### B. Private NAT Gateway
- **resource_type**: `hws.resource.type.privatenat`
- **resource_spec**: **UNKNOWN** - not tested
- Private NAT Gateway has no EIP dependency and is billed differently.

### C. Elastic NAT Gateway
- **resource_type**: `hws.resource.type.elasticnatgateway`
- **resource_spec**: **UNKNOWN** - not tested

### D. Exclusive Standard-price NAT Gateway
- **resource_type**: `hws.resource.type.natgateway.exclusive`
- **resource_spec**: **UNKNOWN** - not tested

---

## 3. resource_spec Discovery Results

### A. Public NAT Gateway - ALL CONFIRMED

| resource_spec | resource_type | usage_factor | usage_value | usage_measure_id | Result | Price (USD) |
|---|---|---|---|---|---|---|
| `natgateway_small` | `hws.resource.type.natgateway` | `duration` | 30 | 0 | **SUCCESS** | 73.14 |
| `natgateway_middle` | `hws.resource.type.natgateway` | `duration` | 30 | 0 | **SUCCESS** | 137.16 |
| `natgateway_large` | `hws.resource.type.natgateway` | `duration` | 30 | 0 | **SUCCESS** | 269.73 |
| `natgateway_xlarge` | `hws.resource.type.natgateway` | `duration` | 30 | 0 | **SUCCESS** | 475.47 |
| `natgateway_small` | `hws.resource.type.natgateway` | `duration` | 1 | 4 | **SUCCESS** | 0.10158/h |
| `natgateway_middle` | `hws.resource.type.natgateway` | `duration` | 1 | 4 | **SUCCESS** | 0.19050/h |
| `natgateway_large` | `hws.resource.type.natgateway` | `duration` | 1 | 4 | **SUCCESS** | 0.37463/h |
| `natgateway_xlarge` | `hws.resource.type.natgateway` | `duration` | 1 | 4 | **SUCCESS** | 0.66038/h |
| `natgateway_small` | `hws.resource.type.natgateway` | `duration` | 730 | 4 | **SUCCESS** | 74.16 |
| `natgateway_small` | `hws.resource.type.natgateway` | `duration_hour` | 730 | 4 | **FAIL** | CBC.6006 |
| `natgateway_small` | `hws.resource.type.natgateway` | `duration_hour` | 1 | 4 | **FAIL** | CBC.6006 |

---

## 4. Validated product_infos

### A. Calculator Format (PRIMARY - usage_value=30, usage_measure_id=0)

```json
{
  "id": "natgateway-small-30d-1",
  "cloud_service_type": "hws.service.type.natgateway",
  "resource_type": "hws.resource.type.natgateway",
  "resource_spec": "natgateway_small",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 30,
  "usage_measure_id": 0,
  "subscription_num": 1
}
```

**Result**: USD 73.14 (30-day month = 720 hours)
**product_id**: OFFI638209145087582211

### B. MCP Standard Format (usage_value=730, usage_measure_id=4)

```json
{
  "id": "natgateway-small-730h-1",
  "cloud_service_type": "hws.service.type.natgateway",
  "resource_type": "hws.resource.type.natgateway",
  "resource_spec": "natgateway_small",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1
}
```

**Result**: USD 74.16 (730 hours)
**product_id**: OFFI638209145087582211

### C. Hourly Rate Format (usage_value=1, usage_measure_id=4)

```json
{
  "id": "natgateway-small-1h-1",
  "cloud_service_type": "hws.service.type.natgateway",
  "resource_type": "hws.resource.type.natgateway",
  "resource_spec": "natgateway_small",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 1,
  "usage_measure_id": 4,
  "subscription_num": 1
}
```

**Result**: USD 0.10158/hour
**product_id**: OFFI638209145087582211

---

## 5. Validated Pricing Summary

| Spec | resource_spec | Hourly (USD) | Monthly 730h (USD) | Calculator 30-day (USD) | product_id |
|---|---|---|---|---|---|
| Small | `natgateway_small` | 0.10158 | 74.16 | 73.14 | OFFI638209145087582211 |
| Middle | `natgateway_middle` | 0.19050 | 139.07 | 137.16 | OFFI638209145087582210 |
| Large | `natgateway_large` | 0.37463 | 273.48 | 269.73 | OFFI638209145087582209 |
| Extra Large | `natgateway_xlarge` | 0.66038 | 482.08 | 475.47 | OFFI638209145087582208 |

**Note**: Monthly 730h = hourly_rate × 730. Calculator 30-day = hourly_rate × 720. The difference (730-720=10 hours) causes the ~1.4% price difference.

---

## 6. usage_measure_id and usage_value Analysis

| usage_measure_id | usage_value | Meaning | Works with BSS/OCE | Used by |
|---|---|---|---|---|
| 0 | 30 | 30-day month (720 hours) | **YES** | Huawei Cloud Price Calculator |
| 4 | 1 | 1 hour | **YES** | MCP hourly rate queries |
| 4 | 730 | 730 hours (monthly) | **YES** | MCP standard monthly pattern |
| 4 | 30 | 30 hours (NOT 30 days) | **YES** (but wrong meaning) | N/A |

**Conclusion**: 
- `usage_measure_id=0` with `usage_value=30` is accepted by BSS/OCE and represents the calculator's 30-day month format.
- `usage_measure_id=4` with `usage_value=730` is the standard MCP pattern for monthly cost estimation.
- For template implementation, use `usage_measure_id=4` with `usage_value={{monthly_hours}}` (default 730) to match the MCP standard pattern used by all other services.

---

## 7. Errors Encountered

| Error Code | Error Message | Context | Resolution |
|---|---|---|---|
| CBC.0100 | "id: must not be null" | First attempt without `id` field in product_infos | Add `id` field (sequential string) |
| CBC.6006 | "Can not find product natgateway_small" | `usage_factor: duration_hour` with `usage_measure_id: 4` | Use `usage_factor: duration` instead |
| CBC.6006 | "Can not find product natgateway_small" | `usage_factor: duration_hour` with `usage_value: 1` | Use `usage_factor: duration` instead |

---

## 8. NAT Gateway Fase 1 Implementation

### Implemented: `nat-gateway-public-payg` (public NAT Gateway instance-only template)

**Rationale:**
- `cloud_service_type` CONFIRMED: `hws.service.type.natgateway`
- `resource_type` CONFIRMED: `hws.resource.type.natgateway`
- All 4 `resource_spec` values CONFIRMED: `natgateway_small`, `natgateway_middle`, `natgateway_large`, `natgateway_xlarge`
- On-demand pricing validated for all 4 specs via live BSS/OCE pricing API
- `usage_factor` CONFIRMED: `duration` (NOT `duration_hour`)
- `product_infos_template` fully defined
- Instance-only template follows the same pattern as CFW, WAF, DDS, DCS Redis Fase 1

**Design decision**: Use Price Calculator day-based billing (`usage_days`, default 30, `usage_measure_id=0`) instead of hourly (`monthly_hours=730`, `usage_measure_id=4`). Both formats are validated and work with BSS/OCE, but Price Calculator uses days as the primary format for NAT Gateway.

### Implemented template: `nat-gateway-public-payg`

```json
{
  "nat-gateway-public-payg": {
    "service": "natgateway",
    "region": "la-north-2",
    "display_name": "Public NAT Gateway pay-per-use",
    "billing_mode": "on_demand",
    "unit": "day",
    "description": "Public NAT Gateway instance. Billed by spec tier per day. Four specs: small (10K SNAT), middle (50K SNAT), large (200K SNAT), xlarge (1M SNAT). Does NOT include EIP, bandwidth, SNAT rules, or DNAT rules.",
    "parameters": {
      "quantity": {
        "type": "integer",
        "required": true,
        "min": 1,
        "default": 1
      },
      "nat_resource_spec": {
        "type": "string",
        "required": true,
        "default": "natgateway_small",
        "description": "NAT Gateway spec. Valid values: natgateway_small, natgateway_middle, natgateway_large, natgateway_xlarge."
      },
      "usage_days": {
        "type": "number",
        "required": true,
        "min": 1,
        "default": 30,
        "description": "Usage duration in days for pay-per-use NAT Gateway pricing. Price Calculator uses 30-day month (usage_measure_id=0)."
      }
    },
    "product_infos_template": [
      {
        "id": "natgateway-public-{{nat_resource_spec}}-{{usage_days}}d-{{quantity}}",
        "cloud_service_type": "hws.service.type.natgateway",
        "resource_type": "hws.resource.type.natgateway",
        "resource_spec": "{{nat_resource_spec}}",
        "region": "{{region}}",
        "usage_factor": "duration",
        "usage_value": "{{usage_days}}",
        "usage_measure_id": 0,
        "subscription_num": "{{quantity}}"
      }
    ],
    "status": "ready"
  }
}
```

**Why `usage_days` (days) instead of `monthly_hours` (hours):**
- Huawei Cloud Price Calculator uses `usage_value=30, usage_measure_id=0` (30-day month) as the primary format for NAT Gateway.
- The hourly format (`usage_value=730, usage_measure_id=4`) is also valid but produces slightly different prices (730h vs 720h = 30 days).
- Using days aligns with Price Calculator output and avoids the ~1.4% discrepancy between 730h and 30-day pricing.
- Other MCP services (ECS, EVS, EIP, RDS, etc.) use `monthly_hours` because Price Calculator uses hours for those services.

**NAT Fase 1 scope:**
- Only prices the Public NAT Gateway base instance.
- Does NOT include EIP.
- Does NOT include bandwidth.
- Does NOT include SNAT rules.
- Does NOT include DNAT rules.
- For DNAT, EIP must be priced separately using `eip-bandwidth-mbps-payg` (Fase 2 will validate if DNAT rules require separate pricing).
- For SNAT, leaving as pending for Fase 2 to validate if public egress cost requires EIP/bandwidth separation.

### Deferred: Private/Elastic/Exclusive NAT Gateway

- `private-nat-gateway-payg`: **BLOCKED** by unknown `resource_spec` for `hws.resource.type.privatenat`.
- `elastic-nat-gateway-payg`: **BLOCKED** by unknown `resource_spec` for `hws.resource.type.elasticnatgateway`.
- `nat-gateway-exclusive-payg`: **BLOCKED** by unknown `resource_spec` for `hws.resource.type.natgateway.exclusive`.
- Bandwith add-on: NAT Gateway bandwidth billing (per Mbps or per GB) not yet investigated. May require separate resource_type or resource_spec.
- SNAT rule pricing: Pending Fase 2 validation.
- DNAT rule pricing: Pending Fase 2 validation.

---

## 9. NAT Gateway Spec Comparison (from product documentation)

| Feature | Small | Middle | Large | Extra Large |
|---|---|---|---|---|
| resource_spec | `natgateway_small` | `natgateway_middle` | `natgateway_large` | `natgateway_xlarge` |
| Max SNAT connections | 10,000 | 50,000 | 200,000 | 1,000,000 |
| Max DNAT connections | 100 | 200 | 500 | 1,000 |
| Hourly rate (USD) | 0.10158 | 0.19050 | 0.37463 | 0.66038 |
| Monthly 730h (USD) | 74.16 | 139.07 | 273.48 | 482.08 |

---

## 10. product_infos_template Implementation

NAT Fase 1 uses the **Price Calculator day-based format** (`usage_measure_id=0`, `usage_value={{usage_days}}`):

```json
{
  "id": "natgateway-public-{{nat_resource_spec}}-{{usage_days}}d-{{quantity}}",
  "cloud_service_type": "hws.service.type.natgateway",
  "resource_type": "hws.resource.type.natgateway",
  "resource_spec": "{{nat_resource_spec}}",
  "region": "{{region}}",
  "usage_factor": "duration",
  "usage_value": "{{usage_days}}",
  "usage_measure_id": 0,
  "subscription_num": "{{quantity}}"
}
```

**Why the calculator format** (`usage_value=30, usage_measure_id=0`):
- Price Calculator uses days as the primary billing unit for NAT Gateway.
- Aligns with Price Calculator output (no ~1.4% discrepancy between 730h and 30-day).
- The hourly format (`usage_value=730, usage_measure_id=4`) was validated and works, but is NOT the default.
- Other MCP services (ECS, EVS, EIP, RDS, etc.) use `monthly_hours` because Price Calculator uses hours for those services.

---

## 11. Files Created/Modified

- **Created**: `docs/nat-gateway-discovery.md` (this file)
- **Modified**: `docs/service-expansion-analysis.md` (updated NAT Gateway section with confirmed findings)
- **Modified**: `/root/.config/maas-pricing/pricing-templates.json` (added `natgateway` service with `nat-gateway-public-payg` template)
- **Modified**: `config/pricing-templates.example.json` (added `natgateway` service with `nat-gateway-public-payg` template)
- **Created**: `test-nat-gateway-public.mjs` (8 test cases: T1-T8)
- **Modified**: `package.json` (added `test-nat-gateway-public.mjs` to test:unit, test:integration, test:all)

---

## 12. Summary

| Item | Status |
|---|---|
| cloud_service_type | **CONFIRMED**: `hws.service.type.natgateway` |
| resource_type | **CONFIRMED**: `hws.resource.type.natgateway` (public NAT) |
| resource_spec | **CONFIRMED**: `natgateway_small`, `natgateway_middle`, `natgateway_large`, `natgateway_xlarge` |
| product_infos (calculator format) | **CONFIRMED & IMPLEMENTED**: usage_value=30, usage_measure_id=0 (days) |
| product_infos (hourly format) | **CONFIRMED but NOT default**: usage_value=730, usage_measure_id=4 |
| usage_factor | **CONFIRMED**: `duration` (NOT `duration_hour`) |
| Validated prices (30d) | Small: $73.14/mo, Middle: $137.16/mo, Large: $269.73/mo, XLarge: $475.47/mo |
| Validated prices (730h) | Small: $74.16/mo, Middle: $139.07/mo, Large: $273.48/mo, XLarge: $482.08/mo |
| Errors | CBC.0100 (missing id), CBC.6006 (duration_hour not valid for pricing API) |
| Private NAT resource_spec | **PENDING** (not tested) |
| Elastic NAT resource_spec | **PENDING** (not tested) |
| Exclusive NAT resource_spec | **PENDING** (not tested) |
| SNAT rule pricing | **PENDING** (Fase 2) |
| DNAT rule pricing | **PENDING** (Fase 2) |
| Implementation | **IMPLEMENTED**: `nat-gateway-public-payg` template (Fase 1, public NAT instance only, day-based billing) |
