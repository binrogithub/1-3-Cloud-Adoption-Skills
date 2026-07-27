# SFS Turbo Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-05-29
**Region**: la-north-2
**Status**: resource_spec CONFIRMED for Standard; on-demand pricing VALIDATED; **template IMPLEMENTED**

---

## 1. BSS/OCE Catalog Findings

### 1.1 Cloud Service Type

| Field | Value |
|-------|-------|
| service_type_code | `hws.service.type.sfs` |
| service_type_name | Scalable File Service |

### 1.2 Resource Types (3 total)

| resource_type_code | name | Relevance |
|--------------------|------|-----------|
| `hws.resource.type.sfs` | File Storage | SFS 1.0 (NFSv3), not in scope |
| `hws.resource.type.sfs.turbo` | SFS Turbo | **PRIMARY TARGET** |
| `hws.resource.type.sfs.pfs.edge` | SFS PFS on CloudPond | Edge variant, not in scope |

### 1.3 Usage Types for `hws.resource.type.sfs.turbo` (5 total)

| code | name | Role |
|------|------|------|
| `duration` | Duration | Period/subscription pricing |
| `period` | period | **On-demand pricing** (confirmed) |
| `trafficduration` | trafficduration | Traffic-based pricing (not validated) |
| `throughputduration` | throughput duration | Throughput-based pricing (not validated) |
| `cachebwduration` | cachebw duration | Cache bandwidth pricing (not validated) |

### 1.4 Measurement Units (relevant)

| measure_id | name | abbreviation | usage |
|------------|------|--------------|-------|
| 4 | Hour | h | usage_measure_id for on-demand |
| 17 | GB | G | size_measure_id for capacity |
| 20 | Month | M | usage_measure_id for period/subscription |

---

## 2. resource_spec Discovery

### 2.1 Candidates Tested

| resource_spec | On-Demand Result | Period Result | Status |
|---------------|-----------------|---------------|--------|
| `sfs.turbo.standard` | **SUCCESS** (usage_factor=period) | **SUCCESS** (usage_factor=duration) | **CONFIRMED** |
| `sfs.turbo` | Product not found | - | REJECTED |
| `sfs.turbo.standard.infra` | Product not found | - | REJECTED |
| `sfs.turbo.standard.enhanced` | Product not found | - | REJECTED |
| `sfs.turbo.enhanced` | Product not found | - | REJECTED |
| `sfs.turbo.standard_enhanced` | Product not found | - | REJECTED |
| `sfs.turbo.standard-enhanced` | Product not found | - | REJECTED |
| `sfs.turbo.hpc` | Product not found | - | REJECTED |
| `sfs.turbo.capacity` | Product not found | - | REJECTED |
| `sfs.turbo.standard.capacity` | Product not found | - | REJECTED |
| `STANDARD` | Product not found | - | REJECTED |
| `20_capacity` | Product not found | - | REJECTED |
| `sfs.turbo.20` / `21` / `22` | Product not found | - | REJECTED |
| `sfs.turbo.standard.a` | Product not found | - | REJECTED |
| `sfs.turbo.standard.la-north-2` | Product not found | - | REJECTED |
| `sfs.turbo.standard.la-north-2a` | Product not found | - | REJECTED |

### 2.2 Confirmed resource_spec

**`sfs.turbo.standard`** - SFS Turbo Standard type.

- Works for both on-demand and period/subscription pricing APIs.
- Enhanced and HPC types were NOT found with any naming convention tested.
- These may use different resource_spec values not yet discovered, or may not be available in la-north-2.

---

## 3. Live Pricing Validation

### 3.1 On-Demand Pricing (la-north-2)

**Working product_infos payload:**

```json
{
  "id": "sfs-turbo-sfs.turbo.standard-500gb-730h-1",
  "cloud_service_type": "hws.service.type.sfs",
  "resource_type": "hws.resource.type.sfs.turbo",
  "resource_spec": "sfs.turbo.standard",
  "region": "la-north-2",
  "usage_factor": "period",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1,
  "resource_size": 500,
  "size_measure_id": 17
}
```

**Results:**

| Test | capacity_gb | hours | Price (USD) | Hourly Rate (USD/h) | Per GB-hour (USD) |
|------|-------------|-------|-------------|---------------------|-------------------|
| 500 GB × 1h | 500 | 1 | 0.062222 | 0.062222 | 0.000124444 |
| 500 GB × 730h | 500 | 730 | 45.42206 | 0.062222 | 0.000124444 |
| 1000 GB × 730h | 1000 | 730 | 90.84412 | 0.124444 | 0.000124444 |

**product_id**: `OFFI583902170677723137`

**Key observations:**
- Pricing is linear with both capacity (GB) and duration (hours).
- 1000 GB is exactly 2x the 500 GB price, confirming no tier breakpoints at these levels.
- usage_factor must be `"period"` for on-demand, NOT `"Duration"` or `"duration"`.
- `resource_size` carries capacity in GB; `size_measure_id` = 17 (GB).

### 3.2 Period/Subscription Pricing (la-north-2)

**Working product_infos payload:**

```json
{
  "id": "sfs-turbo-std-1m-1",
  "cloud_service_type": "hws.service.type.sfs",
  "resource_type": "hws.resource.type.sfs.turbo",
  "resource_spec": "sfs.turbo.standard",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 1,
  "usage_measure_id": 20,
  "subscription_num": 1,
  "resource_size": 500,
  "size_measure_id": 17,
  "period_type": 2,
  "period_num": 1
}
```

**Result:** USD 38.6 for 500 GB × 1 month.

**product_id**: `OFFI1002772120637911041`

**Key observations:**
- Period pricing uses `usage_factor: "duration"` and `usage_measure_id: 20` (Month).
- On-demand monthly estimate (USD 45.42) > period price (USD 38.6), consistent with typical on-demand premium.

### 3.3 Failed On-Demand Queries

| usage_factor | resource_spec | Error |
|-------------|---------------|-------|
| `Duration` | `sfs.turbo.standard` | Product not found |
| `duration` | `sfs.turbo.standard` | Product not found |
| `trafficduration` | `sfs.turbo.standard` | Product not found |
| `throughputduration` | `sfs.turbo.standard` | Product not found |
| `cachebwduration` | `sfs.turbo.standard` | Product not found |
| `period` | `sfs.turbo.enhanced` | Product not found |
| `period` | `sfs.turbo.hpc` | Product not found |

---

## 4. product_infos_template for SFS Turbo Standard

```json
{
  "id": "sfs-turbo-{{resource_spec}}-{{capacity_gb}}gb-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.sfs",
  "resource_type": "hws.resource.type.sfs.turbo",
  "resource_spec": "{{resource_spec}}",
  "region": "{{region}}",
  "usage_factor": "period",
  "usage_value": "{{monthly_hours}}",
  "usage_measure_id": 4,
  "subscription_num": "{{quantity}}",
  "resource_size": "{{capacity_gb}}",
  "size_measure_id": 17
}
```

**Default parameter values:**

| Parameter | Type | Default | Min | Description |
|-----------|------|---------|-----|-------------|
| quantity | integer | 1 | 1 | Number of SFS Turbo file systems |
| resource_spec | string | `sfs.turbo.standard` | - | SFS Turbo type spec |
| capacity_gb | number | 500 | 500 | Provisioned capacity in GB |
| monthly_hours | number | 730 | 1 | Usage duration in hours |

---

## 5. Gaps and Open Questions

| Gap | Severity | Notes |
|-----|----------|-------|
| Enhanced type resource_spec unknown | Medium | `sfs.turbo.standard.enhanced` and variants all fail. May require Huawei Cloud Price Calculator export or support ticket. |
| HPC type resource_spec unknown | Medium | `sfs.turbo.hpc` and variants all fail. Same discovery method needed. |
| Throughput/traffic pricing not validated | Low | `throughputduration`, `trafficduration`, `cachebwduration` usage_types exist but no working resource_spec found. May require separate resource_spec or may not be billable in la-north-2. |
| Minimum capacity constraint | Low | SFS Turbo Standard requires minimum 500 GB. Template should validate `capacity_gb >= 500`. |
| usage_factor asymmetry | Info | On-demand uses `period`; period/subscription uses `duration`. This is unusual and must be documented in template notes. |

---

## 6. Recommendation

**IMPLEMENT SFS Turbo Standard template now.**

Rationale:
- resource_spec `sfs.turbo.standard` is confirmed via live BSS/OCE pricing API.
- On-demand pricing returns consistent, linear results.
- product_infos_template is fully defined.
- Only 1 resource type (`hws.resource.type.sfs.turbo`) needed.
- Pattern is similar to existing EVS template (capacity-based + duration).

**Scope for initial template:**
- SFS Turbo Standard only (`resource_spec: sfs.turbo.standard`).
- Capacity-based on-demand pricing.
- Enhanced and HPC types deferred until resource_spec discovered.

**Proposed template ID:** `sfs-turbo-standard-payg`

**Proposed template status after implementation:** `ready`

---

## 7. Implementation Record

**Date**: 2026-05-29
**Template ID**: `sfs-turbo-standard-payg`
**Status**: `ready`

### Files Modified
- `/root/.config/maas-pricing/pricing-templates.json` — added `sfs` service with `sfs-turbo-standard-payg` template
- `package.json` — added `test-sfs-turbo-standard.mjs` to test:unit, test:integration, test:all

### Files Created
- `test-sfs-turbo-standard.mjs` — 7 test cases (T1-T7)

### Files NOT Modified
- `server.mjs` — no changes needed
- `template-tools.mjs` — no changes needed
- `pricing_catalog_helper.py` — no changes needed

### Test Results
- Unit (no live API): 4 passed, 0 failed, 3 skipped
- Integration (live API): 7 passed, 0 failed, 0 skipped
- Full suite: no regressions

### Validated Pricing (live BSS/OCE)
- 500 GB × 730h = USD 45.42/month
- 1000 GB × 730h = USD 90.84/month
- Linear scaling confirmed
