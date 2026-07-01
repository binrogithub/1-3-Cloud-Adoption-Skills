variable "name_prefix" { type = string }
variable "vpc_id" { type = string }
variable "subnet_id" { type = string }
variable "security_group_id" { type = string }
variable "availability_zone" { type = string default = null }
variable "node_count" { type = number default = 3 }
variable "node_flavor" { type = string default = "smallest_available" }
variable "database_name" { type = string default = "gaussdb" }
