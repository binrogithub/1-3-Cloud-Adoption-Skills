# HSS (Host Security Service) Discovery

## Service Identification

- **cloud_service_type**: `hws.service.type.hss`
- **Service name**: Host Security Service
- **Region validated**: la-north-2

## Resource Types (BSS/OCE Catalog)

| resource_type_code | Name | Description |
|---|---|---|
| `hws.resource.type.hss` | Host Security | Host Security (host protection) |
| `hws.resource.type.cgs` | Container Guard | Container Guard (container security) |
| `hws.resource.type.hses` | Host Security Expert Service | Host Security Expert Service |
| `hws.resource.type.hsms` | Host Security Managed Service | Host Security Managed Service |

## Usage Types (hws.resource.type.hss)

| Code | Name |
|---|---|
| `duration` | Duration |
| `number` | Number |
| `times` | Times |

## Validated resource_specs (hws.resource.type.hss)

| resource_spec | Commercial Edition | On-demand (USD/PCS/month, 730h) | Period (USD/PCS/month, 1mo) | Status |
|---|---|---|---|---|
| `hss.version.basic` | Basic | 0.00 | N/A | Free |
| `hss.version.advanced` | Professional | 7.30 | 4.50 | Confirmed |
| `hss.version.premium` | Enterprise/Premium | 20.44 | **13.80** | Confirmed |
| `hss.version.wtp` | Web Tamper Protection | 251.49 | N/A | Confirmed (separate billing item) |

## NOT Found (CBC.6006 "Product not found")

- `hss.professional`
- `hss.version.enterprise`
- `hss.version.ultimate`
- `hss.version.container`
- `hss.version.ransomware`
- `hss.host.protection`

## Edition Naming Mapping

The BSS/OCE resource_spec naming does NOT match the commercial edition names directly:

| Commercial Name | resource_spec | Notes |
|---|---|---|
| Basic | `hss.version.basic` | Free (USD 0) |
| Professional | `hss.version.advanced` | NOT "hss.version.professional" |
| Enterprise/Premium | `hss.version.premium` | NOT "hss.version.enterprise" |
| Ultimate | NOT FOUND | `hss.version.ultimate` returns CBC.6006 |

## Billing Mode Analysis

HSS supports both on-demand (pay-per-use) and period (yearly/monthly subscription) billing:

| resource_spec | On-demand (730h) | Period (1 month) | On-demand Premium |
|---|---|---|---|
| `hss.version.advanced` | USD 7.30 | USD 4.50 | 62.2% |
| `hss.version.premium` | USD 20.44 | USD 13.80 | 48.7% |

**Key finding**: The benchmark quotation uses **period (monthly subscription) billing**, NOT on-demand. The on-demand price is significantly more expensive (48.7% for premium edition).

## Benchmark Quotation Validation

- Quotation: HSS Premium, 3 PCS, USD 41.40 total (USD 13.80/PCS/month)
- BSS/OCE period: `hss.version.premium` × 3 PCS × 1 month = **USD 41.40** (EXACT MATCH)
- BSS/OCE on-demand: `hss.version.premium` × 3 PCS × 730h = USD 61.32 (does NOT match quotation)

## Price Scaling

Price scales **linearly** by `subscription_num` (number of protected hosts/PCS):
- 1 PCS × USD 13.80 = USD 13.80
- 3 PCS × USD 13.80 = USD 41.40
- 1 PCS × USD 20.44 (on-demand) = USD 20.44
- 3 PCS × USD 20.44 (on-demand) = USD 61.32

## product_infos Format

### On-demand (pay-per-use)

```json
{
  "id": "hss-host-protection-hss.version.premium-730h-1",
  "cloud_service_type": "hws.service.type.hss",
  "resource_type": "hws.resource.type.hss",
  "resource_spec": "hss.version.premium",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1
}
```

### Period (yearly/monthly subscription)

```json
{
  "id": "hss-host-protection-hss.version.premium-730h-1",
  "cloud_service_type": "hws.service.type.hss",
  "resource_type": "hws.resource.type.hss",
  "resource_spec": "hss.version.premium",
  "region": "la-north-2",
  "usage_factor": "duration",
  "usage_value": 730,
  "usage_measure_id": 4,
  "subscription_num": 1,
  "period_type": 2,
  "period_num": 1
}
```

## Fase 1 Scope

- Host protection only (hws.resource.type.hss)
- On-demand billing template: `hss-host-protection-payg`
- Period billing template: `hss-host-protection-period` (Phase 1 implemented)
- Professional (hss.version.advanced) and Enterprise/Premium (hss.version.premium) editions

## Period Billing Template

**Template ID**: `hss-host-protection-period`
**billing_mode**: `period`
**Tool**: `EstimateTemplatePeriodPrice`
**Status**: `ready` (Phase 1 implemented)

**Validated period pricing**:
- `hss.version.premium` x 3 PCS x 1 month = USD 41.40/month (EXACT MATCH with benchmark quote)
- `hss.version.premium` x 1 PCS x 1 month = USD 13.80/month
- `hss.version.advanced` x 3 PCS x 1 month = USD 13.50/month
- `hss.version.advanced` x 1 PCS x 1 month = USD 4.50/month

## NOT in Fase 1

- Web tamper protection (hss.version.wtp) — validated at USD 251.49/PCS/month on-demand, but separate billing item
- Container security (hws.resource.type.cgs) — resource_spec not discovered
- Ransomware protection — resource_spec not found (CBC.6006)
- Host Security Expert Service (hws.resource.type.hses) — resource_spec not discovered
- Host Security Managed Service (hws.resource.type.hsms) — resource_spec not discovered
- Period billing template — IMPLEMENTED as `hss-host-protection-period` (Phase 1)
- Quota packages — not validated
