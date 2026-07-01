resource "huaweicloud_networking_secgroup" "bastion" {
  name        = "${var.name_prefix}-bastion-sg"
  description = "Bastion security group"
}

resource "huaweicloud_networking_secgroup" "bigdata" {
  name        = "${var.name_prefix}-bigdata-sg"
  description = "Private big data services security group"
}

resource "huaweicloud_networking_secgroup_rule" "bastion_ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.allowed_ssh_cidr
  security_group_id = huaweicloud_networking_secgroup.bastion.id
}

resource "huaweicloud_networking_secgroup_rule" "bigdata_internal" {
  direction         = "ingress"
  ethertype         = "IPv4"
  remote_ip_prefix  = var.subnet_cidr
  security_group_id = huaweicloud_networking_secgroup.bigdata.id
}
