# TODO: Validate exact resource arguments for the active Huawei Cloud provider version.
# Keep DWS private-only by default.
resource "huaweicloud_dws_cluster" "this" {
  name              = "${var.name_prefix}-dws"
  availability_zone = var.availability_zone
  vpc_id            = var.vpc_id
  subnet_id         = var.subnet_id
  security_group_id = var.security_group_id
  node_count        = var.node_count
  node_type         = var.node_flavor
  db_name           = var.database_name

  # TODO: Add admin password through secure variable or secret manager only.
  # Do not commit real passwords to GitHub.
}
