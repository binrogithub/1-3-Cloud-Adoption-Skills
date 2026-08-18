# EVS GPSSD Discovery Report

## Summary

EVS General Purpose SSD (GPSSD) `resource_spec` **CONFIRMED** as `GPSSD` via live BSS/OCE pricing API in `la-north-2`. Template `evs-gpssd-gb-payg` implemented with status `ready`.

## Discovery Process

### Step 1: Existing EVS SSD Template Analysis

The existing `evs-ssd-gb-payg` template uses:

| Field | Value |
|-------|-------|
| `cloud_service_type` | `hws.service.type.ebs` |
| `resource_type` | `hws.resource.type.volume` |
| `resource_spec` | `SSD` |
| `usage_factor` | `Duration` |
| `usage_measure_id` | 4 (Hour) |
| `resource_size` | `{{size_gb}}` |
| `size_measure_id` | 17 (GB) |

### Step 2: EVS Volume Types API Query (la-north-2)

| Volume Type | Available AZs | Sold Out |
|-------------|---------------|----------|
| ESSD | la-north-2a, la-north-2b | Yes (both AZs) |
| GPSSD2 | la-north-2a, la-north-2b, la-north-2c | No |
| GPSSD | la-north-2a, la-north-2b, la-north-2c | No |
| SSD | la-north-2a, la-north-2b, la-north-2c | No |
| SAS | la-north-2a, la-north-2b, la-north-2c | No |

### Step 3: BSS/OCE resource_spec Candidates Tested

| resource_spec | Result | Error |
|---------------|--------|-------|
| `GPSSD` | **SUCCESS** | - |
| `GPSSD2` | FAILED | CBC.6006: "Can not find product GPSSD2" |
| `SAS` | SUCCESS (different tier) | - |

### Step 4: BSS/OCE Usage Types for EVS Volume

| usage_factor code | Name | service_type_code |
|--------------------|------|-------------------|
| `Duration` | Duration | hws.service.type.ebs |
| `iops_duration` | iops duration | hws.service.type.ebs |
| `throughput_duration` | throughput duration | hws.service.type.ebs |

`Duration` confirmed as the correct usage_factor for GPSSD capacity billing.

### Step 5: Price Validation (live BSS/OCE, la-north-2)

| Size (GB) | BSS/OCE API (USD) | Quotation (USD) | Diff | % Diff |
|-----------|---------------------|------------------|------|--------|
| 200 | 18.98 | 18.80 | +0.18 | +0.96% |
| 300 | 28.47 | 28.20 | +0.27 | +0.96% |
| 700 | 66.43 | 65.80 | +0.63 | +0.96% |
| 100 | 9.49 | - | - | - |

### Step 6: Linearity Verification

- 100 GB = USD 9.49 → per GB = USD 0.0949
- 200 GB = USD 18.98 → per GB = USD 0.0949
- 300 GB = USD 28.47 → per GB = USD 0.0949
- 700 GB = USD 66.43 → per GB = USD 0.0949

**Price scales linearly by GB** at USD 0.0949/GB/month (730h).

The quotation uses USD 0.0940/GB/month (likely rounded hourly rate). The ~0.96% difference is within normal tolerance for Huawei Cloud pricing (quotation likely uses a rounded per-hour rate).

## Confirmed product_info Fields

| Field | Value |
|-------|-------|
| `cloud_service_type` | `hws.service.type.ebs` |
| `resource_type` | `hws.resource.type.volume` |
| `resource_spec` | `GPSSD` |
| `usage_factor` | `Duration` |
| `usage_measure_id` | 4 |
| `resource_size` | `{{size_gb}}` |
| `size_measure_id` | 17 |

## Template Implementation

- **template_id**: `evs-gpssd-gb-payg`
- **service**: `evs`
- **display_name**: `EVS General Purpose SSD pay-per-use`
- **billing_mode**: `on_demand`
- **unit**: `GB-hour`
- **status**: `ready`
- **Parameters**: `quantity` (int, default 1), `size_gb` (number, default 100), `monthly_hours` (number, default 730)

## Blocked Items

- **GPSSD2**: `resource_spec` "GPSSD2" returns CBC.6006 "Can not find product GPSSD2" in BSS/OCE. Available in EVS API but not in pricing catalog.
- **ESSD**: Sold out in la-north-2a and la-north-2b. Not tested for pricing.

## Test Results

All 8 tests pass (4 unit + 4 live API):

- T1: ListPricingTemplates includes evs-gpssd-gb-payg ✓
- T2: RenderProductInfosFromTemplate with defaults ✓
- T3: RenderProductInfosFromTemplate size_gb=200 ✓
- T4: EstimateTemplateOnDemandPrice 200GB ≈ USD 18.98 ✓
- T5: EstimateTemplateOnDemandPrice 300GB ≈ USD 28.47 ✓
- T6: EstimateTemplateOnDemandPrice 700GB ≈ USD 66.43 ✓
- T7: Architecture 700+300+200 GB ≈ USD 113.88 ✓
- T8: Both evs-ssd-gb-payg and evs-gpssd-gb-payg coexist ✓
