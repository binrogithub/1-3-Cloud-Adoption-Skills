# Terraform DRS Job Reference

Complete reference for the `huaweicloud_drs_job_v5` Terraform resource used to create DRS migration jobs.

## Resource Schema

```hcl
resource "huaweicloud_drs_job_v5" "<name>" {
  region = "<region>"  # Optional, defaults to provider region

  base_info {
    name                  = "<job-name>"       # 4-50 chars, letter start
    job_type              = "<type>"           # migration | sync | cloudDataGuard
    engine_type           = "<engine>"         # mysql-to-mysql | redis-to-gaussredis | etc.
    job_direction         = "<direction>"      # up | down | non-dbs
    task_type             = "<task>"           # FULL_TRANS | FULL_INCR_TRANS | INCR_TRANS
    net_type              = "<net>"            # eip | vpn | vpc
    charging_mode         = "<billing>"        # on_demand | period
    enterprise_project_id = "0"               # Default enterprise project
    expired_days          = "14"               # 14-100, auto-cleanup days

    tags {                                    # Optional tags
      key   = "<key>"
      value = "<value>"
    }
  }

  source_endpoint {
    db_type       = "<db>"            # mysql | gaussdbv5 | redis | rediscluster
    endpoint_type = "<type>"          # offline | ecs | cloud
    endpoint_role = "so"              # Always "so" for source

    endpoint {
      endpoint_name = "<name>"        # See Endpoint Name Map below
      ip            = "<host>"         # IP or hostname
      db_port       = "<port>"        # Database port
      db_user       = "<user>"        # Admin username
      db_password   = "<password>"    # Admin password (sensitive)
      db_name       = "<database>"    # Database name to migrate
      instance_id   = "<id>"          # For Huawei Cloud RDS only
    }

    cloud {                            # Only for endpoint_type = "cloud"
      region     = "<region>"
      project_id = "<pid>"
      az_code    = "<az>"
    }

    vpc {                              # Only for endpoint_type = "ecs"
      vpc_id            = "<vpc-id>"
      subnet_id         = "<subnet-id>"
      security_group_id = "<sg-id>"
    }

    ssl {
      ssl_link = false                 # true if SSL enabled on source
    }
  }

  target_endpoint {
    db_type       = "<db>"
    endpoint_type = "<type>"           # Usually "cloud" for Huawei RDS
    endpoint_role = "ta"               # Always "ta" for target

    endpoint {
      endpoint_name = "<name>"
      ip            = "<host>"
      db_port       = "<port>"
      db_user       = "<user>"
      db_password   = "<password>"
      instance_id   = "<id>"           # Huawei RDS instance ID
    }

    cloud {
      region     = "<region>"
      project_id = "<pid>"
      az_code    = "<az>"
    }

    vpc {
      vpc_id            = "<vpc-id>"
      subnet_id         = "<subnet-id>"
      security_group_id = "<sg-id>"
    }

    config {
      is_target_readonly = true        # Prevent accidental writes during migration
    }
  }

  node_info {
    spec {
      node_type = "<type>"             # micro | small | medium | high
    }

    vpc {
      vpc_id            = "<vpc-id>"   # VPC for DRS node
      subnet_id         = "<subnet-id>"
      security_group_id = "<sg-id>"    # SG for DRS node
    }
  }

  period_order {                        # Only for charging_mode = "period"
    period_type   = 2                   # 2=monthly, 3=yearly
    period_num    = 1
    is_auto_renew = 0
  }
}
```

## Endpoint Name Map

| Source/Target | `endpoint_type` | `endpoint_name` | Description |
|---------------|----------------|-----------------|-------------|
| AWS RDS / other cloud MySQL | `offline` | `mysql` | Self-built/3rd-party MySQL |
| Huawei ECS MySQL | `ecs` | `ecs_mysql` | ECS self-built MySQL |
| Huawei Cloud RDS MySQL | `cloud` | `cloud_mysql` | Huawei RDS for MySQL |
| Self-built Oracle | `offline` | `oracle` | Self-built Oracle |
| ECS Oracle | `ecs` | `ecs_oracle` | ECS self-built Oracle |
| Huawei GaussDB | `cloud` | `cloud_gaussdbv5` | Huawei GaussDB distributed |
| Self-built Redis | `offline` | `redis` | Self-built Redis |
| ECS Redis | `ecs` | `ecs_redis` | ECS self-built Redis |

## Complete Example: AWS RDS → Huawei Cloud RDS

```hcl
variable "db_password" {
  description = "Huawei Cloud RDS root password"
  type        = string
  sensitive   = true
}

variable "source_db_password" {
  description = "AWS RDS admin password"
  type        = string
  sensitive   = true
}

resource "huaweicloud_drs_job_v5" "mysql_migration" {
  base_info {
    name          = "drs-mysql-migration"
    job_type      = "migration"
    engine_type   = "mysql-to-mysql"
    job_direction = "up"
    task_type     = "FULL_INCR_TRANS"
    net_type      = "eip"
    charging_mode = "on_demand"
    expired_days  = "14"

    tags {
      key   = "migration"
      value = "aws-to-huaweicloud"
    }
  }

  source_endpoint {
    db_type       = "mysql"
    endpoint_type = "offline"      # AWS = third-party cloud
    endpoint_role = "so"

    endpoint {
      endpoint_name = "mysql"      # Self-built/3rd-party MySQL
      ip            = "demo-db.ct8ua64omsz2.us-east-2.rds.amazonaws.com"
      db_port       = "3306"
      db_user       = "admin"
      db_password   = var.source_db_password
      db_name       = "wordpress"
    }

    ssl {
      ssl_link = false
    }
  }

  target_endpoint {
    db_type       = "mysql"
    endpoint_type = "cloud"         # Huawei Cloud RDS
    endpoint_role = "ta"

    endpoint {
      endpoint_name = "cloud_mysql"
      instance_id   = huaweicloud_rds_instance.demo_db.id
      db_port       = "3306"
      db_user       = "root"
      db_password   = var.db_password
    }

    cloud {
      region     = "la-north-2"
      project_id = "50bc790b7aa3493f97b3968de4dfd490"
      az_code    = "la-north-2b"
    }

    vpc {
      vpc_id            = huaweicloud_vpc.demo.id
      subnet_id         = huaweicloud_vpc_subnet.private_1.id
      security_group_id = huaweicloud_networking_secgroup.rds.id
    }

    config {
      is_target_readonly = true
    }
  }

  node_info {
    spec {
      node_type = "high"           # Check ListAvailableNodeTypes for your region
    }

    vpc {
      vpc_id            = huaweicloud_vpc.demo.id
      subnet_id         = huaweicloud_vpc_subnet.private_1.id
      security_group_id = huaweicloud_networking_secgroup.ecs.id  # Reuse ECS SG
    }
  }
}
```

## RDS Instance with DRS-Compatible Parameters

```hcl
resource "huaweicloud_rds_instance" "demo_db" {
  name                   = "demo-db"
  flavor                 = "rds.mysql.n1.large.2"
  vpc_id                 = huaweicloud_vpc.demo.id
  subnet_id              = huaweicloud_vpc_subnet.private_1.id
  security_group_id      = huaweicloud_networking_secgroup.rds.id
  availability_zone      = ["la-north-2b"]
  lower_case_table_names = "0"     # Match AWS RDS (case-sensitive) — ForceNew!
  param_group_id         = "<custom-param-template-id>"

  db {
    type     = "MySQL"
    version  = "8.0"
    password = var.db_password
  }

  volume {
    type = "CLOUDSSD"
    size = 20
  }

  backup_strategy {
    start_time = "03:00-04:00"
    keep_days  = 7
  }

  tags = {
    migrated_from = "aws-us-east-2/demo-db"
  }
}
```

## SG Strategy: Reuse ECS SG for DRS Node

The DRS node needs to connect to the target RDS on port 3306. Instead of creating a dedicated SG for the DRS node, **reuse the ECS SG**:

```hcl
node_info {
  spec {
    node_type = "high"
  }
  vpc {
    vpc_id            = huaweicloud_vpc.demo.id
    subnet_id         = huaweicloud_vpc_subnet.private_1.id
    security_group_id = huaweicloud_networking_secgroup.ecs.id  # Reuse ECS SG
  }
}
```

This works because the RDS SG already has a rule allowing MySQL from the ECS SG:

```hcl
resource "huaweicloud_networking_secgroup_rule" "rds_mysql" {
  security_group_id = huaweicloud_networking_secgroup.rds.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 3306
  port_range_max    = 3306
  remote_group_id   = huaweicloud_networking_secgroup.ecs.id  # Allows DRS node
}
```

No additional SG rules needed.

## Important Notes

### NonUpdatable fields

The following fields in `huaweicloud_drs_job_v5` cannot be updated after creation:
- `base_info.*` (all fields)
- `source_endpoint.*` (all fields)
- `target_endpoint.*` (all fields)
- `node_info.*` (all fields)

If any referenced resource changes (e.g., RDS instance is recreated), the DRS job must be deleted and recreated.

### ForceNew on RDS

`lower_case_table_names` is `ForceNew` on `huaweicloud_rds_instance`. Changing it will destroy and recreate the RDS, which in turn requires recreating the DRS job.

### Project ID

The `project_id` in `cloud` blocks and hcloud CLI commands is the **Huawei Cloud project ID**, not the account ID. Get it from:

```bash
hcloud IAM KeystoneListProjects --cli-output=json
# Find the project with name matching your region
```

### DRS node placement

The DRS node is placed in the VPC/subnet specified in `node_info.vpc`. For `net_type = "eip"`, the DRS node gets its own EIP to reach the source database. For `net_type = "vpc"`, the DRS node connects via VPC internal network.
