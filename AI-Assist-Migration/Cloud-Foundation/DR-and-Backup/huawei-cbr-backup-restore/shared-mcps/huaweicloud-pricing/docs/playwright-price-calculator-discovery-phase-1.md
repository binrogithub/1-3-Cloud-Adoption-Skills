# Playwright Price Calculator Discovery — Phase 1 (Final Consolidated)

## Summary

Consolidated results from Huawei Cloud Price Calculator validation via Playwright MCP.
All MCP validations use region `la-north-2` (Mexico). Visual proxy uses `la-south-2` only
when the web calculator does not expose `la-north-2`. Currency baseline: **USD**. CNY is out of scope.

## Validation Matrix

| Service | Status | Visual Price (USD) | MCP Price (USD) | Delta | Notes |
|---|---|---|---|---|---|
| ECS s6.large.2 + GPSSD 40 GiB | OK | 43.22 | 43.216 | rounding only | 730h convention |
| RDS MySQL instance + volume | OK | 64.97 | 64.97 (47.45 + 17.52) | 0.000 | Multi-productInfo pattern confirmed |
| EVS GPSSD 100 GiB | OK | 9.49 | 9.49 | 0.000 | la-north-2 direct |
| EIP bandwidth 10 Mbps | OK | 121.91 | 121.91 | 0.000 | Bandwidth component only; IP reservation (USD 3.65) discovered but not included by default (waived when EIP attached) |
| OBS Standard 720 GB | OK | 2.10 (720h) | 2.13 (730h) | hours convention | Same hourly rate USD 0.00291667/h; 720h vs 730h documented difference |
| ELB v3 instance + LCU | OK | 24.33 | 24.33 (18.25 + 6.08) | 0.000 | Paid ELB v3; template `elb-shared-instance-payg` (canonical name) |
| NAT Gateway small 30d | OK | 73.14 | 73.14 | 0.000 | Day-based billing; independent composition with EIP/traffic |

## Detailed Findings

### ECS

- Flavor: `s6.large.2` with AlmaLinux, GPSSD system disk 40 GiB
- Visual (la-south-2 proxy): USD 43.22
- MCP (la-north-2): USD 43.216
- Delta: rounding only (< 0.01 USD)
- Templates: `ecs-linux-2vcpu-4gb-payg`

### RDS MySQL

- Instance: `rds.mysql.n1.large.2`, Storage: CloudSSD 100 GB
- Visual total: USD 64.97
- MCP instance: USD 47.45, MCP volume: USD 17.52
- Total MCP: USD 64.97
- Delta: USD 0.000
- Confirms multi-productInfo pattern (instance + volume are separate productInfo entries)
- Templates: `rds-mysql-instance-payg`, `rds-mysql-volume-payg`

### EVS GPSSD

- GPSSD 100 GiB
- Visual proxy (la-south-2): USD 9.49
- MCP (la-north-2): USD 9.49
- Delta: USD 0.000
- Template: `evs-gpssd-gb-payg`

### EIP

- Dynamic BGP 10 Mbps
- Visual total: USD 125.56 (bandwidth USD 121.91 + IP reservation USD 3.65)
- MCP bandwidth component: USD 121.91
- IP reservation (hws.resource.type.vpc.ip) is NOT included by default because it is waived when EIP is attached to a resource
- Template: `eip-bandwidth-mbps-payg`

### OBS Standard

- Standard storage 720 GB
- Visual web calculator uses 720h convention
- MCP default uses 730h convention
- Same hourly rate: USD 0.00291667/h
- MCP 720h aligned: USD 2.1000024
- MCP 730h default: USD 2.1291691
- This is NOT a bug; it is an hours convention difference
- Template: `obs-standard-gb-month`

### ELB

- ELB v3 professional, no EIP
- Visual: USD 24.33
- ProductInfos:
  - (a) ELB instance: resourceType=`hws.resource.type.elbv3`, resourceSpecCode=`elbv3.professional`, usageFactor=`instance_duration`, amount ≈ USD 18.25
  - (b) ELB LCU: resourceType=`hws.resource.type.elbv3`, resourceSpecCode=`elbv3.professional`, usageFactor=`l4_lcu_duration`, amount ≈ USD 6.0809
- Canonical template names: `elb-shared-instance-payg` (instance component), `elb-shared-lcu-payg` (LCU component)
- Previous name `elb-shared-basic-payg` has been fully removed from all templates, code, and tests
- ELB v3 professional is a PAID spec; zero-price results from BSS/OCE indicate a data gap, not free tier

### NAT Gateway

- Public NAT Gateway small, 30 days
- Visual: USD 73.14
- ProductInfo: cloudServiceType=`hws.service.type.natgateway`, resourceType=`hws.resource.type.natgateway`, resourceSpecCode=`natgateway_small`, usageFactor=`duration`, usageMeasureId=`0`, usageValue=`30`
- SNAT rules are free
- NAT and EIP must remain independently composable (no hardcoded NAT macro)
- Template: `nat-gateway-public-payg`

## Template Semantic Audit

| Old Name | New Name | Action | Reason |
|---|---|---|---|
| `elb-shared-basic-payg` | `elb-shared-instance-payg` | Removed/Renamed | "basic" implied free tier; ELB v3 professional is a paid instance spec |

## Demo Architecture Impact

- Old model: ELB base USD 0.00 + EIP 10 Mbps USD 121.91 = USD 121.91 public access
- Corrected model: ELB instance USD 18.25 + ELB LCU USD 6.08 + EIP 10 Mbps USD 121.91 = USD 146.24 public access
- Delta: +USD 24.33/month for ELB v3 paid instance + LCU
- If previous full demo total was USD 284.93, corrected total ≈ USD 309.26

## Safety

- No raw HAR files stored
- No sensitive data (AK/SK, tokens, cookies, passwords) captured
- No cloud resources created, modified, or deleted
- No terraform apply/destroy executed
- la-north-2 is the target MCP region
- la-south-2 is visual proxy only
- USD is the only baseline currency
- CNY is out of scope
