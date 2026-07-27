output "vpc_id" {
  description = "VPC ID"
  value       = huaweicloud_vpc.target_vpc.id
}

output "subnet_id" {
  description = "Subnet ID"
  value       = huaweicloud_vpc_subnet.target_subnet.id
}

output "rds_target_rds_postgresql_id" {
  description = "RDS instance ID for target-rds-postgresql"
  value       = huaweicloud_rds_instance.target_rds_postgresql.id
}

output "rds_target_rds_postgresql_private_ips" {
  description = "RDS private IPs for target-rds-postgresql"
  value       = huaweicloud_rds_instance.target_rds_postgresql.private_ips
}