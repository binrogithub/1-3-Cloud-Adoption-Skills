# Service Expansion Analysis for huaweicloud-pricing MCP

## Pre-Flight Verification

**Fix `include_unavailable_reference_pricing` for quantity > 1**: CONFIRMED applied.
- `server.mjs:2466`: `unit_monthly_reference_price = monthlyAmount / quantity`
- `server.mjs:2467`: `monthly_reference_total = monthlyAmount` (no double multiplication)
- Test T3b (quantity=2) and T10b (quantity=40) validate correctness.
- CCE 40-worker scenario: `monthly_reference_total === unit_price * 40`, no inflation.

## 1. Comparative Table

| Service | cloud_service_type | Resource Types (BSS/OCE) | Billing Model | Template Type | Status |
|---------|-------------------|--------------------------|---------------|---------------|--------|
| EVS GPSSD | `hws.service.type.ebs` | volume (1) | Capacity (GB) + duration | simple template | `resource_spec_confirmed` → **IMPLEMENTED** as `evs-gpssd-gb-payg` |
| DCS Redis | `hws.service.type.dcs` | dcs2, dcs3, dcs.shard, dcs.bandwidth, dcs.obs (10 total) | Instance + capacity (GB) + bandwidth + duration | macro-template | `resource_spec_confirmed` (instance only) |
| NAT Gateway | `hws.service.type.natgateway` | natgateway, privatenat, elasticnatgateway, natgateway.exclusive (4 total) | Instance + bandwidth + duration | simple template | `resource_spec_confirmed` (public NAT only) |
| WAF | `hws.service.type.waf` | waf.instance, waf.domain, waf.rule, waf.request, waf.bandwidth (16 total) | Instance + domains + rules + requests + bandwidth | multiple templates | `resource_spec_confirmed` (instance only) |
| CFW | `hws.service.type.cfw` | cfw, cfw.exp.eip, cfw.exp.vpc, cfw.exp.bandwidth, cfw.throughput, cfw.exp.trafficflow (6 total) | Instance + EIP expansion + VPC expansion + bandwidth | multiple templates | `resource_spec_confirmed` (instance only) |
| SFS Turbo | `hws.service.type.sfs` | sfs.turbo (3 total) | Capacity (GB) + throughput + duration | simple template | `resource_spec_confirmed` (Standard only) |
| DDS | `hws.service.type.dds` | dds.vm, dds.volume, dds.cluster, dds.obs (5 total) | Instance + storage + backup + duration | macro-template | `missing_product_infos_template` |
| GaussDB | `hws.service.type.gaussdb` | gaussdb.vm, gaussdb.volume, gaussdb.cluster, gaussdb.obs (4 total) | Instance + storage + backup + duration | macro-template | `missing_product_infos_template` |
| DRS | `hws.service.type.drs` | drs.instance, drs.vm, drs.volume, drs.flow (4 total) | Configuration fee + data flow + duration | simple template | `missing_product_infos_template` (resource_spec NOT FOUND, 25+ variants tested) |
| VPN | `hws.service.type.vpn` + `hws.service.type.vpc` (traffic) | vpn.ipsecvpn, vpn.vgw, vpnconnection (3 total) + bandwidth (traffic) | Gateway instance + traffic per GB (VPC) | macro-template (Fase 2) / simple (Fase 1) | `resource_spec_confirmed` (V300 gateway + 12_share/12_bgp traffic). **Traffic template IMPLEMENTED** as `vpc-bandwidth-traffic-gb-payg` (status `ready`). |
| CBR | `hws.service.type.cbr` | cbr.vault (2+ total) | Capacity (GB) + duration | simple template | `resource_spec_confirmed` (server + disk backup vault). **IMPLEMENTED** as `cbr-server-backup-vault-gb-payg` and `cbr-disk-backup-vault-gb-payg` (status `ready`). |
| HSS | `hws.service.type.hss` | hss, cgs, hses, hsms (4 total) | Instance + duration (on-demand) or period (subscription) | simple template | `resource_spec_confirmed` (host protection). **IMPLEMENTED** as `hss-host-protection-payg` (status `ready`) and `hss-host-protection-period` (status `ready`, Phase 1 period billing). **PERIOD GAP CLOSED**: period template matches benchmark (USD 41.40 for 3 PCS premium). See `docs/period-billing-design.md`. |
| ECS Compute | `hws.service.type.ec2` | vm, vm.image (2+ total) | Instance per hour + OS license per hour (separate productInfo) | simple template | `resource_spec_confirmed` (compute + SUSE license). **IMPLEMENTED** as `ecs-flavor-payg`, `ecs-os-license-payg` (on-demand, status `ready`), `ecs-flavor-period`, `ecs-os-license-period` (period, status `ready`). Period billing matches quotation EXACTLY. See `docs/ecs-benchmark-discovery.md` and `docs/period-billing-design.md`. |

## 2. Per-Service Deep Analysis

### 2.1 DCS Redis

**Billing**: Instance (by spec/capacity) per hour. Capacity in GB determines price tier. Bandwidth add-on for cluster mode. OBS backup storage separate.

**Dependencies**: VPC (subnet), EIP (optional public access), OBS (backup), LTS (audit logs).

**MCP Modeling**: Macro-template `dcs-redis-cluster-payg` expanding to dcs instance + dcs.bandwidth (if cluster) + dcs.obs (if backup). Similar pattern to CCE macro.

**BSS/OCE**: `hws.service.type.dcs` confirmed. **Instance resource_spec CONFIRMED**: V3 spec_codes from DCS API work directly as `resource_spec` in BSS pricing API. Primary resource_type is `hws.resource.type.dcs3` (NOT dcs or dcs2). V1 spec_codes (`dcs.single_node`, `dcs.master_standby`, `dcs.cluster`) with `hws.resource.type.dcs` return "Product not found". V3 spec_codes with `hws.resource.type.dcs2` also return "Product not found". `usage_factor` = "duration", `usage_measure_id` = 4. **Evidence**: catalog confirmed, live pricing API validated for single/ha/ha_rw_split/proxy/cluster modes. See `docs/dcs-redis-discovery.md` for full details.

**Integration**: No `validate_availability` (no ECS flavors). No `service_cost_breakdown` needed. Contributes to `monthly_total`. Warnings for capacity tier mismatch.

**Proposed Templates**:
- `dcs-redis-instance-payg`: params {quantity, resource_spec, monthly_hours}. Status: `ready` → implemented (instance only).
- `dcs-redis-cluster-payg` (macro): params {quantity, resource_spec, cluster_mode, backup_enabled}. Status: `research_required` (blocked by bandwith/obs/shard resource_spec).

**Risks**: resource_spec varies by region (CPU type xu1 vs other). Cluster mode adds shard/bandwidth billing. OBS backup cost may be overlooked (subcotizacion). HA read-write split is significantly more expensive than plain HA.

**Test Cases**: Unit: render product_infos with valid resource_spec. Live: query price for dcs3 single/ha in la-north-2. Invalid: empty resource_spec. monthly_total: instance (+ bandwidth + backup when available).

**Validated Pricing (live BSS/OCE)**:
- `redis.single.xu1.large.1` (single, 1 GB) × 730h = USD 12.41/month
- `redis.single.xu1.large.2` (single, 2 GB) × 730h = USD 24.82/month
- `redis.single.xu1.large.4` (single, 4 GB) × 730h = USD 49.64/month
- `redis.ha.xu1.large.r2.2` (HA, 2 replicas, 2 GB) × 730h = USD 49.64/month
- `redis.ha.xu1.large.r3.2` (HA, 3 replicas, 2 GB) × 730h = USD 74.46/month
- `redis.ha.xu1.large.p2.2` (HA RW split, 2 proxies, 2 GB) × 730h = USD 155.49/month
- `redis.proxy.xu1.large.4` (proxy, 4 GB) × 730h = USD 109.50/month
- `redis.cluster.xu1.large.r1.4` (cluster, 1 replica, 4 GB) × 730h = USD 66.43/month

### 2.2 NAT Gateway

**Billing**: Instance per hour by spec tier (small/middle/large/xlarge). Two billing modes: pay-per-use (hourly) and yearly/monthly. Bandwidth billed separately per Mbps or per GB traffic.

**Dependencies**: VPC (required), EIP (SNAT/DNAT rules reference EIPs), ECS (instances using NAT).

**MCP Modeling**: Simple template `nat-gateway-payg` for instance. Bandwidth add-on deferred.

**BSS/OCE**: `hws.service.type.natgateway` **CONFIRMED**. 4 resource types: `hws.resource.type.natgateway` (public NAT), `hws.resource.type.privatenat` (private NAT), `hws.resource.type.elasticnatgateway` (elastic NAT), `hws.resource.type.natgateway.exclusive` (exclusive standard-price NAT). **Public NAT resource_spec CONFIRMED**: `natgateway_small` (USD 73.14/mo 30d), `natgateway_middle` (USD 137.16/mo 30d), `natgateway_large` (USD 269.73/mo 30d), `natgateway_xlarge` (USD 475.47/mo 30d). `usage_factor` = "duration" (NOT "duration_hour"). **Fase 1 uses day-based billing**: `usage_days` (default 30) with `usage_measure_id=0`, aligned with Price Calculator. Hourly format (`usage_measure_id=4`) was validated but is NOT the default. **Evidence**: catalog confirmed, live pricing API validated for all 4 specs. See `docs/nat-gateway-discovery.md` for full details.

**Integration**: No `validate_availability`. Should generate warnings if VPC not in architecture. Contributes to `monthly_total`.

**Proposed Templates**:
- `nat-gateway-public-payg`: params {quantity, nat_resource_spec, usage_days}. Status: `ready` → **IMPLEMENTED** (public NAT instance only, day-based billing).
- `nat-gateway-bandwidth-payg`: params {quantity, bandwidth_mbps, monthly_hours}. Status: `research_required` (bandwidth resource_spec unknown).

**Risks**: Private/Elastic/Exclusive NAT resource_spec unknown. Bandwidth billing may overlap with EIP bandwidth (double cobro). NAT Gateway bandwidth is separate from EIP bandwidth.

**Test Cases**: Unit: render product_infos with valid resource_spec. Live: query price for small/middle/large/xlarge in la-north-2. Invalid: empty resource_spec. monthly_total: instance (+ bandwidth when available).

**Validated Pricing (live BSS/OCE, 30-day format)**:
- `natgateway_small` (10K SNAT) × 30d = USD 73.14/month
- `natgateway_middle` (50K SNAT) × 30d = USD 137.16/month
- `natgateway_large` (200K SNAT) × 30d = USD 269.73/month
- `natgateway_xlarge` (1M SNAT) × 30d = USD 475.47/month

**Validated Pricing (live BSS/OCE, 730h format)**:
- `natgateway_small` × 730h = USD 74.16/month
- `natgateway_middle` × 730h = USD 139.07/month
- `natgateway_large` × 730h = USD 273.48/month
- `natgateway_xlarge` × 730h = USD 482.08/month

### 2.3 WAF

**Billing**: Instance (dedicated) per hour OR pay-per-use (domain + rule + request counts). Two modes: dedicated engine (instance-based) and cloud WAF (pay-per-use by domain/rule/request).

**Dependencies**: ELB (upstream), EIP (public access), LTS (log audit).

**MCP Modeling**: Multiple templates: `waf-instance-payg` (instance mode) and `waf-cloud-payg` (pay-per-use mode with domain/rule/request counts). `service_cost_breakdown` for dedicated vs cloud breakdown.

**BSS/OCE**: `hws.service.type.waf` confirmed. 16 resource types: `hws.resource.type.waf.instance` (dedicated), `hws.resource.type.waf.payperusedomain`, `hws.resource.type.waf.payperuserule`, `hws.resource.type.waf.payperuserequest`, `hws.resource.type.waf.domain` (host expansion), `hws.resource.type.waf.rule`, `hws.resource.type.waf.request`, `hws.resource.type.waf.bandwidth`, `hws.resource.type.waf.service`, `hws.resource.type.waf.customization`, `hws.resource.type.waf.delicatedengine`, and 5 more. **Instance resource_spec CONFIRMED**: `waf.instance.professional` (USD 576.70/month) and `waf.instance.enterprise` (USD 1,365.10/month). `usage_factor` = "Duration" for instance, "count" for domain/rule/request. **Evidence**: catalog confirmed, live pricing API validated for professional and enterprise editions. **PENDING**: resource_spec for pay-per-use domain/rule/request and all expansion packages (20+ variants tested, all "Product not found" or CBC.6074). See `docs/waf-discovery.md` for full details.

**Integration**: No `validate_availability`. `service_cost_breakdown` recommended for dedicated+cloud split. Contributes to `monthly_total`.

**Proposed Templates**:
- `waf-instance-payg`: params {quantity, resource_spec (default: waf.instance.professional), monthly_hours}. Status: `resource_spec_confirmed` → ready for implementation (instance only).
- `waf-cloud-domain-payg`: params {domain_count, rule_count, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).

**Risks**: Pay-per-use mode has variable costs (requests) hard to predict. Dedicated engine has base cost + bandwidth expansion. resource_spec differs by mode. Expansion packages (bandwidth, service, customization) return CBC.6074 ("The billing item does not exist"), suggesting subscription-only or undiscoverable resource_spec.

**Test Cases**: Unit: render for both modes. Live: price dedicated instance professional/enterprise. Invalid: negative domain_count. monthly_total: instance + domain + rule + request.

**Validated Pricing (live BSS/OCE)**:
- `waf.instance.professional` × 730h = USD 576.70/month
- `waf.instance.enterprise` × 730h = USD 1,365.10/month

### 2.4 CFW / Cloud Firewall

**Billing**: Instance (standard/professional) + EIP expansion packs + VPC expansion packs + bandwidth expansion. Base instance includes default EIP/VPC quotas. Standard edition NOT available for pay-per-use (yearly/monthly only). Professional edition available for both billing modes.

**Dependencies**: VPC (required), EIP (protected EIPs), ELB (optional upstream).

**MCP Modeling**: Multiple templates: `cfw-instance-payg` (base) + expansion packs. `service_cost_breakdown` for base + expansions.

**BSS/OCE**: `hws.service.type.cfw` confirmed. 6 resource types: `hws.resource.type.cfw` (base), `hws.resource.type.cfw.exp.eip`, `hws.resource.type.cfw.exp.vpc`, `hws.resource.type.cfw.exp.bandwidth`, `hws.resource.type.cfw.throughput` (HCSO-only), `hws.resource.type.cfw.exp.trafficflow`. **Instance resource_spec CONFIRMED**: `cfw.professional` (on-demand USD 0.36/h = USD 262.80/month; period USD 1,450/month) and `cfw.standard` (period only USD 420/month). `usage_factor` = "usage_duration" for on-demand, "period_duration" for period. **Expansion resource_spec NOT FOUND**: 22+ naming variants tested across on-demand and period APIs, all returned CBC.6006 "Product not found". Expansion packages are only available with yearly/monthly billing per CFW documentation. See `docs/cfw-discovery.md` for full details.

**Integration**: No `validate_availability`. `service_cost_breakdown` recommended. Contributes to `monthly_total`. Warnings when EIP count exceeds base quota.

**Proposed Templates**:
- `cfw-instance-payg`: params {quantity, instance_resource_spec (default: cfw.professional), monthly_hours}. Status: `resource_spec_confirmed` → ready for implementation (instance only, professional on-demand).
- `cfw-expansion-eip-payg`: params {quantity, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).
- `cfw-expansion-vpc-payg`: params {quantity, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).
- `cfw-expansion-bandwidth-payg`: params {quantity, bandwidth_mbps, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).

**Risks**: Expansion pack resource_spec not discoverable via BSS/OCE API or naming convention inference (same pattern as WAF expansion packages). Subcotizacion if base quota exceeded without expansion. Standard edition not available for pay-per-use. On-demand monthly rate (USD 262.80) is significantly lower than period rate (USD 1,450) for professional - architects may underestimate if they compare against period pricing.

**Test Cases**: Unit: render base instance. Live: price professional on-demand and standard/professional period. Invalid: cfw.standard with on-demand (Product not found). monthly_total: instance (+ expansions when available).

**Validated Pricing (live BSS/OCE)**:
- `cfw.professional` (on-demand) × 730h = USD 262.80/month (USD 0.36/hour)
- `cfw.professional` (period, 1 month) = USD 1,450.00/month
- `cfw.standard` (period, 1 month) = USD 420.00/month

### 2.5 SFS Turbo

**Billing**: Capacity (GB) per hour + throughput tier. Two types: Standard and Enhanced. Billed by provisioned capacity, not usage.

**Dependencies**: VPC (subnet), ECS/CCE (mount clients), OBS (optional backup).

**MCP Modeling**: Simple template `sfs-turbo-standard-payg` with capacity_gb and resource_spec parameters.

**BSS/OCE**: `hws.service.type.sfs` confirmed. `hws.resource.type.sfs.turbo` exists. **resource_spec CONFIRMED**: `sfs.turbo.standard`. **usage_factor CONFIRMED**: `period` for on-demand (NOT "Duration"). **Evidence**: live pricing API validated in la-north-2. 500 GB × 730h = USD 45.42/month. See `docs/sfs-turbo-discovery.md` for full details.

**Integration**: No `validate_availability`. Contributes to `monthly_total`. Warnings for minimum capacity thresholds (500 GB).

**Proposed Templates**:
- `sfs-turbo-standard-payg`: params {quantity, resource_spec, capacity_gb, monthly_hours}. Status: `resource_spec_confirmed` → ready for implementation.

**Risks**: Enhanced and HPC resource_spec NOT FOUND (all naming variants tested failed). Throughput/traffic usage_types not validated. Minimum capacity (500 GB) may cause subcotizacion if architect specifies less. usage_factor asymmetry: on-demand uses `period`, subscription uses `duration`.

**Test Cases**: Unit: render with capacity_gb. Live: price 500 GB standard. Invalid: capacity_gb < 500. monthly_total: capacity * hourly_rate * 730.

### 2.6 DDS (Document Database Service / MongoDB)

**Billing**: Instance (dds.vm) + storage (dds.volume) + backup (dds.obs). Cluster mode adds mongos and shard instances (both billed as dds.vm). Similar to RDS pattern.

**Dependencies**: VPC (subnet), ECS (app connections), OBS (backup), LTS (audit).

**MCP Modeling**: Macro-template following RDS pattern: `dds-instance-payg` + `dds-volume-payg` + `dds-backup-payg`. Cluster mode adds mongos + shard instance pricing.

**BSS/OCE**: `hws.service.type.dds` confirmed. 5 resource types: `hws.resource.type.dds.vm`, `hws.resource.type.dds.volume`, `hws.resource.type.dds.cluster`, `hws.resource.type.dds.obs`, `hws.resource.type.dds.decmem`. **Evidence**: catalog confirmed. **Instance resource_spec CONFIRMED**: `dds.mongodb.s6.large.2.repset` (repset), `dds.mongodb.s6.large.2.mongos` (mongos), `dds.mongodb.s6.large.2.shard` (shard). **Volume resource_spec NOT FOUND**: 20+ naming variants tested, all "Product not found". See `docs/dds-discovery.md` for full details.

**Integration**: No `validate_availability`. Contributes to `monthly_total`. Warnings for cluster vs replica set mode.

**Proposed Templates**:
- `dds-instance-payg`: params {quantity, instance_resource_spec, monthly_hours}. Status: `ready` → implemented (instance only).
- `dds-volume-payg`: params {quantity, storage_resource_spec, storage_gb, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).

**Risks**: Volume resource_spec not discoverable via BSS/OCE API or naming convention inference (same pattern as RDS volume before Price Calculator export). Cluster mode has 3+ instance roles (mongos, shard, config) all billed as dds.vm. Storage type naming mismatch: DDS API returns `ULTRAHIGH`, BSS/OCE may use different name.

**Test Cases**: Unit: render instance. Live: price DDS instance repset/mongos/shard. Invalid: empty instance_resource_spec. monthly_total: instance (+ volume when available + backup when available).

**Validated Pricing (live BSS/OCE)**:
- `dds.mongodb.s6.medium.4.repset` (1 vCPU, 4 GB) × 730h = USD 102.20/month
- `dds.mongodb.s6.large.2.repset` (2 vCPU, 4 GB) × 730h = USD 184.69/month
- `dds.mongodb.c6.large.4.repset` (2 vCPU, 8 GB) × 730h = USD 294.34/month
- `dds.mongodb.s6.large.2.mongos` (2 vCPU, 4 GB) × 730h = USD 61.32/month
- `dds.mongodb.s6.large.2.shard` (2 vCPU, 4 GB) × 730h = USD 184.69/month

### 2.7 GaussDB

**Billing**: Instance (gaussdb.vm) + storage (gaussdb.volume) + backup (gaussdb.obs). Distributed mode (gaussdb.cluster). Supports MySQL, PostgreSQL, openGauss engines.

**Dependencies**: VPC (subnet), ECS (app connections), OBS (backup), LTS (audit).

**MCP Modeling**: Macro-template following RDS pattern: `gaussdb-instance-payg` + `gaussdb-volume-payg` + `gaussdb-backup-payg`.

**BSS/OCE**: **TWO service type codes discovered**: `hws.service.type.gaussdb` (4 resource types) and `hws.service.type.taurus` (15 resource types). GaussDB MySQL (formerly TaurusDB) is primarily billed under `hws.service.type.taurus`. The `taurus` service type includes MySQL (`taurus.vm`), openGauss (`opengauss.vm`), PostgreSQL (`tauruspg.vm`), Serverless (`taurus.serverless`), Monitor (`taurus.monitor`), and Flow (`taurus.flow`). **Evidence**: catalog confirmed for both service types. **resource_spec NOT FOUND**: 30+ naming variants tested across both service types, 3 regions (la-north-2, sa-brazil-1, ap-southeast-1), and multiple usage_factor values. All returned "Product not found". See `docs/gaussdb-discovery.md` for full details.

**Integration**: No `validate_availability`. Contributes to `monthly_total`. Warnings for engine type selection and dual service type ambiguity.

**Proposed Templates**:
- `gaussdb-mysql-instance-payg`: params {quantity, instance_resource_spec, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).
- `gaussdb-opengauss-instance-payg`: params {quantity, instance_resource_spec, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).
- `gaussdb-mysql-volume-payg`: params {quantity, storage_resource_spec, storage_gb, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).

**Risks**: resource_spec varies by engine (mysql/pg/opengauss). Even instance resource_spec not found (worse than DDS where instance was confirmed). Dual service type (gaussdb + taurus) adds ambiguity. Distributed mode adds cluster pricing. Storage spec discovery may face same issues as RDS. Requires Price Calculator export or billing statement analysis to unblock.

**Test Cases**: Blocked until resource_spec discovered.

### 2.8 DRS (Data Replication Service)

**Billing**: Configuration fee (mandatory) + EIP fee (optional). Configuration fee covers compute, storage, and data processing. Pay-per-use: calculated by the second, billed every hour. Real-time migration: pay-per-use ONLY. Real-time synchronization and DR: pay-per-use and yearly/monthly.

**Dependencies**: RDS/DDS/GaussDB (source/target), VPC (subnet), EIP (public network tasks), ECS (optional).

**MCP Modeling**: Simple template `drs-instance-payg` for migration/sync/DR task. Flow-based pricing may require separate template.

**BSS/OCE**: `hws.service.type.drs` confirmed. 4 resource types: `hws.resource.type.drs.instance` (usage_type: architecture), `hws.resource.type.drs.vm` (usage_type: Duration), `hws.resource.type.drs.volume` (usage_type: Duration), `hws.resource.type.drs.flow` (usage_type: Flow). **Evidence**: catalog confirmed, usage types confirmed, DRS API node_types confirmed, DRS v5 API ProductInfo model confirmed (resource_spec_code maps to BSS resource_spec). **resource_spec NOT FOUND**: 30+ naming variants tested across all 4 resource types, multiple regions, both billing APIs (on-demand + period), with region/AZ/task_type suffixes - all returned "Product not found" or "Billing item does not exist". BSS catalog listing endpoints all 404. See `docs/drs-discovery.md` for full details.

**DRS API Node Types** (from ListAvailableNodeTypes API in la-north-2):
- mysql/migration/up: high
- mysql/sync/up/down: micro, small, medium, high, xlarge
- mysql/cloudDataGuard/up/down: high
- postgresql/sync/up: micro, small, medium, high, xlarge
- mongodb/migration/up: high

**Integration**: No `validate_availability`. Contributes to `monthly_total`. Warnings for short-lived migration tasks (cost may be minimal).

**Proposed Templates**:
- `drs-instance-payg`: params {quantity, resource_spec, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).
- `drs-flow-payg`: params {quantity, flow_gb, monthly_hours}. Status: `missing_product_infos_template` (blocked by unknown resource_spec).

**Risks**: DRS is typically short-lived (migration), so monthly estimates may overstate cost. Flow-based pricing hard to predict. resource_spec unknown - same category as GaussDB (blocked by BSS product catalog opacity). DRS CreateJob API has `product_id` field that likely maps to BSS resource_spec, but format is undocumented.

**Test Cases**: Blocked until resource_spec discovered.

### 2.9 VPN (Virtual Private Network)

**Billing**: Gateway instance per hour (V300 = Professional with 10 VPN Connection Groups) + traffic per GB (billed under VPC service as bandwidth). Two traffic components: active (12_share) and standby (12_bgp).

**Dependencies**: VPC (required), EIP (for public-facing VPN), VPC bandwidth (for VPN traffic billing).

**MCP Modeling**: Macro-template `vpn-site-to-site-payg` expanding to VPN gateway + active traffic (12_share) + standby traffic (12_bgp). Fase 1: simple template `vpn-gateway-payg` (gateway only).

**BSS/OCE**: `hws.service.type.vpn` confirmed. 3 resource types: `hws.resource.type.vpn.ipsecvpn` (Enterprise Edition VPN), `hws.resource.type.vpn.vgw` (Virtual Private Network), `hws.resource.type.vpnconnection` (VPN). **Only `vpn.ipsecvpn` works** for on-demand pricing; `vpn.vgw` returns CBC.6074, `vpnconnection` returns CBC.6006. **Gateway resource_spec CONFIRMED**: `V300` (Professional, USD 0.33/h = USD 240.90/month 730h). **Traffic resource_specs CONFIRMED**: `12_share` (active, USD 0.081/GB) and `12_bgp` (standby, USD 0.081/GB) under `hws.service.type.vpc` / `hws.resource.type.bandwidth`. **resource_size and resource_size_measure_id are REQUIRED** for VPN gateway (CBC.6001 error without them). `usage_factor` = "duration" for gateway, "upflow" for traffic. `usage_measure_id` = 4 (Hour) for gateway, 10 (GB) for traffic. **Evidence**: catalog confirmed, live pricing API validated, real quotation matched with 100% accuracy (USD 273.30 total). See `docs/vpn-discovery.md` for full details.

**Integration**: No `validate_availability`. Contributes to `monthly_total`. Warnings for traffic estimation (variable cost).

**Proposed Templates**:
- `vpn-gateway-payg`: params {quantity, gateway_resource_spec, monthly_hours, resource_size}. Status: `ready` → **IMPLEMENTED** (gateway only, Fase 1).
- `vpn-site-to-site-payg` (macro): params {quantity, gateway_resource_spec, monthly_hours, resource_size, traffic_gb}. Status: `resource_spec_confirmed` → designed but deferred (Fase 2, gateway + traffic). Traffic components can now use `vpc-bandwidth-traffic-gb-payg`.
- `vpc-bandwidth-traffic-gb-payg`: params {quantity, traffic_resource_spec, traffic_gb}. Status: `ready` → **IMPLEMENTED** (VPC bandwidth traffic by GB, reusable for VPN and EIP traffic).

**Risks**: Traffic cost is 32% of total in reference quotation (USD 32.40 of USD 273.30). Gateway-only template will understate cost if traffic not estimated separately. V1/V2/V5 specs not found in la-north-2 (may exist in other regions or only as period/subscription). resource_size behavior is non-linear for multiple gateway instances. Traffic uses different cloud_service_type (VPC) than gateway (VPN), complicating macro-template.

**Test Cases**: Unit: render product_infos with V300 and resource_size=1. Live: query price for V300 in la-north-2. Invalid: empty resource_spec, missing resource_size. monthly_total: gateway (+ traffic when available).

**Validated Pricing (live BSS/OCE, 730h format)**:
- `V300` (Professional, 10 conn groups) × 730h = USD 240.90/month
- `12_share` (active traffic) × 200 GB = USD 16.20
- `12_bgp` (standby traffic) × 200 GB = USD 16.20
- **Total** = USD 273.30 (EXACT MATCH with real quotation)

**Validated Pricing (live BSS/OCE, 30d format)**:
- `V300` × 30d = USD 237.60/month

## 3. Implementation Ranking

| Rank | Service | Rationale |
|------|---------|-----------|
| 1 | SFS Turbo | Simplest: 1 resource type, capacity-based, similar to EVS pattern |
| 2 | DDS | Follows RDS pattern exactly (instance+volume), BSS/OCE confirmed |
| 3 | GaussDB | BSS/OCE confirmed (2 service types), but resource_spec NOT FOUND for any engine (30+ variants tested) |
| 4 | DCS Redis | Instance resource_spec CONFIRMED (all 5 cache modes), instance-only Fase 1 viable |
| 5 | CFW | BSS/OCE confirmed but expansion packs add template complexity |
| 6 | WAF | Instance resource_spec CONFIRMED (professional + enterprise), instance-only Fase 1 viable; cloud pay-per-use blocked |
| 7 | DRS | BSS/OCE confirmed but short-lived nature and flow pricing are edge cases |
| 8 | NAT Gateway | UNBLOCKED: `cloud_service_type` confirmed (`hws.service.type.natgateway`), all 4 public NAT specs validated |
| 9 | VPN | UNBLOCKED: `resource_spec` confirmed (`V300`), pricing validated against real quotation (USD 273.30 exact match), gateway + traffic components confirmed |

## 4. Services Ready for Implementation

- **EVS GPSSD**: **IMPLEMENTED** as `evs-gpssd-gb-payg` (status `ready`). `resource_spec` confirmed (`GPSSD`), on-demand pricing validated via live BSS/OCE API in la-north-2. Price scales linearly at USD 0.0949/GB/month. Validated: 200 GB = USD 18.98, 300 GB = USD 28.47, 700 GB = USD 66.43. Quotation comparison within +0.96% tolerance. GPSSD2 not found in BSS/OCE (CBC.6006). See `docs/evs-gpssd-discovery.md`.
- **ECS Compute + OS License**: **IMPLEMENTED** as `ecs-flavor-payg` (compute) and `ecs-os-license-payg` (OS license), both status `ready`. **Period templates IMPLEMENTED** as `ecs-flavor-period` and `ecs-os-license-period`, both status `ready`. Period billing matches quotation EXACTLY. On-demand BSS/OCE prices ~1.39x higher than period for compute, ~2.00x for SUSE. AlmaLinux has no license productInfo (cost = USD 0). See `docs/ecs-benchmark-discovery.md`.
- **SFS Turbo Standard**: `resource_spec` confirmed (`sfs.turbo.standard`), on-demand pricing validated, product_infos_template defined. See `docs/sfs-turbo-discovery.md`.
- **DDS Instance**: `resource_spec` confirmed for repset/mongos/shard roles (e.g., `dds.mongodb.s6.large.2.repset`), on-demand pricing validated, product_infos_template defined. Volume and backup blocked. See `docs/dds-discovery.md`.
- **DCS Redis Instance**: `resource_spec` confirmed for all 5 cache modes (single, ha, ha_rw_split, proxy, cluster) using V3 spec_codes (e.g., `redis.single.xu1.large.2`), on-demand pricing validated, product_infos_template defined. Bandwidth, OBS backup, and shard blocked. See `docs/dcs-redis-discovery.md`.
- **WAF Instance**: `resource_spec` confirmed for professional and enterprise editions (`waf.instance.professional`, `waf.instance.enterprise`), on-demand pricing validated, product_infos_template defined. Pay-per-use domain/rule/request and expansion packages blocked. See `docs/waf-discovery.md`.
- **CFW Instance**: `resource_spec` confirmed for professional edition on-demand (`cfw.professional`, USD 0.36/hour) and both editions period (`cfw.standard` USD 420/month, `cfw.professional` USD 1,450/month), product_infos_template defined. EIP/VPC/bandwidth expansion packages blocked. **IMPLEMENTED** as `cfw-instance-payg` (Fase 1, professional on-demand only). See `docs/cfw-discovery.md`.
- **NAT Gateway**: **IMPLEMENTED** as `nat-gateway-public-payg` (Fase 1, public NAT instance only, day-based billing with `usage_days` default 30). `cloud_service_type` confirmed (`hws.service.type.natgateway`), `resource_spec` confirmed for all 4 public NAT specs (`natgateway_small` USD 73.14/mo, `natgateway_middle` USD 137.16/mo, `natgateway_large` USD 269.73/mo, `natgateway_xlarge` USD 475.47/mo at 30d). Private/Elastic/Exclusive NAT and bandwith add-on blocked. See `docs/nat-gateway-discovery.md`.
- **VPN Gateway**: **IMPLEMENTED** as `vpn-gateway-payg` (Fase 1, gateway only). `resource_spec` confirmed (`V300` = Professional, 10 connection groups), on-demand pricing validated (USD 240.90/month 730h). `resource_size` and `resource_size_measure_id` are REQUIRED for VPN gateway. Traffic components confirmed (`12_share` active, `12_bgp` standby, both USD 0.081/GB) but deferred to Fase 2. Full architecture validated against real quotation: USD 273.30 exact match. See `docs/vpn-discovery.md`.
- **VPC Bandwidth Traffic**: **IMPLEMENTED** as `vpc-bandwidth-traffic-gb-payg` (service `vpc`, status `ready`). Reusable template for VPN traffic and EIP traffic billed by GB (upflow). `resource_spec` confirmed: `12_bgp` (Dynamic BGP) and `12_share` (shared), both USD 0.081/GB in la-north-2. 2 × 300GB = USD 48.60 (real EIP quote: USD 48.61, 0.01 rounding). See `docs/eip-traffic-discovery.md`.
- **CBR Server Backup Vault**: **IMPLEMENTED** as `cbr-server-backup-vault-gb-payg` (service `cbr`, status `ready`). `resource_spec` confirmed: `vault.backup.server.normal`. On-demand pricing validated: 1000 GB × 730h = USD 36.50/month, 2400 GB × 730h = USD 87.60/month (exact match with benchmark quote). Linear scaling at USD 0.0365/GB/month. See `docs/cbr-discovery.md`.
- **CBR Disk Backup Vault**: **IMPLEMENTED** as `cbr-disk-backup-vault-gb-payg` (service `cbr`, status `ready`). `resource_spec` confirmed: `vault.backup.volume.normal`. On-demand pricing validated: 1000 GB × 730h = USD 21.90/month, 2400 GB × 730h = USD 52.56/month. Linear scaling at USD 0.0219/GB/month. See `docs/cbr-discovery.md`.

## 5. Services Blocked by Lack of resource_spec

- **NAT Gateway**: `cloud_service_type` CONFIRMED: `hws.service.type.natgateway`. Public NAT `resource_spec` CONFIRMED for all 4 specs (`natgateway_small`, `natgateway_middle`, `natgateway_large`, `natgateway_xlarge`). **IMPLEMENTED** as `nat-gateway-public-payg` (day-based billing). Private/Elastic/Exclusive NAT resource_spec PENDING. Bandwidth add-on PENDING. SNAT/DNAT rule pricing PENDING (Fase 2). See `docs/nat-gateway-discovery.md`.
- **WAF Pay-per-use / Expansion Packages**: `resource_spec` for `hws.resource.type.waf.payperusedomain`, `hws.resource.type.waf.payperuserule`, `hws.resource.type.waf.payperuserequest`, `hws.resource.type.waf.domain`, `hws.resource.type.waf.rule`, `hws.resource.type.waf.request`, `hws.resource.type.waf.bandwidth`, `hws.resource.type.waf.service`, `hws.resource.type.waf.customization`, and `hws.resource.type.waf.delicatedengine` not found. 20+ naming variants tested. Expansion packages return CBC.6074 ("The billing item does not exist"). Requires Price Calculator export or billing statement analysis. Instance pricing is unblocked via `hws.resource.type.waf.instance`.
- **CFW Expansion Packages**: `resource_spec` for `hws.resource.type.cfw.exp.eip`, `hws.resource.type.cfw.exp.vpc`, and `hws.resource.type.cfw.exp.bandwidth` not found. 22+ naming variants tested across on-demand and period APIs, all returned CBC.6006 ("Product not found"). Expansion packages are only available with yearly/monthly billing per CFW documentation. Requires Price Calculator export or billing statement analysis. Instance pricing is unblocked via `hws.resource.type.cfw` with `cfw.professional` (on-demand) and `cfw.standard`/`cfw.professional` (period).
- **DDS Volume/Backup**: `resource_spec` for `hws.resource.type.dds.volume` and `hws.resource.type.dds.obs` not found. 20+ naming variants tested. Requires Price Calculator export or billing statement analysis (same pattern as RDS volume before discovery).
- **DCS Redis Bandwidth/OBS/Shard**: `resource_spec` for `hws.resource.type.dcs.bandwidth`, `hws.resource.type.dcs.obs`, and `hws.resource.type.dcs.shard` not found. Requires Price Calculator export or billing statement analysis. Instance pricing is unblocked via `hws.resource.type.dcs3`.
- **GaussDB (all engines)**: `resource_spec` NOT FOUND for instance, volume, or cluster. 30+ naming variants tested across 2 service types (`gaussdb` + `taurus`), 3 regions. Even instance resource_spec not found (worse than DDS where instance was confirmed). Requires Price Calculator export, billing statement analysis, or direct GaussDB API flavor listing. See `docs/gaussdb-discovery.md`.
- **DRS (all resource types)**: `resource_spec` NOT FOUND for instance, vm, volume, or flow. 30+ naming variants tested across all 4 resource types, 2 regions, both on-demand and period pricing APIs, with region/AZ/task_type suffixes. DRS API `ListAvailableNodeTypes` confirmed node_types (micro/small/medium/high/xlarge) but these don't map to BSS resource_spec. DRS v5 API `ProductInfo` model confirmed `resource_spec_code` field (maps 1:1 to BSS `resource_spec`), but values are not exposed by any listing API. BSS catalog listing endpoints all 404. Requires Price Calculator reverse engineering, console network capture, or Huawei Cloud support. See `docs/drs-discovery.md`.
- **All others**: `resource_spec` values need validation via Huawei Cloud Price Calculator or live BSS/OCE pricing API calls.

## 6. Services Requiring Macro-Template

- **DCS Redis**: Cluster mode expands to instance + bandwidth + OBS backup. Instance-only template viable for Fase 1; macro deferred until bandwith/obs/shard resource_spec discovered.
- **DDS**: Instance + volume + backup (mirrors RDS macro pattern). Instance-only template viable for Fase 1; macro deferred until volume resource_spec discovered.
- **GaussDB**: Instance + volume + backup (mirrors RDS macro pattern). **BLOCKED**: even instance resource_spec not found. Dual service type (gaussdb + taurus) adds complexity.
- **VPN**: Gateway + active traffic (12_share) + standby traffic (12_bgp). Gateway-only template viable for Fase 1; macro deferred to Fase 2. Traffic uses different cloud_service_type (VPC) than gateway (VPN).

## 7. Services Requiring service_cost_breakdown

- **WAF**: Dedicated instance vs cloud pay-per-use breakdown. Instance-only Fase 1 viable without breakdown; macro deferred until pay-per-use resource_spec discovered.
- **CFW**: Base instance + EIP/VPC/bandwidth expansion breakdown. Instance-only Fase 1 viable without breakdown; macro deferred until expansion resource_specs discovered.

## 8. Recommended Next Service to Implement

**NAT Gateway** (rank 8, **IMPLEMENTED** for public NAT instance-only Fase 1). Rationale:
- `cloud_service_type` CONFIRMED: `hws.service.type.natgateway`.
- `resource_type` CONFIRMED: `hws.resource.type.natgateway`.
- All 4 `resource_spec` values CONFIRMED via live BSS/OCE pricing API: `natgateway_small`, `natgateway_middle`, `natgateway_large`, `natgateway_xlarge`.
- On-demand pricing validated: Small $73.14/mo, Middle $137.16/mo, Large $269.73/mo, XLarge $475.47/mo (30d).
- `product_infos_template` fully defined.
- `usage_factor` = "duration" (NOT "duration_hour").
- **IMPLEMENTED**: `nat-gateway-public-payg` template with day-based billing (`usage_days`, default 30, `usage_measure_id=0`), status `ready`.
- **Deferred**: Private/Elastic/Exclusive NAT, bandwidth add-on, SNAT/DNAT rule pricing, period template.

**WAF Instance** (rank 6, now unblocked for instance-only). Rationale:
- Instance `resource_spec` confirmed for professional and enterprise editions via live BSS/OCE pricing API.
- On-demand pricing validated: `waf.instance.professional` × 730h = USD 576.70/month, `waf.instance.enterprise` × 730h = USD 1,365.10/month.
- `product_infos_template` for instance is fully defined.
- Pay-per-use domain/rule/request and expansion packages deferred until `resource_spec` discovered.
- **Next step**: implement `waf-instance-payg` template with confirmed product_infos_template and promote to `ready`.
- **Deferred**: Cloud pay-per-use templates, expansion packages, dedicated engine, and service_cost_breakdown (resource_spec not found).

**CFW Instance** (rank 5, **IMPLEMENTED** for instance-only Fase 1). Rationale:
- Instance `resource_spec` confirmed for professional edition (on-demand) and both editions (period) via live BSS/OCE pricing API.
- On-demand pricing validated: `cfw.professional` × 730h = USD 262.80/month (USD 0.36/hour).
- Period pricing validated: `cfw.standard` = USD 420/month, `cfw.professional` = USD 1,450/month.
- `product_infos_template` for on-demand instance is fully defined.
- EIP/VPC/bandwidth expansion packages deferred until `resource_spec` discovered.
- **IMPLEMENTED**: `cfw-instance-payg` template with confirmed product_infos_template, status `ready`.
- **Deferred**: Expansion package templates, period template, and service_cost_breakdown (expansion resource_spec not found).

**DCS Redis Instance** (rank 4) already implemented. See `docs/dcs-redis-discovery.md`.

**DDS Instance** (rank 2) already implemented. See `docs/dds-discovery.md`.

**SFS Turbo** (rank 1) already implemented. See `docs/sfs-turbo-discovery.md`.

**VPN Gateway** (rank 9, **IMPLEMENTED** for gateway-only Fase 1). Rationale:
- `cloud_service_type` CONFIRMED: `hws.service.type.vpn`.
- `resource_type` CONFIRMED: `hws.resource.type.vpn.ipsecvpn`.
- `resource_spec` CONFIRMED: `V300` (Professional, 10 VPN Connection Groups).
- On-demand pricing validated: V300 × 730h = USD 240.90/month.
- `resource_size` and `resource_size_measure_id` are REQUIRED (CBC.6001 without them).
- `product_infos_template` fully defined.
- `usage_factor` = "duration" for gateway, "upflow" for traffic.
- Full architecture validated against real quotation: USD 273.30 exact match (gateway USD 240.90 + active traffic USD 16.20 + standby traffic USD 16.20).
- **IMPLEMENTED**: `vpn-gateway-payg` template with confirmed product_infos_template, status `ready`.
- **Deferred**: `vpn-site-to-site-payg` macro-template (Fase 2, gateway + traffic), V1/V2/V5 specs, period template, service_cost_breakdown.

**CBR Backup Vaults** (**IMPLEMENTED** for server + disk backup vault Fase 1). Rationale:
- `cloud_service_type` CONFIRMED: `hws.service.type.cbr`.
- `resource_type` CONFIRMED: `hws.resource.type.cbr.vault`.
- `resource_spec` CONFIRMED: `vault.backup.server.normal` (server backup) and `vault.backup.volume.normal` (disk backup).
- On-demand pricing validated: Server 2400 GB × 730h = USD 87.60/month (exact match with benchmark quote). Disk 1000 GB × 730h = USD 21.90/month.
- Price scales linearly: Server ≈ USD 0.0365/GB/month, Disk ≈ USD 0.0219/GB/month. Server is 1.67x more expensive than disk per GB.
- `size_measure_id=17` (GB) confirmed working; `resource_size_measure_id=17` also accepted by BSS/OCE. Using `size_measure_id` for consistency with EVS/SFS/RDS templates.
- `product_infos_template` fully defined for both vault types.
- `usage_factor` = "duration" (lowercase), `usage_measure_id` = 4 (Hour).
- **IMPLEMENTED**: `cbr-server-backup-vault-gb-payg` and `cbr-disk-backup-vault-gb-payg` templates, status `ready`.
- **Deferred**: Dedicated cloud replication vault, dedicated cloud backup vault, desktop backup vault, multi-AZ server backup vault, database server backup vault, replication vault, cross-region replication, backup traffic, CBR macro-template.

- **HSS Host Protection** (**IMPLEMENTED** for host protection Fase 1). Rationale:
  - `cloud_service_type` CONFIRMED: `hws.service.type.hss`.
  - `resource_type` CONFIRMED: `hws.resource.type.hss`.
  - `resource_spec` CONFIRMED: `hss.version.premium` (Enterprise/Premium, USD 13.80/PCS/month period, USD 20.44/PCS/month on-demand) and `hss.version.advanced` (Professional, USD 4.50/PCS/month period, USD 7.30/PCS/month on-demand).
  - **IMPORTANT**: The benchmark quotation uses period (monthly subscription) billing. Period price for `hss.version.premium` × 3 PCS = USD 41.40/month (EXACT MATCH with benchmark quote). On-demand price = USD 61.32/month (48.7% more expensive).
  - Edition naming: `hss.version.basic` = Basic (free), `hss.version.advanced` = Professional, `hss.version.premium` = Enterprise/Premium. BSS naming does NOT match commercial names directly.
  - `product_infos_template` fully defined.
  - `usage_factor` = "duration", `usage_measure_id` = 4 (Hour).
  - `subscription_num` represents number of protected hosts (PCS). Price scales linearly.
  - **IMPLEMENTED**: `hss-host-protection-payg` template, status `ready`.
  - **IMPLEMENTED**: `hss-host-protection-period` template, status `ready` (Phase 1 period billing).
  - **PERIOD GAP CLOSED**: Period template returns USD 41.40 for 3 PCS premium (EXACT MATCH with benchmark quote).
  - **Deferred**: Web tamper protection (hss.version.wtp), container security, ransomware protection, quota packages, Container Guard (hws.resource.type.cgs), Host Security Expert Service (hws.resource.type.hses), Host Security Managed Service (hws.resource.type.hsms).

## 9. Phase 2: LTS (Log Tank Service) Implementation

**Billing**: Three main components billed per GB: log read/write traffic, log index traffic, and log storage. Additional components: log transfer (basic OBS, senior DIS/DWS).

**Dependencies**: VPC (required), ECS/CCE (log sources), OBS (transfer destination), AOM/CES (monitoring).

**BSS/OCE**: `hws.service.type.lts` confirmed. 6 resource types: `hws.resource.type.lts` (base), `hws.resource.type.lts.logflow` (read/write traffic), `hws.resource.type.lts.logindex` (index traffic), `hws.resource.type.lts.logstorage` (storage), `hws.resource.type.lts.logtransfer` (transfer), `hws.resource.type.ltsforhcso.gov` (HCSO Gov). **Three resource_specs CONFIRMED** via Playwright Price Calculator discovery and live BSS/OCE validation in la-north-2:

- `lts.log.flow` (log read/write traffic): usage_factor=`traffic`, usage_measure_id=10 (GB). Price: USD 0.05/GB.
- `lts.log.index` (log index traffic): usage_factor=`traffic`, usage_measure_id=10 (GB). Price: USD 0.08/GB.
- `lts.log.storage` (log storage): usage_factor=`aom.size`, usage_measure_id=17 (GB). Price: USD 0.000125/GB.

**Transfer resource_specs DISCOVERED but NOT IMPLEMENTED**:
- `lts.log.transfer.basic` (basic OBS transfer): usage_factor=`logbasictransfertraffic`, usage_measure_id=10.
- `lts.log.transfer.senior` (senior DIS/DWS transfer): usage_factor=`logseniortransfertraffic`, usage_measure_id=10.
- Deferred to Phase 3 due to lower priority.

**Integration**: No `validate_availability`. Contributes to `monthly_total`. Warnings for high traffic volumes.

**Implemented Templates**:
- `lts-log-flow-payg`: params {quantity, traffic_gb}. Status: `ready`.
- `lts-log-index-payg`: params {quantity, traffic_gb}. Status: `ready`.
- `lts-log-storage-payg`: params {quantity, storage_gb}. Status: `ready`.

**Validated Pricing (live BSS/OCE, la-north-2)**:
- `lts.log.flow` × 100 GB = USD 5.00
- `lts.log.index` × 100 GB = USD 8.00
- `lts.log.storage` × 100 GB = USD 0.0125

**Playwright Discovery**: Used Price Calculator at ap-southeast-1 (visual proxy) to capture productInfos. Confirmed resource_spec_code values match BSS/OCE format. See `docs/lts-pricing-request.json` and `docs/lts-pricing-response.json`.

## 10. Phase 2: Services Blocked (resource_spec NOT FOUND)

- **APIG (API Gateway)**: `hws.service.type.apig` confirmed, 3 resource types. `resource_spec` NOT FOUND via naming inference (apig.basic, apig.instance.basic, etc. → CBC.6006). Requires Playwright Price Calculator discovery.
- **DMS (Distributed Message Service)**: `hws.service.type.dms` confirmed, 6 resource types. `resource_spec` NOT FOUND via naming inference (dms.instance.kafka, dms.instance.kafka.high, etc. → CBC.6006). Requires Playwright Price Calculator discovery.
- **CES (Cloud Eye)**: `hws.service.type.ces` confirmed, 9 resource types. `resource_spec` NOT FOUND (CBC.6074 "billing item does not exist"). May be free tier or period-only. Requires Playwright Price Calculator discovery.
- **CDN**: `hws.service.type.cdn` confirmed, 5 resource types. `resource_spec` NOT FOUND via naming inference (cdn, cdn.flow, etc. → CBC.6006). Requires Playwright Price Calculator discovery.
