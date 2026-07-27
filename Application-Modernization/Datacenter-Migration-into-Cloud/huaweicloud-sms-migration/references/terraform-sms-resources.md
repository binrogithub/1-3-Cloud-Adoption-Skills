# Terraform SMS Resources

Complete reference for HuaweiCloud Terraform provider SMS resources and data sources.

## Provider Configuration

```hcl
terraform {
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "1.93.0"  # check for latest
    }
  }
}

provider "huaweicloud" {
  region = var.target_region  # e.g. la-north-2 (target ECS region, NOT SMS API region)
}
```

Credentials via environment variables:
```bash
export HW_ACCESS_KEY="<your-ak>"
export HW_SECRET_KEY="<your-sk>"
```

## Data Sources

### huaweicloud_sms_source_servers

Look up source servers registered with SMS.

```hcl
data "huaweicloud_sms_source_servers" "demo" {
  id    = var.source_server_id  # by ID
  # OR
  name  = "server-name"         # by name
  # OR
  state = "waiting"             # by state
  # OR
  ip    = "10.0.1.156"          # by IP
}
```

Attributes: `servers[].{id, name, ip, state, connected, os_type, os_version, agent_version, vcpus, memory, disks[]}`

### huaweicloud_vpc

```hcl
data "huaweicloud_vpc" "demo" {
  name = "demo-vpc"  # or id = "vpc-id"
}
```

### huaweicloud_vpc_subnet

```hcl
data "huaweicloud_vpc_subnet" "demo" {
  name = "demo-public-subnet-1"  # or id = "subnet-id"
}
```

### huaweicloud_networking_secgroup

```hcl
data "huaweicloud_networking_secgroup" "demo" {
  name = "demo-ec2-sg"  # or secgroup_id = "sg-id"
}
```

### huaweicloud_availability_zones

```hcl
data "huaweicloud_availability_zones" "demo" {}
# Use: data.huaweicloud_availability_zones.demo.names[0]  # first AZ
```

### huaweicloud_images_image

```hcl
data "huaweicloud_images_image" "ubuntu" {
  name_regex  = "^Ubuntu 22.04"
  visibility  = "public"
  most_recent = true
}
```

## Resources

### huaweicloud_sms_server_template (RECOMMENDED)

Creates a target server template. SMS uses this to auto-create the target ECS during migration.

```hcl
resource "huaweicloud_sms_server_template" "demo" {
  name               = "demo-template"           # (Required) Template name
  availability_zone  = "la-north-2a"             # (Required) Target AZ
  vpc_id             = data.huaweicloud_vpc.demo.id           # (Optional) Use existing VPC
  subnet_ids         = [data.huaweicloud_vpc_subnet.demo.id] # (Optional) Use existing subnets
  security_group_ids = [data.huaweicloud_networking_secgroup.demo.id] # (Optional) Use existing SGs
  flavor             = "c6.large.4"              # (Optional) Target flavor
  volume_type        = "SAS"                     # (Optional) SAS, SSD (default: SAS)
  target_server_name = "demo-web-server"         # (Optional) Target ECS name
  bandwidth_size     = 10                        # (Optional) EIP bandwidth in Mbit/s (1-2000)
  # region             = "la-north-2"            # (Optional) Defaults to provider region
  # project_id         = "..."                   # (Optional) Defaults to default project
}
```

**Key behavior**: If `vpc_id`, `subnet_ids`, or `security_group_ids` are omitted or set to "autoCreate", SMS creates new ones automatically. To use existing infrastructure, always specify these fields.

**Attributes**: `id`, `vpc_name`

### huaweicloud_sms_task

Creates and optionally starts a migration task.

```hcl
resource "huaweicloud_sms_task" "migration" {
  type               = "MIGRATE_FILE"            # (Required) MIGRATE_FILE or MIGRATE_BLOCK
  os_type            = "LINUX"                   # (Required) LINUX or WINDOWS
  source_server_id   = "<source-id>"             # (Required) Source server ID
  vm_template_id     = huaweicloud_sms_server_template.demo.id  # Template approach
  action             = "start"                   # (Optional) start, stop, restart
  start_target_server = true                     # (Optional) Auto-start target after migration (default: true)
  use_public_ip      = true                      # (Optional) Use public IP for migration (default: true)

  lifecycle {
    ignore_changes = [
      syncing, action, auto_start, start_network_check,
      over_speed_threshold, is_need_consistency_check,
    ]
  }
}
```

**Attributes**: `id`, `state`, `target_server_name`, `migrate_speed`, `enterprise_project_id`, `passphrase`

**Timeouts**: `create` default 5 minutes.

### huaweicloud_sms_task with target_server_id (Pre-create ECS approach)

Alternative approach — use with caution. Requires matching firmware and explicit disk config.

```hcl
resource "huaweicloud_compute_instance" "target" {
  name               = "demo-web-server"
  image_id           = data.huaweicloud_images_image.ubuntu.id
  flavor_id          = "c6.large.4"
  availability_zone  = "la-north-2a"
  security_group_ids = [data.huaweicloud_networking_secgroup.demo.id]
  system_disk_type   = "SAS"
  system_disk_size   = 10

  network {
    uuid = data.huaweicloud_vpc_subnet.demo.id
  }

  eip_type = "5_bgp"
  bandwidth {
    size        = 10
    share_type  = "PER"
    charge_mode = "traffic"
  }
}

resource "huaweicloud_sms_task" "migration" {
  type              = "MIGRATE_FILE"
  os_type           = "LINUX"
  source_server_id  = data.huaweicloud_sms_source_servers.demo.servers[0].id
  target_server_id  = huaweicloud_compute_instance.target.id
  migration_ip      = huaweicloud_compute_instance.target.public_ip  # Required with target_server_id
  action            = "start"
  start_target_server = true
  use_public_ip     = true

  target_server_disks {    # Required with target_server_id
    name        = "/dev/sda"
    size        = 10240     # MB
    device_type = "BOOT"
    disk_id     = "0"

    physical_volumes {
      name        = "/dev/sda1"
      size        = 8080     # MB
      device_type = "OS"
      file_system = "ext4"
      mount_point = "/"
      index       = 0
    }
  }
}
```

**Why this is risky**: The pre-created ECS image may use BIOS firmware while the source uses UEFI. This causes `SMS.0515` error. The template approach avoids this by letting SMS select the correct image.

## Complete Template: main.tf

```hcl
# Data sources
data "huaweicloud_availability_zones" "demo" {}
data "huaweicloud_vpc" "demo" { name = var.vpc_name }
data "huaweicloud_vpc_subnet" "demo" { name = var.subnet_name }
data "huaweicloud_networking_secgroup" "demo" { name = var.secgroup_name }
data "huaweicloud_sms_source_servers" "demo" { id = var.source_server_id }

# SMS server template (SMS auto-creates target ECS)
resource "huaweicloud_sms_server_template" "demo" {
  name               = "${var.target_server_name}-template"
  availability_zone  = data.huaweicloud_availability_zones.demo.names[0]
  vpc_id             = data.huaweicloud_vpc.demo.id
  subnet_ids         = [data.huaweicloud_vpc_subnet.demo.id]
  security_group_ids = [data.huaweicloud_networking_secgroup.demo.id]
  flavor             = var.flavor_id
  volume_type        = var.volume_type
  target_server_name = var.target_server_name
  bandwidth_size     = var.eip_bandwidth_size
}

# SMS migration task
resource "huaweicloud_sms_task" "migration" {
  type               = var.migration_type
  os_type            = var.os_type
  source_server_id   = data.huaweicloud_sms_source_servers.demo.servers[0].id
  vm_template_id     = huaweicloud_sms_server_template.demo.id
  action             = "start"
  start_target_server = true
  use_public_ip      = true

  lifecycle {
    ignore_changes = [
      syncing, action, auto_start, start_network_check,
      over_speed_threshold, is_need_consistency_check,
    ]
  }
}
```

## Complete Template: variables.tf

```hcl
variable "target_region" {
  type    = string
  default = "la-north-2"
}

variable "source_server_id" {
  type        = string
  description = "SMS source server ID (from agent registration)"
}

variable "vpc_name" {
  type    = string
  default = "demo-vpc"
}

variable "subnet_name" {
  type    = string
  default = "demo-public-subnet-1"
}

variable "secgroup_name" {
  type    = string
  default = "demo-ec2-sg"
}

variable "flavor_id" {
  type        = string
  description = "Target ECS flavor (match source vCPU/RAM)"
}

variable "target_server_name" {
  type    = string
  default = "migrated-server"
}

variable "volume_type" {
  type    = string
  default = "SAS"
}

variable "migration_type" {
  type    = string
  default = "MIGRATE_FILE"  # or MIGRATE_BLOCK
}

variable "os_type" {
  type    = string
  default = "LINUX"  # or WINDOWS
}

variable "eip_bandwidth_size" {
  type    = number
  default = 10
}
```

## Complete Template: outputs.tf

```hcl
output "template_id" {
  value = huaweicloud_sms_server_template.demo.id
}

output "task_id" {
  value = huaweicloud_sms_task.migration.id
}

output "task_state" {
  value = huaweicloud_sms_task.migration.state
}

output "target_server_name" {
  value = huaweicloud_sms_task.migration.target_server_name
}
```

## target_server_disks Block Reference

When using `target_server_id` (pre-create ECS approach), `target_server_disks` is required:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Disk device name, e.g. "/dev/sda" |
| `size` | int | Yes | Volume size in MB |
| `device_type` | string | Yes | `BOOT` or `NORMAL` |
| `disk_id` | string | Yes | Disk index, e.g. "0", "1" |
| `used_size` | int | No | Used space in MB |

### physical_volumes sub-block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Volume name, e.g. "/dev/sda1" |
| `size` | int | Yes | Volume size in MB |
| `device_type` | string | Yes | `OS` or `NORMAL` |
| `file_system` | string | Yes | File system type, e.g. "ext4", "vfat" |
| `mount_point` | string | Yes | Mount point, e.g. "/", "/boot/efi" |
| `index` | int | Yes | Serial number of the volume |
| `used_size` | int | No | Used space in MB |
| `uuid` | string | No | GUID of the volume |
