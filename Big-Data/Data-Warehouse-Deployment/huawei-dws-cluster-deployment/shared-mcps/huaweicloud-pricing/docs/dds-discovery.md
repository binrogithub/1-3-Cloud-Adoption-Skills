# DDS Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-05-29
**Region**: la-north-2
**Status**: Instance `resource_spec` CONFIRMED; Volume `resource_spec` NOT FOUND; **Instance-only template IMPLEMENTED**

---

## 1. BSS/OCE Catalog Findings

### 1.1 Cloud Service Type

| Field | Value |
|-------|-------|
| service_type_code | `hws.service.type.dds` |
| service_type_name | Document Database Service |

### 1.2 Resource Types (5 total)

| resource_type_code | name | Relevance |
|--------------------|------|-----------|
| `hws.resource.type.dds.vm` | DDS Instance | **PRIMARY - CONFIRMED** |
| `hws.resource.type.dds.volume` | DDS Cloud Disk | **BLOCKED - resource_spec not found** |
| `hws.resource.type.dds.cluster` | DDS Sharding | Not used directly (mongos/shard use dds.vm) |
| `hws.resource.type.dds.obs` | DDS Cloud Backup | **BLOCKED - resource_spec not found** |
| `hws.resource.type.dds.decmem` | DDS Dedicated Cloud Mem Resource | DeC variant, not in scope |

### 1.3 Usage Types

| resource_type_code | code | name | Role |
|--------------------|------|------|------|
| `hws.resource.type.dds.vm` | `duration` | Duration | Instance on-demand pricing |
| `hws.resource.type.dds.volume` | `duration` | Duration | Volume on-demand pricing |
| `hws.resource.type.dds.cluster` | `architecture` | architecture | Cluster sharding pricing |
| `hws.resource.type.dds.obs` | `size` | Capacity | Backup storage pricing |
| `hws.resource.type.dds.decmem` | `duration` | Duration | DeC memory pricing |

### 1.4 Measurement Units (relevant)

| measure_id | name | abbreviation | usage |
|------------|------|--------------|-------|
| 4 | Hour | h | usage_measure_id for on-demand |
| 10 | GB | G | usage_measure_id for backup size |
| 17 | GB | G | size_measure_id for volume capacity |
| 20 | Month | M | usage_measure_id for period/subscription |

### 1.5 DDS API Storage Types (la-north-2)

| name | az_status |
|------|-----------|
| `ULTRAHIGH` | normal in la-north-2a, la-north-2b, la-north-2c |

Only `ULTRAHIGH` storage is available in la-north-2 for DDS-Community engine.

---

## 2. DDS API Flavor Discovery

### 2.1 Flavor spec_code Format

`dds.mongodb.{flavor_family}.{size}.{mem_ratio}.{role}`

Where:
- `flavor_family`: `s6` (general-purpose), `c6` (compute-optimized)
- `size`: `medium`, `large`, `xlarge`, `2xlarge`, `4xlarge`, `8xlarge`
- `mem_ratio`: `2`, `4`, `8` (vCPU:memory ratio)
- `role`: `repset` (replica set), `mongos` (cluster router), `shard` (cluster shard)

### 2.2 Available Flavors in la-north-2 (48 total)

#### Replica Set (repset)

| spec_code | vCPUs | RAM (GB) |
|-----------|-------|----------|
| `dds.mongodb.s6.medium.4.repset` | 1 | 4 |
| `dds.mongodb.s6.large.2.repset` | 2 | 4 |
| `dds.mongodb.c6.large.4.repset` | 2 | 8 |
| `dds.mongodb.s6.large.4.repset` | 2 | 8 |
| `dds.mongodb.c6.large.8.repset` | 2 | 16 |
| `dds.mongodb.s6.xlarge.2.repset` | 4 | 8 |
| `dds.mongodb.c6.xlarge.4.repset` | 4 | 16 |
| `dds.mongodb.s6.xlarge.4.repset` | 4 | 16 |
| `dds.mongodb.c6.xlarge.8.repset` | 4 | 32 |
| `dds.mongodb.s6.2xlarge.2.repset` | 8 | 16 |
| `dds.mongodb.c6.2xlarge.4.repset` | 8 | 32 |
| `dds.mongodb.s6.2xlarge.4.repset` | 8 | 32 |
| `dds.mongodb.c6.2xlarge.8.repset` | 8 | 64 |
| `dds.mongodb.c6.4xlarge.4.repset` | 16 | 64 |
| `dds.mongodb.c6.4xlarge.8.repset` | 16 | 128 |
| `dds.mongodb.c6.8xlarge.8.repset` | 32 | 256 |

#### Cluster Mongos (mongos)

| spec_code | vCPUs | RAM (GB) |
|-----------|-------|----------|
| `dds.mongodb.s6.medium.4.mongos` | 1 | 4 |
| `dds.mongodb.s6.large.2.mongos` | 2 | 4 |
| `dds.mongodb.c6.large.4.mongos` | 2 | 8 |
| `dds.mongodb.s6.large.4.mongos` | 2 | 8 |
| `dds.mongodb.s6.xlarge.2.mongos` | 4 | 8 |
| `dds.mongodb.c6.xlarge.4.mongos` | 4 | 16 |
| `dds.mongodb.s6.xlarge.4.mongos` | 4 | 16 |
| `dds.mongodb.s6.2xlarge.2.mongos` | 8 | 16 |
| `dds.mongodb.s6.2xlarge.4.mongos` | 8 | 32 |

#### Cluster Shard (shard)

| spec_code | vCPUs | RAM (GB) |
|-----------|-------|----------|
| `dds.mongodb.c6.medium.4.shard` | 1 | 4 |
| `dds.mongodb.s6.medium.4.shard` | 1 | 4 |
| `dds.mongodb.s6.large.2.shard` | 2 | 4 |
| `dds.mongodb.c6.large.4.shard` | 2 | 8 |
| `dds.mongodb.s6.large.4.shard` | 2 | 8 |
| ... (similar to repset) |

---

## 3. Live Pricing Validation

### 3.1 DDS Instance (dds.vm) - CONFIRMED

**Working product_infos payload:**

```json
{
  "id": "dds-instance-{{resource_spec}}-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.dds",
  "resource_type": "hws.resource.type.dds.vm",
  "resource_spec": "dds.mongodb.s6.large.2.repset",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1
}
```

**Results:**

| spec_code | vCPUs | RAM | Hourly (USD) | Monthly 730h (USD) | product_id |
|-----------|-------|-----|-------------|---------------------|------------|
| `dds.mongodb.s6.medium.4.repset` | 1 | 4 GB | 0.140 | 102.20 | OFFI954210053768298496 |
| `dds.mongodb.s6.large.2.repset` | 2 | 4 GB | 0.253 | 184.69 | OFFI954195965870432260 |
| `dds.mongodb.c6.large.4.repset` | 2 | 8 GB | 0.403 | 294.34 | OFFI588635574172991497 |
| `dds.mongodb.s6.large.2.mongos` | 2 | 4 GB | 0.084 | 61.32 | OFFI954195965866237955 |
| `dds.mongodb.s6.large.2.shard` | 2 | 4 GB | 0.253 | 184.69 | OFFI954195965862043658 |

**Key observations:**
- All instance roles (repset, mongos, shard) use `hws.resource.type.dds.vm` with `usage_factor: "duration"`.
- Mongos is significantly cheaper than repset/shard for the same spec (USD 0.084 vs 0.253/hour for s6.large.2).
- Repset and shard have the same hourly rate for the same spec.
- `usage_factor` is `"duration"` (lowercase), consistent with BSS/OCE catalog usage_types.

### 3.2 DDS Volume (dds.volume) - NOT FOUND

**20+ resource_spec variants tested, all returned "Product not found":**

| resource_spec tried | Error |
|---------------------|-------|
| `dds.mongodb.volume.cloudssd` | Product not found |
| `dds.mongodb.volume.ssd` | Product not found |
| `dds.mongodb.volume.ultrahigh` | Product not found |
| `dds.mongodb.volume.ULTRAHIGH` | Product not found |
| `dds.mongodb.volume.ultra-high` | Product not found |
| `dds.mongodb.volume.ultra_high` | Product not found |
| `dds.mongodb.volume.high` | Product not found |
| `dds.mongodb.volume.general` | Product not found |
| `dds.mongodb.volume.ultrassd` | Product not found |
| `dds.mongodb.volume.essd` | Product not found |
| `dds.mongodb.volume.cloudSSD` | Product not found |
| `dds.mongodb.volume.CloudSSD` | Product not found |
| `dds.mongodb.volume.cloudssd.repset` | Product not found |
| `dds.mongodb.volume.ultrahigh.repset` | Product not found |
| `dds.mongodb.volume.repset.ultrahigh` | Product not found |
| `dds.mongodb.volume.ultrahigh.r2` | Product not found |
| `dds.mongodb.s6.large.2.repset.volume` | Product not found |
| `dds.mongodb.s6.large.2.repset.volume.cloudssd` | Product not found |
| `dds.mongodb.s6.large.2.repset.ultrahigh` | Product not found |
| `dds.mongodb.s6.large.2.repset.ultrahigh.volume` | Product not found |
| `dds.mongodb.s6.large.2.repset.disk` | Product not found |
| `dds.mongodb.s6.large.2.repset.storage` | Product not found |
| `dds.mongodb.s6.large.2.repset` (as volume) | Product not found |
| `dds.mongodb.ultrahigh` | Product not found |
| `ULTRAHIGH` | Product not found |
| `cloudssd` | Product not found |

Also tested with `usage_factor: "Duration"` (capital D) - same result.

**Root cause hypothesis:** The DDS volume `resource_spec` for BSS/OCE pricing API is not exposed by the DDS API and does not follow any predictable naming convention. It likely requires:
1. Huawei Cloud Price Calculator export (manual)
2. Billing statement analysis from an existing DDS instance
3. Huawei Cloud support ticket

This is the same pattern observed with RDS volume discovery - the `rds.mysql.volume.cloudssd` resource_spec was only discoverable through the Price Calculator, not through the RDS API or naming convention inference.

### 3.3 DDS Cluster (dds.cluster) - NOT FOUND

`dds.mongodb.s6.large.2.mongos` with `hws.resource.type.dds.cluster` and `usage_factor: "architecture"` returned "Product not found".

**Finding:** Cluster components (mongos, shard) are billed as `dds.vm` instances, not as `dds.cluster`. The `dds.cluster` resource type with `architecture` usage_factor may apply to a different billing dimension or may not be used for on-demand pricing.

### 3.4 DDS Backup (dds.obs) - NOT FOUND

`dds.mongodb.obs` with `hws.resource.type.dds.obs` and `usage_factor: "size"` returned "Product not found".

---

## 4. product_infos_template for DDS Instance (CONFIRMED)

```json
{
  "id": "dds-instance-{{instance_resource_spec}}-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.dds",
  "resource_type": "hws.resource.type.dds.vm",
  "resource_spec": "{{instance_resource_spec}}",
  "region": "{{region}}",
  "usage_factor": "duration",
  "usage_value": "{{monthly_hours}}",
  "usage_measure_id": 4,
  "subscription_num": "{{quantity}}"
}
```

**Default parameter values:**

| Parameter | Type | Default | Min | Description |
|-----------|------|---------|-----|-------------|
| quantity | integer | 1 | 1 | Number of DDS instances |
| instance_resource_spec | string | `dds.mongodb.s6.large.2.repset` | - | DDS instance spec_code from DDS API |
| monthly_hours | number | 730 | 1 | Usage duration in hours |

---

## 5. Gaps and Open Questions

| Gap | Severity | Notes |
|-----|----------|-------|
| Volume resource_spec unknown | **High** | 20+ naming variants tested. All "Product not found". Requires Price Calculator export or billing statement analysis. Same pattern as RDS volume discovery. |
| Backup (OBS) resource_spec unknown | Medium | `dds.mongodb.obs` failed. Likely requires same discovery method as volume. |
| Cluster (dds.cluster) usage unclear | Low | `hws.resource.type.dds.cluster` with `architecture` usage_factor not validated. Cluster components are billed as `dds.vm` instances. |
| Storage type naming mismatch | Medium | DDS API returns `ULTRAHIGH`; BSS/OCE pricing may use a different name (e.g., `cloudssd`). |
| Config node pricing | Low | Cluster config nodes may have separate pricing not yet discovered. |

---

## 6. Recommendation

**IMPLEMENT DDS Fase 1 with instance-only templates.**

Rationale:
- DDS instance `resource_spec` is confirmed for all roles (repset, mongos, shard) via live BSS/OCE pricing API.
- Instance pricing returns consistent results across multiple spec_codes.
- `product_infos_template` for instance is fully defined.
- Volume and backup templates are blocked by missing `resource_spec`, same as RDS volume was before Price Calculator export.

**Scope for DDS Fase 1:**
- Instance template for replica set: `dds-instance-repset-payg`
- Instance template for cluster mongos: `dds-instance-mongos-payg`
- Instance template for cluster shard: `dds-instance-shard-payg`
- Or a single parametric template: `dds-instance-payg` with `instance_resource_spec` parameter

**Deferred to future phases:**
- Volume (storage) template: blocked until `resource_spec` discovered
- Backup (OBS) template: blocked until `resource_spec` discovered
- Cluster `architecture` pricing: unclear usage
- Macro-template `dds-mongodb-small-payg` (instance + volume): blocked by volume

**Proposed template IDs:**
- `dds-instance-payg` (parametric, covers repset/mongos/shard)

**Proposed template status after implementation:** `ready` (instance only), volume remains `missing_product_infos_template`

---

## 7. Comparison with RDS Pattern

| Aspect | RDS | DDS |
|--------|-----|-----|
| Instance resource_type | `hws.resource.type.rds.vm` | `hws.resource.type.dds.vm` |
| Instance resource_spec | `rds.mysql.n1.large.2` | `dds.mongodb.s6.large.2.repset` |
| Instance usage_factor | `Duration` (capital D) | `duration` (lowercase) |
| Instance pricing | CONFIRMED | **CONFIRMED** |
| Volume resource_type | `hws.resource.type.rds.volume` | `hws.resource.type.dds.volume` |
| Volume resource_spec | `rds.mysql.volume.cloudssd` | **NOT FOUND** |
| Volume usage_factor | `Duration` (capital D) | `duration` (lowercase) |
| Volume pricing | CONFIRMED (via Price Calculator) | **BLOCKED** |
| Backup resource_type | `hws.resource.type.rds.obs` | `hws.resource.type.dds.obs` |
| Backup pricing | Not yet implemented | **BLOCKED** |

**Key difference:** RDS instance uses `Duration` (capital D) while DDS uses `duration` (lowercase). This is consistent with BSS/OCE catalog usage_types which returns lowercase `duration` for DDS and `Duration` for RDS.

---

## 8. Files NOT Modified

- `server.mjs` - no changes needed
- `template-tools.mjs` - no changes needed
- `pricing_catalog_helper.py` - no changes needed

---

## 9. Discovery Method

1. BSS/OCE catalog: `QueryServiceResources` for `hws.service.type.dds` → 5 resource types
2. BSS/OCE usage types: `QueryUsageTypes` for each DDS resource type → confirmed `duration`, `architecture`, `size`
3. DDS API: `GET /v3/{project_id}/flavors` → 48 spec_codes with format `dds.mongodb.{flavor}.{size}.{ratio}.{role}`
4. DDS API: `GET /v3/{project_id}/storage-type?engine_name=DDS-Community` → `ULTRAHIGH` only
5. Live pricing: `QueryOnDemandPrice` for instance specs → CONFIRMED
6. Live pricing: `QueryOnDemandPrice` for volume specs → 20+ variants, all "Product not found"
7. Live pricing: `QueryOnDemandPrice` for cluster/backup specs → "Product not found"

---

## 10. Implementation Record

**Date**: 2026-05-29
**Template ID**: `dds-instance-payg`
**Status**: `ready`

### Files Modified
- `/root/.config/maas-pricing/pricing-templates.json` — added `dds` service with `dds-instance-payg` template
- `package.json` — added `test-dds-instance.mjs` to test:unit, test:integration, test:all

### Files Created
- `test-dds-instance.mjs` — 7 test cases (T1-T7)

### Files NOT Modified
- `server.mjs` — no changes needed
- `template-tools.mjs` — no changes needed
- `pricing_catalog_helper.py` — no changes needed

### Test Results
- Unit (no live API): 4 passed, 0 failed, 3 skipped
- Integration (live API): 7 passed, 0 failed, 0 skipped
- Full suite: no regressions

### Validated Pricing (live BSS/OCE)
- `dds.mongodb.s6.medium.4.repset` × 730h = USD 102.20/month
- `dds.mongodb.s6.large.2.repset` × 730h = USD 184.69/month
- `dds.mongodb.c6.large.4.repset` × 730h = USD 294.34/month
- `dds.mongodb.s6.large.2.mongos` × 730h = USD 61.32/month
- `dds.mongodb.s6.large.2.shard` × 730h = USD 184.69/month
