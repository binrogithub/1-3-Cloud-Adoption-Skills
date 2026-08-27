output "vpc_id" {
  description = "VPC ID"
  value       = huaweicloud_vpc.webapp_vpc.id
}

output "subnet_id" {
  description = "Subnet ID"
  value       = huaweicloud_vpc_subnet.webapp_subnet.id
}

output "ecs_webapp_ecs_1_id" {
  description = "ECS instance ID for webapp_ecs-1"
  value       = huaweicloud_compute_instance.webapp_ecs_1.id
}

output "ecs_webapp_ecs_2_id" {
  description = "ECS instance ID for webapp_ecs-2"
  value       = huaweicloud_compute_instance.webapp_ecs_2.id
}

output "eip_webapp_eip_address" {
  description = "Public IP address for webapp_eip"
  value       = huaweicloud_vpc_eip.webapp_eip.address
}

output "elb_webapp_elb_id" {
  description = "ELB ID for webapp_elb"
  value       = huaweicloud_elb_loadbalancer.webapp_elb.id
}

output "rds_webapp_rds_id" {
  description = "RDS instance ID for webapp_rds"
  value       = huaweicloud_rds_instance.webapp_rds.id
}

output "rds_webapp_rds_private_ips" {
  description = "RDS private IPs for webapp_rds"
  value       = huaweicloud_rds_instance.webapp_rds.private_ips
}

output "obs_webapp_uploads_bucket" {
  description = "OBS bucket name for webapp_uploads"
  value       = huaweicloud_obs_bucket.webapp_uploads.bucket
}