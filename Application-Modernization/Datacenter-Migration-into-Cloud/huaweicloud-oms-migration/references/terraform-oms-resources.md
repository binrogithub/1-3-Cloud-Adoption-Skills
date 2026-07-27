# Terraform OMS Resources

Complete reference for Huawei Cloud Terraform provider OMS resources and the OBS bucket resource. Provider version: `1.93.0` (check for latest with `terraform_get_latest_provider_version`).

## Provider Configuration

```hcl
terraform {
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.93.0"
    }
  }
}

provider "huaweicloud" {
  region     = var.hc_region
  access_key = var.hc_ak  # REQUIRED — no IMDS fallback like AWS provider
  secret_key = var.hc_sk
}
```

Credentials via environment variables (alternative):
```bash
export HW_ACCESS_KEY="<your-ak>"
export HW_SECRET_KEY="<your-sk>"
```

---

## huaweicloud_obs_bucket

Creates an OBS bucket. Use this to create the migration destination in the same Terraform config.

```hcl
resource "huaweicloud_obs_bucket" "dest" {
  bucket       = var.hc_bucket
  acl          = "private"       # private, public-read, public-read-write
  storage_class = "STANDARD"     # STANDARD, WARM, COLD
  # versioning   = true          # enable versioning
  # force_destroy = true          # allow destroy even if non-empty
}
```

### Key arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `bucket` | yes | Globally unique bucket name, 3-63 chars, lowercase |
| `acl` | no | `private` (default), `public-read`, `public-read-write` |
| `storage_class` | no | `STANDARD`, `WARM`, `COLD` |
| `region` | no | Defaults to provider region |
| `versioning` | no | Enable object versioning |
| `force_destroy` | no | Allow `terraform destroy` on non-empty bucket |
| `encryption` | no | Enable SSE-KMS |
| `kms_key_id` | no | KMS key ID for SSE-KMS |

---

## huaweicloud_oms_migration_task

One-time migration task. Best for finite object sets. Use `type` to control scope.

### Full bucket migration

```hcl
resource "huaweicloud_oms_migration_task" "full" {
  region = var.hc_region

  source_object {
    data_source = "AWS"
    region      = var.src_region
    bucket      = var.src_bucket
    access_key  = var.src_ak
    secret_key  = var.src_sk
    object      = [""]  # empty string = entire bucket
  }

  destination_object {
    region     = var.hc_region
    bucket     = huaweicloud_obs_bucket.dest.bucket
    access_key = var.hc_ak
    secret_key = var.hc_sk
  }

  type                           = "prefix"
  start_task                     = true
  description                    = "AWS S3 to Huawei OBS migration"
  enable_metadata_migration      = true
  consistency_check              = "size_last_modified"
  object_overwrite_mode          = "SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE"
  enable_failed_object_recording = true
}
```

### Subset migration (specific objects/folders)

```hcl
  type = "object"
  source_object {
    # ...
    object = ["reports/2024/", "data/config.json"]  # trailing / = folder
  }
```

### List-file migration (very large buckets)

```hcl
  type = "list"
  source_object {
    # ...
    list_file_bucket = "my-obs-helper-bucket"  # must be in dest region
    list_file_key    = "object-list/file1.txt"
  }
```

### Bandwidth throttling

```hcl
  bandwidth_policy {
    max_bandwidth = 5    # 1-200 MB/s
    start         = "00:00"
    end           = "06:00"
  }
  bandwidth_policy {
    max_bandwidth = 50
    start         = "06:00"
    end           = "23:59"
  }
```

### SMN notifications

```hcl
  smn_config {
    topic_urn          = "urn:smn:la-north-2:project:topic-name"
    trigger_conditions = ["FAILURE", "SUCCESS"]
    language           = "en-us"  # or zh-cn
  }
```

### All arguments

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `source_object` | yes | block | Source configuration (see below) |
| `destination_object` | yes | block | Destination configuration (see below) |
| `type` | yes | string | `list`, `url_list`, `object`, `prefix` |
| `region` | no | string | Destination region (defaults to provider) |
| `start_task` | no | bool | Start on create (default `true`) |
| `description` | no | string | Plain ASCII only — no `->`, `<>`, `<=` |
| `enable_kms` | no | bool | KMS encryption (default `false`) |
| `enable_metadata_migration` | no | bool | Migrate metadata (default `false`, ContentType always migrated) |
| `enable_restore` | no | bool | Auto-restore archive objects (default `false`) |
| `enable_failed_object_recording` | no | bool | Record failed objects (default `true`) |
| `migrate_since` | no | string | `yyyy-MM-dd HH:mm:ss` — only migrate objects modified after |
| `consistency_check` | no | string | `size_last_modified` (default), `crc64`, `no_check` |
| `object_overwrite_mode` | no | string | `SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE` (default), `NO_OVERWRITE`, `CRC64_COMPARISON_OVERWRITE`, `FULL_OVERWRITE` |
| `enable_requester_pays` | no | bool | Requester pays (default `false`) |
| `task_priority` | no | string | `HIGH`, `MEDIUM`, `LOW` |
| `dst_storage_policy` | no | string | `STANDARD`, `IA`, `ARCHIVE`, `DEEP_ARCHIVE`, `SRC_STORAGE_MAPPING` |
| `bandwidth_policy` | no | block(s) | Up to 5 non-overlapping time segments |
| `source_cdn` | no | block | CDN download configuration |
| `smn_config` | no | block | SMN notification configuration |

### `source_object` block

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `data_source` | no | string | `AWS`, `Azure`, `Aliyun`, `Tencent`, `HuaweiCloud`, `QingCloud`, `KingsoftCloud`, `Baidu`, `Qiniu`, `URLSource`, `UCloud`. Default: `Aliyun` |
| `region` | conditional | string | Source region (required unless `type = url_list`) |
| `bucket` | conditional | string | Source bucket (required unless `type = url_list`) |
| `access_key` | conditional | string | Source AK (required unless `type = url_list`) |
| `secret_key` | conditional | string | Source SK (required unless `type = url_list`) |
| `object` | conditional | list | Object keys / prefixes. `[""]` = entire bucket |
| `app_id` | conditional | string | Required when `data_source = Tencent` |
| `list_file_bucket` | conditional | string | OBS bucket holding the list file (for `type = list/url_list`) |
| `list_file_key` | conditional | string | Object key of the list file |
| `security_token` | no | string | Temporary token |
| `json_auth_file` | no | string | GCS auth file |

### `destination_object` block

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `region` | yes | string | Destination region |
| `bucket` | yes | string | Destination bucket |
| `access_key` | yes | string | Destination AK |
| `secret_key` | yes | string | Destination SK |
| `save_prefix` | no | string | Path prefix added to object keys in destination |
| `security_token` | no | string | Temporary token |

### Attributes

| Attribute | Description |
|-----------|-------------|
| `id` | Task ID |
| `name` | Task name |
| `status` | `1`=waiting, `2`=migrating, `3`=paused, `4`=failed, `5`=succeeded |

---

## huaweicloud_oms_migration_sync_task

Continuous synchronization task. Keeps destination in sync with future source changes. Use when the source bucket is actively written and you need ongoing replication.

```hcl
resource "huaweicloud_oms_migration_sync_task" "sync" {
  region         = var.hc_region
  src_cloud_type = "AWS"
  src_region     = var.src_region
  src_bucket     = var.src_bucket
  src_ak         = var.src_ak
  src_sk         = var.src_sk
  dst_bucket     = huaweicloud_obs_bucket.dest.bucket
  dst_ak         = var.hc_ak
  dst_sk         = var.hc_sk

  description               = "AWS S3 to Huawei OBS continuous sync"
  enable_metadata_migration = true
  consistency_check         = "size_last_modified"
  action                    = "start"  # start or stop
}
```

### All arguments

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `src_region` | yes | string | Source region |
| `src_bucket` | yes | string | Source bucket |
| `src_ak` | yes | string | Source AK |
| `src_sk` | yes | string | Source SK |
| `dst_bucket` | yes | string | Destination bucket |
| `dst_ak` | yes | string | Destination AK |
| `dst_sk` | yes | string | Destination SK |
| `region` | no | string | Destination region (defaults to provider) |
| `src_cloud_type` | no | string | Same options as `data_source` above. Default: `Aliyun` |
| `description` | no | string | Plain ASCII only |
| `enable_kms` | no | bool | KMS encryption (default `false`) |
| `enable_metadata_migration` | no | bool | Migrate metadata (default `false`) |
| `enable_restore` | no | bool | Auto-restore archive (default `false`) |
| `consistency_check` | no | string | `size_last_modified` (default), `crc64`, `no_check` |
| `app_id` | conditional | string | Required when `src_cloud_type = Tencent` |
| `source_cdn` | no | block | CDN configuration |
| `action` | no | string | `start` or `stop` |

### Attributes

| Attribute | Description |
|-----------|-------------|
| `id` | Task ID |
| `status` | `SYNCHRONIZING` or `STOPPED` |
| `created_at` | Creation timestamp |
| `last_start_at` | Last start timestamp |
| `dst_storage_policy` | Destination storage class |
| `object_overwrite_mode` | Overwrite mode |
| `monthly_*` | Monthly stats: `acceptance_request`, `success_object`, `failure_object`, `skip_object`, `size` |

---

## huaweicloud_oms_migration_task_group

Groups multiple migration tasks to share bandwidth limits and SMN config. Use when migrating many buckets or large datasets in parallel.

```hcl
resource "huaweicloud_oms_migration_task_group" "group" {
  region     = var.hc_region
  group_name = "batch-migration-group"
  type       = "MIGRATE_OBJECT"  # or MIGRATE_OBJECT_LIST

  source_object {
    data_source = "AWS"
    region      = var.src_region
    bucket      = var.src_bucket
    access_key  = var.src_ak
    secret_key  = var.src_sk
    object      = ["prefix1/", "prefix2/"]
  }

  destination_object {
    region     = var.hc_region
    bucket     = huaweicloud_obs_bucket.dest.bucket
    access_key = var.hc_ak
    secret_key = var.hc_sk
  }

  description     = "Batch migration group"
  bandwidth_policy {
    max_bandwidth = 10
    start         = "00:00"
    end           = "23:59"
  }
}
```

---

## huaweicloud_oms_sync_event

Manages an OMS synchronization event — used to trigger specific sync operations on a sync task.

```hcl
resource "huaweicloud_oms_sync_event" "event" {
  task_id = huaweicloud_oms_migration_sync_task.sync.id
  # ... event-specific configuration
}
```

---

## Data Sources

The provider also offers data sources to look up existing OMS tasks:

```hcl
# Look up an existing migration task by ID or name
data "huaweicloud_oms_migration_task" "existing" {
  id   = "260661304820157"
  # or name = "task-name"
}
```

Check the provider documentation for the exact data source names available in your version, as they evolve between releases.
