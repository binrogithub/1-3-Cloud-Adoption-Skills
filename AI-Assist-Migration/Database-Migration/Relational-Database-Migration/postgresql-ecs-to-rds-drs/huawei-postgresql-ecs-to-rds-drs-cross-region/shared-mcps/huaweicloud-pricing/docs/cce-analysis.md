# CCE Standard/Turbo Analysis for huaweicloud-pricing MCP

## 1. Billing Diagnosis

CCE is a composite architecture. Billing items:

| Item | BSS service_type | resource_type | resource_spec | On-demand? |
|---|---|---|---|---|
| Cluster mgmt fee | `hws.service.type.cce` | `hws.resource.type.cce.cluster` | `cce.{scale}.{size}` | YES |
| Worker nodes | `hws.service.type.ec2` | `hws.resource.type.vm` | ECS flavor | YES |
| System disk | `hws.service.type.ebs` | `hws.resource.type.volume` | SSD/GPSSD/ESSD | YES |
| Data disk | `hws.service.type.ebs` | `hws.resource.type.volume` | SSD/GPSSD/ESSD | YES |
| Public ELB | `hws.service.type.elb` | `hws.resource.type.elbv2` | `21_instance` | YES |
| EIP bandwidth | `hws.service.type.vpc` | `hws.resource.type.bandwidth` | `19_bgp` | YES |

### Cluster management fee: VALIDATED

BSS/OCE responds successfully. Usage type: `duration`, measure_id: 4 (Hour).

Validated resource_specs (la-north-2, 730h on-demand):

| resource_spec | USD/month | Scale |
|---|---|---|
| `cce.s1.small` | 87.60 | <=50 nodes |
| `cce.s1.medium` | 167.90 | <=50 nodes |
| `cce.s1.large` | 321.20 | <=50 nodes |
| `cce.s1.xlarge` | 795.70 | <=50 nodes |
| `cce.s2.small` | 262.80 | <=200 nodes |
| `cce.s2.medium` | 496.40 | <=200 nodes |
| `cce.s2.large` | 970.90 | <=200 nodes |
| `cce.s2.xlarge` | 2387.10 | <=200 nodes |

Pattern: `cce.{scale}.{size}` (scale=s1/s2, size=small/medium/large/xlarge).

### CCE Turbo: BLOCKED

`hws.resource.type.basiccloud.cceturbo` exists but has zero usage_types.
All tested resource_specs return "Product not found". Likely period-only or undiscovered spec format.

## 2. Recommended Design: Macro-template + Real template

**Model: Architecture composite (Option C + A)**

- `cce-cluster-mgmt-payg` — Real template (status: ready), priceable via BSS/OCE
- `cce-standard-cluster-payg` — Macro-template, expanded by `normalizeArchitectureComponents`

Rationale: CCE is not a single price. The MCP already expands RDS small into instance+volume and public ELB into ELB+EIP. CCE should follow the same pattern.

## 3. Input Schema for CCE Small Cluster

```yaml
service: cce
template_id: cce-standard-cluster-payg
parameters:
  cluster_type: standard | turbo          # default: standard
  cluster_scale: cce.s1.small             # CCE cluster flavor
  ha: true | false                        # default: false
  node_count: 2                           # number of worker nodes
  node_template_id: ecs-linux-2vcpu-4gb-payg
  node_system_disk_size_gb: 40
  node_data_disk_size_gb: null            # optional
  node_data_disk_type: SSD               # optional
  public_ingress: true | false            # default: false
  ingress_bandwidth_mbps: 20             # if public_ingress=true
  validate_node_availability: true | false
```

## 4. Component Expansion

`cce-standard-cluster-payg` expands to:

1. **cce-cluster-mgmt-payg** — 1x cluster management fee (resource_spec=cluster_scale)
2. **ecs {node_template_id}** — node_count x worker node ECS (existing template)
3. **evs-ssd-gb-payg** — node_count x system disk (size=node_system_disk_size_gb)
4. **evs-ssd-gb-payg** — node_count x data disk (if node_data_disk_size_gb set)
5. **elb-shared-instance-payg** — 1x ELB (if public_ingress=true; existing normalization adds EIP)

If `cluster_type=turbo`: component #1 becomes `missing_product_infos_template` with gap.

## 5. Gaps

| Gap | Status | Impact |
|---|---|---|
| CCE Turbo cluster mgmt resource_spec | Not found | Turbo clusters cannot price mgmt fee |
| CCE cluster specs per region | Only validated la-north-2 | Other regions may differ |
| HA master nodes | Not modeled | Multi-master adds cost; deferred to phase 2 |
| CCE Autopilot | Out of scope | Different resource_type, future phase |

## 6. Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Turbo not priceable on-demand | High | Mark as missing_product_infos_template; worker costs still visible |
| resource_spec varies by region | Medium | Parametric template; document per-region specs |
| Architect forgets CCE includes nodes | Medium | Macro forces expansion; draft shows breakdown |
| validate_availability blocks all workers | Medium | include_unavailable_reference_pricing already works for ECS |
| Confusion Standard vs Autopilot | Low | Only Standard/Turbo in scope; Autopilot deferred |

## 7. Test Cases

| # | Case | Key input | Expected |
|---|---|---|---|
| 1 | Small cluster, no ingress | standard, 2 nodes, public_ingress=false | 4 components: mgmt + 2xECS + 2xEVS |
| 2 | Small cluster, public ingress | public_ingress=true, 20Mbps | 5+ components: mgmt + 2xECS + 2xEVS + ELB + EIP |
| 3 | Workers abandon, ref pricing | validate=true, include_unavailable=true | ECS blocked+ref; mgmt priced normally |
| 4 | Turbo cluster | cluster_type=turbo | mgmt=MISSING_PRODUCT_INFOS_TEMPLATE; workers priced |
| 5 | Auto-added ELB/EIP | public_ingress=true | Normalization adds ELB+EIP |
| 6 | validate_availability=false | validate=false | ECS priced without flavor check |
| 7 | With data disk | node_data_disk_size_gb=100 | Extra EVS per node |
| 8 | Direct cluster mgmt only | cce-cluster-mgmt-payg directly | Single pricing, no expansion |

## 8. Minimum Implementation Recommendation

**Files to modify (3):**

1. `pricing-templates.json` — Add `cce > la-north-2 > cce-cluster-mgmt-payg` (ready template with validated product_infos_template)
2. `template-tools.mjs` — Add CCE branch in `normalizeArchitectureComponents` to expand `cce-standard-cluster-payg` into cluster mgmt + ECS + EVS + ELB/EIP
3. No changes to `server.mjs` — Existing EstimateArchitectureOnDemandPrice flow handles normalized components, validate_availability, and service_cost_breakdown already

**Reusable from current MCP:**
- ECS pricing templates (worker nodes)
- EVS pricing templates (system/data disks)
- ELB+EIP normalization (public ingress auto-add)
- `validate_availability` for ECS worker flavors
- `include_unavailable_reference_pricing` for blocked workers
- `service_cost_breakdown` grouping

**Implementation order:**
1. Add `cce-cluster-mgmt-payg` template to pricing-templates.json
2. Add CCE expansion logic in normalizeArchitectureComponents
3. Test with EstimateArchitectureCostDraft
4. Test with EstimateArchitectureOnDemandPrice
5. Document CCE cluster flavors per region as discovered
