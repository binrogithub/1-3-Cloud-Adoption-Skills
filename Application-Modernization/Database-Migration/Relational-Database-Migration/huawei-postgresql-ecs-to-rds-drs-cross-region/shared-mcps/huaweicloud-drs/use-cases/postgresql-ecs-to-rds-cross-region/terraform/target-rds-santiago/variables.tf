variable "region" {
  description = "Huawei Cloud region"
  type        = string
}

variable "availability_zone" {
  description = "Availability zone for compute resources"
  type        = string
  default     = "la-north-2a"
}

variable "rds_password" {
  description = "RDS PostgreSQL root password - set via TF_VAR_rds_password env var"
  type        = string
  sensitive   = true
}

variable "allowed_drs_cidr" {
  description = "CIDR block for DRS access to target RDS - replace with actual DRS CIDR"
  type        = string
  default     = "REPLACE_WITH_DRS_SOURCE_CIDR"
}

variable "allowed_das_cidr" {
  description = "CIDR block for DAS access to target RDS"
  type        = string
  default     = "REPLACE_WITH_DAS_CIDR"
}

variable "admin_ssh_cidr" {
  description = "CIDR block allowed for SSH access - override for your IP"
  type        = string
  default     = "0.0.0.0/0"
}
