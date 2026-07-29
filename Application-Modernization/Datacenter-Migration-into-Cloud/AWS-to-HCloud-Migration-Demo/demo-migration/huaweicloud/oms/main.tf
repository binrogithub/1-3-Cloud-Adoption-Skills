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
  access_key = var.hc_ak
  secret_key = var.hc_sk
}

resource "huaweicloud_obs_bucket" "destino" {
  bucket = var.hc_bucket
  acl    = "private"
}

resource "huaweicloud_oms_migration_task" "aws_to_obs" {
  region = var.hc_region

  source_object {
    data_source = "AWS"
    region      = var.aws_region
    bucket      = var.aws_bucket
    access_key  = var.aws_ak
    secret_key  = var.aws_sk
    object      = [""]
  }

  destination_object {
    region     = var.hc_region
    bucket     = huaweicloud_obs_bucket.destino.bucket
    access_key = var.hc_ak
    secret_key = var.hc_sk
  }

  type                        = "prefix"
  start_task                  = true
  description                 = "AWS S3 to Huawei OBS migration"
  enable_metadata_migration   = true
  consistency_check           = "size_last_modified"
  object_overwrite_mode       = "SIZE_LAST_MODIFIED_COMPARISON_OVERWRITE"
  enable_failed_object_recording = true
}

output "obs_bucket_name" {
  value = huaweicloud_obs_bucket.destino.bucket
}

output "oms_task_id" {
  value = huaweicloud_oms_migration_task.aws_to_obs.id
}

output "oms_task_status" {
  value = huaweicloud_oms_migration_task.aws_to_obs.status
}
