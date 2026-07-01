# TODO: Validate exact agency trust and policy syntax for the target Huawei Cloud account.
# This placeholder keeps the module interface stable for the AI skill.
resource "huaweicloud_identity_agency" "this" {
  name                  = "${var.name_prefix}-bigdata-agency"
  delegated_service_name = "op_svc_mrs"
  duration              = "FOREVER"
  description           = "Agency for big data services to access OBS and related resources"
}
