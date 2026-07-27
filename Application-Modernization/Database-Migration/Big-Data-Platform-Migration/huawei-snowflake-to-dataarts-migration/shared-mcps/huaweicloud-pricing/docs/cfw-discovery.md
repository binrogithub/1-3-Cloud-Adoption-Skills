# CFW (Cloud Firewall) Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-05-29
**Region**: la-north-2
**Status**: Base instance resource_spec CONFIRMED (standard + professional). Expansion packages PENDING.

---

## 1. BSS/OCE Catalog Summary

### cloud_service_type
- **Code**: `hws.service.type.cfw`
- **Name**: Cloud Firewall

### Resource Types (6 total)

| # | resource_type_code | Name | Usage Types | On-Demand | Period |
|---|---|---|---|---|---|
| 1 | `hws.resource.type.cfw` | Cloud Firewall | `period_duration`, `usage_duration` | **CONFIRMED** (professional only) | **CONFIRMED** (standard + professional) |
| 2 | `hws.resource.type.cfw.exp.eip` | Cloud Firewall Internet Border Protection EIP Extension Package | `period_duration`, `usage_duration`, `number` | PENDING | PENDING |
| 3 | `hws.resource.type.cfw.exp.vpc` | Cloud Firewall VPC Quantity Expansion Package | `period_duration`, `usage_duration`, `number` | PENDING | PENDING |
| 4 | `hws.resource.type.cfw.exp.bandwidth` | Cloud Firewall Bandwidth Expansion Package | `period_duration`, `usage_duration`, `megabits_per_second` | PENDING | PENDING |
| 5 | `hws.resource.type.cfw.throughput` | CFW-HCSO | (none) | N/A | N/A |
| 6 | `hws.resource.type.cfw.exp.trafficflow` | Cloud Firewall Traffic Expansion Package | `megabyte` | PENDING | PENDING |

### Usage Types (confirmed per resource type)

| resource_type_code | usage_type code | usage_type name |
|---|---|---|
| `hws.resource.type.cfw` | `period_duration` | period duration |
| `hws.resource.type.cfw` | `usage_duration` | usage duration |
| `hws.resource.type.cfw.exp.eip` | `period_duration` | period duration |
| `hws.resource.type.cfw.exp.eip` | `usage_duration` | usage duration |
| `hws.resource.type.cfw.exp.eip` | `number` | number |
| `hws.resource.type.cfw.exp.vpc` | `period_duration` | period duration |
| `hws.resource.type.cfw.exp.vpc` | `usage_duration` | usage duration |
| `hws.resource.type.cfw.exp.vpc` | `number` | number |
| `hws.resource.type.cfw.exp.bandwidth` | `period_duration` | period duration |
| `hws.resource.type.cfw.exp.bandwidth` | `usage_duration` | usage duration |
| `hws.resource.type.cfw.exp.bandwidth` | `megabits_per_second` | megabits per second |
| `hws.resource.type.cfw.exp.trafficflow` | `megabyte` | megabyte |

Resource type `hws.resource.type.cfw.throughput` has **no usage types** (HCSO-only, not billable via standard BSS/OCE).

---

## 2. Billing Models Identified

### A. CFW Base Instance

**Two editions confirmed via BSS/OCE and product page:**

| Edition | resource_spec | On-Demand (hourly) | On-Demand (monthly 730h) | Period (1 month) | Included EIPs | Included Bandwidth | Included VPCs |
|---|---|---|---|---|---|---|---|
| Standard | `cfw.standard` | NOT AVAILABLE | N/A | USD 420.00 | 20 | 10 Mbit/s | 0 |
| Professional | `cfw.professional` | USD 0.36/h | USD 262.80 | USD 1,450.00 | 50 | 50 Mbit/s | 2 |

**Key observations:**
- `cfw.standard` is **NOT available** for on-demand (pay-per-use) billing. Only yearly/monthly.
- `cfw.professional` is available for **both** on-demand and yearly/monthly billing.
- On-demand pricing for professional: USD 0.36/hour = USD 262.80/month (730h).
- Period pricing for professional: USD 1,450.00/month (1-month subscription).
- Period pricing for standard: USD 420.00/month (1-month subscription).
- The on-demand monthly rate (USD 262.80) is significantly lower than the period rate (USD 1,450.00) for professional. This is because on-demand bills only for the edition instance by usage duration, while the period subscription includes the base capacity (50 EIPs, 50 Mbit/s, 2 VPCs).

**Billing documentation confirms:**
- **Yearly/Monthly billing items**: Edition + extended packages (EIP expansion, bandwidth expansion, VPC expansion).
- **Pay-per-use billing items**: Edition + usage duration only. Expansion packages are NOT separate billing items in pay-per-use mode.
- Peak protection traffic is purchased and billed in **5 Mbit/s increments** (5, 10, 15, ...).
- Adding a protected VPC increases inter-VPC protection bandwidth by 200 Mbit/s.

### B. CFW EIP Expansion Package
- **resource_type**: `hws.resource.type.cfw.exp.eip`
- **usage_types**: `period_duration`, `usage_duration`, `number`
- **resource_spec**: **UNKNOWN** - all patterns tested returned "Product not found"
- **Billing formula** (yearly/monthly): Unit price per EIP x Number of EIPs x Required duration
- Only available with yearly/monthly billing (per documentation).

### C. CFW VPC Expansion Package
- **resource_type**: `hws.resource.type.cfw.exp.vpc`
- **usage_types**: `period_duration`, `usage_duration`, `number`
- **resource_spec**: **UNKNOWN** - all patterns tested returned "Product not found"
- **Billing formula** (yearly/monthly): Unit price per VPC x Number of VPCs x Required duration
- Only available with yearly/monthly billing (per documentation).

### D. CFW Bandwidth Expansion Package
- **resource_type**: `hws.resource.type.cfw.exp.bandwidth`
- **usage_types**: `period_duration`, `usage_duration`, `megabits_per_second`
- **resource_spec**: **UNKNOWN** - all patterns tested returned "Product not found"
- **Billing formula** (yearly/monthly): Unit price per Mbit/s x Traffic (5 Mbit/s increments) x Required duration
- Only available with yearly/monthly billing (per documentation).

### E. CFW Traffic Expansion Package
- **resource_type**: `hws.resource.type.cfw.exp.trafficflow`
- **usage_types**: `megabyte`
- **resource_spec**: **UNKNOWN** - not tested (traffic-based billing, likely pay-per-use only)

### F. CFW-HCSO (throughput)
- **resource_type**: `hws.resource.type.cfw.throughput`
- **usage_types**: NONE
- **Status**: Not billable via standard BSS/OCE. HCSO (Huawei Cloud Stack Online) variant only.

---

## 3. resource_spec Discovery Results

### A. CFW Base Instance - CONFIRMED

| resource_spec | resource_type | On-Demand | Period | Error |
|---|---|---|---|---|
| `cfw.professional` | `hws.resource.type.cfw` | **SUCCESS** (USD 0.36/h) | **SUCCESS** (USD 1,450/month) | - |
| `cfw.standard` | `hws.resource.type.cfw` | Product not found | **SUCCESS** (USD 420/month) | CBC.6006 on on-demand |
| `cfw.enterprise` | `hws.resource.type.cfw` | Product not found | Product not found | CBC.6006 |
| `cfw.ultimate` | `hws.resource.type.cfw` | Product not found | Product not found | CBC.6006 |
| `cfw` | `hws.resource.type.cfw` | Product not found | Product not found | CBC.6006 |

### B. CFW Expansion Packages - ALL PENDING

**resource_specs tested and failed (all returned CBC.6006 "Product not found"):**

| resource_spec | resource_type | Mode | Error |
|---|---|---|---|
| `cfw.exp.eip` | `hws.resource.type.cfw.exp.eip` | on-demand + period | CBC.6006 |
| `cfw.exp.vpc` | `hws.resource.type.cfw.exp.vpc` | on-demand + period | CBC.6006 |
| `cfw.exp.bandwidth` | `hws.resource.type.cfw.exp.bandwidth` | on-demand + period | CBC.6006 |
| `cfw.exp.eip.professional` | `hws.resource.type.cfw.exp.eip` | on-demand + period | CBC.6006 |
| `cfw.exp.vpc.professional` | `hws.resource.type.cfw.exp.vpc` | on-demand + period | CBC.6006 |
| `cfw.exp.bandwidth.professional` | `hws.resource.type.cfw.exp.bandwidth` | on-demand + period | CBC.6006 |
| `cfw.exp.eip.standard` | `hws.resource.type.cfw.exp.eip` | period | CBC.6006 |
| `cfw.professional.exp.eip` | `hws.resource.type.cfw.exp.eip` | on-demand | CBC.6006 |
| `cfw.professional.exp.vpc` | `hws.resource.type.cfw.exp.vpc` | on-demand | CBC.6006 |
| `cfw.professional.exp.bandwidth` | `hws.resource.type.cfw.exp.bandwidth` | on-demand | CBC.6006 |
| `cfw.professional.eip` | `hws.resource.type.cfw.exp.eip` | on-demand | CBC.6006 |
| `cfw.professional.vpc` | `hws.resource.type.cfw.exp.vpc` | on-demand | CBC.6006 |
| `cfw.professional.bandwidth` | `hws.resource.type.cfw.exp.bandwidth` | on-demand | CBC.6006 |
| `cfw.eip` | `hws.resource.type.cfw.exp.eip` | on-demand + period | CBC.6006 |
| `cfw.vpc` | `hws.resource.type.cfw.exp.vpc` | on-demand + period | CBC.6006 |
| `cfw.bandwidth` | `hws.resource.type.cfw.exp.bandwidth` | on-demand + period | CBC.6006 |
| `cfw.eip.expansion` | `hws.resource.type.cfw.exp.eip` | on-demand | CBC.6006 |
| `cfw.vpc.expansion` | `hws.resource.type.cfw.exp.vpc` | on-demand | CBC.6006 |
| `cfw.bandwidth.expansion` | `hws.resource.type.cfw.exp.bandwidth` | on-demand | CBC.6006 |
| `cfw.professional` | `hws.resource.type.cfw.exp.eip` | on-demand | CBC.6006 |
| `cfw.professional` | `hws.resource.type.cfw.exp.vpc` | on-demand | CBC.6006 |
| `cfw.professional` | `hws.resource.type.cfw.exp.bandwidth` | on-demand | CBC.6006 |

**Total patterns tested**: 22+ combinations across on-demand and period APIs.

---

## 4. Validated product_infos

### A. CFW Professional - On-Demand (CONFIRMED)

```json
{
  "id": "cfw-professional-730h-1",
  "cloud_service_type": "hws.service.type.cfw",
  "resource_type": "hws.resource.type.cfw",
  "resource_spec": "cfw.professional",
  "region": "la-north-2",
  "usage_factor": "usage_duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1
}
```

**Result**: USD 262.80/month (USD 0.36/hour x 730 hours)
**product_id**: OFFI896227341816221701

### B. CFW Professional - Period (CONFIRMED)

```json
{
  "id": "cfw-professional-period-1",
  "cloud_service_type": "hws.service.type.cfw",
  "resource_type": "hws.resource.type.cfw",
  "resource_spec": "cfw.professional",
  "region": "la-north-2",
  "usage_factor": "period_duration",
  "usage_value": 1,
  "usage_measure_id": 20,
  "subscription_num": 1,
  "period_type": 2,
  "period_num": 1
}
```

**Result**: USD 1,450.00/month
**product_id**: OFFI740927445305384960

### C. CFW Standard - Period (CONFIRMED)

```json
{
  "id": "cfw-standard-period-1",
  "cloud_service_type": "hws.service.type.cfw",
  "resource_type": "hws.resource.type.cfw",
  "resource_spec": "cfw.standard",
  "region": "la-north-2",
  "usage_factor": "period_duration",
  "usage_value": 1,
  "usage_measure_id": 20,
  "subscription_num": 1,
  "period_type": 2,
  "period_num": 1
}
```

**Result**: USD 420.00/month
**product_id**: OFFI740927445305384966

---

## 5. Validated Pricing Summary

| Edition | Billing Mode | Hourly Rate | Monthly (730h) | Period (1 month) |
|---|---|---|---|---|
| Standard | Yearly/Monthly | N/A | N/A | USD 420.00 |
| Professional | Pay-per-use | USD 0.36 | USD 262.80 | N/A |
| Professional | Yearly/Monthly | N/A | N/A | USD 1,450.00 |

---

## 6. Errors Encountered

| Error Code | Error Message | Context |
|---|---|---|
| CBC.6006 | "Can not find product cfw.standard" | On-demand pricing for standard edition (not available) |
| CBC.6006 | "Can not find product cfw.enterprise" | Both on-demand and period (edition does not exist in la-north-2) |
| CBC.6006 | "Can not find product cfw.ultimate" | Both on-demand and period (edition does not exist) |
| CBC.6006 | "Can not find product cfw" | Both on-demand and period (bare name invalid) |
| CBC.6006 | "Can not find product cfw.exp.eip" | All expansion package resource_specs |
| CBC.6006 | "Can not find product cfw.exp.eip.professional" | Edition-qualified expansion |
| CBC.6006 | "Can not find product cfw.exp.eip.standard" | Edition-qualified expansion |
| CBC.6006 | "Can not find product cfw.professional.exp.eip" | Prefix-qualified expansion |
| CBC.6006 | "Can not find product cfw.professional.eip" | Dot-qualified expansion |
| CBC.6006 | "Can not find product cfw.eip" | Simple expansion name |
| CBC.6006 | "Can not find product cfw.eip.expansion" | Expansion suffix |
| CBC.6006 | "Can not find product cfw.professional" | Wrong resource_type (exp.eip instead of cfw) |
| CBC.0100 | "region: must not be null" | Missing region field in product_infos |
| CBC.0100 | "id: must not be null" | Missing id field in product_infos |

---

## 7. CFW Fase 1 Recommendation

### Implement: `cfw-instance-payg` (instance-only template)

**Rationale:**
- Base instance `resource_spec` CONFIRMED for both `cfw.standard` (period) and `cfw.professional` (on-demand + period).
- On-demand pricing validated: `cfw.professional` at USD 0.36/hour.
- Period pricing validated: `cfw.standard` at USD 420/month, `cfw.professional` at USD 1,450/month.
- `product_infos_template` fully defined for on-demand (professional) and period (standard + professional).
- Instance-only template follows the same pattern as WAF, DDS, DCS Redis Fase 1.

### Proposed template: `cfw-instance-payg`

```json
{
  "cfw-instance-payg": {
    "service": "cfw",
    "region": "la-north-2",
    "display_name": "CFW Cloud Firewall instance pay-per-use",
    "billing_mode": "on_demand",
    "unit": "hour",
    "description": "CFW Cloud Firewall instance. Billed by edition per hour. Professional edition only (standard not available for pay-per-use).",
    "parameters": {
      "quantity": {
        "type": "integer",
        "required": true,
        "min": 1,
        "default": 1
      },
      "instance_resource_spec": {
        "type": "string",
        "required": true,
        "default": "cfw.professional",
        "description": "CFW instance resource_spec. Valid values: cfw.professional. Standard edition (cfw.standard) is NOT available for pay-per-use billing."
      },
      "monthly_hours": {
        "type": "number",
        "required": true,
        "min": 1,
        "default": 730,
        "description": "Usage duration in hours for pay-per-use CFW instance pricing."
      }
    },
    "product_infos_template": [
      {
        "id": "cfw-instance-{{instance_resource_spec}}-{{monthly_hours}}h-{{quantity}}",
        "cloud_service_type": "hws.service.type.cfw",
        "resource_type": "hws.resource.type.cfw",
        "resource_spec": "{{instance_resource_spec}}",
        "region": "{{region}}",
        "usage_factor": "usage_duration",
        "usage_value": "{{monthly_hours}}",
        "usage_measure_id": 4,
        "subscription_num": "{{quantity}}"
      }
    ],
    "status": "ready"
  }
}
```

### Deferred: Expansion packages

- `cfw-exp-eip-payg`, `cfw-exp-vpc-payg`, `cfw-exp-bandwidth-payg`: **BLOCKED** by unknown `resource_spec`.
- 22+ naming variants tested across on-demand and period APIs, all returned "Product not found".
- Expansion packages are only available with yearly/monthly billing per CFW documentation.
- Requires Price Calculator export, billing statement analysis, or CFW API inspection to discover the correct `resource_spec`.
- `service_cost_breakdown` for base + expansions deferred until expansion resource_specs are discovered.

### Deferred: Period (yearly/monthly) template

- A `cfw-instance-period` template could be implemented for yearly/monthly billing (standard + professional).
- This is a separate effort from the on-demand template and requires period-specific product_infos_template with `period_type`, `period_num`, `usage_factor: period_duration`, `usage_measure_id: 20`.

---

## 8. CFW Edition Feature Comparison (from product page)

| Feature | Standard | Professional |
|---|---|---|
| Internet border protection | Yes | Yes |
| Traffic intrusion detection | Yes | Yes |
| Protected EIPs at Internet boundary | 20 (expandable) | 50 (expandable) |
| Peak protection traffic at Internet boundary | 10 Mbit/s (expandable) | 50 Mbit/s (expandable) |
| Protected VPCs | 0 | 2 (expandable) |
| Max protection traffic between VPCs | N/A | 200 Mbit/s |
| Log storage space | 7 days | 7 days |
| North-south protection (EIPs) | Supported | Supported |
| East-west protection (inter-VPC + NAT) | Not supported | Supported |
| Intrusion prevention system (IPS) | Supported | Supported |
| Antivirus | Not supported | Supported |
| Custom IPS signature database | Not supported | Supported |
| Network packet capture | Not supported | Supported |
| Pay-per-use billing | Not available | Available |
| Yearly/monthly billing | Available | Available |

---

## 9. CFW Fase 1 Implementation Status

| Item | Status |
|---|---|
| `cfw-instance-payg` template | **IMPLEMENTED** in pricing-templates.json |
| `test-cfw-instance.mjs` | **IMPLEMENTED** (T1-T7) |
| `cfw.standard` period template | **DEFERRED** (not Fase 1) |
| `cfw.professional` period template | **DEFERRED** (not Fase 1) |
| EIP expansion template | **DEFERRED** (resource_spec unknown) |
| VPC expansion template | **DEFERRED** (resource_spec unknown) |
| Bandwidth expansion template | **DEFERRED** (resource_spec unknown) |
| Traffic expansion template | **DEFERRED** (resource_spec unknown) |
| `service_cost_breakdown` for CFW | **DEFERRED** (not Fase 1, requires expansion resource_specs) |
| `validate_availability` | **NOT APPLICABLE** (CFW has no ECS flavors) |
| `include_unavailable_reference_pricing` | **NOT APPLICABLE** (applies to ECS only) |

**Fase 1 scope**: `cfw.professional` on-demand only. All other billing modes, editions, and expansion packages are deferred.

---

## 10. Files Created/Modified

- **Created**: `docs/cfw-discovery.md` (this file)
- **Modified**: `docs/service-expansion-analysis.md` (updated CFW section with confirmed findings)
- **Modified**: `/root/.config/maas-pricing/pricing-templates.json` (added cfw-instance-payg template)
- **Created**: `test-cfw-instance.mjs` (CFW Fase 1 test suite T1-T7)
- **Modified**: `package.json` (added test-cfw-instance.mjs to test:unit, test:integration, test:all)

---

## 10. Summary

| Item | Status |
|---|---|
| CFW base instance resource_spec | **CONFIRMED**: `cfw.standard` (period), `cfw.professional` (on-demand + period) |
| CFW EIP expansion resource_spec | **PENDING**: 22+ patterns tested, all "Product not found" |
| CFW VPC expansion resource_spec | **PENDING**: 22+ patterns tested, all "Product not found" |
| CFW bandwidth expansion resource_spec | **PENDING**: 22+ patterns tested, all "Product not found" |
| CFW traffic expansion resource_spec | **PENDING**: not tested (different billing model) |
| resource_type confirmed | `hws.resource.type.cfw` (base), `hws.resource.type.cfw.exp.eip`, `hws.resource.type.cfw.exp.vpc`, `hws.resource.type.cfw.exp.bandwidth` |
| product_infos (on-demand professional) | **CONFIRMED**: USD 0.36/hour |
| product_infos (period standard) | **CONFIRMED**: USD 420/month |
| product_infos (period professional) | **CONFIRMED**: USD 1,450/month |
| Validated prices | Professional on-demand: USD 262.80/month; Standard period: USD 420/month; Professional period: USD 1,450/month |
| Errors | CBC.6006 for all expansion resource_specs and unavailable editions |
| Recommendation | **CFW Fase 1 IMPLEMENTED** as `cfw-instance-payg` (instance-only, professional on-demand). All other items deferred. |
