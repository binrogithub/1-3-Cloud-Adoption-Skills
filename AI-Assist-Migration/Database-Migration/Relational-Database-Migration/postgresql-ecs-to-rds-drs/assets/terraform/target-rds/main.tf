###############################################################################
# Target infrastructure for a DRS PostgreSQL migration
#
# Two network modes, controlled by create_network:
#
#   create_network = true   (default)
#     Creates a new VPC, subnet and security group.
#
#   create_network = false
#     Uses an existing VPC, subnet and security group. Set existing_vpc_id,
#     existing_subnet_id and existing_security_group_id. Nothing is created
#     on the network side and nothing existing is modified.
#
# Credentials come from the environment, never from a file:
#   export HW_ACCESS_KEY='...'
#   export HW_SECRET_KEY='...'
#   export TF_VAR_rds_password='...'
#
# Discover valid values before applying - they vary by region:
#   hcloud_list_rds_datastores(region=..., database_name="PostgreSQL")
#   hcloud_list_rds_flavors(region=..., database_name="PostgreSQL", version_name=...)
#   hcloud_list_rds_storage_types(region=..., database_name="PostgreSQL", version_name=...)
#   hcloud_list_availability_zones(region=...)
###############################################################################

terraform {
  required_version = ">= 1.3.0"

  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = ">= 1.60.0"
    }
  }
}

provider "huaweicloud" {
  region = var.region
  # access_key / secret_key read from HW_ACCESS_KEY / HW_SECRET_KEY
}

locals {
  vpc_id            = var.create_network ? huaweicloud_vpc.target[0].id : var.existing_vpc_id
  subnet_id         = var.create_network ? huaweicloud_vpc_subnet.target[0].id : var.existing_subnet_id
  security_group_id = var.create_network ? huaweicloud_networking_secgroup.target[0].id : var.existing_security_group_id
}

###############################################################################
# Network - created only when create_network = true
###############################################################################

resource "huaweicloud_vpc" "target" {
  count = var.create_network ? 1 : 0

  name = var.vpc_name
  cidr = var.vpc_cidr
}

resource "huaweicloud_vpc_subnet" "target" {
  count = var.create_network ? 1 : 0

  name              = var.subnet_name
  cidr              = var.subnet_cidr
  gateway_ip        = var.subnet_gateway
  vpc_id            = huaweicloud_vpc.target[0].id
  availability_zone = var.availability_zone
}

###############################################################################
# Security group
#
# The DRS replication instance is created INSIDE this VPC and reaches the RDS
# instance over the subnet. Because delete_default_rules removes the implicit
# intra-group allow, an explicit ingress rule on 5432 from the subnet CIDR is
# REQUIRED - without it the DRS target connection test fails with
# "Connection failed. Check security group...".
#
# The rule is scoped to the subnet CIDR, not 0.0.0.0/0. The RDS instance has no
# public IP, so it is not reachable from outside the VPC either way.
#
# Set admin_access_cidr only if a specific host needs direct access. It must be
# a /32; anything wider is rejected.
###############################################################################

resource "huaweicloud_networking_secgroup" "target" {
  count = var.create_network ? 1 : 0

  name                 = var.security_group_name
  description          = "Target RDS security group for DRS migration"
  delete_default_rules = true
}

resource "huaweicloud_networking_secgroup_rule" "egress_all" {
  count = var.create_network ? 1 : 0

  security_group_id = huaweicloud_networking_secgroup.target[0].id
  direction         = "egress"
  ethertype         = "IPv4"
  remote_ip_prefix  = "0.0.0.0/0"
}

# Required: lets the DRS replication instance reach the RDS instance.
resource "huaweicloud_networking_secgroup_rule" "ingress_postgres_subnet" {
  count = var.create_network ? 1 : 0

  security_group_id = huaweicloud_networking_secgroup.target[0].id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 5432
  port_range_max    = 5432
  remote_ip_prefix  = var.subnet_cidr
  description       = "DRS replication instance to RDS, within the VPC subnet"
}

resource "huaweicloud_networking_secgroup_rule" "ingress_postgres_admin" {
  count = var.admin_access_cidr == "" ? 0 : 1

  security_group_id = local.security_group_id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 5432
  port_range_max    = 5432
  remote_ip_prefix  = var.admin_access_cidr
}

###############################################################################
# RDS for PostgreSQL
###############################################################################

resource "huaweicloud_rds_instance" "target" {
  name              = var.instance_name
  flavor            = var.flavor
  vpc_id            = local.vpc_id
  subnet_id         = local.subnet_id
  security_group_id = local.security_group_id
  availability_zone = [var.availability_zone]
  charging_mode     = "postPaid"

  db {
    type     = "PostgreSQL"
    version  = var.postgresql_version
    password = var.rds_password
    port     = 5432
  }

  # NOTE ON STORAGE TYPE
  # This configuration supports storage classes that do not require a
  # provisioned IOPS value: CLOUDSSD (recommended), ULTRAHIGH, HIGH.
  #
  # GPSSD2 and ESSD2 are NOT supported here. They require an explicit iops
  # parameter and the API rejects them without it:
  #   "parameter error: iops/null" (DBS.01280023)
  # The volume_type variable validates this and fails at plan time rather than
  # letting the apply fail against the API.
  volume {
    type = var.volume_type
    size = var.volume_size
  }

  backup_strategy {
    start_time = var.backup_start_time
    keep_days  = var.backup_keep_days
  }

  lifecycle {
    ignore_changes = [db[0].password]
  }
}
