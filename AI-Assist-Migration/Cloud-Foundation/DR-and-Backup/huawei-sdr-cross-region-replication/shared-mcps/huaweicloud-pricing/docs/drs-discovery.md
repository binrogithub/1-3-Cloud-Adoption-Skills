# DRS Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-06-01 (updated 2026-06-01)
**Region**: la-north-2
**Status**: Instance `resource_spec` NOT FOUND; VM `resource_spec` NOT FOUND; Volume `resource_spec` NOT FOUND; Flow `resource_spec` NOT FOUND; **ALL BLOCKED**

---

## 1. BSS/OCE Catalog Findings

### 1.1 Cloud Service Type (1 discovered)

| Field | Value |
|-------|-------|
| service_type_code | `hws.service.type.drs` |
| service_type_name | Data Replication Service |
| abbreviation | DRS |

### 1.2 Resource Types (4 total)

| resource_type_code | name | description | Relevance |
|--------------------|------|-------------|-----------|
| `hws.resource.type.drs.instance` | DRS instance | - | **BLOCKED (resource_spec not found)** |
| `hws.resource.type.drs.vm` | DRS Replicate Server | DRS Replicate Server | **BLOCKED (resource_spec not found)** |
| `hws.resource.type.drs.volume` | DRS Replicate Server Storeage | DRS Replicate Server Storeage | **BLOCKED (resource_spec not found)** |
| `hws.resource.type.drs.flow` | Data flow | - | **BLOCKED (resource_spec not found)** |

### 1.3 Usage Types per Resource Type

| resource_type_code | usage_type code | usage_type name | Interpretation |
|--------------------|-----------------|-----------------|----------------|
| `hws.resource.type.drs.instance` | `architecture` | architecture | Task type/engine/spec selector (like RDS architecture) |
| `hws.resource.type.drs.vm` | `duration` | Duration | Time-based billing (hours) |
| `hws.resource.type.drs.volume` | `duration` | Duration | Time-based billing (hours) |
| `hws.resource.type.drs.flow` | `flow` | Flow | Data flow/traffic billing |

---

## 2. DRS API Node Types (from ListAvailableNodeTypes API)

Node types were successfully queried via the DRS v3 API (`ListAvailableNodeTypes`) in la-north-2:

| engine_type | db_use_type | job_direction | Available node_types |
|-------------|-------------|---------------|---------------------|
| mysql | migration | up | high |
| mysql | sync | up | micro, small, medium, high, xlarge |
| mysql | sync | down | micro, small, medium, high, xlarge |
| mysql | cloudDataGuard | up | high |
| mysql | cloudDataGuard | down | high |
| postgresql | sync | up | micro, small, medium, high, xlarge |
| postgresql | sync | down | micro, small, medium, high, xlarge |
| mongodb | migration | up | high |
| mariadb | sync | up | micro, small, medium, high, xlarge |

**Key observations**:
- Migration tasks only support `high` node type.
- Sync tasks support 5 node types: micro, small, medium, high, xlarge.
- DR (cloudDataGuard) tasks only support `high` node type.
- `taurusdb` is not a valid engine_type for DRS API (use `mysql` for MySQL->TaurusDB flows).
- `gaussdb`, `oracle`, `kafka` are not valid engine_types for DRS API.
- `mariadb` is a valid engine_type (sync only, same node_types as mysql sync).

---

## 3. Billing Model (from documentation)

### 3.1 Billed Items

| Billed Item | Description | Billing Mode |
|-------------|-------------|--------------|
| Configuration fee (mandatory) | Compute and storage resources + data processing | Pay-per-use: by actual usage duration. Yearly/monthly: upfront payment. |
| EIP fee (optional) | Public network access data processing and traffic | Billed by EIP service separately. |

### 3.2 Billing Mode Support

| Function | Pay-per-use | Yearly/Monthly |
|----------|-------------|----------------|
| Real-time migration | Yes (ONLY mode) | No |
| Real-time synchronization | Yes | Yes |
| Real-time disaster recovery | Yes | Yes |
| Backup migration | Free | Free |
| Data subscription | Free (OBT) | Free (OBT) |
| Traffic replay | Free (OBT) | Free (OBT) |

### 3.3 Pay-per-use Billing Rules
- Calculated by the second, billed every hour.
- Billing starts when the task is launched, ends when the task is completed.
- Specification changes create a new order; original order becomes invalid.

### 3.4 Commercial Data Flows (from billing documentation)

**Migration (to cloud)**:
- MySQL -> MySQL, MySQL -> DDM, MySQL -> TaurusDB
- MongoDB -> DDS, MongoDB -> GeminiDB Mongo
- MySQL schema and logic table -> DDM
- Redis -> GeminiDB Redis, Redis -> Redis

**Sync (to cloud)**:
- MySQL -> MySQL, MySQL -> PostgreSQL, MySQL -> TaurusDB, MySQL -> GaussDB
- DDM -> MySQL, DDM -> DDM
- Oracle -> MySQL, Oracle -> TaurusDB, Oracle -> DDM, Oracle -> PostgreSQL, Oracle -> GaussDB
- PostgreSQL -> PostgreSQL, MongoDB -> DDS, MariaDB -> MariaDB, TaurusDB -> TaurusDB

**Sync (from cloud)**: Multiple flows including MySQL/DDS/TaurusDB/GaussDB -> various targets.

**DR**: MySQL -> MySQL, MySQL -> TaurusDB, TaurusDB -> TaurusDB.

---

## 4. Resource Spec Discovery Attempts

### 4.1 Patterns Tested (ALL returned "Product not found" or "Billing item does not exist")

Over 25 resource_spec patterns were tested across all 4 resource types. None returned valid pricing.

**Round 2 (2026-06-01)**: Additional 8 patterns tested with region, AZ, and task_type suffixes. Also tested BSS catalog listing endpoints and DRS v5 API. All returned "Product not found" or 404.

**drs.instance (usage_type: architecture)**:

| resource_spec tried | Error |
|---------------------|-------|
| `migration.mysql` | Product not found |
| `sync.mysql` | Product not found |
| `cloudDataGuard.mysql` | Product not found |
| `drs.migration.mysql` | Product not found |
| `migration.mysql.high` | Product not found |
| `sync.mysql.medium` | Product not found |
| `drs.mysql.migration.high` | Product not found |
| `drs.mysql.sync.medium` | Product not found |
| `drs.mysql.migration.high.up` | Product not found |
| `drs.mysql.sync.medium.up` | Product not found |
| `migration.high` | Product not found |
| `sync.medium` | Product not found |
| `drs.migration.mysql.high` | Product not found |

**Round 2 - additional patterns (drs.instance)**:

| resource_spec tried | Error |
|---------------------|-------|
| `drs.mysql.migration.high.up.la-north-2` | Product not found |
| `drs.mysql.sync.medium.up.la-north-2` | Product not found |
| `drs.mysql.migration.high.FULL_INCR_TRANS` | Product not found |

**Round 2 - additional patterns (drs.vm)**:

| resource_spec tried | Error |
|---------------------|-------|
| `drs.migration.mysql.high.la-north-2` | Product not found |
| `drs.mysql.migration.high.la-north-2a` | Product not found |
| `drs.migration.mysql.high.FULL_INCR_TRANS` | Product not found |
| `drs.sync.mysql.medium.FULL_INCR_TRANS` | Product not found |
| `drs.mysql.sync.medium.FULL_INCR_TRANS.up` | Product not found |

**drs.vm (usage_type: Duration)**:

| resource_spec tried | Error |
|---------------------|-------|
| `migration.mysql` | Billing item does not exist |
| `sync.mysql` | Billing item does not exist |
| `cloudDataGuard.mysql` | Billing item does not exist |
| `drs.migration.mysql.s1` | Product not found |
| `migration.mysql.s1` | Product not found |
| `sync.mysql.s1` | Product not found |
| `cloudDataGuard.mysql.s1` | Product not found |
| `migration.mysql.medium` | Product not found |
| `sync.mysql.medium` | Product not found |
| `drs.mysql.migration.medium` | Product not found |
| `drs.mysql.sync.medium` | Product not found |
| `drs.migration.mysql.high` | Product not found |
| `mysql.high.migration` | Product not found |
| `high.mysql.migration` | Product not found |
| `migration.mysql.high.up` | Product not found |
| `drs_migration_mysql_high` | Product not found |
| `drs-migration-mysql-high` | Product not found |

**drs.volume (usage_type: Duration)**:

| resource_spec tried | Error |
|---------------------|-------|
| `drs.volume.mysql` | Product not found |

**drs.flow (usage_type: Flow)**:

| resource_spec tried | Error |
|---------------------|-------|
| `drs.flow.mysql` | Product not found |

### 4.2 Also Tested

- Different regions (la-north-2, cn-north-4) - same "Product not found" error.
- Period (yearly/monthly) pricing API - same "Product not found" error.
- Different usage_factor values (numeric 1, "Duration", "architecture", "flow") - same errors.
- Different usage_value values (730, 1) - same errors.

### 4.3 Round 2 Additional Tests (2026-06-01)

- Resource_spec patterns with region/AZ suffixes (e.g., `.la-north-2`, `.la-north-2a`) - all "Product not found".
- Resource_spec patterns with task_type suffixes (e.g., `.FULL_INCR_TRANS`) - all "Product not found".
- BSS catalog listing endpoints:
  - `/v2/products/commercial/metering-specs` - 404 (API does not exist)
  - `/v2/products/commercial/products` - 404 (API does not exist)
  - `/v2/products/commercial/product-specs` - 404 (API does not exist)
  - `/v2/products/commercial/offering-detail` - 404 (API does not exist)
  - `/v2/bills/ratings/products` - 404 (API does not exist)
- DRS v5 API `ListJobs` - returns 0 existing jobs (no ProductInfo to inspect).
- DRS v5 API `ListSupportLinks` - works but doesn't expose resource_spec_code.

---

## 5. DRS API Insights

### 5.1 CreateJobReq Fields

The DRS v3 API `CreateJobReq` includes a `product_id` field (type: str) that likely maps to the BSS resource_spec. However, the format of this product_id is not documented and could not be determined through API exploration.

Key fields in CreateJobReq:
- `db_use_type`: migration, sync, cloudDataGuard
- `engine_type`: mysql, postgresql, mongodb, etc.
- `node_type`: micro, small, medium, high, xlarge (from ListAvailableNodeTypes)
- `job_direction`: up, down
- `product_id`: **UNKNOWN FORMAT** - this is likely the BSS resource_spec
- `charging_mode`: period (yearly/monthly) or on_demand
- `period_order`: PeriodOrderInfo (period_type, period_num, is_auto_renew)

### 5.2 ListAvailableNodeTypes API

Successfully queried. Requires: engine_type, job_type, db_use_type, job_direction, is_rdb.

### 5.3 DRS v5 API Insights (new in Round 2)

**ProductInfo model** (from `huaweicloudsdkdrs.v5.model.product_info`):

| Field | Type | Notes |
|-------|------|-------|
| id | str | Product ID |
| cloud_service_type | str | e.g., hws.service.type.drs |
| resource_type | str | e.g., hws.resource.type.drs.vm |
| **resource_spec_code** | **str** | **THIS IS THE BSS resource_spec** |
| resource_size | int | Optional (for volume/flow) |
| usage_factor | str | e.g., "Duration", "architecture", "flow" |
| usage_value | float | Usage amount |
| usage_measure_id | int | e.g., 4 (hour) |
| resource_size_measure_id | int | e.g., 10 (GB), 17 (GB) |

**Key finding**: The DRS v5 API defines `ProductInfo` with `resource_spec_code` field that maps 1:1 to the BSS pricing API's `resource_spec`. However, the DRS service generates this internally when creating jobs - it's not exposed via any listing API.

**JobNodeBaseInfo model**:

| Field | Type | Notes |
|-------|------|-------|
| instance_type | str | Instance type |
| arch | str | Architecture |
| availability_zone | str | AZ |
| status | str | Node status |
| role | str | Node role |

**ListSupportLinks API**: Successfully queried. Returns supported link configurations with engine_type, net_type, task_modes, job_direction, cluster_mode. Does NOT expose resource_spec_code.

**ListJobs API**: Successfully queried. Returns 0 existing jobs in la-north-2. No ProductInfo to inspect from existing tasks.

---

## 6. Conclusion

### 6.1 What Was Confirmed

| Item | Status | Value |
|------|--------|-------|
| cloud_service_type | CONFIRMED | `hws.service.type.drs` |
| service_type_name | CONFIRMED | Data Replication Service |
| resource_type (instance) | CONFIRMED | `hws.resource.type.drs.instance` |
| resource_type (vm) | CONFIRMED | `hws.resource.type.drs.vm` |
| resource_type (volume) | CONFIRMED | `hws.resource.type.drs.volume` |
| resource_type (flow) | CONFIRMED | `hws.resource.type.drs.flow` |
| usage_type (instance) | CONFIRMED | `architecture` |
| usage_type (vm) | CONFIRMED | `duration` |
| usage_type (volume) | CONFIRMED | `duration` |
| usage_type (flow) | CONFIRMED | `flow` |
| node_types (from DRS API) | CONFIRMED | micro, small, medium, high, xlarge (varies by task type) |
| billing model | CONFIRMED | Configuration fee + EIP fee |
| pay-per-use billing | CONFIRMED | By the second, billed hourly |

### 6.2 What Was NOT Found

| Item | Status | Notes |
|------|--------|-------|
| resource_spec (drs.instance) | NOT FOUND | 16+ patterns tried, all "Product not found" |
| resource_spec (drs.vm) | NOT FOUND | 22+ patterns tried, all "Product not found" |
| resource_spec (drs.volume) | NOT FOUND | Pattern tried, "Product not found" |
| resource_spec (drs.flow) | NOT FOUND | Pattern tried, "Product not found" |
| product_id format | NOT FOUND | CreateJobReq.product_id format unknown; v5 ProductInfo.resource_spec_code confirmed as BSS resource_spec but values not exposed by any API |
| validated pricing | NONE | No pricing could be validated without resource_spec |

### 6.3 Recommendation

**DRS is BLOCKED by lack of resource_spec** - same category as GaussDB.

The resource_spec format for DRS is not documented in the BSS/OCE catalog and cannot be discovered through trial-and-error with the pricing API. The DRS service uses a `product_id` field in its CreateJob API, but the format of this product_id is unknown.

**Possible paths forward**:
1. **Price Calculator reverse engineering**: Use browser DevTools on the Huawei Cloud Price Calculator for DRS to capture the actual product_infos payload sent to the BSS API. **This is the most promising approach.**
2. **Console network capture**: Create a DRS task in the Huawei Cloud console and capture the BSS pricing API call from the network tab.
3. **Huawei Cloud support**: Request the resource_spec_code format from Huawei Cloud technical support.
4. **Existing DRS task billing**: If an existing DRS task exists in another project/region, query its billing details to find the resource_spec_code used.
5. **DRS v5 ShowJob ProductInfo**: If a DRS job is created (even briefly), the ShowJob response may include the ProductInfo with resource_spec_code.

---

## 7. product_infos_template (NOT FUNCTIONAL - for reference only)

These templates are **NOT functional** because resource_spec values are unknown. They are provided as reference for future implementation once resource_spec is discovered.

### 7.1 DRS VM (Replicate Server) - if resource_spec were known

```json
{
  "id": "drs-vm-{{resource_spec}}-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.drs",
  "resource_type": "hws.resource.type.drs.vm",
  "resource_spec": "{{resource_spec}}",
  "region": "{{region}}",
  "usage_factor": "Duration",
  "usage_value": "{{monthly_hours}}",
  "usage_measure_id": 4,
  "subscription_num": "{{quantity}}"
}
```

### 7.2 DRS Instance - if resource_spec were known

```json
{
  "id": "drs-instance-{{resource_spec}}-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.drs",
  "resource_type": "hws.resource.type.drs.instance",
  "resource_spec": "{{resource_spec}}",
  "region": "{{region}}",
  "usage_factor": "architecture",
  "usage_value": "{{monthly_hours}}",
  "usage_measure_id": 4,
  "subscription_num": "{{quantity}}"
}
```

### 7.3 DRS Flow - if resource_spec were known

```json
{
  "id": "drs-flow-{{resource_spec}}-{{flow_gb}}gb-{{quantity}}",
  "cloud_service_type": "hws.service.type.drs",
  "resource_type": "hws.resource.type.drs.flow",
  "resource_spec": "{{resource_spec}}",
  "region": "{{region}}",
  "usage_factor": "flow",
  "usage_value": "{{flow_gb}}",
  "usage_measure_id": 10,
  "subscription_num": "{{quantity}}"
}
```

### 7.4 DRS Volume - if resource_spec were known

```json
{
  "id": "drs-volume-{{resource_spec}}-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.drs",
  "resource_type": "hws.resource.type.drs.volume",
  "resource_spec": "{{resource_spec}}",
  "region": "{{region}}",
  "usage_factor": "Duration",
  "usage_value": "{{monthly_hours}}",
  "usage_measure_id": 4,
  "subscription_num": "{{quantity}}"
}
```
