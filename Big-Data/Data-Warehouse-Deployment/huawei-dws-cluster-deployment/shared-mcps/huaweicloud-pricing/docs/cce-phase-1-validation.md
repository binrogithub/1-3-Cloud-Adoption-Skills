# CCE Phase 1 — Validation Summary

## What CCE Phase 1 Implements

- **CCE cluster management pricing** (`cce-cluster-mgmt-payg` template): on-demand cost for CCE Standard cluster control plane.
- **Macro `cce-standard-cluster-payg`** in `template-tools.mjs`: composes a full CCE cluster cost estimate from:
  - CCE cluster management (control plane)
  - ECS worker nodes (compute)
  - EVS disks (node storage)
  - ELB + EIP (public ingress, optional)
- **`include_unavailable_reference_pricing`** support: when ECS flavors are blocked (`abandon`/`sellout`), their reference pricing is still computed but excluded from `monthly_total` and reported under `monthly_total_estimated_with_blocked`.
- **End-to-end test** (`test-cce-standard-cluster.mjs`) validates the full composition and pricing flow.

## What CCE Phase 1 Does NOT Implement

- CCE Turbo cluster pricing.
- Auto-scaling group pricing.
- CCE Add-on marketplace pricing.
- CCE container network (CCI) pricing.
- Persistent volume (EVS attached to pods) beyond node root disks.
- GPU/Accelerate flavor pricing.
- DCS, NAT Gateway, WAF, SFS Turbo, DDS, GaussDB, DRS.
- Period (yearly/monthly) subscription pricing for CCE.

## CCE Cost Composition

| Component | Description | Pricing Basis |
|-----------|-------------|---------------|
| Cluster management | CCE Standard control plane | Fixed per-cluster, pay-per-use |
| ECS workers | Node compute (e.g. s6.large.2) | Per-flavor, pay-per-use |
| EVS disks | Node root volume (GPSSD/SSD) | Per-GB, pay-per-use |
| ELB | Public load balancer (if ingress) | Per-LCU + fixed, pay-per-use |
| EIP | Public IP bandwidth (if ingress) | Per-Mbps, pay-per-use |

## End-to-End Validated Results

| Metric | Value (USD) |
|--------|-------------|
| `monthly_total` | 345.436 |
| `monthly_total_estimated_with_blocked` | 503.116 |
| CCE cluster management | 87.60 |
| EVS | 14.016 |
| EIP | 243.82 |
| ECS (reference, blocked) | 78.84 |

### Breakdown

- **Deployable cost** (`monthly_total` = 345.436): CCE cluster management + EVS + EIP. These components are available and can be provisioned.
- **Reference cost** (`monthly_total_estimated_with_blocked` = 503.116): Includes ECS worker reference pricing even though the selected flavor is not available for deployment.

## Warnings

- **ECS `s6.large.2` is `abandon`** in the target AZ. This flavor is not recommended for deployment. The ECS cost appears only as reference pricing.
- **Do NOT use `monthly_total_estimated_with_blocked` as a deployable cost.** It includes components that cannot be provisioned. Always use `monthly_total` for budgeting actual deployments.

## Rule

> `monthly_total` = sum of costs for **available** components only.
> `monthly_total_estimated_with_blocked` = `monthly_total` + sum of **blocked** component reference costs.
> Only `monthly_total` represents a deployable cost estimate.
