output "rds_instance_id" {
  description = "Target RDS instance ID. Needed when creating the DRS task in step 5."
  value       = huaweicloud_rds_instance.target.id
}

output "rds_private_ip" {
  description = "Private IP of the target RDS. Needed for validation and cutover."
  value       = try(huaweicloud_rds_instance.target.private_ips[0], null)
}

output "rds_port" {
  description = "Port of the target RDS instance."
  value       = huaweicloud_rds_instance.target.db[0].port
}

output "rds_engine_version" {
  description = "PostgreSQL version actually provisioned. Compare against the source."
  value       = huaweicloud_rds_instance.target.db[0].version
}

output "vpc_id" {
  description = "VPC holding the target, whether created here or pre-existing."
  value       = local.vpc_id
}

output "subnet_id" {
  description = "Subnet holding the target."
  value       = local.subnet_id
}

output "security_group_id" {
  description = "Security group attached to the target."
  value       = local.security_group_id
}

output "network_was_created" {
  description = "true if this configuration created the network, false if it reused one."
  value       = var.create_network
}

output "subnet_cidr" {
  description = "CIDR of the target subnet. Needed to verify the DRS ingress rule in step 6.3."
  value       = var.create_network ? var.subnet_cidr : null
}

output "region" {
  description = "Target region."
  value       = var.region
}
