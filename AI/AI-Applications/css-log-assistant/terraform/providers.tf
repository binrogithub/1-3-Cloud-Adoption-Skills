terraform {
  required_version = ">= 1.0.0"

  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = ">= 1.63.0"
    }
  }
}

provider "huaweicloud" {
  region     = var.css_region
  access_key = var.huaweicloud_access_key
  secret_key = var.huaweicloud_secret_key
}

provider "huaweicloud" {
  alias      = "maas"
  region     = "ap-southeast-1"
  access_key = var.huaweicloud_access_key
  secret_key = var.huaweicloud_secret_key
}
