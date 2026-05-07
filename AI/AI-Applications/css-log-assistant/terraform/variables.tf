variable "huaweicloud_access_key" {
  description = "Huawei Cloud Access Key ID"
  type        = string
  sensitive   = true
}

variable "huaweicloud_secret_key" {
  description = "Huawei Cloud Secret Access Key"
  type        = string
  sensitive   = true
}

variable "css_region" {
  description = "Region for CSS cluster deployment"
  type        = string
  default     = "la-north-2"
}

variable "maas_region" {
  description = "Region for MaaS service"
  type        = string
  default     = "ap-southeast-1"
}

variable "css_admin_password" {
  description = "CSS cluster admin password (8-32 chars, at least 3 of: uppercase, lowercase, digit, special)"
  type        = string
  sensitive   = true
}

variable "maas_api_key" {
  description = "MaaS API Key for GLM-5.1 model access"
  type        = string
  sensitive   = true
}

variable "css_cluster_name" {
  description = "CSS cluster name"
  type        = string
  default     = "css-log-assistant"
}

variable "css_engine_version" {
  description = "CSS engine version"
  type        = string
  default     = "7.10.2"
}

variable "css_flavor" {
  description = "CSS node flavor"
  type        = string
  default     = "ess.spec-4u8g"
}

variable "css_node_count" {
  description = "Number of CSS data nodes"
  type        = number
  default     = 3
}

variable "css_volume_size" {
  description = "CSS node volume size in GB"
  type        = number
  default     = 40
}

variable "css_volume_type" {
  description = "CSS node volume type (COMMON/HIGH/ULTRAHIGH)"
  type        = string
  default     = "HIGH"
}

variable "public_bandwidth" {
  description = "Public access bandwidth in Mbit/s"
  type        = number
  default     = 10
}

variable "enterprise_project_id" {
  description = "Enterprise project ID (0 = default)"
  type        = string
  default     = "0"
}

variable "allowed_cidrs" {
  description = "Allowed CIDR blocks for public access (ES 9200, Kibana 5601, MCP SSE 8000)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
