variable "huaweicloud_ak" {
  description = "Huawei Cloud Access Key"
  type        = string
  sensitive   = true
}

variable "huaweicloud_sk" {
  description = "Huawei Cloud Secret Key"
  type        = string
  sensitive   = true
}

variable "target_db_password" {
  description = "Huawei Cloud RDS root password"
  type        = string
  sensitive   = true
}

variable "source_db_password" {
  description = "AWS RDS admin password"
  type        = string
  sensitive   = true
}

variable "source_db_user" {
  description = "AWS RDS admin username"
  type        = string
  default     = "admin"
}

variable "source_db_endpoint" {
  description = "AWS RDS endpoint"
  type        = string
  default     = "demo-db.ct8ua64omsz2.us-east-2.rds.amazonaws.com"
}

variable "source_db_port" {
  description = "AWS RDS port"
  type        = string
  default     = "3306"
}
