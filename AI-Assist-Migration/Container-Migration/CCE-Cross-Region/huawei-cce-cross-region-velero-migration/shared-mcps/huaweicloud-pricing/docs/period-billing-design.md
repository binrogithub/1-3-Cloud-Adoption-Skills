# Period Billing Design for huaweicloud-pricing MCP

**Date**: 2026-06-01
**Status**: Phase 1 IMPLEMENTED (HSS period + ECS/SUSE period)
**Author**: Technical audit and design analysis

---

## 1. Problem Statement

The MCP currently only supports on-demand (pay-per-use) billing through template-based tools (`EstimateTemplateOnDemandPrice`, `EstimateArchitectureOnDemandPrice`). The benchmark quotation for HSS uses period (monthly subscription) billing, which produces a different (lower) price than on-demand for the same resource.

**Confirmed gap**: HSS Premium 3 PCS = USD 41.40/month (period) vs USD 61.32/month (on-demand). The MCP only returns the on-demand price.

---

## 2. Current State Analysis

### 2.1 What exists today

| Component | Period Support | Notes |
|---|---|---|
| `pricing_api_helper.py` | YES | Supports `period-price` operation → `/v2/bills/ratings/period-resources/subscribe-rate` |
| `server.mjs` → `callHuaweiPricingApi()` | YES | Routes `period-price` to the period API path |
| `QueryPeriodPrice` tool | YES | Raw tool accepts `product_infos` and calls period API |
| `QueryOnDemandPrice` tool | YES | Raw tool for on-demand API |
| `pricing-templates.json` | NO | All 22 templates have `billing_mode: "on_demand"` |
| `template-tools.mjs` → `renderProductInfosFromTemplate()` | NO | Renders templates but does not route to period API |
| `EstimateTemplateOnDemandPrice` | NO | Hardcoded to `/v2/bills/ratings/on-demand-resources` |
| `EstimateArchitectureOnDemandPrice` | NO | Hardcoded to `/v2/bills/ratings/on-demand-resources` |

**Conclusion**: The raw API plumbing for period billing exists (`QueryPeriodPrice`, `callHuaweiPricingApi`, `pricing_api_helper.py`), but the template-driven pricing pipeline does NOT route to it. Templates have no `period_type`/`period_num` fields, and the estimate tools always call the on-demand endpoint.

### 2.2 Template system current fields

Each template's `product_infos_template` supports these fields via placeholders:

| Field | Example | Used by |
|---|---|---|
| `cloud_service_type` | `hws.service.type.hss` | All |
| `resource_type` | `hws.resource.type.hss` | All |
| `resource_spec` | `hss.version.premium` | All |
| `region` | `la-north-2` | All |
| `usage_factor` | `duration` | All |
| `usage_value` | `730` | All |
| `usage_measure_id` | `4` | All |
| `subscription_num` | `3` | HSS, CFW, WAF |
| `resource_size` | `2400` | CBR, VPN |
| `size_measure_id` | `17` | CBR, EVS, SFS |
| `resource_size_measure_id` | `17` | VPN |

**Missing for period billing**: `period_type`, `period_num`, and the ability to switch `usage_factor`/`usage_value`/`usage_measure_id` to period-specific values.

---

## 3. BSS/OCE Period API Payload Analysis

### 3.1 Two distinct period payload patterns

BSS/OCE period billing uses the endpoint `/v2/bills/ratings/period-resources/subscribe-rate`. However, the `product_infos` payload structure varies by service:

#### Pattern A: Duration-preserving (HSS)

The `usage_factor`, `usage_value`, and `usage_measure_id` remain the same as on-demand. Only `period_type` and `period_num` are added:

```json
{
  "id": "hss-host-protection-hss.version.premium-730h-1",
  "cloud_service_type": "hws.service.type.hss",
  "resource_type": "hws.resource.type.hss",
  "resource_spec": "hss.version.premium",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 3,
  "period_type": 2,
  "period_num": 1
}
```

**Result**: USD 41.40/month (3 PCS × 1 month)

#### Pattern B: Period-duration (CFW)

The `usage_factor` changes to `period_duration`, `usage_value` becomes `1`, and `usage_measure_id` changes to `20`:

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

**Implication**: Period templates cannot use a single generic transformation. Each service may require its own `product_infos_template` for period billing. This strongly favors **Option A** (separate templates).

### 3.2 `period_type` values

| Value | Meaning |
|---|---|
| 2 | Month |
| 3 | Year |

### 3.3 `usage_measure_id` values for period

| Value | Meaning | Used by |
|---|---|---|
| 20 | Period (month/year) | CFW, likely others |
| 4 | Hour (preserved from on-demand) | HSS |

---

## 4. HSS Period Reference Case

### 4.1 Exact payload for HSS Premium 3 PCS 1 month

```json
{
  "project_id": "<HUAWEI_PROJECT_ID>",
  "product_infos": [
    {
      "id": "hss-host-protection-hss.version.premium-period-3",
      "cloud_service_type": "hws.service.type.hss",
      "resource_type": "hws.resource.type.hss",
      "resource_spec": "hss.version.premium",
      "region": "la-north-2",
      "usage_factor": "duration",
      "usage_value": 730,
      "usage_measure_id": 4,
      "subscription_num": 3,
      "period_type": 2,
      "period_num": 1
    }
  ]
}
```

**API endpoint**: `POST /v2/bills/ratings/period-resources/subscribe-rate`

**Expected result**: `amount = 41.40`, `official_website_amount = 41.40`

### 4.2 Comparison

| Billing Mode | API Endpoint | Price (3 PCS) | Delta vs Benchmark |
|---|---|---|---|
| On-demand | `/v2/bills/ratings/on-demand-resources` | USD 61.32 | +48.7% |
| Period | `/v2/bills/ratings/period-resources/subscribe-rate` | USD 41.40 | 0.0% (exact match) |

---

## 5. Services Affected by Lack of Period Billing

### 5.1 Services where period is required or preferred

| Service | Period-Only? | Period Preferred? | Impact | Priority |
|---|---|---|---|---|
| **HSS** | No | YES (benchmark uses it) | 48.7% price gap for premium; benchmark mismatch | **HIGH** |
| **CFW Standard** | YES | YES | Cannot price at all on-demand; `cfw.standard` returns CBC.6006 | **HIGH** |
| **CFW Expansion Packs** | YES | YES | EIP/VPC/bandwidth expansion only available period | **MEDIUM** |
| **ECS** | No | Common for production | Period typically 30-50% cheaper; many real deployments use yearly/monthly | **MEDIUM** |
| **RDS** | No | Common for production | Period pricing is standard for database instances | **MEDIUM** |
| **WAF Instance** | No | Possible | Both modes available; period may be preferred for dedicated instances | **LOW** |
| **NAT Gateway** | No | Possible | Both modes available | **LOW** |
| **VPN Gateway** | No | Possible | Both modes available | **LOW** |
| **DCS Redis** | No | Possible | Both modes available | **LOW** |
| **DDS** | No | Possible | Both modes available | **LOW** |
| **SFS Turbo** | No | Unlikely | On-demand is standard for file systems | **LOW** |
| **OS License (SUSE)** | YES | YES | SUSE/RHEL licenses are period-only add-ons to ECS | **MEDIUM** |

### 5.2 Summary of impact

- **2 services are period-only** (CFW Standard, CFW Expansion Packs) and **cannot be priced at all** with current MCP.
- **1 service has benchmark mismatch** (HSS) because the benchmark uses period billing.
- **4+ services commonly use period in production** (ECS, RDS, OS licenses, CFW Professional) but are only available on-demand in the MCP.
- The gap is **most acute for HSS** (benchmark validation) and **CFW Standard** (cannot price at all).

---

## 6. Design Options

### Option A: Separate Period Templates (RECOMMENDED)

Add new templates with `-period` suffix, each with its own `product_infos_template` containing period-specific fields.

**Example templates**:
- `hss-host-protection-period` (billing_mode: `period`)
- `cfw-standard-period` (billing_mode: `period`)
- `cfw-professional-period` (billing_mode: `period`)
- `ecs-linux-2vcpu-4gb-period` (billing_mode: `period`)

**Template structure**:
```json
{
  "hss-host-protection-period": {
    "service": "hss",
    "region": "la-north-2",
    "display_name": "HSS Host Protection monthly subscription",
    "billing_mode": "period",
    "unit": "host-month",
    "parameters": {
      "quantity": { "type": "integer", "required": true, "min": 1, "default": 1 },
      "hss_resource_spec": { "type": "string", "required": true, "default": "hss.version.premium" },
      "period_type": { "type": "integer", "required": true, "default": 2 },
      "period_num": { "type": "integer", "required": true, "min": 1, "default": 1 }
    },
    "product_infos_template": [
      {
        "id": "hss-host-protection-{{hss_resource_spec}}-period-{{quantity}}",
        "cloud_service_type": "hws.service.type.hss",
        "resource_type": "hws.resource.type.hss",
        "resource_spec": "{{hss_resource_spec}}",
        "region": "{{region}}",
        "usage_factor": "duration",
        "usage_value": 730,
        "usage_measure_id": 4,
        "subscription_num": "{{quantity}}",
        "period_type": "{{period_type}}",
        "period_num": "{{period_num}}"
      }
    ],
    "status": "ready"
  }
}
```

**Changes required**:
1. `pricing-templates.json`: Add period templates (no modification to existing templates)
2. `server.mjs`: Add `EstimateTemplatePeriodPrice` tool OR extend `EstimateTemplateOnDemandPrice` to route based on `billing_mode`
3. `server.mjs`: Add `EstimateArchitecturePeriodPrice` tool OR extend `EstimateArchitectureOnDemandPrice` to support mixed billing
4. `template-tools.mjs`: No changes needed (rendering is billing-mode agnostic)

**Pros**:
- Zero impact on existing on-demand templates
- Each period template has explicit `product_infos_template` matching its service's period payload format
- Clear separation: `-payg` vs `-period` naming convention
- No risk of breaking existing behavior
- Handles both Pattern A (HSS) and Pattern B (CFW) naturally

**Cons**:
- Template proliferation (potentially 2x templates for services supporting both modes)
- Architect must choose the right template explicitly
- Mixed architectures require both `-payg` and `-period` components

### Option B: Extend Existing Templates with `billing_mode` Switch

Add `billing_mode` parameter to existing templates, with conditional `product_infos_template` selection.

**Example**:
```json
{
  "hss-host-protection-payg": {
    "billing_mode": "on_demand",
    "parameters": {
      "billing_mode": { "type": "string", "enum": ["on_demand", "period"], "default": "on_demand" },
      "period_type": { "type": "integer", "default": 2 },
      "period_num": { "type": "integer", "default": 1 }
    },
    "product_infos_template_on_demand": [...],
    "product_infos_template_period": [...]
  }
}
```

**Changes required**:
1. `pricing-templates.json`: Add `product_infos_template_period` and period parameters to templates
2. `server.mjs`: Route to period API when `billing_mode=period`
3. `template-tools.mjs`: Modify `renderProductInfosFromTemplate` to select template by billing_mode

**Pros**:
- Single template per service
- Architect can switch billing mode with a parameter change

**Cons**:
- **Breaks the constraint**: Modifies `template-tools.mjs` and `pricing-templates.json` structure
- Requires conditional template selection logic in rendering
- Pattern A vs Pattern B payload differences make conditional logic complex
- Risk of breaking existing on-demand behavior if not carefully implemented
- `billing_mode` in template metadata becomes ambiguous (is it the template's default or a switch?)

### Option C: Defer Period Billing, Document the Gap

Keep period billing out of the MCP and document the difference in benchmark docs.

**Changes required**:
1. `docs/minimum-quote-benchmark.md`: Already documents the HSS gap
2. No code changes

**Pros**:
- Zero implementation risk
- No code changes

**Cons**:
- Cannot price CFW Standard at all
- Cannot match HSS benchmark
- Cannot support common production billing modes (ECS/RDS monthly)
- Growing gap as more services need period billing

---

## 7. Recommended Design: Option A (Separate Templates)

### 7.1 Rationale

1. **Payload diversity**: Period `product_infos` differ by service (Pattern A vs Pattern B). Separate templates naturally accommodate this.
2. **Zero regression risk**: Existing on-demand templates are untouched. No changes to `template-tools.mjs` rendering logic.
3. **Explicit intent**: Architect explicitly selects `-period` template, making billing mode clear in architecture definitions.
4. **Incremental**: Can implement HSS period first, then CFW, then ECS/RDS as needed.
5. **Minimal code changes**: Only `server.mjs` needs new routing logic; `template-tools.mjs` and Python helpers are unchanged.

### 7.2 Implementation scope

#### Phase 1: HSS Period (minimum viable)

**New template**: `hss-host-protection-period`

**New tool**: `EstimateTemplatePeriodPrice`
- Renders template, calls `/v2/bills/ratings/period-resources/subscribe-rate`
- Returns `period_amount` (the subscription cost for `period_num` × `period_type`)
- Computes `monthly_amount = period_amount / period_num` (when `period_type=2`)

**New tool**: `EstimateArchitecturePeriodPrice`
- Same as `EstimateArchitectureOnDemandPrice` but routes period templates to period API
- Supports mixed architectures by routing each component based on its `billing_mode`

**Alternative**: Extend `EstimateArchitectureOnDemandPrice` to auto-detect `billing_mode` from template and route accordingly. This is simpler for the architect but requires more careful implementation.

#### Phase 2: CFW Period

**New templates**: `cfw-standard-period`, `cfw-professional-period`

#### Phase 3: ECS/RDS Period

**New templates**: `ecs-linux-2vcpu-4gb-period`, `rds-mysql-instance-period`, etc.

---

## 8. `monthly_total` Semantics

### 8.1 Current semantics

`monthly_total` = sum of all `monthly_amount` values, where:
- For on-demand with `usage_factor=duration`: `monthly_amount = api_amount` (already covers `usage_value` hours)
- For on-demand without duration: `monthly_amount = api_amount × monthly_hours`

### 8.2 Proposed semantics for period

For period billing:
- `period_amount` = the API response `amount` (cost for `period_num` × `period_type`)
- When `period_type=2` (month): `monthly_amount = period_amount / period_num`
- When `period_type=3` (year): `monthly_amount = period_amount / (period_num × 12)`

### 8.3 Mixed architecture `monthly_total`

When an architecture contains both on-demand and period components:

```
monthly_total = sum(on_demand.monthly_amount) + sum(period.monthly_amount)
```

This is a **normalized monthly cost** that allows comparison but has caveats:
- On-demand is a variable cost (scales with actual usage hours)
- Period is a fixed cost (committed for the subscription duration)
- Mixing them in a single `monthly_total` can be misleading

### 8.4 Proposed output structure

```json
{
  "pricing_summary": {
    "monthly_total": 128.40,
    "monthly_total_on_demand": 87.60,
    "monthly_total_period": 41.40,
    "annual_simple_total": 1540.80,
    "priced_components_count": 2,
    "billing_modes": ["on_demand", "period"]
  },
  "priced_components": [
    {
      "template_id": "cbr-server-backup-vault-gb-payg",
      "billing_mode": "on_demand",
      "monthly_amount": 87.60,
      "pricing_basis": {
        "api_amount": 87.60,
        "api_amount_interpretation": "API amount interpreted as already covering the requested usage_value in product_infos.",
        "billing_mode": "on_demand"
      }
    },
    {
      "template_id": "hss-host-protection-period",
      "billing_mode": "period",
      "monthly_amount": 41.40,
      "period_amount": 41.40,
      "pricing_basis": {
        "api_amount": 41.40,
        "api_amount_interpretation": "API amount is the period subscription cost for period_num=1 month.",
        "billing_mode": "period",
        "period_type": 2,
        "period_num": 1,
        "period_type_name": "month"
      }
    }
  ]
}
```

### 8.5 Semantic preservation

- **`monthly_total`**: Continues to represent the normalized monthly cost estimate. Its interpretation does not change.
- **New fields**: `monthly_total_on_demand` and `monthly_total_period` provide decomposition without changing `monthly_total` semantics.
- **Warning**: When both billing modes are present, add a warning: `"Architecture contains both on-demand and period billing. monthly_total is a normalized estimate: on-demand costs vary with usage, period costs are fixed for the subscription duration."`

### 8.6 Fields NOT to change

- `monthly_total_calculated` → keep as-is (sum of all monthly_amounts)
- `monthly_total_validated` → keep as-is
- `annual_simple_total_calculated` → keep as-is (monthly_total × 12)

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Period API returns different structure than on-demand | ~~LOW~~ **HIGH** (caused T3/T8/T9 failures) | `extractPeriodAmounts()` helper normalizes period response shape; see Section 14 |
| Pattern A vs Pattern B payload differences | MEDIUM | Separate templates with explicit `product_infos_template` per billing mode |
| `monthly_total` mixing variable and fixed costs | MEDIUM | Add decomposition fields and warning; document in output |
| Template proliferation | LOW | Acceptable trade-off for safety; naming convention `-period` makes it clear |
| Period price includes base capacity (CFW Professional) | MEDIUM | Document in template `notes`; architect must understand what's included |
| `period_type=3` (yearly) discount calculation | LOW | Start with `period_type=2` (monthly) only; add yearly later |
| Regression in on-demand pricing | LOW | Zero changes to existing templates and on-demand code paths |
| `inquiry_precision` not supported by period API | LOW | Period API does not accept `inquiry_precision`; skip it for period calls |

---

## 10. Proposed Tests

### 10.1 Unit tests (no live API)

| Test ID | Description | Validates |
|---|---|---|
| UT-P1 | `ListPricingTemplates` includes `hss-host-protection-period` | Template registered |
| UT-P2 | `RenderProductInfosFromTemplate` for `hss-host-protection-period` produces correct payload with `period_type=2`, `period_num=1` | Template rendering |
| UT-P3 | `RenderProductInfosFromTemplate` for `hss-host-protection-period` with `quantity=3` produces `subscription_num=3` | Quantity scaling |
| UT-P4 | `RenderProductInfosFromTemplate` for `cfw-standard-period` produces Pattern B payload (`usage_factor=period_duration`, `usage_measure_id=20`) | Pattern B rendering |
| UT-P5 | `EstimateArchitectureCostDraft` with mixed on-demand + period components | Draft mapping |
| UT-P6 | Period template `billing_mode` field is `period` | Metadata correctness |

### 10.2 Live API tests

| Test ID | Description | Validates |
|---|---|---|
| LT-P1 | `EstimateTemplatePeriodPrice` for HSS Premium 3 PCS = USD 41.40 | HSS period benchmark match |
| LT-P2 | `EstimateTemplatePeriodPrice` for HSS Advanced 3 PCS = USD 13.50 | HSS period scaling |
| LT-P3 | `EstimateTemplatePeriodPrice` for CFW Standard = USD 420.00 | CFW period-only pricing |
| LT-P4 | `EstimateTemplatePeriodPrice` for CFW Professional = USD 1,450.00 | CFW period pricing |
| LT-P5 | `EstimateArchitecturePeriodPrice` with HSS period + CBR on-demand = USD 128.40 total | Mixed architecture |
| LT-P6 | `monthly_total_on_demand` + `monthly_total_period` = `monthly_total` | Decomposition correctness |

### 10.3 Retrocompatibility tests

| Test ID | Description | Validates |
|---|---|---|
| RT-P1 | `EstimateTemplateOnDemandPrice` for HSS Premium 3 PCS still returns USD 61.32 | On-demand unchanged |
| RT-P2 | `EstimateArchitectureOnDemandPrice` with only on-demand components unchanged | Architecture on-demand unchanged |
| RT-P3 | `monthly_total` semantics unchanged for on-demand-only architectures | No semantic drift |
| RT-P4 | All existing test suites pass | Full regression |

### 10.4 Validation tests

| Test ID | Description | Validates |
|---|---|---|
| VT-P1 | `hss-host-protection-period` with `period_type=3` (yearly) returns 12-month cost | Yearly period |
| VT-P2 | Mixed architecture warning is present when both billing modes exist | Warning system |
| VT-P3 | `monthly_total_on_demand` and `monthly_total_period` are present in mixed architecture | Decomposition fields |
| VT-P4 | Period-only architecture has `monthly_total_on_demand = 0` | Edge case |

---

## 11. Files to Create/Modify

### Phase 1 (HSS Period)

| File | Action | Description |
|---|---|---|
| `pricing-templates.json` | MODIFY | Add `hss-host-protection-period` template |
| `server.mjs` | MODIFY | Add `EstimateTemplatePeriodPrice` and `EstimateArchitecturePeriodPrice` tools (or extend existing tools with billing_mode routing) |
| `test-hss-host-protection.mjs` | MODIFY | Add period billing test cases |
| `docs/period-billing-design.md` | CREATE | This document |
| `docs/minimum-quote-benchmark.md` | MODIFY | Update with period pricing closure |

### Phase 2 (CFW Period)

| File | Action | Description |
|---|---|---|
| `pricing-templates.json` | MODIFY | Add `cfw-standard-period`, `cfw-professional-period` templates |
| `test-cfw-instance.mjs` | MODIFY | Add period test cases |

### Phase 3 (ECS/RDS Period)

| File | Action | Description |
|---|---|---|
| `pricing-templates.json` | MODIFY | Add ECS/RDS period templates |
| Corresponding test files | MODIFY | Add period test cases |

### Files NOT modified

| File | Reason |
|---|---|
| `template-tools.mjs` | Rendering is billing-mode agnostic; no changes needed |
| `pricing_api_helper.py` | Already supports `period-price` operation |
| `pricing_catalog_helper.py` | No catalog changes needed for period billing |

---

## 12. Implementation Status

### Phase 1: HSS Period — IMPLEMENTED

**Date**: 2026-06-01

**New template**: `hss-host-protection-period` (billing_mode: period, status: ready)

**New tools**:
- `EstimateTemplatePeriodPrice`: Renders template, calls `/v2/bills/ratings/period-resources/subscribe-rate`, returns `period_amount` and `monthly_amount` (normalized to monthly).
- `EstimateArchitecturePeriodPrice`: Supports mixed on-demand and period components. Routes each component based on its template `billing_mode`. Adds `monthly_total_on_demand`, `monthly_total_period`, `billing_modes`, and `warnings` for mixed architectures.

**Routing guards**:
- `EstimateTemplateOnDemandPrice` rejects period templates with `ROUTING_ERROR`.
- `EstimateTemplatePeriodPrice` rejects on-demand templates with `ROUTING_ERROR`.

**Validation**:
- HSS Premium 3 PCS period 1 month = USD 41.40 (EXACT MATCH with benchmark quote)
- HSS Premium 3 PCS on-demand 730h = USD 61.32 (unchanged)
- Period billing closes the HSS benchmark gap

**Files modified**:
- `/root/.config/maas-pricing/pricing-templates.json`: Added `hss-host-protection-period` template
- `server.mjs`: Added `EstimateTemplatePeriodPrice`, `EstimateArchitecturePeriodPrice`, routing guards
- `config/pricing-templates.example.json`: Added `hss-host-protection-period` template
- `test-hss-period-billing.mjs`: New test file with 9 test cases
- `package.json`: Added test-hss-period-billing.mjs to test scripts
- `docs/period-billing-design.md`: Updated status to IMPLEMENTED
- `docs/hss-discovery.md`: Updated with period template info
- `docs/minimum-quote-benchmark.md`: Updated with period gap closure
- `docs/service-expansion-analysis.md`: Updated HSS entry

**monthly_total semantics**:
- `monthly_total` = `monthly_total_on_demand` + `monthly_total_period` (normalized monthly cost)
- `monthly_total_on_demand` and `monthly_total_period` provide decomposition
- Warning when both billing modes are present in an architecture
- Existing `monthly_total_calculated` and `monthly_total_validated` unchanged in `EstimateArchitectureOnDemandPrice`

**Limitations**:
- Only HSS and ECS/SUSE period templates implemented (Phase 1)
- CFW period, RDS period NOT implemented
- `EstimateArchitectureOnDemandPrice` does NOT route period components (use `EstimateArchitecturePeriodPrice` for mixed architectures)
- `inquiry_precision` not supported by period API (not passed)
- Yearly period (`period_type=3`) supported but not validated against real API

---

## 15. ECS/SUSE Period Implementation (Phase 1 Extension)

**Date**: 2026-06-01

### 15.1 New Templates

| Template | Service | billing_mode | resource_type | Status |
|----------|---------|-------------|---------------|--------|
| `ecs-flavor-period` | ecs | period | hws.resource.type.vm | ready |
| `ecs-os-license-period` | ecs | period | hws.resource.type.vm.image | ready |

### 15.2 Template Design

Both templates use **Pattern A** (duration-preserving), identical to HSS period:
- `usage_factor=Duration`, `usage_value=730`, `usage_measure_id=4` (same as on-demand)
- `period_type=2` (month), `period_num=1` added for period billing
- Period API ignores `usage_value` for ECS; price determined by `period_type` and `period_num`

### 15.3 Parameters

**ecs-flavor-period**: `quantity`, `ecs_resource_spec` (default: s6.xlarge.4.linux), `period_type` (default: 2), `period_num` (default: 1), `monthly_hours` (default: 730)

**ecs-os-license-period**: `quantity`, `os_resource_spec` (default: suse.12), `period_type` (default: 2), `period_num` (default: 1), `monthly_hours` (default: 730)

### 15.4 Validation Results

| resource_spec | Period API (USD/month) | Quotation (USD/month) | Match |
|--------------|------------------------|----------------------|-------|
| m6.3xlarge.8.linux | 356.36 | 356.36 | EXACT |
| c6.3xlarge.4.linux | 271.21 | 271.21 | EXACT |
| s6.xlarge.4.linux | 63.07 | 63.07 | EXACT |
| suse.12 | 55.00 | 55.00 | EXACT |

### 15.5 Routing Guards

- `EstimateTemplateOnDemandPrice` rejects `ecs-flavor-period` and `ecs-os-license-period` with `ROUTING_ERROR`
- `EstimateTemplatePeriodPrice` rejects `ecs-flavor-payg` and `ecs-os-license-payg` with `ROUTING_ERROR`

### 15.6 Mixed Architecture Support

`EstimateArchitecturePeriodPrice` supports mixed period + on-demand components:
- ECS compute + SUSE license → period (ecs-flavor-period, ecs-os-license-period)
- EVS GPSSD → on-demand (evs-gpssd-gb-payg)
- `monthly_total = monthly_total_period + monthly_total_on_demand`
- Warning present when both billing modes exist

### 15.7 Files Modified

- `/root/.config/maas-pricing/pricing-templates.json`: Added `ecs-flavor-period` and `ecs-os-license-period` templates
- `config/pricing-templates.example.json`: Added same templates
- `test-ecs-period-billing.mjs`: New test file with 12 test cases (T1-T12)
- `package.json`: Added test-ecs-period-billing.mjs to test scripts
- `docs/ecs-benchmark-discovery.md`: Updated with period template info
- `docs/minimum-quote-benchmark.md`: Updated with period gap closure
- `docs/service-expansion-analysis.md`: Updated ECS entry
- `docs/period-billing-design.md`: Updated status and added Section 15

### 15.8 Not Implemented (Deferred)

- Macro-template combining ECS compute + OS license + system disk (ecs-instance-with-system-disk)
- Windows license period template (resource_spec TBD)
- Automatic OS detection (SUSE vs AlmaLinux vs Windows)
- On-demand premium warning in payg template output

---

## 13. Next Step Recommendation

**Implement HSS period first** (Phase 1 only).

Rationale:
- Closes the benchmark gap (highest priority)
- Validates the design with the simplest case (Pattern A payload)
- Minimal scope: 1 new template, 1-2 new tools or routing extension
- Can be validated against the known benchmark value (USD 41.40)
- CFW Standard (period-only) and CFW Professional period can follow in Phase 2
- ECS/RDS period are lower priority (nice-to-have, not blocking benchmark validation)

---

## 14. BSS/OCE Response Shape Difference (Root Cause of T3/T8/T9 Failures)

**Date**: 2026-06-01 (post-implementation fix)

### 14.1 On-demand API response shape

Endpoint: `POST /v2/bills/ratings/on-demand-resources`

```json
{
  "amount": 61.32,
  "discount_amount": 0.0,
  "official_website_amount": 61.32,
  "measure_id": 1,
  "currency": "USD",
  "product_rating_results": [...]
}
```

Amounts are at the **top level**: `amount`, `official_website_amount`, `discount_amount`.

### 14.2 Period API response shape

Endpoint: `POST /v2/bills/ratings/period-resources/subscribe-rate`

```json
{
  "official_website_rating_result": {
    "official_website_amount": 41.4,
    "installment_official_website_amount": null,
    "installment_period_type": null,
    "measure_id": 1,
    "product_rating_results": [...]
  },
  "optional_discount_rating_results": [],
  "currency": "USD"
}
```

Amounts are **nested** inside `official_website_rating_result` and `optional_discount_rating_results`. There is **no top-level `amount` field**.

### 14.3 Root cause

The initial implementation of `EstimateTemplatePeriodPrice` and `EstimateArchitecturePeriodPrice` extracted amounts using the on-demand path:

```js
const data = helperData.data || {};
const periodAmount = data.amount ?? null;  // null — field does not exist in period response
const officialPeriodAmount = data.official_website_amount ?? null;  // null — nested under official_website_rating_result
```

This caused `monthly_amount = null` for all period components, resulting in:
- T3: `monthly must be ~41.40, got null`
- T8: `HSS must have positive monthly_amount`
- T9: `monthly_total_period must be positive`

### 14.4 Fix: `extractPeriodAmounts()` helper

Added `extractPeriodAmounts(data)` in `server.mjs` to normalize the period response shape:

```js
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
```

Used in both `EstimateTemplatePeriodPrice` and `EstimateArchitecturePeriodPrice` (period branch only). On-demand parsing is unchanged.

### 14.5 Impact

- Zero impact on on-demand pricing (same code path, same response shape).
- Period components now correctly extract `official_website_amount` from `official_website_rating_result`.
- `monthly_amount` is correctly computed from the period amount.
- `monthly_total_period` correctly accumulates in `EstimateArchitecturePeriodPrice`.
