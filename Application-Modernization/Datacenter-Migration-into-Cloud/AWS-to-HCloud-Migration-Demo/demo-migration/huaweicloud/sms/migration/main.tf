terraform {
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "1.93.0"
    }
  }
}

provider "huaweicloud" {
  region = "la-north-2"
}

data "huaweicloud_availability_zones" "demo" {}

data "huaweicloud_vpc" "demo" {
  name = "demo-vpc"
}

data "huaweicloud_vpc_subnet" "demo" {
  name = "demo-subnet"
}

data "huaweicloud_networking_secgroup" "demo" {
  name = "demo-sg"
}

data "huaweicloud_sms_source_servers" "demo" {
  id = "d317cae9-f32a-4ac2-94d2-e098215b4664"
}

resource "huaweicloud_sms_server_template" "demo" {
  name               = "demo-web-template"
  availability_zone  = data.huaweicloud_availability_zones.demo.names[0]
  vpc_id             = data.huaweicloud_vpc.demo.id
  subnet_ids         = [data.huaweicloud_vpc_subnet.demo.id]
  security_group_ids = [data.huaweicloud_networking_secgroup.demo.id]
  flavor             = "c6.large.4"
  volume_type        = "SAS"
  target_server_name = "demo-web"
  bandwidth_size     = 10
}

resource "huaweicloud_sms_task" "migration" {
  type                = "MIGRATE_FILE"
  os_type             = "LINUX"
  source_server_id    = data.huaweicloud_sms_source_servers.demo.servers[0].id
  vm_template_id      = huaweicloud_sms_server_template.demo.id
  action              = "start"
  start_target_server = true
  use_public_ip       = true

  lifecycle {
    ignore_changes = [
      syncing, action, auto_start, start_network_check,
      over_speed_threshold, is_need_consistency_check,
    ]
  }
}

output "template_id" {
  value = huaweicloud_sms_server_template.demo.id
}

output "task_id" {
  value = huaweicloud_sms_task.migration.id
}

output "task_state" {
  value = huaweicloud_sms_task.migration.state
}

output "target_server_name" {
  value = huaweicloud_sms_task.migration.target_server_name
}
