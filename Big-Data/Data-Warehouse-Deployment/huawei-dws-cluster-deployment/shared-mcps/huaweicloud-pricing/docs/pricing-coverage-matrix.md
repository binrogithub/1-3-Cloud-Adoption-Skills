# Pricing Coverage Matrix — la-north-2 (Mexico)

**Region**: la-north-2 | **Currency**: USD | **Last updated**: 2026-06-03 | **Phase**: 2

## Matrix

| Service | Template IDs | Status | Billing Modes | Validation | Known Price Examples | Known Gaps | Priority | Next Action |
|---------|-------------|--------|---------------|------------|---------------------|------------|----------|-------------|
| ECS | ecs-linux-2vcpu-4gb-payg, ecs-linux-4vcpu-8gb-payg, ecs-flavor-payg, ecs-os-license-payg, ecs-flavor-period, ecs-os-license-period | READY | on-demand, period | BSS/OCE | s6.large.2.linux 730h ≈ USD 43.22/mo | ESSD system disk, GPU flavors | HIGH | Maintain |
| EVS | evs-ssd-gb-payg, evs-gpssd-gb-payg | READY | on-demand | BSS/OCE | GPSSD 100GB 730h = USD 9.49/mo | ESSD, period billing | HIGH | Add ESSD if resource_spec discovered |
| EIP | eip-bandwidth-mbps-payg | READY | on-demand | BSS/OCE | 10Mbps 730h = USD 121.91/mo | IP reservation, traffic billing, period | MEDIUM | Add period template |
| VPC | vpc-bandwidth-traffic-gb-payg | READY | on-demand (traffic) | BSS/OCE | 12_bgp 300GB = USD 24.30 | Period, shared bandwidth | MEDIUM | Maintain |
| ELB | elb-shared-instance-payg, elb-shared-lcu-payg | READY | on-demand | BSS/OCE + Playwright | instance+LCU 730h = USD 24.33/mo | Dedicated ELB, L7 LCU, period | MEDIUM | Add period template |
| RDS | rds-mysql-instance-payg, rds-mysql-volume-payg | READY | on-demand | BSS/OCE + Playwright | instance+volume 730h = USD 64.97/mo | PostgreSQL/SQL Server, period | HIGH | Add period, PostgreSQL |
| OBS | obs-standard-gb-month | READY | on-demand | BSS/OCE | 500GB = USD 1.46/mo | Infrequent access, request pricing | MEDIUM | Add IA storage class |
| SFS | sfs-turbo-standard-payg | READY | on-demand | BSS/OCE | 500GB 730h = USD 45.42/mo | Enhanced, HPC types | LOW | Maintain |
| DDS | dds-instance-payg | READY | on-demand | BSS/OCE | s6.medium.4.repset 730h = USD 102.20/mo | Volume, backup, period | MEDIUM | Discover volume resource_spec |
| DCS | dcs-redis-instance-payg | READY | on-demand | BSS/OCE | single.xu1.large.2 730h = USD 24.82/mo | Bandwidth, OBS backup, shard | MEDIUM | Maintain |
| WAF | waf-instance-payg | READY | on-demand | BSS/OCE | professional 730h = USD 576.70/mo | Cloud pay-per-use, expansion packages | MEDIUM | Maintain |
| CFW | cfw-instance-payg | READY | on-demand | BSS/OCE | professional 730h = USD 262.80/mo | Expansion packages (EIP/VPC/bandwidth) | MEDIUM | Maintain |
| NAT | nat-gateway-public-payg | READY | on-demand (day-based) | BSS/OCE | small 30d = USD 73.14/mo | Private/Elastic/Exclusive NAT, period | MEDIUM | Maintain |
| VPN | vpn-gateway-payg | READY | on-demand | BSS/OCE | V300 730h = USD 240.90/mo | Site-to-site macro, period | MEDIUM | Implement vpn-site-to-site macro |
| CBR | cbr-server-backup-vault-gb-payg, cbr-disk-backup-vault-gb-payg | READY | on-demand | BSS/OCE | server 2400GB = USD 87.60/mo | Replication vault, desktop vault | LOW | Maintain |
| CCE | cce-cluster-mgmt-payg | READY | on-demand | BSS/OCE | cce.s1.small 730h ≈ USD 0.00/mo | Turbo cluster, period | MEDIUM | Add period template |
| HSS | hss-host-protection-payg, hss-host-protection-period | READY | on-demand, period | BSS/OCE | premium 3PCS period = USD 41.40/mo | WTP, container, ransomware | MEDIUM | Maintain |
| **LTS** | **lts-log-flow-payg, lts-log-index-payg, lts-log-storage-payg** | **READY** | **on-demand** | **BSS/OCE + Playwright** | **flow 100GB = USD 5.00, index 100GB = USD 8.00, storage 100GB = USD 0.0125** | **Log transfer (basic/senior), cold storage, period** | **HIGH** | **Add transfer templates if needed** |
| APIG | — | DISCOVERED_NOT_IMPLEMENTED | on-demand, period | BSS/OCE catalog confirmed | — | resource_spec NOT FOUND via naming inference | HIGH | Playwright Price Calculator discovery required |
| DMS | — | DISCOVERED_NOT_IMPLEMENTED | on-demand, period | BSS/OCE catalog confirmed | — | resource_spec NOT FOUND via naming inference | HIGH | Playwright Price Calculator discovery required |
| CES | — | DISCOVERED_NOT_IMPLEMENTED | on-demand | BSS/OCE catalog confirmed | — | resource_spec NOT FOUND (CBC.6074) | MEDIUM | Playwright Price Calculator discovery required |
| CDN | — | DISCOVERED_NOT_IMPLEMENTED | on-demand (traffic) | BSS/OCE catalog confirmed | — | resource_spec NOT FOUND via naming inference | MEDIUM | Playwright Price Calculator discovery required |
| GaussDB | — | BLOCKED | on-demand | BSS/OCE catalog confirmed (2 service types) | — | resource_spec NOT FOUND (30+ variants) | LOW | Requires billing statement or console capture |
| DRS | — | BLOCKED | on-demand | BSS/OCE catalog confirmed | — | resource_spec NOT FOUND (30+ variants) | LOW | Blocked per previous analysis |
| Auto Scaling | — | NOT_STARTED | free (no charge) | — | USD 0 | No charge for AS service itself | LOW | No template needed (free service) |
| AOM | — | NOT_STARTED | on-demand | — | — | Complex pricing model | LOW | Low priority |

## Architecture Coverage Summary

| Architecture Type | Covered Services | Missing (High-Value) |
|-------------------|-----------------|---------------------|
| Small web app | ECS, EVS, ELB, EIP, RDS, OBS, CBR, HSS, WAF | — (fully covered) |
| E-commerce | ELB, ECS, RDS, DCS, OBS, WAF, CBR, HSS | **LTS** (now covered), Auto Scaling (free) |
| Private workload + outbound | ECS, EVS, NAT, EIP/traffic, CBR, HSS | **LTS** (now covered) |
| API platform | **APIG** (blocked), ECS/CCE, ELB, WAF, DCS, RDS | APIG resource_spec discovery |
| Data/migration | OBS, SFS, CBR, RDS/DDS | DRS (blocked), GaussDB (blocked) |

## Phase 2 Batch Results

| Service | Status | productInfos Captured | Template Added | BSS/OCE Validation | Playwright Used |
|---------|--------|----------------------|----------------|-------------------|-----------------|
| LTS | VALIDATED_READY_TO_TEMPLATE | Yes (3 components) | Yes (3 templates) | Yes (la-north-2) | Yes (ap-southeast-1 proxy) |
| APIG | BLOCKED_MISSING_RESOURCE_SPEC | No | No | No (CBC.6006) | Not yet attempted |
| DMS | BLOCKED_MISSING_RESOURCE_SPEC | No | No | No (CBC.6006) | Not yet attempted |
| CES | BLOCKED_MISSING_RESOURCE_SPEC | No | No | No (CBC.6074) | Not yet attempted |
| CDN | BLOCKED_MISSING_RESOURCE_SPEC | No | No | No (CBC.6006) | Not yet attempted |

## LTS Discovered productInfos

### Log Read/Write Traffic (lts.log.flow)
```json
{
  "cloud_service_type": "hws.service.type.lts",
  "resource_type": "hws.resource.type.lts.logflow",
  "resource_spec_code": "lts.log.flow",
  "usage_factor": "traffic",
  "usage_measure_id": 10
}
```
- Price: USD 0.05/GB in la-north-2

### Log Index Traffic (lts.log.index)
```json
{
  "cloud_service_type": "hws.service.type.lts",
  "resource_type": "hws.resource.type.lts.logindex",
  "resource_spec_code": "lts.log.index",
  "usage_factor": "traffic",
  "usage_measure_id": 10
}
```
- Price: USD 0.08/GB in la-north-2

### Log Storage (lts.log.storage)
```json
{
  "cloud_service_type": "hws.service.type.lts",
  "resource_type": "hws.resource.type.lts.logstorage",
  "resource_spec_code": "lts.log.storage",
  "usage_factor": "aom.size",
  "usage_measure_id": 17
}
```
- Price: USD 0.000125/GB in la-north-2

### Log Transfer (discovered but not implemented)
- `lts.log.transfer.basic` — basic OBS transfer, usage_factor=`logbasictransfertraffic`
- `lts.log.transfer.senior` — senior DIS/DWS transfer, usage_factor=`logseniortransfertraffic`
- Not implemented in this phase due to lower priority
