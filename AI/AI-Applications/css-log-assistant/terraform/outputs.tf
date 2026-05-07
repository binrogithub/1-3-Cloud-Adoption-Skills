output "css_cluster_id" {
  description = "CSS cluster ID"
  value       = huaweicloud_css_cluster.log_assistant.id
}

output "css_cluster_name" {
  description = "CSS cluster name"
  value       = huaweicloud_css_cluster.log_assistant.name
}

output "css_cluster_endpoint" {
  description = "CSS cluster internal endpoint (host:port)"
  value       = huaweicloud_css_cluster.log_assistant.endpoint
}

output "css_cluster_status" {
  description = "CSS cluster status (200=available)"
  value       = huaweicloud_css_cluster.log_assistant.status
}

output "css_public_ip" {
  description = "CSS cluster public IP address"
  value       = huaweicloud_css_cluster.log_assistant.public_access[0].public_ip
}

output "css_nodes" {
  description = "CSS cluster node information"
  value       = huaweicloud_css_cluster.log_assistant.nodes
}

output "vpc_id" {
  description = "VPC ID"
  value       = huaweicloud_vpc.css.id
}

output "subnet_id" {
  description = "Subnet ID"
  value       = huaweicloud_vpc_subnet.css.id
}

output "security_group_id" {
  description = "Security group ID"
  value       = huaweicloud_networking_secgroup.css.id
}

output "availability_zone" {
  description = "Availability zone used"
  value       = data.huaweicloud_availability_zones.available.names[0]
}
