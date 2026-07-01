# TODO: Validate resource arguments, cluster version, component names, and node group schema
# against the active Huawei Cloud Terraform provider and region.
resource "huaweicloud_mrs_cluster" "this" {
  name              = "${var.name_prefix}-mrs"
  availability_zone = var.availability_zone
  vpc_id            = var.vpc_id
  subnet_id         = var.subnet_id
  security_group_id = var.security_group_id
  agency            = var.agency_name

  # Suggested components for this skill:
  # Hadoop, Hive, Spark, Ranger, ClickHouse
  # TODO: Replace with provider-supported component syntax.

  # TODO: Replace node group blocks with supported syntax for selected MRS version.
  # master_nodes = var.master_nodes
  # core_nodes   = var.core_nodes
  # task_nodes   = var.task_nodes
  # node_flavor  = var.node_flavor
  # disk_type    = var.disk_type
  # disk_size    = var.disk_size
}
