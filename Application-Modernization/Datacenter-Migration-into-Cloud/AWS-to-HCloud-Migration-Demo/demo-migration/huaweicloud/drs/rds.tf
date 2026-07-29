locals {
  vpc_id    = "35af0c49-55aa-4643-bb4c-7ac61f5f0419"
  subnet_id = "5536568f-4656-4489-b42e-7c8ae816e752"
  sg_id     = "211aae9d-c2f7-4b76-badb-1386bf906d71"
  project_id = "50bc790b7aa3493f97b3968de4dfd490"
  param_template_id = "86051aa9a79346e1bbef11332700df3epr01"
}

resource "huaweicloud_rds_instance" "demo_db" {
  name                   = "demo-db"
  flavor                 = "rds.mysql.n1.large.2"
  vpc_id                 = local.vpc_id
  subnet_id              = local.subnet_id
  security_group_id      = local.sg_id
  availability_zone      = ["la-north-2a"]
  lower_case_table_names = "0"
  param_group_id         = local.param_template_id

  db {
    type     = "MySQL"
    version  = "8.0"
    password = var.target_db_password
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
