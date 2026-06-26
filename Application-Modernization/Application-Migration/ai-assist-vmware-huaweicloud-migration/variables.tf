variable "source_access_key" {
  type        = string
  sensitive   = true
  description = "Source account AK (read-only usage in this workflow)."
}

variable "source_secret_key" {
  type        = string
  sensitive   = true
  description = "Source account SK (read-only usage in this workflow)."
}

variable "source_region" {
  type        = string
  default     = "ap-southeast-4"
  description = "Preferred source region hint. Script will auto-discover when IDs are not in this region."
}

variable "source_project_id" {
  type        = string
  default     = ""
  description = "Preferred source project ID hint. Script will auto-discover when IDs are not in this project."
}

variable "destination_access_key" {
  type        = string
  sensitive   = true
  description = "Destination account AK."
}

variable "destination_secret_key" {
  type        = string
  sensitive   = true
  description = "Destination account SK."
}

variable "destination_region" {
  type        = string
  default     = "ap-southeast-4"
  description = "Preferred destination region hint. Script will auto-discover target ECS by fixed IP if needed."
}

variable "destination_region_name" {
  type        = string
  default     = ""
  description = "Optional destination region display name for SMS migproject. Empty means auto-resolve."
}

variable "destination_project_id" {
  type        = string
  default     = ""
  description = "Preferred destination project ID hint. Script will auto-discover target ECS by fixed IP if needed."
}

variable "source_server_ids" {
  type = list(string)
  default = [
    "b48b532f-a165-4ee1-9a49-28a0b688998d",
    "dec12878-2fd9-4704-b608-b511bb8feb23",
    "7fdf29e6-74d1-4a26-8014-ef404fd013fe",
    "a3126272-54f4-4890-a800-ba8b0269c4b6",
  ]
  description = "Source ECS IDs to migrate via SMS."
}

variable "eip_bandwidth_mbps" {
  type        = number
  default     = 100
  description = "Destination EIP bandwidth size in Mbps."
}

variable "security_group_rule_description" {
  type        = string
  default     = "虚拟机迁移"
  description = "Description used when adding destination security group rules."
}

variable "sms_endpoint" {
  type        = string
  default     = "https://sms.ap-southeast-3.myhuaweicloud.com"
  description = "SMS endpoint."
}
