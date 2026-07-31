# Resource Creation, Update, and Deletion

Create, modify, and remove Huawei Cloud resources with validation and async handling.

## The workflow: Discover → Dryrun → Execute → Verify

Every mutation follows the same 4-step pattern:

```bash
# 1. DISCOVER — check existing resources, gather required IDs
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'

# 2. DRYRUN — validate the call without executing
hcloud --dryrun VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# 3. EXECUTE — run the actual call (add --cli-waiter for async operations)
hcloud VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# 4. VERIFY — confirm the resource was created/modified as expected
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`demo-vpc`]'
```

## Dryrun

`--dryrun` validates parameters and prints the request that would be sent, without executing:

```bash
hcloud --dryrun VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16
```

Output shows the HTTP method, URL, headers, and body:

```
POST https://vpc.la-north-2.myhuaweicloud.com/v1/PROJECT_ID/vpcs
Content-Type: application/json;charset=UTF-8
X-Project-Id: PROJECT_ID
X-Sdk-Date: 20260622T141618Z
Authorization: ****

{"vpc": {"name": "demo-vpc", "cidr": "10.0.0.0/16"}}
```

**Always dryrun before execute.** This catches:
- Missing required parameters
- Invalid parameter values
- Wrong parameter names
- Auth/permission issues

## Skeleton

For complex operations with many nested parameters, generate a JSON skeleton:

```bash
hcloud --skeleton ECS CreateServers
```

This creates a file like `ECS_CreateServers_en-20260622.json` with all parameters as placeholders.

### Skeleton workflow

```bash
# 1. Generate
hcloud --skeleton RDS CreateInstance

# 2. Edit the JSON — fill required values, remove unused optional params
#    (use Read + Edit tools to modify the file)

# 3. Dryrun
hcloud --dryrun RDS CreateInstance --cli-region=la-north-2 --cli-jsonInput=./RDS_CreateInstance_en-*.json

# 4. Execute with waiter
hcloud RDS CreateInstance --cli-region=la-north-2 \
  --cli-waiter='{"expr":"instances[0].status","to":"ACTIVE","timeout":600}' \
  --cli-jsonInput=./RDS_CreateInstance_en-*.json
```

## JSON input

For operations with deeply nested body parameters, use `--cli-jsonInput` instead of `--param=value`:

```bash
# Inline parameters (simple cases)
hcloud VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo --vpc.cidr=10.0.0.0/16

# JSON file (complex cases)
hcloud ECS CreateServers --cli-region=la-north-2 --cli-jsonInput=./create-ecs.json
```

## Common creation flows

### VPC + Subnet + Security Group

```bash
REGION=la-north-2

# 1. Create VPC
hcloud --dryrun VPC CreateVpc --cli-region=$REGION --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16
hcloud VPC CreateVpc --cli-region=$REGION --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16
# → vpc.id = VPC_ID

# 2. Create Subnet in the VPC
hcloud --dryrun VPC CreateSubnet --cli-region=$REGION \
  --vpc_id=VPC_ID \
  --subnet.name=demo-subnet \
  --subnet.cidr=10.0.0.0/24 \
  --subnet.gateway_ip=10.0.0.1
hcloud VPC CreateSubnet --cli-region=$REGION \
  --vpc_id=VPC_ID \
  --subnet.name=demo-subnet \
  --subnet.cidr=10.0.0.0/24 \
  --subnet.gateway_ip=10.0.0.1
# → subnet.id = SUBNET_ID

# 3. Create Security Group
hcloud --dryrun VPC CreateSecurityGroup --cli-region=$REGION --security_group.name=demo-sg
hcloud VPC CreateSecurityGroup --cli-region=$REGION --security_group.name=demo-sg
# → security_group.id = SG_ID

# 4. Add inbound rule to SG (e.g., allow SSH)
hcloud --dryrun VPC CreateSecurityGroupRule --cli-region=$REGION \
  --security_group_id=SG_ID \
  --security_group_rule.direction=ingress \
  --security_group_rule.protocol=tcp \
  --security_group_rule.port_range_min=22 \
  --security_group_rule.port_range_max=22 \
  --security_group_rule.remote_ip_prefix=0.0.0.0/0
hcloud VPC CreateSecurityGroupRule --cli-region=$REGION \
  --security_group_id=SG_ID \
  --security_group_rule.direction=ingress \
  --security_group_rule.protocol=tcp \
  --security_group_rule.port_range_min=22 \
  --security_group_rule.port_range_max=22 \
  --security_group_rule.remote_ip_prefix=0.0.0.0/0
```

### ECS Instance

```bash
REGION=la-north-2

# 1. Discover prerequisites (parallel)
hcloud VPC ListVpcs --cli-region=$REGION --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
hcloud VPC ListSubnets --cli-region=$REGION --vpc_id=VPC_ID --cli-output=json --cli-query='subnets[].{name:name,id:id}'
hcloud VPC ListSecurityGroups --cli-region=$REGION --cli-output=json --cli-query='security_groups[].{name:name,id:id}'
hcloud ECS ListFlavors --cli-region=$REGION --availability_zone=la-north-2a --cli-output=json --cli-query='flavors[].{id:id,name:name,vcpus:vcpus,ram:ram}'
hcloud IMS ListImages --cli-region=$REGION --__imagetype=gold --__os_type=Linux --__platform=Ubuntu --cli-output=json --cli-query='images[].{id:id,name:name}'
hcloud ECS ListKeypairs --cli-region=$REGION --cli-output=json --cli-query='keypairs[].{name:keypair.name}'

# 2. Create (with waiter)
hcloud --dryrun ECS CreateServers --cli-region=$REGION \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID \
  --server.key_name=KEYPAIR_NAME

hcloud ECS CreateServers --cli-region=$REGION \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID \
  --server.key_name=KEYPAIR_NAME

# 3. Verify
hcloud ECS ListServersDetails --cli-region=$REGION --name=demo-ecs --cli-output=json --cli-query='servers[].{name:name,id:id,status:status}'
```

### RDS Instance

```bash
REGION=la-north-2

# 1. Discover prerequisites
hcloud RDS ListDatastores --cli-region=$REGION --database_name=MySQL --cli-output=json
hcloud RDS ListFlavors --cli-region=$REGION --database_name=MySQL --cli-output=json
hcloud RDS ListStorageTypes --cli-region=$REGION --database_name=MySQL --cli-output=json

# 2. Use skeleton for complex create
hcloud --skeleton RDS CreateInstance

# 3. Edit skeleton, then dryrun
hcloud --dryrun RDS CreateInstance --cli-region=$REGION --cli-jsonInput=./RDS_CreateInstance_en-*.json

# 4. Execute with waiter (RDS creation takes several minutes)
hcloud RDS CreateInstance --cli-region=$REGION \
  --cli-waiter='{"expr":"instances[0].status","to":"ACTIVE","timeout":600}' \
  --cli-jsonInput=./RDS_CreateInstance_en-*.json

# 5. Verify
hcloud RDS ListInstances --cli-region=$REGION --cli-output=json --cli-query='instances[].{name:name,id:id,status:status}'
```

### Elastic IP

```bash
# Create EIP
hcloud EIP CreatePublicip --cli-region=la-north-2 \
  --publicip.type=5_sbgp \
  --bandwidth.name=eip-bandwidth \
  --bandwidth.size=5 \
  --bandwidth.charge_mode=traffic

# Associate EIP to an ECS
hcloud EIP AssociatePublicips --cli-region=la-north-2 \
  --publicip_id=EIP_ID \
  --publicip.port_id=PORT_ID
```

## Updates

```bash
# Update ECS name
hcloud ECS BatchUpdateServersName --cli-region=la-north-2 \
  --servers.1.id=SERVER_ID \
  --name=new-name

# Resize ECS flavor
hcloud ECS BatchResizeServers --cli-region=la-north-2 \
  --servers.1.id=SERVER_ID \
  --servers.1.flavor_ref=c6.xlarge.2 \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}'

# Change ECS OS
hcloud ECS ChangeServerOsWithCloudInit --cli-region=la-north-2 \
  --server_id=SERVER_ID \
  --os_image=IMAGE_ID \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}'
```

## Deletion

```bash
# 1. Find the resource
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`old-vpc`].id'

# 2. Check dependencies (e.g., subnets in the VPC)
hcloud VPC ListSubnets --cli-region=la-north-2 --vpc_id=VPC_ID --cli-output=json --cli-query='subnets[].{name:name,id:id}'

# 3. Delete dependencies first
hcloud VPC DeleteSubnet --cli-region=la-north-2 --vpc_id=VPC_ID --subnet_id=SUBNET_ID

# 4. Dryrun the delete
hcloud --dryrun VPC DeleteVpc --cli-region=la-north-2 --vpc_id=VPC_ID

# 5. Execute
hcloud VPC DeleteVpc --cli-region=la-north-2 --vpc_id=VPC_ID

# 6. Verify
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`old-vpc`]'
```

### Delete ECS

```bash
# Batch delete
hcloud ECS BatchStopServers --cli-region=la-north-2 --servers.1.id=SERVER_ID --os_stop.force=true
hcloud ECS DeleteServers --cli-region=la-north-2 --servers.1.id=SERVER_ID --delete_publicip=true --delete_volume=true
```

## Best practices

1. **Always dryrun first** — catch errors before they affect real resources.
2. **Use skeleton for complex creates** — ECS, RDS, CCE cluster creation have many nested params.
3. **Use waiter for async operations** — never poll manually. See [waiter-patterns.md](waiter-patterns.md).
4. **Verify after every mutation** — confirm the resource reached the expected state.
5. **Delete in dependency order** — subnets before VPCs, nodes before clusters, etc.
6. **Check for existing resources** — before creating, query to avoid duplicates.
7. **Keep `--cli-region` explicit** — don't rely on profile defaults for destructive operations.
