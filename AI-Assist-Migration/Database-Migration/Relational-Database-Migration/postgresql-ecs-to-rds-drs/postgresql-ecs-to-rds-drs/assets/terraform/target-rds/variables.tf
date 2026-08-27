variable "region" {
  description = "Target region. Must be DIFFERENT from the source region."
  type        = string
}

variable "availability_zone" {
  description = "Availability zone in the target region, e.g. la-north-2a"
  type        = string
}

###############################################################################
# Network mode
###############################################################################

variable "create_network" {
  description = <<-EOT
    true  - create a new VPC, subnet and security group (default)
    false - use an existing network; set the three existing_* variables below
  EOT
  type        = bool
  default     = true
}

variable "existing_vpc_id" {
  description = "Existing VPC ID. Required when create_network = false."
  type        = string
  default     = ""
}

variable "existing_subnet_id" {
  description = "Existing subnet ID. Required when create_network = false."
  type        = string
  default     = ""
}

variable "existing_security_group_id" {
  description = "Existing security group ID. Required when create_network = false."
  type        = string
  default     = ""
}

###############################################################################
# New network - ignored when create_network = false
###############################################################################

variable "vpc_name" {
  description = "Name of the new VPC"
  type        = string
  default     = "target-vpc"
}

variable "vpc_cidr" {
  description = "CIDR of the new VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_name" {
  description = "Name of the new subnet"
  type        = string
  default     = "target-subnet"
}

variable "subnet_cidr" {
  description = "CIDR of the new subnet"
  type        = string
  default     = "10.0.0.0/24"
}

variable "subnet_gateway" {
  description = "Gateway IP of the new subnet"
  type        = string
  default     = "10.0.0.1"
}

variable "security_group_name" {
  description = "Name of the new security group"
  type        = string
  default     = "target-rds-sg"
}

variable "admin_access_cidr" {
  description = <<-EOT
    Optional single host allowed to reach PostgreSQL on the target directly.
    Must be a /32. Leave empty ("") to create no ingress rule at all, which is
    the recommended default - DRS reaches the instance privately in the VPC.
  EOT
  type        = string
  default     = ""

  validation {
    condition     = var.admin_access_cidr == "" || can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/32$", var.admin_access_cidr))
    error_message = "admin_access_cidr must be empty or a single host in /32 form, e.g. 203.0.113.7/32. Wider prefixes are not allowed."
  }
}

###############################################################################
# RDS
###############################################################################

variable "instance_name" {
  description = "Name of the target RDS instance"
  type        = string
  default     = "target-rds-postgresql"
}

variable "postgresql_version" {
  description = <<-EOT
    PostgreSQL major version. Must match the source major version.
    Discover with:
      hcloud_list_rds_datastores(region=..., database_name="PostgreSQL")
  EOT
  type        = string
}

variable "flavor" {
  description = <<-EOT
    RDS flavor ID. Varies by region - never assume one exists. Discover with:
      hcloud_list_rds_flavors(region=..., database_name="PostgreSQL", version_name=...)
  EOT
  type        = string
}

variable "volume_type" {
  description = <<-EOT
    Storage type. CLOUDSSD is the recommended default.

    GPSSD2 and ESSD2 are NOT supported by this configuration: they require a
    provisioned iops value and the API rejects them without one
    ("parameter error: iops/null", DBS.01280023). If the customer specifically
    needs one of those classes, provision the instance from the console.

    Discover what a region offers with:
      hcloud_list_rds_storage_types(region=..., database_name="PostgreSQL", version_name=...)
  EOT
  type        = string
  default     = "CLOUDSSD"

  validation {
    condition     = contains(["CLOUDSSD", "ULTRAHIGH", "HIGH", "COMMON"], var.volume_type)
    error_message = "volume_type must be one of CLOUDSSD, ULTRAHIGH, HIGH, COMMON. GPSSD2 and ESSD2 need a provisioned iops value and are not supported here."
  }
}

variable "volume_size" {
  description = "Storage in GB. Must exceed the source database size from step 1."
  type        = number
  default     = 40
}

variable "rds_password" {
  description = <<-EOT
    Admin password for the RDS instance. Pass it via the environment, never in
    a .tfvars file:
      export TF_VAR_rds_password='...'

    Huawei RDS requires 8-32 characters with at least one uppercase letter, one
    lowercase letter, one digit, and one special character from
    ~!@#$%^&*()-_=+|[{}];:,.<>?
  EOT
  type        = string
  sensitive   = true

  validation {
    condition = (
      length(var.rds_password) >= 8 &&
      length(var.rds_password) <= 32 &&
      can(regex("[A-Z]", var.rds_password)) &&
      can(regex("[a-z]", var.rds_password)) &&
      can(regex("[0-9]", var.rds_password)) &&
      can(regex("[~!@#$%^&*()\\-_=+|\\[{}\\];:,.<>?]", var.rds_password))
    )
    error_message = "rds_password must be 8-32 characters and contain an uppercase letter, a lowercase letter, a digit, and a special character from ~!@#$%^&*()-_=+|[{}];:,.<>?"
  }
}

variable "backup_start_time" {
  description = "Daily backup window, UTC, e.g. 02:00-03:00"
  type        = string
  default     = "02:00-03:00"
}

variable "backup_keep_days" {
  description = "Backup retention in days"
  type        = number
  default     = 7
}
