output "cluster_id" { value = huaweicloud_dws_cluster.this.id }
output "endpoint" { value = try(huaweicloud_dws_cluster.this.endpoint, null) }
