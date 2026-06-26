terraform {
  required_version = ">= 1.5.0"
}

locals {
  run_fingerprint = sha1(jsonencode({
    source_region                   = var.source_region
    source_project_id               = var.source_project_id
    destination_region              = var.destination_region
    destination_region_name         = var.destination_region_name
    destination_project_id          = var.destination_project_id
    source_server_ids               = var.source_server_ids
    eip_bandwidth_mbps              = var.eip_bandwidth_mbps
    security_group_rule_description = var.security_group_rule_description
    sms_endpoint                    = var.sms_endpoint
  }))
}

resource "terraform_data" "sms_existing_target_batch" {
  triggers_replace = [local.run_fingerprint]

  provisioner "local-exec" {
    command = "bash ${path.module}/scripts/run_migration.sh"
    environment = {
      SOURCE_ACCESS_KEY = var.source_access_key
      SOURCE_SECRET_KEY = var.source_secret_key
      SOURCE_REGION     = var.source_region
      SOURCE_PROJECT_ID = var.source_project_id

      DESTINATION_ACCESS_KEY  = var.destination_access_key
      DESTINATION_SECRET_KEY  = var.destination_secret_key
      DESTINATION_REGION      = var.destination_region
      DESTINATION_REGION_NAME = var.destination_region_name
      DESTINATION_PROJECT_ID  = var.destination_project_id

      SOURCE_SERVER_IDS   = join(",", var.source_server_ids)
      EIP_BANDWIDTH_MBPS  = tostring(var.eip_bandwidth_mbps)
      SG_RULE_DESCRIPTION = var.security_group_rule_description
      SMS_ENDPOINT        = var.sms_endpoint
      RESULT_PATH         = "${path.module}/out/migration_result.json"
    }
  }
}

output "migration_result_file" {
  value       = "${path.module}/out/migration_result.json"
  description = "Execution result json written by scripts/mgc_sms_existing_target_batch.py"
}
