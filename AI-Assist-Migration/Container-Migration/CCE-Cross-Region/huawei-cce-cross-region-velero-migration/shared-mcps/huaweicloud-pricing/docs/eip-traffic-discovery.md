# EIP Traffic Discovery Report for huaweicloud-pricing MCP

**Date**: 2026-06-01
**Region**: la-north-2 (LA-Mexico City2)
**Status**: EIP traffic (upflow by GB) CONFIRMED via VPC bandwidth billing. Template `vpc-bandwidth-traffic-gb-payg` **IMPLEMENTED** (status `ready`).

---

## 1. Background

EIP bandwidth is billed under `hws.service.type.vpc` with `resource_type=hws.resource.type.bandwidth`. Two billing dimensions exist:

1. **Bandwidth by Mbps/duration** — `resource_spec=19_bgp`, `usage_factor=Duration`, `usage_measure_id=4` (Hour), `resource_size` in Mbps. Covered by `eip-bandwidth-mbps-payg`.
2. **Traffic by GB** — `resource_spec=12_bgp` or `12_share`, `usage_factor=upflow`, `usage_measure_id=10` (GB), `usage_value` in GB. Covered by `vpc-bandwidth-traffic-gb-payg`.

---

## 2. BSS/OCE Validation

### 2.1 resource_specs for Traffic

| resource_spec | Type | Per GB (USD) | 200 GB (USD) | 300 GB (USD) | product_id |
|---|---|---|---|---|---|
| `12_share` | Shared bandwidth | 0.081 | 16.20 | 24.30 | OFFI951287093288931328 |
| `12_bgp` | Dynamic BGP | 0.081 | 16.20 | 24.30 | OFFI580665045183791104 |

**Key finding**: `12_share` and `12_bgp` have the **same per-GB rate** (USD 0.081/GB) in la-north-2.

### 2.2 Validated product_infos

```json
{
  "cloud_service_type": "hws.service.type.vpc",
  "resource_type": "hws.resource.type.bandwidth",
  "resource_spec": "12_bgp",
  "region": "la-north-2",
  "usage_factor": "upflow",
  "usage_value": 300,
  "usage_measure_id": 10,
  "subscription_num": 1
}
```

**Result**: USD 24.30 (300 GB)

### 2.3 Field Analysis

| Field | Value | Role |
|---|---|---|
| `usage_value` | 300 | Traffic volume in GB |
| `usage_measure_id` | 10 | Unit = GB |
| `resource_size` | (not used) | Not applicable for traffic |
| `usage_factor` | `upflow` | Upstream/egress traffic |

---

## 3. Comparison Against Real EIP Quotation

| Item | Quotation (USD) | BSS/OCE (USD) | Match |
|---|---|---|---|
| 2 EIP Dynamic BGP, 300GB each | 48.61 | 48.60 | **0.01 diff** (rounding) |

The 0.01 USD difference is attributable to BSS/OCE rounding (high precision mode returns 24.30 per 300GB, 2 × 24.30 = 48.60 vs real quote 48.61).

---

## 4. Template Implementation

**Template**: `vpc-bandwidth-traffic-gb-payg`
**Service**: `vpc`
**Status**: `ready`

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `quantity` | integer | 1 | Number of traffic subscriptions |
| `traffic_resource_spec` | string | `12_bgp` | `12_bgp` (Dynamic BGP) or `12_share` (shared) |
| `traffic_gb` | number | 300 | Traffic volume in GB |

### Usage

- **VPN traffic**: Use `traffic_resource_spec=12_share` for active tunnel, `12_bgp` for standby tunnel.
- **EIP traffic**: Use `traffic_resource_spec=12_bgp` for Dynamic BGP EIP traffic.
- **Architecture composition**: Combine with `eip-bandwidth-mbps-payg` for complete EIP cost (bandwidth + traffic).

---

## 5. Relationship to Existing Templates

| Template | Billing Dimension | usage_factor | usage_measure_id | resource_size |
|---|---|---|---|---|
| `eip-bandwidth-mbps-payg` | Mbps × hours | Duration | 4 (Hour) | Yes (Mbps) |
| `vpc-bandwidth-traffic-gb-payg` | GB traffic | upflow | 10 (GB) | No |

These templates are **complementary**, not conflicting. EIP bandwidth (Mbps) covers the provisioned bandwidth rate. VPC traffic (GB) covers the actual data transfer volume.

---

## 6. Limitations

- `12_share` and `12_bgp` validated only in la-north-2. Other regions must be validated before use.
- `downflow` (ingress traffic) not validated. Most Huawei Cloud regions bill only egress (`upflow`).
- `mainflow` not validated.
- Does not create EIP resources — only models traffic billing.
- Does not replace `eip-bandwidth-mbps-payg` for bandwidth provisioning cost.
