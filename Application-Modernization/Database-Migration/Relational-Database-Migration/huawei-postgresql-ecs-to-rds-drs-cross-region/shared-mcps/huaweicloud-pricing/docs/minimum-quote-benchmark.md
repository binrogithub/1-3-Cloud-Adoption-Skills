# Minimum Quote Benchmark Comparison

## Benchmark Source

Real Huawei Cloud quotation for LA-Mexico City2 / la-north-2.

**Total quotation: USD 1,309.35/month**

## Benchmark Items

| Service | Resource | Spec | Capacity | Quoted Price (USD/month) | Billing Mode |
|---------|----------|------|----------|--------------------------|---|
| ECS BD | Compute | m6.3xlarge.8.linux | 1 instance | 356.36 | Period (monthly subscription) |
| ECS BD | OS License | suse.12 | 1 license | 55.00 | Period (monthly subscription) |
| ECS BD | System Disk | GPSSD | 700 GB | 65.80 | On-demand |
| ECS Sesiones | Compute | c6.3xlarge.4.linux | 1 instance | 271.21 | Period (monthly subscription) |
| ECS Sesiones | OS License | AlmaLinux 9.4 | N/A | 0.00 | Free |
| ECS Sesiones | System Disk | GPSSD | 300 GB | 28.20 | On-demand |
| ECS Aplicaciones | Compute | s6.xlarge.4.linux | 1 instance | 63.07 | Period (monthly subscription) |
| ECS Aplicaciones | OS License | AlmaLinux 9.4 | N/A | 0.00 | Free |
| ECS Aplicaciones | System Disk | GPSSD | 200 GB | 18.80 | On-demand |
| CBR | Server backup vault | vault.backup.server.normal | 2400 GB | 87.60 | On-demand |
| HSS | Host Protection Premium | hss.version.premium | 3 PCS | 41.40 | Period (monthly subscription) |
| EIP/VPC | Bandwidth + Traffic | 19_bgp + 12_share/12_bgp | Various | Various | On-demand |
| VPN | Gateway + Traffic | V300 + 12_share/12_bgp | Various | Various | On-demand |
| NAT | Public Gateway | natgateway_small | 1 instance | Various | On-demand |

## ECS Line Breakdown

### BD Line (USD 477.16 quotation)

| Component | Template | Quotation (USD) | BSS/OCE On-demand (USD) | BSS/OCE Period (USD) | Period Match? |
|-----------|----------|-----------------|-------------------------|---------------------|---------------|
| ECS Compute | ecs-flavor-payg / ecs-flavor-period | 356.36 | 494.94 | 356.36 | EXACT |
| SUSE License | ecs-os-license-payg / ecs-os-license-period | 55.00 | 109.50 | 55.00 | EXACT |
| GPSSD 700 GB | evs-gpssd-gb-payg | 65.80 | 66.43 | N/A | +0.96% |
| **Line Total** | | **477.16** | **670.87** | **477.36** | **+0.04%** |

### Sesiones Line (USD 299.41 quotation)

| Component | Template | Quotation (USD) | BSS/OCE On-demand (USD) | BSS/OCE Period (USD) | Period Match? |
|-----------|----------|-----------------|-------------------------|---------------------|---------------|
| ECS Compute | ecs-flavor-payg / ecs-flavor-period | 271.21 | 376.68 | 271.21 | EXACT |
| AlmaLinux License | N/A (free OS) | 0.00 | 0.00 | 0.00 | N/A |
| GPSSD 300 GB | evs-gpssd-gb-payg | 28.20 | 28.47 | N/A | +0.96% |
| **Line Total** | | **299.41** | **405.15** | **299.68** | **+0.09%** |

### Aplicaciones Line (USD 81.87 quotation)

| Component | Template | Quotation (USD) | BSS/OCE On-demand (USD) | BSS/OCE Period (USD) | Period Match? |
|-----------|----------|-----------------|-------------------------|---------------------|---------------|
| ECS Compute | ecs-flavor-payg / ecs-flavor-period | 63.07 | 87.60 | 63.07 | EXACT |
| AlmaLinux License | N/A (free OS) | 0.00 | 0.00 | 0.00 | N/A |
| GPSSD 200 GB | evs-gpssd-gb-payg | 18.80 | 18.98 | N/A | +0.96% |
| **Line Total** | | **81.87** | **106.58** | **82.05** | **+0.22%** |

### Three ECS Lines Total

| Source | USD/month |
|--------|-----------|
| Quotation total | 858.44 |
| BSS/OCE on-demand total | 1,182.60 |
| BSS/OCE period total | 859.09 |
| On-demand ratio | 1.38x |
| Period ratio | 1.001x (+0.08%) |

**With ECS period billing, the three ECS lines match the quotation within +0.08%** (remaining gap is EVS GPSSD at +0.96%).

## MCP Validation Results

### On-Demand Templates (Current)

| Service | Template | Capacity | BSS/OCE Price (USD/month) | Benchmark (USD/month) | Delta | Billing Mode |
|---------|----------|----------|---------------------------|-----------------------|-------|---|
| ECS Compute | ecs-flavor-payg | m6.3xlarge.8.linux | 494.94 | 356.36 | +39% | On-demand |
| ECS Compute | ecs-flavor-payg | c6.3xlarge.4.linux | 376.68 | 271.21 | +39% | On-demand |
| ECS Compute | ecs-flavor-payg | s6.xlarge.4.linux | 87.60 | 63.07 | +39% | On-demand |
| ECS OS License | ecs-os-license-payg | suse.12 | 109.50 | 55.00 | +99% | On-demand |
| EVS GPSSD | evs-gpssd-gb-payg | 700 GB | 66.43 | 65.80 | +0.96% | On-demand |
| EVS GPSSD | evs-gpssd-gb-payg | 300 GB | 28.47 | 28.20 | +0.96% | On-demand |
| EVS GPSSD | evs-gpssd-gb-payg | 200 GB | 18.98 | 18.80 | +0.96% | On-demand |
| CBR | cbr-server-backup-vault-gb-payg | 2400 GB | 87.60 | 87.60 | 0.00 (exact match) | On-demand |
| HSS | hss-host-protection-period | 3 PCS | 41.40 | 41.40 | 0.00 (exact match) | Period |

### Period Templates (Validated via QueryPeriodPrice, NOW IMPLEMENTED as templates)

| Service | Template | Capacity | BSS/OCE Period (USD/month) | Benchmark (USD/month) | Delta | Billing Mode |
|---------|----------|----------|----------------------------|-----------------------|-------|---|
| ECS Compute | ecs-flavor-period | m6.3xlarge.8.linux | 356.36 | 356.36 | 0.00 (exact match) | Period |
| ECS Compute | ecs-flavor-period | c6.3xlarge.4.linux | 271.21 | 271.21 | 0.00 (exact match) | Period |
| ECS Compute | ecs-flavor-period | s6.xlarge.4.linux | 63.07 | 63.07 | 0.00 (exact match) | Period |
| ECS OS License | ecs-os-license-period | suse.12 | 55.00 | 55.00 | 0.00 (exact match) | Period |

## BSS/OCE vs Price Calculator Discrepancy - RESOLVED

**Date**: 2026-06-01

The discrepancy between BSS/OCE on-demand API and the Price Calculator quotation for ECS compute and SUSE license is **caused by a billing model mismatch**, NOT by API errors, parser bugs, or missing fields.

### Root Cause

The Price Calculator quotation uses **period (monthly subscription) billing** for ECS compute and OS licenses. The BSS/OCE on-demand API returns pay-per-use rates that include a premium:

- **ECS compute on-demand**: ~1.39x the period/quotation price (+39% premium)
- **SUSE license on-demand**: ~1.99x the period/quotation price (+99% premium)

The BSS/OCE **period API** (`/v2/bills/ratings/period-resources/subscribe-rate`) with `period_type=2, period_num=1` returns prices that **match the quotation EXACTLY** for all four items.

### Previously Suspected Causes (Ruled Out)

| Suspected Cause | Status | Evidence |
|----------------|--------|----------|
| Incorrect endpoint | RULED OUT | Both endpoints are valid; they return different billing models |
| Parser bug | RULED OUT | Parser correctly extracts `amount` (on-demand) and `official_website_amount` (period) |
| Missing field in productInfo | RULED OUT | All required fields present; adding `inquiry_precision=0` does not change result |
| Regional discount not visible | RULED OUT | `discount_amount=0`, `discount_rating_results=[]` in all responses |
| Currency/tax difference | RULED OUT | Same currency (USD), same region, same product_ids |
| BSS/OCE API limitation | RULED OUT | Period API returns correct prices; on-demand API returns correct on-demand prices |
| Price Calculator applies hidden discount | RULED OUT | Period API confirms the quotation price is the official period price, not a discount |

### Confirmed Cause

**Billing model mismatch**: On-demand (pay-per-use) carries a systematic premium over period (monthly subscription) for ECS compute and OS licenses. This is consistent with cloud pricing models where monthly subscriptions are discounted relative to pay-per-use.

## HSS Billing Mode Note

The HSS benchmark quotation uses **period (monthly subscription) billing**, NOT on-demand. This is significant because:

- **Period price** (matches quotation): `hss.version.premium` × 3 PCS = USD 41.40/month
- **On-demand price** (template default): `hss.version.premium` × 3 PCS × 730h = USD 61.32/month

The on-demand price is 48.7% more expensive than the period price. HSS is typically sold as a monthly subscription per host. The MCP provides both `hss-host-protection-payg` (on-demand) and `hss-host-protection-period` (period) templates.

## ECS Billing Mode Note (NEW)

**Date**: 2026-06-01

The ECS benchmark quotation uses **period (monthly subscription) billing** for compute and OS licenses, NOT on-demand. This is the same pattern as HSS.

### On-Demand vs Period Price Comparison

| Item | On-demand (USD/month) | Period (USD/month) | On-demand Premium |
|------|----------------------|-------------------|-------------------|
| m6.3xlarge.8.linux | 494.94 | 356.36 | +39% |
| c6.3xlarge.4.linux | 376.68 | 271.21 | +39% |
| s6.xlarge.4.linux | 87.60 | 63.07 | +39% |
| suse.12 | 109.50 | 55.00 | +99% |

### Period Payload Pattern

ECS compute and SUSE license use **Pattern A** (duration-preserving) for period billing, identical to HSS:

```json
{
  "id": "ecs-<flavor>-period",
  "cloud_service_type": "hws.service.type.ec2",
  "resource_type": "hws.resource.type.vm",
  "resource_spec": "<flavor>.linux",
  "region": "la-north-2",
  "usage_factor": "Duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1,
  "period_type": 2,
  "period_num": 1
}
```

Note: The period API **ignores `usage_value`** for ECS. The price is determined by `period_type` and `period_num` only.

## Per-PCS Breakdown

| Edition | resource_spec | Period (USD/PCS/month) | On-demand (USD/PCS/month) | On-demand Premium |
|---------|---|---|---|---|
| Professional | hss.version.advanced | 4.50 | 7.30 | +62.2% |
| Enterprise/Premium | hss.version.premium | 13.80 | 20.44 | +48.7% |

## AlmaLinux Note

AlmaLinux does **NOT** generate a license productInfo in the Price Calculator. Cost = USD 0. No `ecs-os-license-payg` template call is needed for AlmaLinux instances. This is confirmed by the benchmark quotation where both AlmaLinux ECS instances show USD 0.00 for OS license.

## Conclusion

- **ECS compute**: Period API matches quotation EXACTLY. On-demand is +39% over period. `ecs-flavor-period` template needed.
- **SUSE license**: Period API matches quotation EXACTLY. On-demand is +99% over period. `ecs-os-license-period` template needed.
- **EVS GPSSD**: BSS/OCE matches quotation within +0.96% tolerance (on-demand is correct for EVS).
- **CBR Server Backup Vault**: BSS/OCE matches quotation exactly (USD 87.60 for 2400 GB).
- **HSS Host Protection Premium**: Period template matches quotation exactly (USD 41.40 for 3 PCS).
- **AlmaLinux**: No license cost, no template needed.

## Open Items

- ~~Investigate BSS/OCE vs Price Calculator price discrepancy for ECS compute and SUSE license~~ **RESOLVED**: Billing model mismatch (on-demand vs period)
- ~~Implement `ecs-flavor-period` template (Pattern A, `period_type=2, period_num=1`)~~ **IMPLEMENTED**: Template added, validated against live API
- ~~Implement `ecs-os-license-period` template (Pattern A, `period_type=2, period_num=1`)~~ **IMPLEMENTED**: Template added, validated against live API
- Add on-demand premium warning in `ecs-flavor-payg` and `ecs-os-license-payg` output
- Consider macro-template combining ECS compute + OS license + system disk (deferred)

## Final End-to-End Benchmark Result

- **Status**: PASS
- **Real quote**: USD 1,309.35
- **MCP/BSS total**: USD 1,310.42
- **Delta**: +0.082% (threshold: <= 0.20%)
- **Components**: 14/14 priced, 0 failures

See: [Final End-to-End Benchmark — USD 1,309.35](./final-end-to-end-benchmark-1309.md)
