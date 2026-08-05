---
name: hcloud-services-quickstart
description: Quick reference for 30+ Huawei Cloud services with CRUD examples via hcloud CLI and MCP tools. Use when working with hcloud services, looking up service availability, or needing quick command examples.
---

# Huawei Cloud Services Quick Reference

Quick CRUD examples for the most used Huawei Cloud services via `hcloud` CLI and MCP tools. Region is `la-north-2` in all examples — replace with your region.

## Service Overview

| Service | CLI Name | MCP Tools | Description |
|---------|----------|-----------|-------------|
| ECS | ECS | `hcloud_list_servers`, `hcloud_show_server` | Elastic Cloud Server (VM) |
| VPC | VPC | `hcloud_list_vpcs`, `hcloud_list_subnets` | Virtual Private Cloud |
| CCE | CCE | `hcloud_list_cce_clusters`, `hcloud_list_cce_nodes` | Cloud Container Engine (K8s) |
| RDS | RDS | `hcloud_list_rds_instances` | Relational Database Service |
| DCS | DCS | `hcloud_list_dcs_instances` | Distributed Cache (Redis) |
| DDS | DDS | `hcloud_list_dds_instances` | Document Database (MongoDB) |
| ELB | ELB | `hcloud_list_load_balancers` | Elastic Load Balance |
| EVS | EVS | `hcloud_list_volumes` | Elastic Volume Service |
| OBS | obs | `hcloud_obs_ls`, `hcloud_obs_cat` | Object Storage |
| IAM | IAM | `hcloud_list_users`, `hcloud_list_groups` | Identity & Access |
| KMS | KMS | `hcloud_list_kms_keys` | Key Management |
| DNS | DNS | `hcloud_list_dns_zones` | Domain Name Service |
| SMN | SMN | `hcloud_list_smn_topics` | Simple Message Notification |
| CES | CES | `hcloud_list_metrics`, `hcloud_list_alarms` | Cloud Eye (Monitoring) |
| NAT | NAT | `hcloud_list_nat_gateways` | NAT Gateway |
| AS | AS | `hcloud_list_scaling_groups` | Auto Scaling |
| EIP | EIP | `hcloud_list_public_ips` | Elastic Public IP |
| IMS | IMS | `hcloud_list_images` | Image Management |
| SWR | SWR | — | Software Repository (Container) |
| FunctionGraph | FunctionGraph | — | Serverless Functions |
| APIG | APIG | — | API Gateway |
| WAF | WAF | — | Web Application Firewall |
| CDN | CDN | — | Content Delivery Network |
| DIS | DIS | — | Data Ingestion Service |
| DMS | DMS | — | Distributed Message Service |
| DWS | DWS | — | Data Warehouse |
| GaussDB | GaussDB | — | GaussDB (openGauss) |
| AOS | AOS | — | Application Orchestration (IaC) |
| RFS | RFS | — | Resource Formation (IaC) |
| AOM | AOM | — | Application Operations Management |
| LTS | LTS | — | Log Tank Service |
| DEW | DEW | — | Data Encryption Workshop |

---

## ECS (Elastic Cloud Server)

```bash
# List servers
hcloud ECS ListServers --cli-region=la-north-2
# MCP: hcloud_list_servers(region="la-north-2")

# Show server details
hcloud ECS ShowServer --cli-region=la-north-2 --server_id=<id>
# MCP: hcloud_show_server(region="la-north-2", server_id="<id>")

# List flavors
hcloud ECS ListFlavors --cli-region=la-north-2
# MCP: hcloud_list_flavors(region="la-north-2")

# List images (public Linux)
hcloud IMS ListImages --cli-region=la-north-2 --imagetype=gold --os_type=Linux
# MCP: hcloud_list_images(region="la-north-2", imagetype="gold", os_type="Linux")

# Create server (requires confirm)
hcloud ECS CreateServers --cli-region=la-north-2 \
  --name=my-server \
  --image_id=<image-id> \
  --flavor_id=ac7.2xlarge.2 \
  --vpcid=<vpc-id> \
  --subnet_id=<subnet-id> \
  --security_group_id=<sg-id> \
  --adminPass=MyPassword123!

# List keypairs
hcloud ECS ListKeypairs --cli-region=la-north-2
# MCP: hcloud_list_keypairs(region="la-north-2")

# List server interfaces (NICs)
hcloud ECS ListServerInterfaces --cli-region=la-north-2 --server_id=<id>
# MCP: hcloud_list_server_interfaces(region="la-north-2", server_id="<id>")

# List block devices
hcloud ECS ListServerBlockDevices --cli-region=la-north-2 --server_id=<id>
# MCP: hcloud_list_server_block_devices(region="la-north-2", server_id="<id>")
```

## VPC (Virtual Private Cloud)

```bash
# List VPCs
hcloud VPC ListVpcs --cli-region=la-north-2
# MCP: hcloud_list_vpcs(region="la-north-2")

# Show VPC details
hcloud VPC ShowVpc --cli-region=la-north-2 --vpc_id=<id>
# MCP: hcloud_show_vpc(region="la-north-2", vpc_id="<id>")

# List subnets
hcloud VPC ListSubnets --cli-region=la-north-2 --vpc_id=<vpc-id>
# MCP: hcloud_list_subnets(region="la-north-2", vpc_id="<vpc-id>")

# List security groups
hcloud VPC ListSecurityGroups --cli-region=la-north-2
# MCP: hcloud_list_security_groups(region="la-north-2")

# List security group rules
hcloud VPC ListSecurityGroupRules --cli-region=la-north-2 --security_group_id=<sg-id>
# MCP: hcloud_list_security_group_rules(region="la-north-2", security_group_id="<sg-id>")

# List route tables
hcloud VPC ListRouteTables --cli-region=la-north-2 --vpc_id=<vpc-id>
# MCP: hcloud_list_route_tables(region="la-north-2", vpc_id="<vpc-id>")
```

## CCE (Cloud Container Engine / Kubernetes)

```bash
# List clusters
hcloud CCE ListClusters --cli-region=la-north-2
# MCP: hcloud_list_cce_clusters(region="la-north-2")

# Show cluster details
hcloud CCE ShowCluster --cli-region=la-north-2 --cluster_id=<id>
# MCP: hcloud_show_cce_cluster(region="la-north-2", cluster_id="<id>")

# List nodes in a cluster
hcloud CCE ListClusterNodes --cli-region=la-north-2 --cluster_id=<id>
# MCP: hcloud_list_cce_nodes(region="la-north-2", cluster_id="<id>")

# List node pools
hcloud CCE ListNodePools --cli-region=la-north-2 --cluster_id=<id>
# MCP: hcloud_list_node_pools(region="la-north-2", cluster_id="<id>")

# List add-ons
hcloud CCE ListAddons --cli-region=la-north-2 --cluster_id=<id>
# MCP: hcloud_list_addon_instances(region="la-north-2", cluster_id="<id>")
```

## RDS (Relational Database Service)

```bash
# List instances
hcloud RDS ListInstances --cli-region=la-north-2
# MCP: hcloud_list_rds_instances(region="la-north-2")

# List flavors
hcloud RDS ListFlavors --cli-region=la-north-2 --database_name=MySQL
# MCP: hcloud_list_rds_flavors(region="la-north-2", database_name="MySQL")

# List datastore versions
hcloud RDS ListDatastores --cli-region=la-north-2 --database_name=MySQL
# MCP: hcloud_list_rds_datastores(region="la-north-2", database_name="MySQL")

# List storage types
hcloud RDS ListStorageTypes --cli-region=la-north-2 --database_name=MySQL --version_name=8.0
# MCP: hcloud_list_rds_storage_types(region="la-north-2", database_name="MySQL", version_name="8.0")

# List backups
hcloud RDS ListBackups --cli-region=la-north-2 --instance_id=<id>
# MCP: hcloud_list_rds_backups(region="la-north-2", instance_id="<id>")
```

## DCS (Distributed Cache / Redis)

```bash
# List instances
hcloud DCS ListInstances --cli-region=la-north-2
# MCP: hcloud_list_dcs_instances(region="la-north-2")

# List flavors
hcloud DCS ListFlavors --cli-region=la-north-2
# MCP: hcloud_list_dcs_flavors(region="la-north-2")

# List available AZs
hcloud DCS ListAvailableZones --cli-region=la-north-2
# MCP: hcloud_list_dcs_available_zones(region="la-north-2")

# Show instance details
hcloud DCS ShowInstance --cli-region=la-north-2 --instance_id=<id>
# MCP: hcloud_show_dcs_instance(region="la-north-2", instance_id="<id>")
```

### DCS Instance Types

| Spec Code | Engine | Mode | Capacities (GB) |
|-----------|--------|------|------------------|
| `dcs.single_node` | Redis 3.0 | Single | 2, 4, 8, 16, 32, 64 |
| `dcs.master_standby` | Redis 3.0 | HA (master/standby) | 2, 4, 8, 16, 32, 64 |
| `dcs.cluster` | Redis 3.0 | Cluster (proxy) | 64, 128, 256, 512, 1024 |
| `redis.ha.xu1.large.*` | Redis 4.0/5.0/6.0 | HA RW split | 1, 2, ... |
| `dcs.memcached.single_node` | Memcached | Single | 2, 4, 8, 16, 32, 64 |

## DDS (Document Database / MongoDB)

```bash
# List instances
hcloud DDS ListInstances --cli-region=la-north-2
# MCP: hcloud_list_dds_instances(region="la-north-2")

# List flavors
hcloud DDS ListFlavors --cli-region=la-north-2 --engine=DDS-Community
# MCP: hcloud_list_dds_flavors(region="la-north-2", engine="DDS-Community")

# List storage types
hcloud DDS ListStorageTypes --cli-region=la-north-2 --engine=DDS-Community
# MCP: hcloud_list_dds_storage_types(region="la-north-2", engine="DDS-Community")
```

## ELB (Elastic Load Balance)

```bash
# List load balancers
hcloud ELB ListLoadBalancers --cli-region=la-north-2
# MCP: hcloud_list_load_balancers(region="la-north-2")

# Show load balancer details
hcloud ELB ShowLoadBalancer --cli-region=la-north-2 --loadbalancer_id=<id>
# MCP: hcloud_show_load_balancer(region="la-north-2", loadbalancer_id="<id>")

# Show topology (listeners, pools, members)
hcloud ELB ShowLoadBalancerTopology --cli-region=la-north-2 --loadbalancer_id=<id>
# MCP: hcloud_show_load_balancer_topology(region="la-north-2", loadbalancer_id="<id>")

# List listeners
hcloud ELB ListListeners --cli-region=la-nE-north-2 --loadbalancer_id=<id>
# MCP: hcloud_list_listeners(region="la-north-2", loadbalancer_id="<id>")

# List pools (backend server groups)
hcloud ELB ListPools --cli-region=la-north-2
# MCP: hcloud_list_pools(region="la-north-2")

# List health monitors
hcloud ELB ListHealthMonitors --cli-region=la-north-2
# MCP: hcloud_list_health_monitors(region="la-north-2")

# List L7 policies
hcloud ELB ListL7Policies --cli-region=la-north-2 --listener_id=<id>
# MCP: hcloud_list_l7_policies(region="la-north-2", listener_id="<id>")

# List flavors
hcloud ELB ListFlavors --cli-region=la-north-2
# MCP: hcloud_list_elb_flavors(region="la-north-2")
```

### ELB Flavor Types

| Type | Examples | Use Case |
|------|----------|----------|
| L4 | `L4_flavor.elb.s1.small` | TCP/UDP load balancing |
| L7 | `L7_flavor.elb.s1.small` | HTTP/HTTPS load balancing |
| L4_basic | `L4_flavor.elb.basic.*` | Basic L4 (shared) |
| L7_basic | `L7_flavor.elb.basic.*` | Basic L7 (shared) |
| L4_elastic_max | `L4_flavor.elb.pro.max` | Elastic L4 (auto-scale) |
| L7_elastic | `L7_flavor.elb.pro.*` | Elastic L7 (auto-scale) |

## EVS (Elastic Volume Service)

```bash
# List volumes
hcloud EVS ListVolumes --cli-region=la-north-2
# MCP: hcloud_list_volumes(region="la-north-2")

# Show volume details
hcloud EVS ShowVolume --cli-region=la-north-2 --volume_id=<id>
# MCP: hcloud_show_volume(region="la-north-2", volume_id="<id>")

# List volume types
hcloud EVS ListVolumeTypes --cli-region=la-north-2
# MCP: hcloud_list_volume_types(region="la-north-2")

# List snapshots
hcloud EVS ListSnapshots --cli-region=la-north-2
# MCP: hcloud_list_snapshots(region="la-north-2")
```

## OBS (Object Storage)

```bash
# List buckets
hcloud obs ls --cli-region=la-north-2
# MCP: hcloud_obs_ls(region="la-north-2")

# List objects in bucket
hcloud obs ls obs://my-bucket --cli-region=la-north-2
# MCP: hcloud_obs_ls(region="la-north-2", bucket="my-bucket")

# List with prefix filter
hcloud obs ls obs://my-bucket/logs/ --cli-region=la-north-2
# MCP: hcloud_obs_ls(region="la-north-2", bucket="my-bucket", prefix="logs/")

# Show bucket properties
hcloud obs stat obs://my-bucket --cli-region=la-north-2
# MCP: hcloud_obs_stat(region="la-north-2", bucket="my-bucket")

# View text object content
hcloud obs cat obs://my-bucket/config.txt --cli-region=la-north-2
# MCP: hcloud_obs_cat(region="la-north-2", bucket="my-bucket", key="config.txt")

# Upload file (confirm=true in MCP)
hcloud obs cp /local/file.txt obs://my-bucket/file.txt --cli-region=la-north-2

# Download file
hcloud obs cp obs://my-bucket/file.txt /local/file.txt --cli-region=la-north-2

# Sync directory
hcloud obs sync /local/dir/ obs://my-bucket/dir/ --cli-region=la-north-2

# Delete object (confirm=true required)
hcloud obs rm obs://my-bucket/file.txt --cli-region=la-north-2
```

## IAM (Identity and Access Management)

```bash
# List users
hcloud IAM ListUsers
# MCP: hcloud_list_users()

# Show user details
hcloud IAM ShowUser --user_id=<id>
# MCP: hcloud_show_user(user_id="<id>")

# List groups
hcloud IAM ListGroups
# MCP: hcloud_list_groups()

# List policies
hcloud IAM ListPolicies
# MCP: hcloud_list_policies()

# List domains
hcloud IAM ListAuthDomains
# MCP: hcloud_list_domains()

# List projects
hcloud IAM ListProjects
# MCP: hcloud_list_projects()

# List agencies (trust relationships)
hcloud IAM ListAgencies
# MCP: hcloud_list_agencies()

# List user policies
hcloud IAM ListUserPolicies --user_id=<id>
# MCP: hcloud_list_user_policies(user_id="<id>")
```

## KMS (Key Management Service)

```bash
# List keys
hcloud KMS ListKeys --cli-region=la-north-2
# MCP: hcloud_list_kms_keys(region="la-north-2")

# Show key details
hcloud KMS ShowKey --cli-region=la-north-2 --key_id=<id>
# MCP: hcloud_show_kms_key_detail(region="la-north-2", key_id="<id>")
```

## DNS (Domain Name Service)

```bash
# List zones (public)
hcloud DNS ListZones --cli-region=la-north-2 --type=public
# MCP: hcloud_list_dns_zones(region="la-north-2", type="public")

# List zones (private)
hcloud DNS ListZones --cli-region=la-north-2 --type=private
# MCP: hcloud_list_dns_zones(region="la-north-2", type="private")

# Show zone details
hcloud DNS ShowZone --cli-region=la-north-2 --zone_id=<id> --zone_type=public
# MCP: hcloud_show_dns_zone(region="la-north-2", zone_id="<id>", zone_type="public")

# List record sets
hcloud DNS ListRecordSets --cli-region=la-north-2 --zone_id=<id>
# MCP: hcloud_list_dns_recordsets(region="la-north-2", zone_id="<id>")
```

## SMN (Simple Message Notification)

```bash
# List topics
hcloud SMN ListTopics --cli-region=la-north-2
# MCP: hcloud_list_smn_topics(region="la-north-2")

# List subscriptions
hcloud SMN ListSubscriptions --cli-region=la-north-2 --topic_urn=<urn>
# MCP: hcloud_list_smn_subscriptions(region="la-north-2", topic_urn="<urn>")
```

## CES (Cloud Eye / Monitoring)

```bash
# List metrics
hcloud CES ListMetrics --cli-region=la-north-2 --namespace=SYS.ECS
# MCP: hcloud_list_metrics(region="la-north-2", namespace="SYS.ECS")

# List alarms
hcloud CES ListAlarms --cli-region=la-north-2
# MCP: hcloud_list_alarms(region="la-north-2")

# List alarm rules (v2)
hcloud CES ListAlarmRules --cli-region=la-north-2
# MCP: hcloud_list_alarm_rules(region="la-north-2")

# Show metric data
hcloud CES ShowMetricData --cli-region=la-north-2 \
  --namespace=SYS.ECS \
  --metric_name=cpu_util \
  --dim_0=instance_id,<instance-id> \
  --filter=average \
  --period=300 \
  --from=<timestamp-ms> \
  --to=<timestamp-ms>
# MCP: hcloud_show_metric_data(region="la-north-2", namespace="SYS.ECS", ...)
```

## NAT Gateway

```bash
# List NAT gateways
hcloud NAT ListNatGateways --cli-region=la-north-2
# MCP: hcloud_list_nat_gateways(region="la-north-2")

# Show NAT gateway details
hcloud NAT ShowNatGateway --cli-region=la-north-2 --nat_gateway_id=<id>
# MCP: hcloud_show_nat_gateway(region="la-north-2", nat_gateway_id="<id>")

# List SNAT rules
hcloud NAT ListSnatRules --cli-region=la-north-2 --nat_gateway_id=<id>
# MCP: hcloud_list_nat_gateway_snat_rules(region="la-north-2", nat_gateway_id="<id>")

# List DNAT rules
hcloud NAT ListDnatRules --cli-region=la-north-2 --nat_gateway_id=<id>
# MCP: hcloud_list_nat_gateway_dnat_rules(region="la-north-2", nat_gateway_id="<id>")
```

## AS (Auto Scaling)

```bash
# List scaling groups
hcloud AS ListScalingGroups --cli-region=la-north-2
# MCP: hcloud_list_scaling_groups(region="la-north-2")

# List scaling configurations
hcloud AS ListScalingConfigurations --cli-region=la-north-2
# MCP: hcloud_list_scaling_configs(region="la-north-2")

# List scaling policies
hcloud AS ListScalingPolicies --cli-region=la-north-2 --scaling_group_id=<id>
# MCP: hcloud_list_scaling_policies(region="la-north-2", scaling_group_id="<id>")

# List instances in AS group
hcloud AS ListScalingInstances --cli-region=la-north-2 --scaling_group_id=<id>
# MCP: hcloud_list_scaling_instances(region="la-north-2", scaling_group_id="<id>")
```

## EIP (Elastic Public IP)

```bash
# List EIPs
hcloud EIP ListPublicIps --cli-region=la-north-2
# MCP: hcloud_list_public_ips(region="la-north-2")

# Show EIP details
hcloud EIP ShowPublicIp --cli-region=la-north-2 --publicip_id=<id>
# MCP: hcloud_show_public_ip(region="la-north-2", publicip_id="<id>")

# List bandwidths
hcloud EIP ListBandwidths --cli-region=la-north-2
# MCP: hcloud_list_bandwidths(region="la-north-2")

# List EIP quotas
hcloud EIP ListQuotas --cli-region=la-north-2
# MCP: hcloud_list_eip_quotas(region="la-north-2")
```

## IMS (Image Management)

```bash
# List images (public, Linux)
hcloud IMS ListImages --cli-region=la-north-2 --imagetype=gold --os_type=Linux
# MCP: hcloud_list_images(region="la-north-2", imagetype="gold", os_type="Linux")

# Show image details
hcloud IMS ShowImage --cli-region=la-north-2 --image_id=<id>
# MCP: hcloud_show_image(region="la-north-2", image_id="<id>")

# List OS versions
hcloud IMS ListOsVersions --cli-region=la-north-2
# MCP: hcloud_list_os_versions(region="la-north-2")

# Show image quotas
hcloud IMS ShowImageQuotas --cli-region=la-north-2
# MCP: hcloud_show_image_quotas(region="la-north-2")
```

## FunctionGraph (Serverless)

```bash
# List functions
hcloud FunctionGraph ListFunctions --cli-region=la-north-2

# Show function details
hcloud FunctionGraph ShowFunction --cli-region=la-north-2 --function_urn=<urn>

# Invoke function
hcloud FunctionGraph InvokeFunction --cli-region=la-north-2 --function_urn=<urn> --body='{"key":"value"}'
```

## SWR (Software Repository / Container Registry)

```bash
# List namespaces
hcloud SWR ListNamespaces --cli-region=la-north-2

# List repositories
hcloud SWR ListRepos --cli-region=la-north-2 --namespace=my-namespace

# List tags
hcloud SWR ListTags --cli-region=la-north-2 --namespace=my-namespace --repository=my-app
```

## APIG (API Gateway)

```bash
# List APIs
hcloud APIG ListApis --cli-region=la-north-2 --gateway_id=<id>

# List API groups
hcloud APIG ListApiGroups --cli-region=la-north-2 --gateway_id=<id>
```

## WAF (Web Application Firewall)

```bash
# List domains
hcloud WAF ListDomains --cli-region=la-north-2

# List policies
hcloud WAF ListPolicies --cli-region=la-north-2
```

## CDN (Content Delivery Network)

```bash
# List domains
hcloud CDN ListDomains --cli-region=la-north-2

# Show domain details
hcloud CDN ShowDomain --cli-region=la-north-2 --domain_name=example.com
```

## Common CES Namespaces

| Namespace | Service | Key Metrics |
|-----------|---------|-------------|
| `SYS.ECS` | ECS | `cpu_util`, `mem_usedPercent`, `disk_usedPercent` |
| `SYS.VPC` | VPC | `net_bitRateIn`, `net_bitRateOut` |
| `SYS.EVS` | EVS | `volume_read_bytes_sec`, `volume_write_bytes_sec` |
| `SYS.RDS` | RDS | `rds_cpu_util`, `rds_mem_util` |
| `SYS.ELB` | ELB | `l7_qps`, `l4_connection` |
| `SYS.CCE` | CCE | `cpu_usage`, `memory_usage` |
| `PAAS.NODE` | CustomBare Metal | `cpu_usage` |

## Tips

1. **Use MCP structured tools** for read operations — they return clean JSON.
2. **Use `hcloud_cli`** for write operations or services without structured MCP tools.
3. **Always pass `--cli-region`** in CLI commands or set it globally with `hcloud configure set`.
4. **Destructive operations** need `confirm=true` in MCP or run without `--dryrun` in CLI.
5. **OBS commands** use a different syntax (`obs ls`, `obs cp`) — see the `hcloud-cli-setup` skill.
6. **JSON output** is forced automatically — pipe through `jq` for filtering.
7. **Pagination**: structured MCP tools handle pagination internally. CLI uses `--limit` and `--offset`.
