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

resource "huaweicloud_vpc" "demo" {
  name = "demo-vpc"
  cidr = "10.0.0.0/16"
}

resource "huaweicloud_vpc_subnet" "demo" {
  name       = "demo-subnet"
  cidr       = "10.0.1.0/24"
  gateway_ip = "10.0.1.1"
  vpc_id     = huaweicloud_vpc.demo.id
}

resource "huaweicloud_networking_secgroup" "demo" {
  name        = "demo-sg"
  description = "Allow HTTP and SSH inbound"
}

resource "huaweicloud_networking_secgroup_rule" "ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = huaweicloud_networking_secgroup.demo.id
}

resource "huaweicloud_networking_secgroup_rule" "http" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = huaweicloud_networking_secgroup.demo.id
}

resource "huaweicloud_networking_secgroup_rule" "https" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = huaweicloud_networking_secgroup.demo.id
}

output "vpc_id" {
  value = huaweicloud_vpc.demo.id
}

output "subnet_id" {
  value = huaweicloud_vpc_subnet.demo.id
}

output "secgroup_id" {
  value = huaweicloud_networking_secgroup.demo.id
}
