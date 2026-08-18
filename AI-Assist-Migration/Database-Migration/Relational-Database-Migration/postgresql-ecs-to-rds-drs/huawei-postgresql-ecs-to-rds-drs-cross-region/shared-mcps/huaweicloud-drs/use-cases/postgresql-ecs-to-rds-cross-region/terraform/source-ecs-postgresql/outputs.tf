output "vpc_id" {
  description = "VPC ID"
  value       = huaweicloud_vpc.source_vpc.id
}

output "subnet_id" {
  description = "Subnet ID"
  value       = huaweicloud_vpc_subnet.source_subnet.id
}

output "ecs_source_ecs_postgresql_id" {
  description = "ECS instance ID for source-ecs-postgresql"
  value       = huaweicloud_compute_instance.source_ecs_postgresql.id
}

output "eip_source_eip_address" {
  description = "Public IP address for source-eip"
  value       = huaweicloud_vpc_eip.source_eip.address
}