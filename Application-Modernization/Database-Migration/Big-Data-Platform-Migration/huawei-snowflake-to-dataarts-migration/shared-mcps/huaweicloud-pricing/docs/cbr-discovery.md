# CBR (Cloud Backup and Recovery) Discovery for huaweicloud-pricing MCP

## 1. Service Overview

CBR provides backup and recovery for ECS servers, EVS disks, and SFS Turbo file systems. Vaults are the billing unit: each vault has a capacity (GB) and a type (server, disk, etc.).

## 2. BSS/OCE Catalog

- **cloud_service_type**: `hws.service.type.cbr`
- **resource_type**: `hws.resource.type.cbr.vault`
- **resource_spec values confirmed**:
  - `vault.backup.server.normal` — Server backup vault (protects ECS servers)
  - `vault.backup.volume.normal` — Disk backup vault (protects EVS disks)

## 3. product_infos Field Mapping

| Field | Value | Notes |
|-------|-------|-------|
| cloud_service_type | `hws.service.type.cbr` | Confirmed |
| resource_type | `hws.resource.type.cbr.vault` | Confirmed |
| resource_spec | `vault.backup.server.normal` or `vault.backup.volume.normal` | Confirmed |
| region | `la-north-2` | Validated region |
| usage_factor | `duration` | Lowercase |
| usage_value | 730 | Monthly hours |
| usage_measure_id | 4 | Hour |
| resource_size | capacity in GB | e.g., 2400 |
| size_measure_id | 17 | GB — confirmed working |
| subscription_num | 1 | Quantity |

**Field name note**: Both `size_measure_id` and `resource_size_measure_id` are accepted by BSS/OCE for CBR vaults. The Price Calculator UI shows `resouceSizeMeasureId` (with typo). This MCP uses `size_measure_id` for consistency with EVS, SFS, and RDS volume templates.

## 4. Validated Pricing (live BSS/OCE, la-north-2)

### Server Backup Vault (`vault.backup.server.normal`)

| Capacity (GB) | Duration (h) | Monthly Price (USD) | Unit Price (USD/GB/month) |
|---------------|--------------|---------------------|---------------------------|
| 1000 | 730 | 36.50 | 0.0365 |
| 2400 | 730 | 87.60 | 0.0365 |

**Linear scaling confirmed**: 2400 GB / 1000 GB = 2.4x, 87.60 / 36.50 = 2.4x.

### Disk Backup Vault (`vault.backup.volume.normal`)

| Capacity (GB) | Duration (h) | Monthly Price (USD) | Unit Price (USD/GB/month) |
|---------------|--------------|---------------------|---------------------------|
| 1000 | 730 | 21.90 | 0.0219 |
| 2400 | 730 | 52.56 | 0.0219 |

**Linear scaling confirmed**: 2400 GB / 1000 GB = 2.4x, 52.56 / 21.90 = 2.4x.

### Price Comparison

| Vault Type | Unit Price (USD/GB/month) | Ratio vs Disk |
|------------|---------------------------|---------------|
| Server backup | 0.0365 | 1.67x |
| Disk backup | 0.0219 | 1.0x |

Server backup vault is 1.67x more expensive per GB than disk backup vault. They do NOT share the same unit price.

## 5. Benchmark Quote Comparison

| Item | Benchmark Quote | BSS/OCE API | Delta |
|------|----------------|-------------|-------|
| CBR Server Backup Vault 2400 GB | USD 87.60 | USD 87.60 | 0.00 (exact match) |

## 6. Implemented Templates

### cbr-server-backup-vault-gb-payg

- **service**: `cbr`
- **display_name**: CBR Server Backup Vault pay-per-use
- **billing_mode**: `on_demand`
- **unit**: `GB-hour`
- **status**: `ready`
- **parameters**: quantity (default 1), capacity_gb (default 2400), monthly_hours (default 730)

### cbr-disk-backup-vault-gb-payg

- **service**: `cbr`
- **display_name**: CBR Disk Backup Vault pay-per-use
- **billing_mode**: `on_demand`
- **unit**: `GB-hour`
- **status**: `ready`
- **parameters**: quantity (default 1), capacity_gb (default 1000), monthly_hours (default 730)

## 7. Deferred Vault Types (Fase 2+)

The following vault types are NOT implemented in Fase 1. Their `resource_spec` values are not yet confirmed:

- Dedicated cloud replication vault
- Dedicated cloud backup vault
- Desktop backup vault
- Multi-AZ server backup vault
- Database server backup vault
- Replication vault
- Cross-region replication
- Backup traffic

These require Price Calculator payload capture or BSS/OCE catalog discovery to confirm their `resource_spec` values.

## 8. Integration Notes

- No `validate_availability` (CBR does not participate in ECS flavor validation).
- No `service_cost_breakdown` in Fase 1 (vault is a simple capacity-based component).
- CBR contributes to `monthly_total` in architecture pricing.
- `usage_factor` = "duration" (lowercase) — consistent with DDS, DCS, NAT Gateway, VPN Gateway.
- `size_measure_id` = 17 (GB) — consistent with EVS, SFS Turbo, RDS volume templates.
