variable "project" { type = string }
variable "env" { type = string }
variable "region" { type = string default = "la-north-2" }
variable "availability_zone" { type = string default = null }
variable "vpc_cidr" { type = string default = "10.10.0.0/16" }
variable "subnet_cidr" { type = string default = "10.10.1.0/24" }
variable "allowed_ssh_cidr" { type = string default = "127.0.0.1/32" }
variable "enable_bastion" { type = bool default = true }
variable "enable_kms" { type = bool default = false }
variable "enable_mrs" { type = bool default = true }
variable "enable_dws" { type = bool default = false }
variable "enable_dli" { type = bool default = false }
variable "enable_cdm" { type = bool default = false }
