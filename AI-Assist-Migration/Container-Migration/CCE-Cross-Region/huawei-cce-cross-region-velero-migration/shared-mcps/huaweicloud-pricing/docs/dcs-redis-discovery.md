# DCS Redis Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-05-29
**Region**: la-north-2
**Status**: Instance resource_spec CONFIRMED. Bandwidth/OBS/Shard resource_spec NOT FOUND.

---

## 1. BSS/OCE Catalog

### 1.1 Service Type

| Field | Value |
|-------|-------|
| service_type_code | `hws.service.type.dcs` |
| service_type_name | Distributed Cache Service |

### 1.2 Resource Types (10 total)

| resource_type_code | name | Discovery Status |
|--------------------|------|-----------------|
| `hws.resource.type.dcs3` | Distributed Cache Service V2 | **PRIMARY - CONFIRMED** |
| `hws.resource.type.dcs2` | DCS V2 | NOT WORKING with V3 spec_codes |
| `hws.resource.type.dcs` | Distributed Cache Service | NOT WORKING with V1 spec_codes |
| `hws.resource.type.dcs.obs` | Storage Space of Distributed Cache | **BLOCKED - resource_spec not found** |
| `hws.resource.type.dcs.bandwidth` | Distributed Cache Service Bandwidth | **BLOCKED - resource_spec not found** |
| `hws.resource.type.dcs.shard` | Distributed Cache Service Shard Mode | **BLOCKED - resource_spec not found** |
| `hws.resource.type.dcs.memcached` | Memcached Instance | Not in scope (Redis only) |
| `hws.resource.type.dcs2.libos` | DCS Plus | Not in scope |
| `hws.resource.type.dcs.dec` | Redis DeC Instance | DeC variant, not in scope |
| `hws.resource.type.dcs.decmemcached` | Memcached DeC Instance | DeC variant, not in scope |

### 1.3 Usage Types

| resource_type_code | usage_type code | usage_type name | Purpose |
|--------------------|----------------|----------------|---------|
| `hws.resource.type.dcs3` | `duration` | Duration | Instance on-demand pricing |
| `hws.resource.type.dcs2` | `duration` | Duration | Instance on-demand pricing (V2) |
| `hws.resource.type.dcs` | `duration` | Duration | Instance on-demand pricing (V1) |
| `hws.resource.type.dcs.shard` | `dcsduration` | dcsduration | Shard mode pricing |
| `hws.resource.type.dcs.bandwidth` | `bandwidth` | bandwidth | Bandwidth pricing |
| `hws.resource.type.dcs.obs` | `size` | Capacity | Backup storage pricing |

---

## 2. DCS API Flavor Discovery

### 2.1 Method

Queried DCS API `GET /v2/{project_id}/flavors?engine=redis` in la-north-2.

### 2.2 spec_code Format

The DCS API returns `spec_code` which maps directly to BSS `resource_spec`.

**V3 spec_code format** (current generation, uses `hws.resource.type.dcs3`):

| cache_mode | Format | Example | Description |
|------------|--------|---------|-------------|
| single | `redis.single.xu1.large.{capacity}` | `redis.single.xu1.large.2` | Single node, 2 GB |
| single (tiny) | `redis.single.xu1.tiny.{capacity_mb}` | `redis.single.xu1.tiny.128` | Single node, 128 MB |
| single (free) | `redis.single.xu1.free.{capacity_mb}` | `redis.single.xu1.free.128` | Free tier, 128 MB |
| ha | `redis.ha.xu1.large.r{replicas}.{capacity}` | `redis.ha.xu1.large.r2.2` | HA, 2 replicas, 2 GB |
| ha_rw_split | `redis.ha.xu1.large.p{proxies}.{capacity}` | `redis.ha.xu1.large.p2.2` | HA read-write split, 2 proxies, 2 GB |
| proxy | `redis.proxy.xu1.large.{capacity}` | `redis.proxy.xu1.large.4` | Proxy cluster, 4 GB |
| proxy (sharded) | `redis.proxy.xu1.large.s{shards}.{capacity}` | `redis.proxy.xu1.large.s1.4` | Proxy cluster, 1 shard, 4 GB |
| cluster | `redis.cluster.xu1.large.r{replicas}.{capacity}` | `redis.cluster.xu1.large.r1.4` | Cluster, 1 replica, 4 GB |
| cluster (sharded) | `redis.cluster.xu1.large.r{replicas}.s{shards}.{capacity}` | `redis.cluster.xu1.large.r3.s1.4` | Cluster, 3 replicas, 1 shard, 4 GB |

**V1 spec_code format** (legacy, uses `hws.resource.type.dcs`):

| cache_mode | spec_code | BSS Status |
|------------|-----------|------------|
| single | `dcs.single_node` | **Product not found** |
| ha | `dcs.master_standby` | **Product not found** |
| proxy | `dcs.cluster` | **Product not found** |

### 2.3 Flavor Counts by cache_mode (la-north-2)

| cache_mode | Flavor Count | resource_type |
|------------|-------------|---------------|
| single | 14 | hws.resource.type.dcs3 |
| ha | 49 | hws.resource.type.dcs3 |
| ha_rw_split | 35 | hws.resource.type.dcs3 |
| proxy | 75 | hws.resource.type.dcs3 |
| cluster | 256 | hws.resource.type.dcs3 |

---

## 3. BSS/OCE Pricing Validation

### 3.1 DCS Redis Instance (dcs3) - CONFIRMED

**Working product_infos payload:**

```json
{
  "id": "dcs-redis-{{resource_spec}}-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.dcs",
  "resource_type": "hws.resource.type.dcs3",
  "resource_spec": "redis.single.xu1.large.2",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1
}
```

### 3.2 Single Node Pricing (redis.single.xu1.large.{capacity})

| spec_code | Capacity | Hourly (USD) | Monthly 730h (USD) | product_id |
|-----------|----------|-------------|---------------------|------------|
| `redis.single.xu1.tiny.128` | 0.125 GB | 0.002 | 1.46 | OFFI592252373302738948 |
| `redis.single.xu1.free.128` | 0.125 GB | 0.000 | 0.00 | OFFI592252332765052959 |
| `redis.single.xu1.large.1` | 1 GB | 0.017 | 12.41 | OFFI592252332765052963 |
| `redis.single.xu1.large.2` | 2 GB | 0.034 | 24.82 | OFFI592252332765052967 |
| `redis.single.xu1.large.4` | 4 GB | 0.068 | 49.64 | OFFI592252332765052973 |
| `redis.single.xu1.large.8` | 8 GB | 0.135 | 98.55 | OFFI592252373302738946 |
| `redis.single.xu1.large.16` | 16 GB | 0.270 | 197.10 | OFFI592252332765052961 |

### 3.3 HA Pricing (redis.ha.xu1.large.r{replicas}.{capacity})

| spec_code | Replicas | Capacity | Hourly (USD) | Monthly 730h (USD) | product_id |
|-----------|----------|----------|-------------|---------------------|------------|
| `redis.ha.xu1.large.r2.1` | 2 | 1 GB | 0.034 | 24.82 | OFFI592252263298990098 |
| `redis.ha.xu1.large.r2.2` | 2 | 2 GB | 0.068 | 49.64 | OFFI592252263298990100 |
| `redis.ha.xu1.large.r2.4` | 2 | 4 GB | 0.136 | 99.28 | OFFI592252263298990103 |
| `redis.ha.xu1.large.r3.2` | 3 | 2 GB | 0.102 | 74.46 | OFFI592252263298990109 |

### 3.4 HA Read-Write Split Pricing (redis.ha.xu1.large.p{proxies}.{capacity})

| spec_code | Proxies | Capacity | Hourly (USD) | Monthly 730h (USD) | product_id |
|-----------|---------|----------|-------------|---------------------|------------|
| `redis.ha.xu1.large.p2.2` | 2 | 2 GB | 0.213 | 155.49 | OFFI923962513847017485 |

### 3.5 Proxy Cluster Pricing (redis.proxy.xu1.large.{capacity})

| spec_code | Capacity | Hourly (USD) | Monthly 730h (USD) | product_id |
|-----------|----------|-------------|---------------------|------------|
| `redis.proxy.xu1.large.4` | 4 GB | 0.150 | 109.50 | OFFI592252332760858647 |

### 3.6 Cluster Pricing (redis.cluster.xu1.large.r{replicas}.{capacity})

| spec_code | Replicas | Capacity | Hourly (USD) | Monthly 730h (USD) | product_id |
|-----------|----------|----------|-------------|---------------------|------------|
| `redis.cluster.xu1.large.r1.4` | 1 | 4 GB | 0.091 | 66.43 | OFFI592252134856556589 |

### 3.7 Key Observations

- All V3 spec_codes use `hws.resource.type.dcs3` with `usage_factor: "duration"`.
- V1 spec_codes (`dcs.single_node`, `dcs.master_standby`, `dcs.cluster`) with `hws.resource.type.dcs` return "Product not found".
- V3 spec_codes with `hws.resource.type.dcs2` also return "Product not found".
- Single node pricing is linear with capacity: 1 GB = USD 12.41, 2 GB = USD 24.82, 4 GB = USD 49.64.
- HA r2 pricing is exactly 2x single node pricing for the same capacity.
- HA r3 pricing is 3x single node pricing (r3.2 = USD 74.46 = 3 x 24.82).
- HA read-write split (p2) is significantly more expensive than plain HA (r2) for the same capacity: USD 155.49 vs 49.64 for 2 GB.
- Free tier (redis.single.xu1.free.128) has zero cost.
- `resource_spec` only allows `a-zA-Z0-9_-.` characters (no `+` or other special chars).

### 3.8 Non-Instance Resource Types - NOT FOUND

| resource_type | resource_spec tried | Error |
|---------------|-------------------|-------|
| `hws.resource.type.dcs.bandwidth` | `dcs.bandwidth` | Product not found |
| `hws.resource.type.dcs.obs` | `dcs.obs` | Product not found |
| `hws.resource.type.dcs.shard` | `redis.cluster.xu1.large.r1.s1.4` | Product not found |

---

## 4. Resource Spec Discovery Summary

### 4.1 Working Combinations

| cloud_service_type | resource_type | resource_spec pattern | Status |
|-------------------|---------------|----------------------|--------|
| `hws.service.type.dcs` | `hws.resource.type.dcs3` | `redis.single.xu1.large.{capacity}` | **CONFIRMED** |
| `hws.service.type.dcs` | `hws.resource.type.dcs3` | `redis.ha.xu1.large.r{replicas}.{capacity}` | **CONFIRMED** |
| `hws.service.type.dcs` | `hws.resource.type.dcs3` | `redis.ha.xu1.large.p{proxies}.{capacity}` | **CONFIRMED** |
| `hws.service.type.dcs` | `hws.resource.type.dcs3` | `redis.proxy.xu1.large.{capacity}` | **CONFIRMED** |
| `hws.service.type.dcs` | `hws.resource.type.dcs3` | `redis.cluster.xu1.large.r{replicas}.{capacity}` | **CONFIRMED** |

### 4.2 Non-Working Combinations

| cloud_service_type | resource_type | resource_spec | Error |
|-------------------|---------------|--------------|-------|
| `hws.service.type.dcs` | `hws.resource.type.dcs` | `dcs.single_node` | Product not found |
| `hws.service.type.dcs` | `hws.resource.type.dcs` | `dcs.master_standby` | Product not found |
| `hws.service.type.dcs` | `hws.resource.type.dcs` | `dcs.cluster` | Product not found |
| `hws.service.type.dcs` | `hws.resource.type.dcs2` | `redis.single.xu1.large.2` | Product not found |
| `hws.service.type.dcs` | `hws.resource.type.dcs2` | `redis.ha.xu1.large.r2.2` | Product not found |

---

## 5. product_infos_template for DCS Redis Instance

```json
{
  "id": "dcs-redis-{{resource_spec}}-{{monthly_hours}}h-{{quantity}}",
  "cloud_service_type": "hws.service.type.dcs",
  "resource_type": "hws.resource.type.dcs3",
  "resource_spec": "{{resource_spec}}",
  "region": "{{region}}",
  "usage_factor": "duration",
  "usage_value": "{{monthly_hours}}",
  "usage_measure_id": 4,
  "subscription_num": "{{quantity}}"
}
```

**Parameters:**
- `resource_spec`: DCS V3 spec_code from DCS API (e.g., `redis.single.xu1.large.2`)
- `monthly_hours`: Usage duration in hours (default 730)
- `quantity`: Number of instances (default 1)

---

## 6. Phase 1 Recommendation

### 6.1 Implement DCS Redis Fase 1 as instance-only template

**Rationale:**
- Instance resource_spec CONFIRMED for all 5 cache modes (single, ha, ha_rw_split, proxy, cluster).
- On-demand pricing validated: `redis.single.xu1.large.2` x 730h = USD 24.82/month.
- DCS API provides flavor listing for dynamic spec_code discovery.
- Bandwidth, OBS backup, and shard resource_spec NOT FOUND (same pattern as DDS volume/backup).
- Instance-only template is viable for Fase 1, following the same pattern as DDS Fase 1.

### 6.2 Proposed Template

- `dcs-redis-instance-payg`: params {quantity, resource_spec, monthly_hours}. Status: `ready` to implement.
  - `resource_spec` must be a valid DCS V3 spec_code (e.g., `redis.single.xu1.large.2`).
  - Default `resource_spec`: `redis.single.xu1.large.2` (single node, 2 GB, cheapest non-free option).

### 6.3 Deferred Items

- `dcs-redis-bandwidth-payg`: Blocked by unknown resource_spec for `hws.resource.type.dcs.bandwidth`.
- `dcs-redis-backup-payg`: Blocked by unknown resource_spec for `hws.resource.type.dcs.obs`.
- `dcs-redis-shard-payg`: Blocked by unknown resource_spec for `hws.resource.type.dcs.shard`.
- Macro-template (instance + bandwith + backup): Deferred until secondary resource_specs discovered.

### 6.4 Risks

- resource_spec varies by region (CPU type xu1 vs other). Different regions may have different flavor families.
- HA read-write split (ha_rw_split) is significantly more expensive than plain HA.
- Free tier instance has zero cost but may have limitations not captured in pricing.
- Cluster mode has many spec_code variants (256 flavors in la-north-2), making template selection complex.

---

## 7. Comparison with DDS Discovery

| Aspect | DDS | DCS Redis |
|--------|-----|-----------|
| Service type code | `hws.service.type.dds` | `hws.service.type.dcs` |
| Instance resource_type | `hws.resource.type.dds.vm` | `hws.resource.type.dcs3` |
| Instance resource_spec | `dds.mongodb.s6.large.2.repset` | `redis.single.xu1.large.2` |
| resource_spec source | DDS API flavors | DCS API flavors |
| usage_factor | `duration` | `duration` |
| Volume resource_spec | NOT FOUND | N/A (DCS has no separate volume) |
| Backup resource_spec | NOT FOUND | NOT FOUND |
| Bandwidth resource_spec | N/A | NOT FOUND |
| Instance pricing confirmed | Yes | Yes |
| Fase 1 viable | Yes (instance-only) | Yes (instance-only) |
| Fase 1 implemented | Yes (`dds-instance-payg`) | Yes (`dcs-redis-instance-payg`) |
