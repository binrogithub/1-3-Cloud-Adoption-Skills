resource "huaweicloud_vpc_eip" "this" {
  publicip {
    type = "5_bgp"
  }
  bandwidth {
    name        = "${var.name_prefix}-eip-bandwidth"
    size        = 5
    share_type  = "PER"
    charge_mode = "traffic"
  }
}
