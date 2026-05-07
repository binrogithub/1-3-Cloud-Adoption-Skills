data "huaweicloud_availability_zones" "available" {}

resource "huaweicloud_vpc" "css" {
  name = "${var.css_cluster_name}-vpc"
  cidr = "192.168.0.0/16"
}

resource "huaweicloud_vpc_subnet" "css" {
  name       = "${var.css_cluster_name}-subnet"
  vpc_id     = huaweicloud_vpc.css.id
  cidr       = "192.168.0.0/24"
  gateway_ip = "192.168.0.1"
}

resource "huaweicloud_networking_secgroup" "css" {
  name        = "${var.css_cluster_name}-secgroup"
  description = "Security group for CSS log assistant cluster"
}

resource "huaweicloud_networking_secgroup_rule" "es_rest" {
  for_each          = toset(var.allowed_cidrs)
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 9200
  port_range_max    = 9200
  remote_ip_prefix  = each.value
  security_group_id = huaweicloud_networking_secgroup.css.id
}

resource "huaweicloud_networking_secgroup_rule" "kibana" {
  for_each          = toset(var.allowed_cidrs)
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 5601
  port_range_max    = 5601
  remote_ip_prefix  = each.value
  security_group_id = huaweicloud_networking_secgroup.css.id
}

resource "huaweicloud_networking_secgroup_rule" "mcp_sse" {
  for_each          = toset(var.allowed_cidrs)
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8000
  port_range_max    = 8000
  remote_ip_prefix  = each.value
  security_group_id = huaweicloud_networking_secgroup.css.id
}

resource "huaweicloud_networking_secgroup_rule" "es_transport" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 9300
  port_range_max    = 9300
  remote_ip_prefix  = "192.168.0.0/16"
  security_group_id = huaweicloud_networking_secgroup.css.id
}

resource "huaweicloud_networking_secgroup_rule" "internal_comm" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 9200
  port_range_max    = 9400
  remote_ip_prefix  = "192.168.0.0/16"
  security_group_id = huaweicloud_networking_secgroup.css.id
}
