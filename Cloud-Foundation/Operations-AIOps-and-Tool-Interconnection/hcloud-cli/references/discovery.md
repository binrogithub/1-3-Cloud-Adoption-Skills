# Discovery — Querying Existing Resources

The "snapshot" of your cloud environment. Always run discovery before creating or modifying resources.

## General pattern

```bash
hcloud <Service> List<Resources> --cli-region=<region> --cli-output=json --cli-query='<jmespath>'
```

## Networking

### VPCs

```bash
# List all VPCs
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr,status:status}'

# Find a VPC by name
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[?name==`prod-vpc`].{id:id,cidr:cidr}'

# VPC details
hcloud VPC ShowVpc --cli-region=X --vpc_id=VPC_ID --cli-output=json
```

### Subnets

```bash
# List subnets in a VPC
hcloud VPC ListSubnets --cli-region=X --vpc_id=VPC_ID --cli-output=json --cli-query='subnets[].{name:name,id:id,cidr:cidr,gateway_ip:gateway_ip}'

# List all subnets (no VPC filter)
hcloud VPC ListSubnets --cli-region=X --cli-output=json --cli-query='subnets[].{name:name,id:id,vpc_id:vpc_id,cidr:cidr}'
```

### Security Groups

```bash
# List security groups
hcloud VPC ListSecurityGroups --cli-region=X --cli-output=json --cli-query='security_groups[].{name:name,id:id}'

# Security group rules
hcloud VPC ShowSecurityGroup --cli-region=X --security_group_id=SG_ID --cli-output=json
```

### Elastic IPs

```bash
# List EIPs
hcloud EIP ListPublicips --cli-region=X --cli-output=json --cli-query='publicips[].{id:id,public_ip_address:public_ip_address,status:status}'

# Available EIPs only
hcloud EIP ListPublicips --cli-region=X --cli-output=json --cli-query='publicips[?status==`DOWN`].{id:id,public_ip_address:public_ip_address}'
```

### NAT Gateways

```bash
hcloud NAT ListNatGateways --cli-region=X --cli-output=json --cli-query='nat_gateways[].{id:id,name:name,status:status}'
```

### Load Balancers

```bash
hcloud ELB ListLoadbalancers --cli-region=X --cli-output=json --cli-query='loadbalancers[].{id:id,name:name,provisioning_status:provisioning_status}'
```

### DNS

```bash
# List zones
hcloud DNS ListPublicZones --cli-region=X --cli-output=json --cli-query='zones[].{id:id,name:name}'

# List records in a zone
hcloud DNS ListRecordSets --cli-region=X --zone_id=ZONE_ID --cli-output=json
```

### VPC Endpoint (VPCEP)

```bash
hcloud VPCEP ListVpcEndpointServices --cli-region=X --cli-output=json --cli-query='endpoint_services[].{id:id,service_name:service_name}'
```

## Compute

### ECS Instances

```bash
# List all ECS instances
hcloud ECS ListServersDetails --cli-region=X --cli-output=json --cli-query='servers[].{name:name,id:id,status:status,flavor:flavor.id}'

# Find by name
hcloud ECS ListServersDetails --cli-region=X --name=web-server --cli-output=json --cli-query='servers[].{id:id,status:status}'

# With private IP
hcloud ECS ListServersDetails --cli-region=X --ip=10.0.0 --cli-output=json

# Server details
hcloud ECS ShowServer --cli-region=X --server_id=SERVER_ID --cli-output=json
```

### Flavors

```bash
# List flavors (AZ-optional for filtering)
hcloud ECS ListFlavors --cli-region=X --cli-output=json --cli-query='flavors[].{id:id,name:name,vcpus:vcpus,ram:ram}'

# Flavors available in a specific AZ
hcloud ECS ListFlavors --cli-region=X --availability_zone=la-north-2a --cli-output=json --cli-query='flavors[].{id:id,vcpus:vcpus,ram:ram}'

# Resize flavors (for scaling an existing instance)
hcloud ECS ListResizeFlavors --cli-region=X --source_flavor_id=c6.large.2 --cli-output=json
```

### Images

```bash
# Public Linux images
hcloud IMS ListImages --cli-region=X --__imagetype=gold --__os_type=Linux --cli-output=json --cli-query='images[].{id:id,name:name}'

# Ubuntu images
hcloud IMS ListImages --cli-region=X --__imagetype=gold --__os_type=Linux --__platform=Ubuntu --cli-output=json --cli-query='images[].{id:id,name:name}'

# Private images
hcloud IMS ListImages --cli-region=X --__imagetype=private --cli-output=json --cli-query='images[].{id:id,name:name}'

# Image details
hcloud IMS ShowImage --cli-region=X --image_id=IMAGE_ID --cli-output=json
```

### Key Pairs

```bash
hcloud ECS ListKeypairs --cli-region=X --cli-output=json --cli-query='keypairs[].{name:keypair.name,fingerprint:keypair.fingerprint}'
```

### Availability Zones

```bash
hcloud ECS ListServerAzInfo --cli-region=X --cli-output=json --cli-query='azs[].{zone:zone,status:status}'
```

### Server Groups

```bash
hcloud ECS ListServerGroups --cli-region=X --cli-output=json
```

## Database

### RDS

```bash
# List RDS instances
hcloud RDS ListInstances --cli-region=X --cli-output=json --cli-query='instances[].{name:name,id:id,status:status,datastore:datastore.type}'

# Available datastores (engines)
hcloud RDS ListDatastores --cli-region=X --database_name=MySQL --cli-output=json --cli-query='datastores[].{name:name,version:version}'

# Available flavors
hcloud RDS ListFlavors --cli-region=X --database_name=MySQL --cli-output=json --cli-query='flavors[].{id:id,name:name,ram:ram,vcpus:vcpus}'

# Storage types
hcloud RDS ListStorageTypes --cli-region=X --database_name=MySQL --cli-output=json
```

### DDS (Document Database / MongoDB)

```bash
hcloud DDS ListInstances --cli-region=X --cli-output=json --cli-query='instances[].{name:name,id:id,status:status}'
hcloud DDS ListFlavors --cli-region=X --cli-output=json
```

### DCS (Redis)

```bash
hcloud DCS ListInstances --cli-region=X --cli-output=json --cli-query='instances[].{name:name,id:id,status:status}'
hcloud DCS ListFlavors --cli-region=X --cli-output=json
```

### GaussDB

```bash
hcloud GaussDB ListInstances --cli-region=X --cli-output=json
hcloud GaussDBforopenGauss ListInstances --cli-region=X --cli-output=json
hcloud GaussDBforNoSQL ListInstances --cli-region=X --cli-output=json
```

## Container

### CCE (Kubernetes)

```bash
# List clusters
hcloud CCE ListClusters --cli-region=X --cli-output=json --cli-query='clusters[].{name:name,id:id,status:status.phase}'

# Cluster details
hcloud CCE ShowCluster --cli-region=X --cluster_id=CLUSTER_ID --cli-output=json

# Node pools
hcloud CCE ListNodePools --cli-region=X --cluster_id=CLUSTER_ID --cli-output=json --cli-query='nodepools[].{name:name,id:id,status:status}'

# Nodes
hcloud CCE ListNodes --cli-region=X --cluster_id=CLUSTER_ID --cli-output=json
```

## Storage

### EVS (Volumes)

```bash
# List volumes
hcloud EVS ListVolumes --cli-region=X --cli-output=json --cli-query='volumes[].{name:name,id:id,status:status,size:size}'

# Volume types
hcloud EVS CinderListVolumeTypes --cli-region=X --cli-output=json
```

### CBR (Backup)

```bash
# Vaults (backup containers)
hcloud CBR ListVault --cli-region=X --cli-output=json --cli-query='vaults[].{name:name,id:id,status:status}'

# Backups
hcloud CBR ListBackups --cli-region=X --cli-output=json
```

### OBS (Object Storage)

OBS uses obsutil, not standard hcloud APIs. See [obs.md](obs.md) for full reference.

```bash
# List all buckets (brief)
hcloud obs ls -s

# List buckets with storage class
hcloud obs ls -s -sc

# List objects in a bucket
hcloud obs ls obs://my-bucket/ -s

# List objects in a prefix
hcloud obs ls obs://my-bucket/prefix/ -s

# List with human-readable sizes
hcloud obs ls obs://my-bucket/ -s -bf=human-readable

# Get total size of a prefix
hcloud obs ls obs://my-bucket/prefix/ -s -du

# Bucket properties
hcloud obs stat obs://my-bucket

# Object properties
hcloud obs stat obs://my-bucket/key

# List multipart uploads
hcloud obs ls obs://my-bucket/ -s -m

# List object versions
hcloud obs ls obs://my-bucket/ -s -v
```

## Security & IAM

### IAM

```bash
# Users
hcloud IAM KeystoneListUsers --cli-output=json --cli-query='users[].{name:name,id:id,enabled:enabled}'

# Projects
hcloud IAM KeystoneListProjects --cli-output=json --cli-query='projects[].{name:name,id:id}'

# Roles
hcloud IAM KeystoneListRoles --cli-output=json --cli-query='roles[].{name:name,id:id}'

# Groups
hcloud IAM KeystoneListGroups --cli-output=json --cli-query='groups[].{name:name,id:id}'

# Policies
hcloud IAM ListPolicies --cli-output=json --cli-query='policies[].{name:name,id:id}'

# Access keys
hcloud IAM ListAccessKeys --cli-output=json --cli-query='accesskeys[].{user:user,access:access,status:status}'
```

### KMS

```bash
hcloud KMS ListKey --cli-region=X --cli-output=json --cli-query='keys[].{id:key_id,state:key_state,alias:key_alias}'
```

### WAF

```bash
hcloud WAF ListInstance --cli-region=X --cli-output=json
```

## Governance

### Organizations

```bash
hcloud Organizations ShowOrganization --cli-output=json
hcloud Organizations ListOrganizationalUnits --cli-output=json --cli-query='organizational_units[].{name:name,id:id}'
hcloud Organizations ListAccounts --cli-output=json --cli-query='accounts[].{name:name,id:id,status:status}'
```

### Identity Center (IAM Identity Center)

```bash
hcloud IdentityCenter DescribeInstance --cli-output=json
hcloud IdentityCenter ListPermissionSets --cli-instance-id=INSTANCE_ID --cli-output=json
hcloud IdentityCenter ListAccountAssignments --cli-instance-id=INSTANCE_ID --cli-output=json
```

### Enterprise Projects

```bash
hcloud EPS ListEnterpriseProject --cli-output=json --cli-query='enterprise_projects[].{name:name,id:id,status:status}'
```

### Tags

```bash
hcloud TMS ListTagKeys --cli-region=X --cli-output=json
hcloud TMS ListTagValues --cli-region=X --key=env --cli-output=json
```

## Monitoring

### CES (Cloud Eye)

```bash
# Alarm rules
hcloud CES ListAlarmHistories --cli-region=X --cli-output=json

# Metrics
hcloud CES ListMetrics --cli-region=X --namespace=SYS.ECS --cli-output=json --cli-query='metrics[].{name:metric_name,dimensions:dimensions}'
```

### SMN (Notifications)

```bash
# Topics
hcloud SMN ListTopics --cli-region=X --cli-output=json --cli-query='topics[].{name:topic_name,id:topic_urn}'

# Subscriptions
hcloud SMN ListSubscriptions --cli-region=X --cli-output=json
```

## Pagination

For large result sets, use `--limit` and `--marker`/`--offset`:

```bash
# First page
hcloud ECS ListServersDetails --cli-region=X --limit=100 --offset=1 --cli-output=json

# Next page
hcloud ECS ListServersDetails --cli-region=X --limit=100 --offset=101 --cli-output=json
```

Some APIs use `--marker` (last resource ID) instead of `--offset`:

```bash
hcloud VPC ListSubnets --cli-region=X --limit=100 --marker=LAST_SUBNET_ID --cli-output=json
```

## Dependency chains

Some discoveries depend on values from previous queries. Always resolve dependencies in order:

| What you need | Depends on | How to resolve |
|---------------|-----------|----------------|
| Subnet ID | VPC ID | List VPCs → pick VPC → list subnets with `--vpc_id` |
| RDS flavor | Engine + version | List datastores → pick engine → list flavors with `--database_name` |
| RDS storage type | Engine + version | List datastores → pick version → list storage types |
| ECS resize flavors | Current flavor | List resize flavors with `--source_flavor_id` |
| CCE node pools | Cluster ID | List clusters → pick cluster → list node pools with `--cluster_id` |
| Security group rules | Security group ID | List security groups → pick SG → show SG rules |

## Cross-service lookups

### Find the VPC for an ECS instance

```bash
# Get the ECS's network info
hcloud ECS ListServerInterfaces --cli-region=X --server_id=SERVER_ID --cli-output=json --cli-query='interfaces[].{subnet_id:subnet_id,vpc_id:vpc_id}'

# Or from server details
hcloud ECS ShowServer --cli-region=X --server_id=SERVER_ID --cli-output=json --cli-query='server.metadata'
```

### Find volumes attached to an ECS

```bash
hcloud ECS ListServerVolumeAttachments --cli-region=X --server_id=SERVER_ID --cli-output=json --cli-query='volumeAttachments[].{id:id,device:device}'
```

### Find the image used by an ECS

```bash
hcloud ECS ShowServer --cli-region=X --server_id=SERVER_ID --cli-output=json --cli-query='server.image.id'
```

## Best practices

1. **Always use `--cli-query`** — raw API responses can be huge. Project only the fields you need.
2. **Batch independent queries** — VPCs, security groups, flavors, and images can all be queried in parallel.
3. **Resolve names to IDs** — most create operations require IDs, but users provide names. Always do the lookup.
4. **Check for existing resources before creating** — avoid duplicates by querying first.
5. **Use `--limit` for large sets** — some APIs default to 25 or 1000 results. Set `--limit=100` and paginate.
