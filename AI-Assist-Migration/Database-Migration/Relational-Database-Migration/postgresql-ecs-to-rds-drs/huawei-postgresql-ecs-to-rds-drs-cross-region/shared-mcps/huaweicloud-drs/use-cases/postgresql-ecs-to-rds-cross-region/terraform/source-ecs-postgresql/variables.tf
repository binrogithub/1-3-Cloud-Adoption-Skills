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

variable "admin_ssh_cidr" {
  description = "CIDR block allowed for SSH access - override for your IP"
  type        = string
  default     = "0.0.0.0/0"
}

variable "allowed_drs_cidr" {
  description = "CIDR block for DRS source access to PostgreSQL - replace with actual DRS CIDR from console"
  type        = string
  default     = "REPLACE_WITH_DRS_SOURCE_CIDR"
}

variable "eip_bandwidth_mbps" {
  description = "EIP bandwidth in Mbps"
  type        = number
  default     = 5
}
