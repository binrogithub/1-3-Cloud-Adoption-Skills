# LTS (Log Tank Service) Discovery

## Summary

LTS pricing discovered via Playwright Price Calculator (ap-southeast-1 visual proxy) and validated via live BSS/OCE pricing API in la-north-2.

## BSS/OCE Catalog

- **Service type code**: `hws.service.type.lts`
- **Resource types** (6 total):
  1. `hws.resource.type.lts` — Log Tank Service (base)
  2. `hws.resource.type.lts.logflow` — Log Read Write Traffic
  3. `hws.resource.type.lts.logindex` — Log Index Traffic
  4. `hws.resource.type.lts.logstorage` — Log Storage Size
  5. `hws.resource.type.lts.logtransfer` — Log Transfer
  6. `hws.resource.type.ltsforhcso.gov` — LTS for HCSO_Gov

## Usage Types

| Resource Type | Usage Types |
|---------------|-------------|
| lts | value, options, storagesize |
| lts.logflow | traffic |
| lts.logindex | traffic, traffic.search.type |
| lts.logstorage | aom.size (capacity), logcoldstoragesize |
| lts.logtransfer | (not queried) |

## Discovered resource_specs (Playwright)

### Log Read/Write Traffic
- `resource_spec_code`: `lts.log.flow`
- `resource_type`: `hws.resource.type.lts.logflow`
- `usage_factor`: `traffic`
- `usage_measure_id`: 10 (GB)

### Log Index Traffic
- `resource_spec_code`: `lts.log.index`
- `resource_type`: `hws.resource.type.lts.logindex`
- `usage_factor`: `traffic`
- `usage_measure_id`: 10 (GB)

### Log Storage
- `resource_spec_code`: `lts.log.storage`
- `resource_type`: `hws.resource.type.lts.logstorage`
- `usage_factor`: `aom.size`
- `usage_measure_id`: 17 (GB)

### Log Transfer (basic)
- `resource_spec_code`: `lts.log.transfer.basic`
- `resource_type`: `hws.resource.type.lts.logtransfer`
- `usage_factor`: `logbasictransfertraffic`
- `usage_measure_id`: 10 (GB)

### Log Transfer (senior)
- `resource_spec_code`: `lts.log.transfer.senior`
- `resource_type`: `hws.resource.type.lts.logtransfer`
- `usage_factor`: `logseniortransfertraffic`
- `usage_measure_id`: 10 (GB)

## BSS/OCE Validation (la-north-2)

| Component | Test | Result |
|-----------|------|--------|
| lts.log.flow | 100 GB | USD 5.00 (USD 0.05/GB) |
| lts.log.index | 100 GB | USD 8.00 (USD 0.08/GB) |
| lts.log.storage | 100 GB | USD 0.0125 (USD 0.000125/GB) |

## Playwright Capture

- **Request**: See `docs/lts-pricing-request.json`
- **Response**: See `docs/lts-pricing-response.json`
- **Visual proxy region**: ap-southeast-1
- **MCP validation region**: la-north-2
- **Visual estimated price**: USD 72.64 (default config in ap-southeast-1)

## Templates Implemented

1. `lts-log-flow-payg` — Log read/write traffic by GB
2. `lts-log-index-payg` — Log index traffic by GB
3. `lts-log-storage-payg` — Log storage by GB

## Deferred

- `lts-log-transfer-basic-payg` — Basic OBS transfer (lower priority)
- `lts-log-transfer-senior-payg` — Senior DIS/DWS transfer (lower priority)
- Cold storage template (logcoldstoragesize usage type)
- Period billing templates
