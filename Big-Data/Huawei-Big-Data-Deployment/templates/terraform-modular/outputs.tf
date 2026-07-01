output "vpc_id" { value = module.vpc.vpc_id }
output "subnet_id" { value = module.vpc.subnet_id }
output "obs_bucket_name" { value = module.obs.bucket_name }
output "security_group_ids" {
  value = {
    bastion = module.security.bastion_security_group_id
    bigdata = module.security.bigdata_security_group_id
  }
}
output "iam_agency_name" { value = module.iam_agency.agency_name }
output "bastion_eip" { value = try(module.bastion[0].eip_address, null) }
output "mrs_cluster_id" { value = try(module.mrs[0].cluster_id, null) }
output "mrs_manager_url" { value = try(module.mrs[0].manager_url, null) }
output "dws_endpoint" { value = try(module.dws[0].endpoint, null) }
output "dli_queue_name" { value = try(module.dli[0].queue_name, null) }
output "kms_key_id" { value = try(module.kms[0].key_id, null) }
