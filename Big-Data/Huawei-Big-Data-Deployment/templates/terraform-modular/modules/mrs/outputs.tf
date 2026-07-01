output "cluster_id" { value = huaweicloud_mrs_cluster.this.id }
output "manager_url" { value = try(huaweicloud_mrs_cluster.this.manager_url, null) }
