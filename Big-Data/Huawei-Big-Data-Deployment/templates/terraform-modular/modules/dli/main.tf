# TODO: Validate exact queue type and supported CU sizes in target region.
resource "huaweicloud_dli_queue" "this" {
  name     = "${var.name_prefix}-dli-gp"
  cu_count = var.queue_cu_count
  type     = "general"
}
