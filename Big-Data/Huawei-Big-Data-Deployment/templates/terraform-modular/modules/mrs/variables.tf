variable "name_prefix" { type = string }
variable "vpc_id" { type = string }
variable "subnet_id" { type = string }
variable "security_group_id" { type = string }
variable "agency_name" { type = string }
variable "availability_zone" { type = string default = null }
variable "master_nodes" { type = number default = 3 }
variable "core_nodes" { type = number default = 3 }
variable "task_nodes" { type = number default = 2 }
variable "node_flavor" { type = string default = "smallest_available" }
variable "disk_type" { type = string default = "smallest_available" }
variable "disk_size" { type = number default = 100 }
