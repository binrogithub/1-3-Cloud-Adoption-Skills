variable "name_prefix" { type = string }
variable "vpc_id" { type = string }
variable "subnet_id" { type = string }
variable "security_group_id" { type = string }
variable "availability_zone" { type = string default = null }
variable "flavor_id" { type = string default = "s6.small.1" }
variable "image_id" { type = string default = null }
