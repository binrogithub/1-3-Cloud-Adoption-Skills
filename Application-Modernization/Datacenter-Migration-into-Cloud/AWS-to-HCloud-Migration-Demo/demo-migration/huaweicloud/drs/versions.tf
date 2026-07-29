terraform {
  required_version = ">= 1.5"
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "1.93.0"
    }
  }
}

provider "huaweicloud" {
  region     = "la-north-2"
  access_key = var.huaweicloud_ak
  secret_key = var.huaweicloud_sk
}
