resource "huaweicloud_css_cluster" "log_assistant" {
  name           = var.css_cluster_name
  engine_version = var.css_engine_version
  security_mode  = true
  password       = var.css_admin_password
  https_enabled  = true

  ess_node_config {
    flavor          = var.css_flavor
    instance_number = var.css_node_count
    volume {
      volume_type = var.css_volume_type
      size        = var.css_volume_size
    }
  }

  availability_zone  = data.huaweicloud_availability_zones.available.names[0]
  vpc_id             = huaweicloud_vpc.css.id
  subnet_id          = huaweicloud_vpc_subnet.css.id
  security_group_id  = huaweicloud_networking_secgroup.css.id

  public_access {
    bandwidth        = var.public_bandwidth
    whitelist_enabled = false
  }

  tags = {
    project     = "css-log-assistant"
    environment = "demo"
    managed-by  = "terraform"
  }
}
