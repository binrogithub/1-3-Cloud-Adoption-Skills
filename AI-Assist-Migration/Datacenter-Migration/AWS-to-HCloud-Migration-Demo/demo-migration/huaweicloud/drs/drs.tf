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
    endpoint_type = "offline"
    endpoint_role = "so"

    endpoint {
      endpoint_name = "mysql"
      ip            = var.source_db_endpoint
      db_port       = var.source_db_port
      db_user       = var.source_db_user
      db_password   = var.source_db_password
    }

    ssl {
      ssl_link = false
    }
  }

  target_endpoint {
    db_type       = "mysql"
    endpoint_type = "cloud"
    endpoint_role = "ta"

    endpoint {
      endpoint_name = "cloud_mysql"
      instance_id   = huaweicloud_rds_instance.demo_db.id
      db_port       = "3306"
      db_user       = "root"
      db_password   = var.target_db_password
    }

    cloud {
      region     = "la-north-2"
      project_id = local.project_id
      az_code    = "la-north-2a"
    }

    vpc {
      vpc_id            = local.vpc_id
      subnet_id         = local.subnet_id
      security_group_id = local.sg_id
    }

    config {
      is_target_readonly = true
    }
  }

  node_info {
    spec {
      node_type = "high"
    }

    vpc {
      vpc_id            = local.vpc_id
      subnet_id         = local.subnet_id
      security_group_id = local.sg_id
    }
  }
}
