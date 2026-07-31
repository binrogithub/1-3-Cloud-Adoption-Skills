# GaussDB Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-05-29
**Region**: la-north-2 (also tested sa-brazil-1, ap-southeast-1)
**Status**: Instance `resource_spec` NOT FOUND; Volume `resource_spec` NOT FOUND; Cluster `resource_spec` NOT FOUND; **ALL BLOCKED**

---

## 1. BSS/OCE Catalog Findings

### 1.1 Cloud Service Types (2 discovered)

GaussDB spans TWO service type codes in the BSS/OCE catalog:

| Field | Value | Notes |
|-------|-------|-------|
| service_type_code | `hws.service.type.gaussdb` | Newer GaussDB service type (4 resource types) |
| service_type_code | `hws.service.type.taurus` | Legacy TaurusDB service type (15 resource types) |

**Critical finding**: GaussDB MySQL (formerly TaurusDB) is primarily billed under `hws.service.type.taurus`, NOT `hws.service.type.gaussdb`. The `gaussdb` service type appears to be a newer/separate product registration. Both were tested; neither returned valid pricing.

### 1.2 Resource Types under `hws.service.type.gaussdb` (4 total)

| resource_type_code | name | Relevance |
|--------------------|------|-----------|
| `hws.resource.type.gaussdb.vm` | GaussDB VM | **PRIMARY - BLOCKED (resource_spec not found)** |
| `hws.resource.type.gaussdb.volume` | GaussDB Storage | **BLOCKED (resource_spec not found)** |
| `hws.resource.type.gaussdb.cluster` | GaussDB Cluster | **BLOCKED (resource_spec not found)** |
| `hws.resource.type.gaussdb.obs` | GaussDB Backup Space | **BLOCKED (resource_spec not found)** |

### 1.3 Resource Types under `hws.service.type.taurus` (15 total)

| resource_type_code | name | Relevance |
|--------------------|------|-----------|
| `hws.resource.type.taurus.vm` | TaurusDB VM | GaussDB MySQL instance (legacy billing) |
| `hws.resource.type.taurus.volume` | TaurusDB Storage | GaussDB MySQL storage (legacy billing) |
| `hws.resource.type.taurus.obs` | TaurusDB Backup Space | GaussDB MySQL backup (legacy billing) |
| `hws.resource.type.taurus.cluster` | TaurusDB Cluster | GaussDB MySQL cluster |
| `hws.resource.type.opengauss.vm` | GaussDB for openGauss VM | openGauss instance |
| `hws.resource.type.opengauss.volume` | GaussDB for openGauss Storage | openGauss storage |
| `hws.resource.type.opengauss.obs` | GaussDB for openGauss Backup Space | openGauss backup |
| `hws.resource.type.tauruspg.vm` | TaurusDB PostgreSQL VM | GaussDB PostgreSQL instance |
| `hws.resource.type.tauruspg.volume` | TaurusDB PostgreSQL Storage | GaussDB PostgreSQL storage |
| `hws.resource.type.tauruspg.obs` | TaurusDB PostgreSQL Backup Space | GaussDB PostgreSQL backup |
| `hws.resource.type.tauruspg.instance` | TaurusDB PostgreSQL Instance | PostgreSQL instance type |
| `hws.resource.type.taurus.serverless` | TaurusDB Serverless VM | Serverless mode |
| `hws.resource.type.taurus.monitor` | TaurusDB Database Monitor | Database monitoring |
| `hws.resource.type.taurus.flow` | TaurusDB Flow | Data flow |
| `hws.resource.type.database.hcso.fullstackdec` | Database HCSO project | HCSO variant, not in scope |

### 1.4 Usage Types

#### Under `hws.service.type.gaussdb`

| resource_type_code | code | name | Role |
|--------------------|------|------|------|
| `hws.resource.type.gaussdb.vm` | `duration` | Duration | Instance on-demand pricing |
| `hws.resource.type.gaussdb.vm` | `count` | count | Instance subscription/period pricing |
| `hws.resource.type.gaussdb.volume` | `duration` | Duration | Volume on-demand pricing |
| `hws.resource.type.gaussdb.cluster` | `architecture` | architecture | Cluster distributed pricing |
| `hws.resource.type.gaussdb.obs` | `size` | Capacity | Backup storage pricing |

#### Under `hws.service.type.taurus`

| resource_type_code | code | name | Role |
|--------------------|------|------|------|
| `hws.resource.type.taurus.vm` | `duration` | Duration | Instance on-demand pricing |

### 1.5 Measurement Units (relevant)

| measure_id | name | abbreviation | usage |
|------------|------|--------------|-------|
| 4 | Hour | h | usage_measure_id for on-demand |
| 10 | GB | G | usage_measure_id for backup size |
| 17 | GB | G | size_measure_id for volume capacity |
| 20 | Month | M | usage_measure_id for period/subscription |

---

## 2. Live Pricing Validation

### 2.1 GaussDB Instance (gaussdb.vm) - NOT FOUND

**30+ resource_spec variants tested, all returned "Product not found":**

#### Under `hws.service.type.gaussdb` / `hws.resource.type.gaussdb.vm`

| resource_spec tried | usage_factor | Error |
|---------------------|-------------|-------|
| `gaussdb.mysql.x1.large.2` | duration | Product not found |
| `gaussdb.mysql.x1.large.2` | Duration | Product not found |
| `gaussdb.mysql.x2.large.4` | duration | Product not found |
| `gaussdb.mysql.x1.2xlarge.4` | duration | Product not found |
| `gaussdb.mysql.n1.large.2` | duration | Product not found |
| `gaussdb.mysql.s6.large.2` | Duration | Product not found |
| `gaussdb.mysql.c6.large.2` | Duration | Product not found |
| `gaussdb.mysql.x1.large.2.ha` | duration | Product not found |
| `gaussdb.mysql.x1.large.2.ha` | Duration | Product not found |
| `gaussdb.mysql.n1.large.2.ha` | duration | Product not found |
| `gaussdb.mysql.x1.large.4` | duration | Product not found |
| `gaussdb.mysql.x1.xlarge.2` | duration | Product not found |
| `gaussdb.mysql.x1.medium.2` | duration | Product not found |
| `gaussdb.mysql.x1.small.2` | duration | Product not found |
| `gaussdb.mysql.x1.large.2.in` | duration | Product not found |
| `gaussdb.mysql.x1.large.2.cluster` | duration | Product not found |
| `gaussdb.mysql.x1.large.2.single` | duration | Product not found |
| `gaussdb.mysql.x1.large.2.primary` | duration | Product not found |
| `gaussdb.mysql.x1.large.2.ro` | duration | Product not found |
| `gaussdb.mysql.x1.large.2.economy` | duration | Product not found |
| `gaussdb.mysql.x1.large.2.ha` | count | Product not found |
| `gaussdb.opengauss.x1.large.2` | duration | Product not found |
| `gaussdb-mysql.x1.large.2` | duration | Product not found |
| `gaussdb-mysql.x1.large.2.ha` | duration | Product not found |

#### Under `hws.service.type.taurus` / `hws.resource.type.taurus.vm`

| resource_spec tried | usage_factor | Error |
|---------------------|-------------|-------|
| `taurus.mysql.x1.large.2` | duration | Product not found |
| `taurus.mysql.x1.large.2` | Duration | Product not found |
| `taurus.mysql.n1.large.2` | duration | Product not found |
| `taurus.mysql.large.2` | duration | Product not found |
| `taurus.mysql.x1.large.2.ha` | duration | Product not found |
| `taurus.mysql.x1.large.2.in` | duration | Product not found |

#### Under `hws.service.type.taurus` / `hws.resource.type.opengauss.vm`

| resource_spec tried | usage_factor | Error |
|---------------------|-------------|-------|
| `opengauss.x1.large.2` | duration | Product not found |
| `gaussdb.opengauss.x1.large.2` | duration | Product not found |

#### Cross-region tests (all "Product not found")

| region | service_type | resource_spec | Error |
|--------|-------------|---------------|-------|
| sa-brazil-1 | gaussdb | `gaussdb.mysql.x1.large.2` | Product not found |
| ap-southeast-1 | gaussdb | `gaussdb.mysql.x1.large.2` | Product not found |
| ap-southeast-1 | taurus | `taurus.mysql.x1.large.2` | Product not found |

### 2.2 GaussDB Volume (gaussdb.volume) - NOT TESTED

Volume testing was skipped because instance resource_spec was not found. Without a confirmed instance resource_spec, volume discovery has no reference point.

### 2.3 GaussDB Cluster (gaussdb.cluster) - NOT TESTED

Cluster testing was skipped. No evidence of cluster-specific pricing separate from instance billing.

---

## 3. Comparison with Other Database Services

| Aspect | RDS | DDS | GaussDB |
|--------|-----|-----|---------|
| Service type code | `hws.service.type.rds` | `hws.service.type.dds` | `hws.service.type.gaussdb` + `hws.service.type.taurus` |
| Instance resource_type | `hws.resource.type.rds.vm` | `hws.resource.type.dds.vm` | `hws.resource.type.gaussdb.vm` / `hws.resource.type.taurus.vm` |
| Instance resource_spec | `rds.mysql.n1.large.2` | `dds.mongodb.s6.large.2.repset` | **NOT FOUND** |
| Instance usage_factor | `Duration` (capital D) | `duration` (lowercase) | `duration` (catalog) / `Duration` (catalog) — both tested |
| Instance pricing | CONFIRMED | CONFIRMED | **BLOCKED** |
| Volume resource_spec | `rds.mysql.volume.cloudssd` | **NOT FOUND** | **NOT FOUND** |
| Volume pricing | CONFIRMED (via Price Calculator) | BLOCKED | **BLOCKED** |
| Backup resource_spec | Not yet implemented | **NOT FOUND** | **NOT FOUND** |
| Dual service type | No | No | **Yes** (gaussdb + taurus) |

**Key differences:**
1. GaussDB spans TWO service type codes in BSS/OCE (`gaussdb` and `taurus`), unlike RDS and DDS which have a single service type.
2. Even the INSTANCE resource_spec is not found for GaussDB, whereas DDS instance was confirmed. This makes GaussDB harder to implement than DDS.
3. The `taurus` service type has 15 resource types covering MySQL, openGauss, PostgreSQL, Serverless, Monitor, and Flow — much more complex than RDS or DDS.
4. Both `duration` and `Duration` usage_factor variants were tested for gaussdb.vm; both failed.

---

## 4. Root Cause Hypothesis

The GaussDB/TaurusDB `resource_spec` for BSS/OCE pricing API is not discoverable through:

1. **Naming convention inference**: 30+ naming variants tested across both service types, multiple regions, and usage_factor values. All returned "Product not found".
2. **BSS/OCE catalog API**: The catalog confirms service types and resource types exist, but does not expose the `resource_spec` values needed for pricing.
3. **Cross-service pattern matching**: Neither RDS-like (`n1.large.2`), DDS-like (`s6.large.2.repset`), nor documented GaussDB API format (`x1.large.2`) worked.

**Possible explanations:**
1. The `resource_spec` format is completely different from any known naming convention (e.g., uses internal product IDs instead of spec codes).
2. GaussDB MySQL may not be available for pay-per-use in the tested regions (la-north-2, sa-brazil-1, ap-southeast-1).
3. The `hws.service.type.gaussdb` service type may not have any products registered yet in the BSS/OCE pricing catalog.
4. The `hws.service.type.taurus` service type may use a different resource_spec format that is not documented.

**Required discovery methods (same as DDS volume):**
1. Huawei Cloud Price Calculator export (manual) — most likely to work
2. Billing statement analysis from an existing GaussDB instance
3. Huawei Cloud support ticket
4. GaussDB MySQL API flavor listing via direct API access (`GET /v3/{project_id}/flavors`)

---

## 5. Gaps and Open Questions

| Gap | Severity | Notes |
|-----|----------|-------|
| Instance resource_spec unknown | **Critical** | 30+ naming variants tested across 2 service types, 3 regions. All "Product not found". Worse than DDS where instance was confirmed. |
| Volume resource_spec unknown | **High** | Not tested (blocked by instance). Likely same pattern as RDS/DDS volume discovery. |
| Backup (OBS) resource_spec unknown | Medium | Not tested. Likely same pattern as DDS. |
| Cluster (gaussdb.cluster) usage unclear | Low | `architecture` usage_factor confirmed in catalog but not validated. |
| Dual service type ambiguity | **High** | GaussDB spans `gaussdb` and `taurus` service types. Unclear which to use for pricing. |
| openGauss resource_spec unknown | Medium | `hws.resource.type.opengauss.vm` exists under `taurus` but resource_spec not found. |
| PostgreSQL variant resource_spec unknown | Medium | `hws.resource.type.tauruspg.vm` exists under `taurus` but not tested. |
| Serverless variant | Low | `hws.resource.type.taurus.serverless` exists. Separate billing model. |

---

## 6. Recommendation

**BLOCK GaussDB Fase 1. Do NOT implement templates until resource_spec is discovered.**

Rationale:
- GaussDB instance `resource_spec` is NOT confirmed for ANY engine (MySQL, openGauss, PostgreSQL) via live BSS/OCE pricing API.
- 30+ naming variants tested across 2 service types, 3 regions, and multiple usage_factor values. All returned "Product not found".
- This is worse than DDS Fase 1, where at least the instance resource_spec was confirmed.
- Without a confirmed instance resource_spec, no template can be created.
- The dual service type (`gaussdb` + `taurus`) adds complexity and ambiguity.

**Prerequisite for unblocking:**
- Discover `resource_spec` for at least one GaussDB engine variant (MySQL preferred) through:
  1. Huawei Cloud Price Calculator export
  2. Billing statement analysis from an existing GaussDB instance
  3. Huawei Cloud support ticket
  4. Direct GaussDB API flavor listing

**If resource_spec is discovered, proposed scope for GaussDB Fase 1:**
- Instance template for MySQL: `gaussdb-mysql-instance-payg`
- Instance template for openGauss: `gaussdb-opengauss-instance-payg` (if under `taurus` service type)
- Volume and backup templates: deferred until resource_spec discovered (same as DDS pattern)
- Macro-template `gaussdb-mysql-small-payg` (instance + volume): blocked by volume

**Proposed template IDs (when unblocked):**
- `gaussdb-mysql-instance-payg` (parametric, instance only)
- `gaussdb-opengauss-instance-payg` (parametric, instance only, if under taurus)

**Proposed template status:** `missing_product_infos_template` (all)

---

## 7. Discovery Method

1. BSS/OCE catalog: `QueryServiceResources` for `hws.service.type.gaussdb` → 4 resource types
2. BSS/OCE catalog: `QueryServiceResources` for `hws.service.type.taurus` → 15 resource types
3. BSS/OCE usage types: `QueryUsageTypes` for each GaussDB/Taurus resource type → confirmed `duration`, `count`, `architecture`, `size`
4. Live pricing: `QueryOnDemandPrice` for 30+ instance spec variants across both service types → ALL "Product not found"
5. Cross-region testing: la-north-2, sa-brazil-1, ap-southeast-1 → ALL "Product not found"
6. Volume/cluster/backup testing: skipped (blocked by instance)

---

## 8. Files NOT Modified

- `server.mjs` — no changes needed
- `template-tools.mjs` — no changes needed
- `pricing_catalog_helper.py` — no changes needed
- `pricing-templates.json` — no changes needed

---

## 9. Complete List of resource_spec Variants Tested

### Under `hws.service.type.gaussdb` / `hws.resource.type.gaussdb.vm`

1. `gaussdb.mysql.x1.large.2` (duration)
2. `gaussdb.mysql.x2.large.4` (duration)
3. `gaussdb.mysql.x1.2xlarge.4` (duration)
4. `gaussdb.mysql.n1.large.2` (duration)
5. `gaussdb.mysql.s6.large.2` (Duration)
6. `gaussdb.mysql.c6.large.2` (Duration)
7. `taurus.mysql.x1.large.2` (duration) — with gaussdb service type
8. `gaussdb-mysql.x1.large.2` (duration)
9. `gaussdb.mysql.x1.large.2.ha` (duration)
10. `gaussdb.mysql.n1.large.2.ha` (duration)
11. `gaussdb.mysql.x1.large.4` (duration)
12. `gaussdb.opengauss.x1.large.2` (duration)
13. `gaussdb.mysql.x1.large.2.in` (duration)
14. `gaussdb.mysql.x1.large.2.ha` (Duration)
15. `gaussdb.mysql.x1.large.2` (Duration)
16. `gaussdb-mysql.x1.large.2.ha` (duration)
17. `gaussdb.mysql.x1.large.2.primary` (duration)
18. `gaussdb.mysql.x1.large.2.ro` (duration)
19. `gaussdb.mysql.x1.xlarge.2` (duration)
20. `gaussdb.mysql.x1.medium.2` (duration)
21. `gaussdb.mysql.x1.small.2` (duration)
22. `gaussdb.mysql.x1.large.2.cluster` (duration)
23. `gaussdb.mysql.x1.large.2.single` (duration)
24. `gaussdb.mysql.x1.large.2.economy` (duration)
25. `gaussdb.mysql.x1.large.2.ha` (count)

### Under `hws.service.type.taurus` / `hws.resource.type.taurus.vm`

26. `taurus.mysql.x1.large.2` (duration)
27. `taurus.mysql.x1.large.2` (Duration)
28. `taurus.mysql.n1.large.2` (duration)
29. `taurus.mysql.large.2` (duration)
30. `taurus.mysql.x1.large.2.ha` (duration)
31. `taurus.mysql.x1.large.2.in` (duration)

### Under `hws.service.type.taurus` / `hws.resource.type.opengauss.vm`

32. `opengauss.x1.large.2` (duration)
33. `gaussdb.opengauss.x1.large.2` (duration)

### Cross-region (all "Product not found")

34. `gaussdb.mysql.x1.large.2` in sa-brazil-1 (gaussdb service type)
35. `gaussdb.mysql.x1.large.2` in ap-southeast-1 (gaussdb service type)
36. `taurus.mysql.x1.large.2` in ap-southeast-1 (taurus service type)
