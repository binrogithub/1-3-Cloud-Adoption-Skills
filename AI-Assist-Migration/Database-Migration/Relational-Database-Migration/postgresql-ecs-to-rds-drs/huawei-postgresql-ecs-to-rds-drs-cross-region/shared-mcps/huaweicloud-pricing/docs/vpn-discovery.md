# VPN Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-06-01
**Region**: la-north-2 (LA-Mexico City2)
**Status**: VPN Gateway V300 CONFIRMED. Traffic components (12_share, 12_bgp) CONFIRMED. Full architecture validated against real quotation. **Fase 1 IMPLEMENTED** as `vpn-gateway-payg` (gateway only, status `ready`).

---

## 1. BSS/OCE Catalog Summary

### cloud_service_type

- **Code**: `hws.service.type.vpn`
- **Name**: Virtual Private Network
- **Source**: Confirmed via BSS/OCE `/v2/products/service-types` and `/v2/products/service-resources`

### Resource Types (3 total)

| # | resource_type_code | Name | On-Demand Pricing | Notes |
|---|---|---|---|---|
| 1 | `hws.resource.type.vpn.ipsecvpn` | Enterprise Edition VPN | **CONFIRMED** (V300) | Primary resource type for on-demand pricing |
| 2 | `hws.resource.type.vpn.vgw` | Virtual Private Network | **FAIL** (CBC.6074) | Does NOT support on-demand pricing API |
| 3 | `hws.resource.type.vpnconnection` | VPN | **FAIL** (CBC.6006) | Does NOT support on-demand pricing API |

### Usage Types

| resource_type_code | usage_type code | usage_type name |
|---|---|---|
| `hws.resource.type.vpn.ipsecvpn` | `duration` | duration |
| `hws.resource.type.vpn.vgw` | `count` | Count |

**Critical finding**: Only `hws.resource.type.vpn.ipsecvpn` with `usage_factor=duration` works for on-demand pricing. The other two resource types (`vpn.vgw`, `vpnconnection`) return errors.

### VPC Bandwidth Resource Types (for VPN traffic)

| resource_type_code | usage_type code | usage_type name | Notes |
|---|---|---|---|
| `hws.resource.type.bandwidth` | `upflow` | Upstream bandwidth | **CONFIRMED** for VPN traffic |
| `hws.resource.type.bandwidth` | `downflow` | Downstream bandwidth | Not tested |
| `hws.resource.type.bandwidth` | `Duration` | Duration | Not tested for VPN |
| `hws.resource.type.bandwidth` | `mainflow` | Main Flow Traffic | Not tested |

---

## 2. Billing Models Identified

### A. VPN Gateway Instance (Enterprise Edition)

**One spec confirmed via BSS/OCE live pricing API:**

| Spec | resource_spec | Hourly Rate (USD) | Monthly 730h (USD) | 30-Day (USD) | product_id |
|---|---|---|---|---|---|
| Professional | `V300` | 0.33 | 240.90 | 237.60 | OFFI808958474453983232 |

**Key observations:**
- `resource_size` and `resource_size_measure_id` are **REQUIRED** fields. Without them, the API returns CBC.6001 "Required param resourceSpecSize or resourceSize is null or empty".
- `resource_size=1, resource_size_measure_id=14` (1 PCS) represents 1 VPN gateway instance.
- The "10 VPN Connection Groups" in the quotation is a property of the V300/Professional spec, not a separate billing parameter.
- `usage_value=730, usage_measure_id=4` (730 hours) is the standard MCP monthly pattern.
- `usage_value=30, usage_measure_id=0` (30 days) also works but yields USD 237.60 (720h) vs USD 240.90 (730h).
- The quotation uses the 730h format (USD 240.90 matches exactly).

### B. VPN Traffic / Bandwidth (VPC service)

**Two resource_specs confirmed for VPN traffic billing:**

| Spec | resource_spec | Type | Per GB (USD) | 200 GB (USD) | product_id |
|---|---|---|---|---|---|
| Shared | `12_share` | Active/primary | 0.081 | 16.20 | OFFI951287093288931328 |
| BGP | `12_bgp` | Standby/secondary | 0.081 | 16.20 | OFFI580665045183791104 |

**Key observations:**
- VPN traffic is billed under `hws.service.type.vpc` (NOT `hws.service.type.vpn`).
- `resource_type` is `hws.resource.type.bandwidth` (same as EIP bandwidth).
- `usage_factor=upflow` with `usage_measure_id=10` (GB).
- `usage_value` represents the traffic volume in GB. For 200 GB, `usage_value=200`.
- Both `12_share` and `12_bgp` have the same per-GB rate (USD 0.081/GB) in la-north-2.
- `12_share` likely represents the active VPN tunnel traffic (shared bandwidth).
- `12_bgp` likely represents the standby VPN tunnel traffic (BGP-routed bandwidth).

---

## 3. resource_spec Discovery Results

### A. VPN Gateway - V300 CONFIRMED, others FAIL

| resource_spec | resource_type | usage_factor | resource_size | Result | Price (USD/730h) |
|---|---|---|---|---|---|
| `V300` | `hws.resource.type.vpn.ipsecvpn` | `duration` | 1 | **SUCCESS** | 240.90 |
| `V1` | `hws.resource.type.vpn.ipsecvpn` | `duration` | 1 | **FAIL** | CBC.6006 "Can not find product V1" |
| `V2` | `hws.resource.type.vpn.ipsecvpn` | `duration` | 1 | **FAIL** | CBC.6006 "Can not find product V2" |
| `V5` | `hws.resource.type.vpn.ipsecvpn` | `duration` | 1 | **FAIL** | CBC.6006 "Can not find product V5" |
| `vpn.v300` | `hws.resource.type.vpn.ipsecvpn` | `duration` | 1 | **FAIL** | CBC.6006 "Can not find product vpn.v300" |
| `professional` | `hws.resource.type.vpn.ipsecvpn` | `duration` | 1 | **FAIL** | CBC.6006 "Can not find product professional" |
| `vpn.professional` | `hws.resource.type.vpn.ipsecvpn` | `duration` | 1 | **FAIL** | CBC.6006 "Can not find product vpn.professional" |
| `V300.1` | `hws.resource.type.vpn.ipsecvpn` | `duration` | 1 | **FAIL** | CBC.6006 "Can not find product V300.1" |
| `V300` | `hws.resource.type.vpn.vgw` | `count` | 1 | **FAIL** | CBC.6006 "Can not find product V300" |
| `V300` | `hws.resource.type.vpnconnection` | `duration` | 1 | **FAIL** | CBC.6006 "Can not find product V300" |

### B. Traffic/Bandwidth - 12_share and 12_bgp CONFIRMED

| resource_spec | resource_type | usage_factor | usage_value | Result | Price (USD) |
|---|---|---|---|---|---|
| `12_share` | `hws.resource.type.bandwidth` | `upflow` | 1 | **SUCCESS** | 0.081 (per GB) |
| `12_bgp` | `hws.resource.type.bandwidth` | `upflow` | 1 | **SUCCESS** | 0.081 (per GB) |
| `12_share` | `hws.resource.type.bandwidth` | `upflow` | 200 | **SUCCESS** | 16.20 (200 GB) |
| `12_bgp` | `hws.resource.type.bandwidth` | `upflow` | 200 | **SUCCESS** | 16.20 (200 GB) |

---

## 4. Validated product_infos

### A. VPN Gateway (Calculator Format - usage_value=1, usage_measure_id=4)

```json
{
  "id": "vpn-gateway-v300-1h-1",
  "cloud_service_type": "hws.service.type.vpn",
  "resource_type": "hws.resource.type.vpn.ipsecvpn",
  "resource_spec": "V300",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 1,
  "usage_measure_id": 4,
  "resource_size": 1,
  "resource_size_measure_id": 14,
  "subscription_num": 1
}
```

**Result**: USD 0.33/hour
**product_id**: OFFI808958474453983232

### B. VPN Gateway (MCP Standard Format - usage_value=730, usage_measure_id=4)

```json
{
  "id": "vpn-gateway-v300-730h-1",
  "cloud_service_type": "hws.service.type.vpn",
  "resource_type": "hws.resource.type.vpn.ipsecvpn",
  "resource_spec": "V300",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "resource_size": 1,
  "resource_size_measure_id": 14,
  "subscription_num": 1
}
```

**Result**: USD 240.90 (730 hours)
**product_id**: OFFI808958474453983232

### C. Traffic Active (12_share, 200 GB)

```json
{
  "id": "vpn-traffic-active-200gb",
  "cloud_service_type": "hws.service.type.vpc",
  "resource_type": "hws.resource.type.bandwidth",
  "resource_spec": "12_share",
  "region": "la-north-2",
  "usage_factor": "upflow",
  "usage_value": 200,
  "usage_measure_id": 10,
  "subscription_num": 1
}
```

**Result**: USD 16.20 (200 GB)
**product_id**: OFFI951287093288931328

### D. Traffic Standby (12_bgp, 200 GB)

```json
{
  "id": "vpn-traffic-standby-200gb",
  "cloud_service_type": "hws.service.type.vpc",
  "resource_type": "hws.resource.type.bandwidth",
  "resource_spec": "12_bgp",
  "region": "la-north-2",
  "usage_factor": "upflow",
  "usage_value": 200,
  "usage_measure_id": 10,
  "subscription_num": 1
}
```

**Result**: USD 16.20 (200 GB)
**product_id**: OFFI580665045183791104

### E. Full Architecture (3 product_infos combined)

```json
[
  {
    "id": "vpn-gateway-v300",
    "cloud_service_type": "hws.service.type.vpn",
    "resource_type": "hws.resource.type.vpn.ipsecvpn",
    "resource_spec": "V300",
    "region": "la-north-2",
    "usage_factor": "duration",
    "usage_value": 730,
    "usage_measure_id": 4,
    "resource_size": 1,
    "resource_size_measure_id": 14,
    "subscription_num": 1
  },
  {
    "id": "vpn-traffic-active",
    "cloud_service_type": "hws.service.type.vpc",
    "resource_type": "hws.resource.type.bandwidth",
    "resource_spec": "12_share",
    "region": "la-north-2",
    "usage_factor": "upflow",
    "usage_value": 200,
    "usage_measure_id": 10,
    "subscription_num": 1
  },
  {
    "id": "vpn-traffic-standby",
    "cloud_service_type": "hws.service.type.vpc",
    "resource_type": "hws.resource.type.bandwidth",
    "resource_spec": "12_bgp",
    "region": "la-north-2",
    "usage_factor": "upflow",
    "usage_value": 200,
    "usage_measure_id": 10,
    "subscription_num": 1
  }
]
```

**Result**: USD 273.30 total (240.90 + 16.20 + 16.20)

---

## 5. Validated Pricing Summary

| Component | resource_spec | Hourly/Per-GB (USD) | Monthly 730h (USD) | product_id |
|---|---|---|---|---|
| VPN Gateway Professional | `V300` | 0.33/h | 240.90 | OFFI808958474453983232 |
| Traffic Active (shared) | `12_share` | 0.081/GB | 16.20 (200 GB) | OFFI951287093288931328 |
| Traffic Standby (BGP) | `12_bgp` | 0.081/GB | 16.20 (200 GB) | OFFI580665045183791104 |
| **Total** | | | **273.30** | |

---

## 6. Comparison Against Real Quotation

| Item | Quotation (USD) | BSS/OCE Validated (USD) | Match |
|---|---|---|---|
| VPN Professional 1 / 10 VPN Connection Groups | 240.90 | 240.90 | **EXACT** |
| Traffic 200GB (active) | 16.20 | 16.20 | **EXACT** |
| Traffic 200GB (standby) | 16.20 | 16.20 | **EXACT** |
| **Total** | **273.30** | **273.30** | **EXACT** |

**Conclusion**: All three components validated with 100% accuracy against the real Huawei Cloud quotation in la-north-2.

---

## 7. 200GB Traffic Field Analysis

| Field | Value | Role |
|---|---|---|
| `usage_value` | 200 | **Quantity of traffic in GB** |
| `usage_measure_id` | 10 | **Unit = GB** (confirmed from measurement units catalog: measure_id 10 = "GB") |
| `resource_size` | (not used) | Not applicable for traffic components |
| `resource_size_measure_id` | (not used) | Not applicable for traffic components |

**Conclusion**: For VPN traffic, `usage_value` with `usage_measure_id=10` (GB) represents the traffic volume. `usage_value=200` means 200 GB. This is consistent with the EIP bandwidth billing pattern where `usage_value` represents the quantity and `usage_measure_id` specifies the unit.

---

## 8. resource_size Analysis for VPN Gateway

| resource_size | resource_size_measure_id | Monthly 730h (USD) | Increment |
|---|---|---|---|
| 1 | 14 (PCS) | 240.90 | Base |
| 2 | 14 (PCS) | 266.45 | +25.55 |
| 10 | 14 (PCS) | 470.85 | +230.00 |

**Analysis**: `resource_size` represents the number of VPN gateway instances. The pricing is not linear:
- Base cost (resource_size=1): USD 0.33/h
- Incremental cost per additional instance: USD 0.035/h
- Formula: `cost = 0.33 + (resource_size - 1) * 0.035` per hour

For the standard single-gateway deployment, `resource_size=1` is the correct value (matches the calculator payload and quotation).

---

## 9. usage_measure_id and usage_value Analysis

### VPN Gateway

| usage_measure_id | usage_value | Meaning | Works with BSS/OCE | Used by |
|---|---|---|---|---|
| 4 | 1 | 1 hour | **YES** | MCP hourly rate queries |
| 4 | 730 | 730 hours (monthly) | **YES** | MCP standard monthly pattern |
| 0 | 30 | 30-day month (720 hours) | **YES** | Huawei Cloud Price Calculator |
| 0 | 1 | 1 day | **YES** | Per-day rate queries |

### VPN Traffic

| usage_measure_id | usage_value | Meaning | Works with BSS/OCE | Used by |
|---|---|---|---|---|
| 10 | 1 | 1 GB | **YES** | Per-GB rate queries |
| 10 | 200 | 200 GB | **YES** | Traffic volume queries |

---

## 10. Errors Encountered

| Error Code | Error Message | Context | Resolution |
|---|---|---|---|
| CBC.6001 | "Required param resourceSpecSize or resourceSize is null or empty" | VPN gateway without `resource_size` / `resource_size_measure_id` | Add `resource_size=1, resource_size_measure_id=14` (REQUIRED for VPN gateway) |
| CBC.6074 | "The billing item does not exist" | `hws.resource.type.vpn.vgw` with on-demand pricing | Use `hws.resource.type.vpn.ipsecvpn` instead |
| CBC.6006 | "Can not find product V300" | `hws.resource.type.vpnconnection` with V300 | Use `hws.resource.type.vpn.ipsecvpn` instead |
| CBC.6006 | "Can not find product V1" | resource_spec `V1` | Only `V300` confirmed for la-north-2 |
| CBC.6006 | "Can not find product V2" | resource_spec `V2` | Only `V300` confirmed for la-north-2 |
| CBC.6006 | "Can not find product V5" | resource_spec `V5` | Only `V300` confirmed for la-north-2 |
| CBC.6006 | "Can not find product vpn.v300" | resource_spec `vpn.v300` | Use `V300` (no prefix) |
| CBC.6006 | "Can not find product professional" | resource_spec `professional` | Use `V300` (BSS uses V-prefixed spec codes) |
| CBC.6006 | "Can not find product vpn.professional" | resource_spec `vpn.professional` | Use `V300` |

---

## 11. VPN Implementation Recommendation

### Recommendation: Implement VPN Fase 1 (gateway-only template)

**Rationale:**
- VPN gateway `resource_spec` CONFIRMED: `V300`
- VPN gateway on-demand pricing VALIDATED: USD 240.90/month (730h)
- `resource_size` and `resource_size_measure_id` are REQUIRED fields (unlike most other services)
- Traffic components use a different `cloud_service_type` (`hws.service.type.vpc`) than the gateway (`hws.service.type.vpn`)
- Traffic is 32% of total cost in the reference quotation (USD 32.40 of USD 273.30)

### Fase 1: Simple Template `vpn-gateway-payg`

**Scope**: VPN gateway instance only (no traffic).

```json
{
  "vpn-gateway-payg": {
    "service": "vpn",
    "region": "la-north-2",
    "display_name": "VPN Gateway pay-per-use",
    "billing_mode": "on_demand",
    "unit": "hour",
    "description": "VPN Gateway instance (Enterprise Edition / IPSec VPN). Billed per hour by spec. V300 = Professional with 10 VPN Connection Groups. Does NOT include VPN traffic/bandwidth (billed separately under VPC service).",
    "parameters": {
      "quantity": {
        "type": "integer",
        "required": true,
        "min": 1,
        "default": 1
      },
      "vpn_resource_spec": {
        "type": "string",
        "required": true,
        "default": "V300",
        "description": "VPN Gateway spec. Valid values: V300 (Professional, 10 connection groups)."
      },
      "monthly_hours": {
        "type": "number",
        "required": true,
        "min": 1,
        "default": 730,
        "description": "Usage duration in hours for pay-per-use VPN Gateway pricing."
      }
    },
    "product_infos_template": [
      {
        "id": "vpn-gateway-{{vpn_resource_spec}}-{{monthly_hours}}h-{{quantity}}",
        "cloud_service_type": "hws.service.type.vpn",
        "resource_type": "hws.resource.type.vpn.ipsecvpn",
        "resource_spec": "{{vpn_resource_spec}}",
        "region": "{{region}}",
        "usage_factor": "duration",
        "usage_value": "{{monthly_hours}}",
        "usage_measure_id": 4,
        "resource_size": 1,
        "resource_size_measure_id": 14,
        "subscription_num": "{{quantity}}"
      }
    ],
    "status": "ready"
  }
}
```

### Fase 2: Macro-Template `vpn-site-to-site-payg` (DEFERRED)

**Scope**: VPN gateway + active traffic + standby traffic (3 product_infos).

```json
{
  "vpn-site-to-site-payg": {
    "service": "vpn",
    "region": "la-north-2",
    "display_name": "VPN Site-to-Site pay-per-use (gateway + traffic)",
    "billing_mode": "on_demand",
    "unit": "hour",
    "description": "VPN Site-to-Site connection: gateway instance + active traffic (12_share) + standby traffic (12_bgp). Gateway billed per hour. Traffic billed per GB.",
    "parameters": {
      "quantity": {
        "type": "integer",
        "required": true,
        "min": 1,
        "default": 1
      },
      "vpn_resource_spec": {
        "type": "string",
        "required": true,
        "default": "V300",
        "description": "VPN Gateway spec. Valid values: V300 (Professional, 10 connection groups)."
      },
      "monthly_hours": {
        "type": "number",
        "required": true,
        "min": 1,
        "default": 730
      },
      "traffic_gb": {
        "type": "number",
        "required": true,
        "min": 0,
        "default": 200,
        "description": "VPN traffic volume in GB per month (applied to both active and standby tunnels)."
      }
    },
    "product_infos_template": [
      {
        "id": "vpn-gateway-{{vpn_resource_spec}}-{{monthly_hours}}h-{{quantity}}",
        "cloud_service_type": "hws.service.type.vpn",
        "resource_type": "hws.resource.type.vpn.ipsecvpn",
        "resource_spec": "{{vpn_resource_spec}}",
        "region": "{{region}}",
        "usage_factor": "duration",
        "usage_value": "{{monthly_hours}}",
        "usage_measure_id": 4,
        "resource_size": 1,
        "resource_size_measure_id": 14,
        "subscription_num": "{{quantity}}"
      },
      {
        "id": "vpn-traffic-active-{{traffic_gb}}gb-{{quantity}}",
        "cloud_service_type": "hws.service.type.vpc",
        "resource_type": "hws.resource.type.bandwidth",
        "resource_spec": "12_share",
        "region": "{{region}}",
        "usage_factor": "upflow",
        "usage_value": "{{traffic_gb}}",
        "usage_measure_id": 10,
        "subscription_num": "{{quantity}}"
      },
      {
        "id": "vpn-traffic-standby-{{traffic_gb}}gb-{{quantity}}",
        "cloud_service_type": "hws.service.type.vpc",
        "resource_type": "hws.resource.type.bandwidth",
        "resource_spec": "12_bgp",
        "region": "{{region}}",
        "usage_factor": "upflow",
        "usage_value": "{{traffic_gb}}",
        "usage_measure_id": 10,
        "subscription_num": "{{quantity}}"
      }
    ],
    "status": "ready"
  }
}
```

### Why Fase 1 first (gateway-only):

1. Follows the established MCP pattern (CFW, WAF, NAT, DCS, DDS all start with instance-only Fase 1).
2. Traffic estimation is variable and hard to predict (depends on actual usage, not provisioned capacity).
3. Traffic uses a different `cloud_service_type` (`hws.service.type.vpc`) which complicates the macro-template.
4. Architects can combine `vpn-gateway-payg` + `eip-bandwidth-mbps-payg` for traffic in the interim.
5. Fase 2 macro-template is fully designed but deferred until Fase 1 is implemented and tested.

### Why NOT maintain VPN blocked:

1. `resource_spec` CONFIRMED: `V300` works with live BSS/OCE pricing API.
2. On-demand pricing VALIDATED against real quotation with 100% accuracy.
3. All required fields identified, including the mandatory `resource_size` / `resource_size_measure_id`.
4. Traffic components also validated (12_share, 12_bgp).
5. No blockers remain for Fase 1 implementation.

---

## 12. Files Created/Modified

- **Created**: `docs/vpn-discovery.md` (this file)
- **Modified**: `docs/service-expansion-analysis.md` (updated VPN section with confirmed findings)

---

## 13. Summary

| Item | Status |
|---|---|
| cloud_service_type (gateway) | **CONFIRMED**: `hws.service.type.vpn` |
| cloud_service_type (traffic) | **CONFIRMED**: `hws.service.type.vpc` |
| resource_type (gateway) | **CONFIRMED**: `hws.resource.type.vpn.ipsecvpn` |
| resource_type (traffic) | **CONFIRMED**: `hws.resource.type.bandwidth` |
| resource_spec (gateway) | **CONFIRMED**: `V300` (Professional, 10 connection groups) |
| resource_spec (traffic active) | **CONFIRMED**: `12_share` |
| resource_spec (traffic standby) | **CONFIRMED**: `12_bgp` |
| resource_size / resource_size_measure_id | **REQUIRED**: `1` / `14` (PCS) for VPN gateway |
| usage_factor (gateway) | **CONFIRMED**: `duration` |
| usage_factor (traffic) | **CONFIRMED**: `upflow` |
| usage_measure_id (gateway) | **CONFIRMED**: `4` (Hour) |
| usage_measure_id (traffic) | **CONFIRMED**: `10` (GB) |
| 200GB traffic field | **CONFIRMED**: `usage_value=200` with `usage_measure_id=10` |
| Validated price (gateway 730h) | USD 240.90 |
| Validated price (traffic 200GB share) | USD 16.20 |
| Validated price (traffic 200GB bgp) | USD 16.20 |
| Validated total | USD 273.30 |
| Quotation match | **EXACT** (all 3 components) |
| V1/V2/V5 resource_spec | **NOT FOUND** in la-north-2 |
| vpn.vgw on-demand | **NOT SUPPORTED** (CBC.6074) |
| vpnconnection on-demand | **NOT SUPPORTED** (CBC.6006) |
| Fase 1 recommendation | **IMPLEMENTED** `vpn-gateway-payg` (gateway only, status `ready`) |
| Fase 2 recommendation | **DEFER** `vpn-site-to-site-payg` macro-template (gateway + traffic) |

---

## 14. Fase 1 Implementation Record

**Date**: 2026-06-01
**Template**: `vpn-gateway-payg`
**Service**: `vpn`
**Region**: `la-north-2`
**Status**: `ready`

**Scope**:
- VPN Gateway instance only (V300 = Professional, 10 VPN Connection Groups)
- Parameters: quantity, gateway_resource_spec, monthly_hours, resource_size
- product_infos_template with required resource_size and resource_size_measure_id fields
- Price sourced from BSS/OCE live API (not hardcoded)

**Explicitly NOT included in Fase 1**:
- VPN traffic/bandwidth (12_share, 12_bgp upflow) — deferred to Fase 2
- vpn-site-to-site-payg macro-template — deferred to Fase 2
- vpn-traffic-payg template — deferred to Fase 2
- service_cost_breakdown — deferred to Fase 2
- validate_availability — VPN does not participate in ECS flavor validation
- include_unavailable_reference_pricing — applies to ECS blocked flavors, not VPN

**Fase 2 requirements**:
- Implement vpn-site-to-site-payg macro-template with 3 product_infos:
  1. VPN gateway (hws.service.type.vpn / hws.resource.type.vpn.ipsecvpn / V300)
  2. Active traffic (hws.service.type.vpc / hws.resource.type.bandwidth / 12_share / upflow)
  3. Standby traffic (hws.service.type.vpc / hws.resource.type.bandwidth / 12_bgp / upflow)
- Implement service_cost_breakdown for gateway + traffic split
- Full quotation reproduction: USD 273.30 (240.90 + 16.20 + 16.20)
- VPN Fase 2 traffic components can now use `vpc-bandwidth-traffic-gb-payg` template instead of raw product_infos (implemented 2026-06-01)

**Files modified**:
- `/root/.config/maas-pricing/pricing-templates.json` — added vpn-gateway-payg template
- `config/pricing-templates.example.json` — added vpn-gateway-payg template
- `test-vpn-gateway.mjs` — created (T1-T7)
- `package.json` — added test-vpn-gateway.mjs to test:unit, test:integration, test:all
- `docs/vpn-discovery.md` — added Fase 1 implementation record
- `docs/service-expansion-analysis.md` — updated VPN Fase 1 status to IMPLEMENTED

**Files NOT modified**:
- `server.mjs` — no changes required
- `template-tools.mjs` — no changes required
- `pricing_catalog_helper.py` — no changes required
- `pricing_api_helper.py` — no changes required

---

## 15. Fase 2 Traffic Template Record

**Date**: 2026-06-01
**Template**: `vpc-bandwidth-traffic-gb-payg`
**Service**: `vpc`
**Region**: `la-north-2`
**Status**: `ready`

**Scope**:
- VPC bandwidth traffic (upflow) by GB — reusable for VPN traffic and EIP traffic
- Parameters: quantity, traffic_resource_spec (12_bgp / 12_share), traffic_gb
- Price sourced from BSS/OCE live API (not hardcoded)

**Validated pricing (BSS/OCE, la-north-2)**:
- 12_bgp 200GB = USD 16.20
- 12_bgp 300GB = USD 24.30
- 12_share 200GB = USD 16.20
- 12_share 300GB = USD 24.30
- 2 × 12_bgp 300GB = USD 48.60 (real EIP quote: USD 48.61, 0.01 rounding diff)

**This template enables**:
- VPN Fase 2: use vpc-bandwidth-traffic-gb-payg for traffic instead of raw product_infos
- EIP traffic: use vpc-bandwidth-traffic-gb-payg alongside eip-bandwidth-mbps-payg for complete EIP cost
