variable "region" {
  description = "Huawei Cloud region"
  type        = string
}

variable "availability_zone" {
  description = "Availability zone for compute resources"
  type        = string
  default     = "la-north-2a"
}

variable "ecs_admin_password" {
  description = "ECS admin password - set via TF_VAR_ecs_admin_password env var"
  type        = string
  sensitive   = true
}

variable "rds_password" {
  description = "RDS MySQL root password - set via TF_VAR_rds_password env var"
  type        = string
  sensitive   = true
}

variable "admin_ssh_cidr" {
  description = "CIDR block allowed for SSH access - override for your IP"
  type        = string
  default     = "0.0.0.0/0"
}

variable "eip_bandwidth_mbps" {
  description = "EIP bandwidth in Mbps"
  type        = number
  default     = 10
}
