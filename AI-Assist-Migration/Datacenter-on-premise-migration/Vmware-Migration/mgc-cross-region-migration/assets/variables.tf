variable "access_key" {
  type        = string
  sensitive   = true
  description = "Huawei Cloud AK"
}

variable "secret_key" {
  type        = string
  sensitive   = true
  description = "Huawei Cloud SK"
}

variable "domain_name" {
  type        = string
  default     = ""
  description = "Account domain name (kept for audit/context, not required for AK/SK signed requests)."
}

variable "source_server_id" {
  type        = string
  default     = "4fb3d857-aa08-4b79-8810-760cab680418"
  description = "Source VM ID in LA-Mexico City2."
}

variable "source_region" {
  type        = string
  default     = "la-north-2"
  description = "Source region code (LA-Mexico City2)."
}

variable "target_region" {
  type        = string
  default     = "la-south-2"
  description = "Target region code (LA-Santiago)."
}

variable "target_region_name" {
  type        = string
  default     = "LA-Santiago"
  description = "Target region display name used in SMS task body."
}

variable "target_vpc_name" {
  type        = string
  default     = "vpc-migration"
  description = "Target VPC name in destination region."
}

variable "target_vpc_cidr" {
  type        = string
  default     = "10.250.0.0/16"
  description = "Target VPC CIDR used when creating target VPC automatically."
}

variable "target_subnet_cidr" {
  type        = string
  default     = "10.250.1.0/24"
  description = "Target subnet CIDR used when creating target subnet automatically."
}

variable "target_image_id" {
  type        = string
  description = "Image ID in destination region used to create the intermediate target ECS before SMS cutover."
}

variable "target_server_name" {
  type        = string
  default     = "mx2-to-santiago-migrated"
  description = "Target ECS name to create in Santiago."
}

variable "target_flavor_id" {
  type        = string
  default     = ""
  description = "Optional target ECS flavor ID override; empty means auto-select by source CPU/RAM."
}

variable "target_admin_password" {
  type        = string
  sensitive   = true
  default     = "MgcMigr@te2026!"
  description = "Target ECS admin password used for initial login and rsync fallback."
}

variable "eip_bandwidth_mbps" {
  type        = number
  default     = 5
  description = "Target EIP bandwidth size in Mbps."
}

variable "root_volume_type" {
  type        = string
  default     = "SSD"
  description = "Root disk volume type for target ECS creation."
}

variable "data_volume_type" {
  type        = string
  default     = "SSD"
  description = "Data disk volume type for target ECS creation."
}

variable "sms_endpoint" {
  type        = string
  default     = "https://sms.ap-southeast-3.myhuaweicloud.com"
  description = "SMS endpoint from Huawei Cloud documentation for international site."
}

variable "preferred_migration_method" {
  type        = string
  default     = "sms"
  description = "Primary migration method: sms (default) or rsync."
}

variable "enable_rsync_fallback" {
  type        = bool
  default     = true
  description = "When true, fallback to rsync if SMS is incompatible or task creation fails with unsupported-source errors."
}

variable "source_private_ip" {
  type        = string
  default     = ""
  description = "Optional on-prem source private IP used in SG peer allow-list and records."
}

variable "extra_peer_ips" {
  type        = list(string)
  default     = []
  description = "Additional IPv4 peers to allow in target/source security groups."
}

variable "rsync_source_host" {
  type        = string
  default     = "10.8.0.2"
  description = "SSH host/IP used to access source VM (for host-port forwarding scenarios)."
}

variable "rsync_source_port" {
  type        = number
  default     = 2222
  description = "SSH port used to access source VM."
}

variable "rsync_source_user" {
  type        = string
  default     = "root"
  description = "SSH username for source VM."
}

variable "rsync_source_password" {
  type        = string
  sensitive   = true
  default     = ""
  description = "SSH password for source VM. Required when key login is unavailable."
}

variable "rsync_target_host" {
  type        = string
  default     = ""
  description = "Optional SSH host/IP override for target ECS. Empty means use target floating IP then fixed IP."
}

variable "rsync_target_port" {
  type        = number
  default     = 22
  description = "SSH port used for target ECS."
}

variable "rsync_target_user" {
  type        = string
  default     = "root"
  description = "SSH username for target ECS."
}

variable "rsync_target_password" {
  type        = string
  sensitive   = true
  default     = ""
  description = "SSH password for target ECS. Empty means fallback to target_admin_password."
}

variable "rsync_source_paths" {
  type        = list(string)
  default     = ["/"]
  description = "Source paths to synchronize. Root migration commonly uses ['/'] with excludes."
}

variable "rsync_staging_dir" {
  type        = string
  default     = "/tmp/mgc-rsync-stage"
  description = "Local temporary staging directory for source->local->target rsync workflow."
}

variable "rsync_incremental_rounds" {
  type        = number
  default     = 1
  description = "Number of incremental sync rounds before cutover."
}

variable "rsync_timeout_sec" {
  type        = number
  default     = 7200
  description = "Timeout per rsync/ssh command in seconds."
}

variable "rsync_common_args" {
  type        = string
  default     = "--numeric-ids --info=stats2,progress2 --partial"
  description = "Extra rsync arguments shared by full/incremental/cutover phases."
}

variable "rsync_excludes" {
  type = list(string)
  default = [
    "/dev/*",
    "/proc/*",
    "/sys/*",
    "/tmp/*",
    "/run/*",
    "/mnt/*",
    "/media/*",
    "/lost+found",
    "/swapfile",
    "/var/tmp/*",
    "/var/run/*",
    "/boot/efi/*"
  ]
  description = "Exclude list for root-level rsync migration."
}

variable "rsync_cutover_stop_cmd" {
  type        = string
  default     = ""
  description = "Optional command executed on source host before final cutover sync (for example stop app/service)."
}

variable "rsync_cutover_start_cmd" {
  type        = string
  default     = ""
  description = "Optional command executed on source host after final cutover sync."
}

variable "rsync_target_finalize_cmd" {
  type        = string
  default     = ""
  description = "Optional command executed on target host after cutover sync."
}

variable "enable_vpn_bridge" {
  type        = bool
  default     = true
  description = "When true, use codex OpenVPN server + VPC peering bridge to connect source VM network and target VPC for rsync."
}

variable "enable_target_vpn_client" {
  type        = bool
  default     = true
  description = "Enable OpenVPN client bootstrap on target ECS so source and target are connected through Codex VPN server."
}

variable "vpn_server_public_ip" {
  type        = string
  default     = ""
  description = "OpenVPN server public IP. Empty means auto-detect from metadata."
}

variable "vpn_server_port" {
  type        = number
  default     = 1194
  description = "OpenVPN server UDP port."
}

variable "vpn_client_common_name" {
  type        = string
  default     = "site-mx2-target"
  description = "OpenVPN client certificate common name for target ECS."
}

variable "vpn_client_static_ip" {
  type        = string
  default     = "10.8.0.10"
  description = "Static OpenVPN IP to assign target ECS via CCD."
}
