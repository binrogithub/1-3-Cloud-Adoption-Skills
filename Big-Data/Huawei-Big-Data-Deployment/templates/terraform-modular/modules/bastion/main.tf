# TODO: Replace image_id/flavor_id with values available in the target region.
resource "huaweicloud_compute_instance" "this" {
  name              = "${var.name_prefix}-bastion"
  flavor_id         = var.flavor_id
  image_id          = var.image_id
  availability_zone = var.availability_zone
  security_groups   = [var.security_group_id]

  network {
    uuid = var.subnet_id
  }
}

resource "huaweicloud_vpc_eip" "this" {
  publicip {
    type = "5_bgp"
  }
  bandwidth {
    name        = "${var.name_prefix}-bastion-bw"
    size        = 5
    share_type  = "PER"
    charge_mode = "traffic"
  }
}

resource "huaweicloud_compute_eip_associate" "this" {
  public_ip   = huaweicloud_vpc_eip.this.address
  instance_id = huaweicloud_compute_instance.this.id
}
