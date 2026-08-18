# ECS Benchmark Discovery

## Region

LA-Mexico City2 / `la-north-2`

## Benchmark ECS Instances

### 1. ECS BD (Base de Datos)

| Attribute | Value |
|-----------|-------|
| Flavor | `m6.3xlarge.8` |
| OS | SUSE Linux Enterprise Server 15 SP7 |
| System Disk | GPSSD 700 GB |
| Compute resource_spec | `m6.3xlarge.8.linux` |
| License resource_spec | `suse.12` |

### 2. ECS Sesiones

| Attribute | Value |
|-----------|-------|
| Flavor | `c6.3xlarge.4` |
| OS | AlmaLinux 9.4 |
| System Disk | GPSSD 300 GB |
| Compute resource_spec | `c6.3xlarge.4.linux` |
| License resource_spec | N/A (AlmaLinux is free, no license productInfo) |

### 3. ECS Aplicaciones

| Attribute | Value |
|-----------|-------|
| Flavor | `s6.xlarge.4` |
| OS | AlmaLinux 9.4 |
| System Disk | GPSSD 200 GB |
| Compute resource_spec | `s6.xlarge.4.linux` |
| License resource_spec | N/A (AlmaLinux is free, no license productInfo) |

## BSS/OCE ProductInfo Structure

### ECS Compute

```json
{
  "cloud_service_type": "hws.service.type.ec2",
  "resource_type": "hws.resource.type.vm",
  "resource_spec": "<flavor>.linux",
  "usage_factor": "Duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1
}
```

### OS License (SUSE)

```json
{
  "cloud_service_type": "hws.service.type.ec2",
  "resource_type": "hws.resource.type.vm.image",
  "resource_spec": "suse.12",
  "usage_factor": "Duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1
}
```

### Key Observations

1. ECS compute uses `hws.service.type.ec2` / `hws.resource.type.vm`.
2. OS license uses `hws.service.type.ec2` / `hws.resource.type.vm.image` (same cloud_service_type, different resource_type).
3. SUSE generates a **separate** productInfo from compute. Both must be priced and summed.
4. AlmaLinux does **NOT** generate a license productInfo. Cost = USD 0. No template needed.
5. `suse.12` resource_spec corresponds to SUSE Linux Enterprise Server 15 SP7 in Price Calculator.
6. The `id` field is **required** by BSS/OCE API (CBC.0100 error if null).

## BSS/OCE On-Demand Pricing Validation

| Flavor | resource_spec | BSS/OCE On-demand (USD/month) | Quotation (USD/month) | BSS/Quote Ratio |
|--------|--------------|-------------------------------|----------------------|-----------------|
| m6.3xlarge.8 | m6.3xlarge.8.linux | 494.94 | 356.36 | 1.389 |
| c6.3xlarge.4 | c6.3xlarge.4.linux | 376.68 | 271.21 | 1.389 |
| s6.xlarge.4 | s6.xlarge.4.linux | 87.60 | 63.07 | 1.389 |
| SUSE license | suse.12 | 109.50 | 55.00 | 1.991 |

## BSS/OCE Period Pricing Validation (ROOT CAUSE INVESTIGATION)

**Date**: 2026-06-01

Period API endpoint: `POST /v2/bills/ratings/period-resources/subscribe-rate`

Period productInfo (Pattern A, duration-preserving, same as HSS):

```json
{
  "id": "ecs-<flavor>-period",
  "cloud_service_type": "hws.service.type.ec2",
  "resource_type": "hws.resource.type.vm",
  "resource_spec": "<flavor>.linux",
  "region": "la-north-2",
  "usage_factor": "Duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1,
  "period_type": 2,
  "period_num": 1
}
```

### Period API Results

| Flavor | resource_spec | Period API (USD/month) | Quotation (USD/month) | Match? |
|--------|--------------|------------------------|----------------------|--------|
| m6.3xlarge.8 | m6.3xlarge.8.linux | 356.36 | 356.36 | EXACT |
| c6.3xlarge.4 | c6.3xlarge.4.linux | 271.21 | 271.21 | EXACT |
| s6.xlarge.4 | s6.xlarge.4.linux | 63.07 | 63.07 | EXACT |
| SUSE license | suse.12 | 55.00 | 55.00 | EXACT |

**All four items match the quotation EXACTLY via the period API.**

### Period API Product IDs

| resource_spec | product_id (period) | product_id (on-demand) |
|--------------|---------------------|------------------------|
| m6.3xlarge.8.linux | OFFI959429066893660167 | OFFI588674131579551746 |
| c6.3xlarge.4.linux | OFFI959429066461646854 | OFFI579285845618147346 |
| s6.xlarge.4.linux | OFFI959429065966718979 | OFFI579284585010589711 |
| suse.12 | OFFI1012176672711426049 | OFFI1012176672833060870 |

Note: Period and on-demand APIs return **different product_ids** for the same resource_spec. This confirms they are distinct pricing entries in the BSS/OCE catalog.

## Root Cause Analysis

### Confirmed Root Cause

The BSS/OCE on-demand API (`/v2/bills/ratings/on-demand-resources`) returns **pay-per-use hourly rates** that include a premium over monthly subscription prices. The Price Calculator quotation uses **period (monthly subscription) billing** for ECS, which produces lower prices.

**This is NOT caused by:**
- Incorrect endpoint (both endpoints are valid, they return different billing models)
- Incorrect parser (parser correctly extracts `amount` from on-demand, `official_website_amount` from period)
- Missing fields in productInfo (all required fields are present)
- API bug or limitation (the on-demand API correctly returns the on-demand rate)
- Discount not visible (no discounts exist in either response; `discount_amount=0`, `discount_rating_results=[]`)
- Currency or tax differences (same currency, same region)

**This IS caused by:**
- **Billing model mismatch**: The quotation uses period billing (monthly subscription) while the MCP templates use on-demand billing (pay-per-use)
- On-demand ECS compute carries a **~39% premium** over period billing (ratio 1.389)
- On-demand SUSE license carries a **~99% premium** over period billing (ratio 1.991)

### On-Demand vs Period Price Comparison

| Item | On-demand (USD/month) | Period (USD/month) | On-demand Premium | Hourly Rate (on-demand) |
|------|----------------------|-------------------|-------------------|------------------------|
| m6.3xlarge.8.linux | 494.94 | 356.36 | +39% | 0.678 USD/h |
| c6.3xlarge.4.linux | 376.68 | 271.21 | +39% | 0.516 USD/h |
| s6.xlarge.4.linux | 87.60 | 63.07 | +39% | 0.120 USD/h |
| suse.12 | 109.50 | 55.00 | +99% | 0.150 USD/h |

### Period API Behavior Notes

1. The period API **ignores `usage_value`** for ECS compute. With `usage_value=1` or `usage_value=730`, the period API returns the same monthly subscription price (356.36 for m6.3xlarge.8.linux). The price is determined solely by `period_type` and `period_num`.
2. The period API requires `id` field in productInfo (CBC.0100 error if null).
3. The period API requires `period_type` and `period_num` in productInfo.
4. The period API does NOT support `inquiry_precision` (not passed in payload).
5. ECS compute uses **Pattern A** (duration-preserving) for period billing, same as HSS.

## BSS/OCE Response Field Analysis

### On-Demand API Response (Complete Fields)

```json
{
  "amount": 494.94,
  "discount_amount": 0,
  "official_website_amount": 494.94,
  "measure_id": 1,
  "currency": "USD",
  "product_rating_results": [
    {
      "id": "<product_info_id>",
      "product_id": "OFFI588674131579551746",
      "amount": 494.94,
      "discount_amount": 0,
      "official_website_amount": 494.94,
      "measure_id": 1,
      "discount_rating_results": []
    }
  ]
}
```

**Fields present**: `amount`, `discount_amount`, `official_website_amount`, `measure_id`, `currency`, `product_rating_results[]`
**Fields absent**: `optional_discount_rating_results`, `official_website_rating_result`, `installment_*`

**Key observation**: `amount` == `official_website_amount` for all ECS on-demand queries. No discounts are available.

### Period API Response (Complete Fields)

```json
{
  "official_website_rating_result": {
    "official_website_amount": 356.36,
    "installment_official_website_amount": null,
    "installment_period_type": null,
    "measure_id": 1,
    "product_rating_results": [
      {
        "id": "<product_info_id>",
        "product_id": "OFFI959429066893660167",
        "official_website_amount": 356.36,
        "measure_id": 1,
        "installment_official_website_amount": null,
        "installment_period_type": null
      }
    ]
  },
  "optional_discount_rating_results": [],
  "currency": "USD"
}
```

**Fields present**: `official_website_rating_result.official_website_amount`, `official_website_rating_result.installment_official_website_amount`, `official_website_rating_result.installment_period_type`, `official_website_rating_result.measure_id`, `optional_discount_rating_results`, `currency`
**Fields absent**: Top-level `amount`, `discount_amount`, `official_website_amount`

## MCP Parser Analysis

### Current Parser (On-Demand)

**File**: `server.mjs:2802`
**Primary field**: `data.amount` (top-level `amount` from BSS/OCE on-demand response)
**Also extracted**: `data.official_website_amount`, `data.discount_amount` (for informational display)

Since `amount` == `official_website_amount` for ECS, switching between them would NOT change the result.

### Current Parser (Period)

**File**: `server.mjs:96-108` (`extractPeriodAmounts()`)
**Primary field**: `data.official_website_rating_result.official_website_amount`
**Also extracted**: `data.optional_discount_rating_results[0].official_website_amount` (if present)

### Monthly Conversion Logic

**On-demand** (`server.mjs:2809-2818`): Since ECS productInfos have `usage_factor=Duration` and `usage_measure_id=4`, the `hasDurationUsage` flag is `true`, so `monthlyAmount = apiAmount` directly (no hourly-to-monthly conversion).

**Period** (`server.mjs:2931-2943`): For `period_type=2` (month), `monthlyAmount = periodAmount / periodNum`. For `period_num=1`, this is `monthlyAmount = periodAmount`.

## Inquiry Precision Test

| inquiry_precision | m6.3xlarge.8.linux (on-demand) |
|-------------------|-------------------------------|
| 0 (default) | 494.94 |
| 1 (high) | 494.94 |

**Result**: `inquiry_precision` does NOT affect the on-demand price for ECS. The discrepancy is NOT caused by precision settings.

## Templates Implemented

1. **`ecs-flavor-payg`** (service: ecs, billing_mode: on_demand, status: ready): ECS compute flavor pay-per-use. Parameters: `quantity`, `ecs_resource_spec`, `monthly_hours`.
2. **`ecs-os-license-payg`** (service: ecs, billing_mode: on_demand, status: ready): ECS OS license pay-per-use. Parameters: `quantity`, `os_resource_spec`, `monthly_hours`.
3. **`ecs-flavor-period`** (service: ecs, billing_mode: period, status: ready): ECS compute flavor monthly subscription. Parameters: `quantity`, `ecs_resource_spec`, `period_type`, `period_num`, `monthly_hours`. Pattern A period payload. Matches quotation exactly.
4. **`ecs-os-license-period`** (service: ecs, billing_mode: period, status: ready): ECS OS license monthly subscription. Parameters: `quantity`, `os_resource_spec`, `period_type`, `period_num`, `monthly_hours`. Pattern A period payload. Matches quotation exactly.

## Templates Previously NOT Implemented (NOW IMPLEMENTED)

1. ~~**`ecs-flavor-period`** (service: ecs, billing_mode: period): ECS compute flavor monthly subscription.~~ **IMPLEMENTED**. Pattern A period payload with `period_type=2, period_num=1`. Matches quotation exactly.
2. ~~**`ecs-os-license-period`** (service: ecs, billing_mode: period): ECS OS license monthly subscription.~~ **IMPLEMENTED**. Pattern A period payload with `period_type=2, period_num=1`. Matches quotation exactly.

## Not Implemented (Deferred)

- Macro-template combining ECS compute + OS license + system disk
- Automatic OS detection (SUSE vs AlmaLinux vs Windows)
- AlmaLinux license template (not needed, cost = USD 0)
- Windows license template (resource_spec TBD)
- System disk expansion (GPSSD already exists as `evs-gpssd-gb-payg`)

## Recommendation

1. ~~**Add `ecs-flavor-period` template** (HIGH PRIORITY)~~ **IMPLEMENTED**: Period billing matches quotation exactly. Pattern A payload (duration-preserving with `period_type=2, period_num=1`). Same approach as `hss-host-protection-period`.
2. ~~**Add `ecs-os-license-period` template** (HIGH PRIORITY)~~ **IMPLEMENTED**: Period billing matches quotation exactly for SUSE. Pattern A payload.
3. **Keep `ecs-flavor-payg` and `ecs-os-license-payg`** for architects who need on-demand estimates.
4. **Add warning** in on-demand template output when price is significantly higher than period equivalent (e.g., "+39% over monthly subscription for compute, +99% for SUSE").
5. **Update `minimum-quote-benchmark.md`** to show that ECS period billing closes the gap (same as HSS period closed the HSS gap).
