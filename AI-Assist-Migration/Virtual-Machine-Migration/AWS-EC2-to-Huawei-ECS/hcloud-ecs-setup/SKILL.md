---
name: hcloud-ecs-setup
description: Create ECS (Elastic Cloud Server) instances on Huawei Cloud with flavors, images, keypairs, security groups, and volumes. Use when setting up ECS servers, selecting flavors/images, or troubleshooting ECS creation.
---

# ECS Server Setup on Huawei Cloud

Create and manage ECS (Elastic Cloud Server) instances on Huawei Cloud — the equivalent of AWS EC2.

## Prerequisites

- **hcloud CLI** configured with AK/SK (see `hcloud-cli-setup` skill)
- A **VPC**, **subnet**, and **security group** exist in the target region

## EC2 ↔ ECS Mapping

| AWS EC2 | Huawei Cloud ECS |
|---|---|
| Instance | ECS Server |
| AMI | IMS Image |
| Instance Type | Flavor |
| EBS Volume | EVS Volume |
| Security Group | Security Group |
| Key Pair | Key Pair |
| Elastic IP | EIP |
| Placement Group | ECS Group |

## Step 1: Gather Prerequisites

### List AZs
```bash
hcloud ECS NovaListAvailabilityZones --cli-region=la-north-2
# AZs: la-north-2a, la-north-2b, la-north-2c
```

### List flavors
```bash
hcloud ECS NovaListFlavors --cli-region=la-north-2
# Or via MCP: hcloud_list_flavors(region="la-north-2", availability_zone="la-north-2a")
```

### Common flavors (la-north-2)

| Flavor | vCPU | RAM | Gen | CPU |
|---|---|---|---|---|
| `ac8.large.2` | 2 | 4GB | ac8 | AMD |
| `ac8.large.4` | 2 | 8GB | ac8 | AMD |
| `ac8.xlarge.2` | 4 | 8GB | ac8 | AMD |
| `ac8.xlarge.4` | 4 | 16GB | ac8 | AMD |
| `ac8.2xlarge.2` | 8 | 16GB | ac8 | AMD |
| `ac9.large.2` | 2 | 4GB | ac9 | AMD 2.7GHz |
| `ac9.xlarge.2` | 4 | 8GB | ac9 | AMD 2.7GHz |
| `c6.2xlarge.2` | 8 | 16GB | c6 | Intel Cascade Lake |

Naming: `{gen}.{size}.{cpu_mem_ratio}` — `ac8.xlarge.2` = ac8 gen, 4 vCPU, 2:1 ratio (8GB).

### List images
```bash
# Public Linux images
hcloud IMS ListImages --cli-region=la-north-2 --imagetype=gold --os_type=Linux
# Via MCP: hcloud_list_images(region="la-north-2", imagetype="gold", os_type="Linux")
```

Common images: EulerOS 2.0 (active), Ubuntu 22.04, CentOS 7.9 (EOL).

### List VPCs and subnets
```bash
hcloud VPC ListVpcs --cli-region=la-north-2
hcloud VPC ListSubnets --cli-region=la-north-2 --vpc_id=<VPC_ID>
```

### List security groups
```bash
hcloud VPC ListSecurityGroups --cli-region=la-north-2
# Via MCP: hcloud_list_security_groups(region="la-north-2")
```

## Step 2: Create SSH Key Pair

```bash
# Create from public key
hcloud ECS CreateKeypair --cli-region=la-north-2 \
  --keypair.name=my-keypair \
  --public_key="$(cat ~/.ssh/id_rsa.pub)"

# List keypairs
hcloud ECS NovaListKeypairs --cli-region=la-north-2
# Via MCP: hcloud_list_keypairs(region="la-north-2")
```

## Step 3: Create Security Group (if needed)

```bash
# Create security group
hcloud VPC CreateSecurityGroup --cli-region=la-north-2 \
  --security_group.name=sg-web \
  --security_group.vpc_id=<VPC_ID>

# Add ingress rule (SSH)
hcloud VPC CreateSecurityGroupRule --cli-region=la-north-2 \
  --security_group_id=<SG_ID> \
  --security_group_rule.direction=ingress \
  --security_group_rule.ethertype=IPv4 \
  --security_group_rule.protocol=tcp \
  --security_group_rule.port_range_min=22 \
  --security_group_rule.port_range_max=22 \
  --security_group_rule.remote_ip_prefix=0.0.0.0/0

# Add ingress rule (HTTP)
hcloud VPC CreateSecurityGroupRule --cli-region=la-north-2 \
  --security_group_id=<SG_ID> \
  --security_group_rule.direction=ingress \
  --security_group_rule.ethertype=IPv4 \
  --security_group_rule.protocol=tcp \
  --security_group_rule.port_range_min=80 \
  --security_group_rule.port_range_max=80 \
  --security_group_rule.remote_ip_prefix=0.0.0.0/0
```

## Step 4: Create the ECS Server

```bash
hcloud ECS CreateServers --cli-region=la-north-2 \
  --server.name=my-server \
  --server.flavorRef=ac8.xlarge.2 \
  --server.imageRef=<IMAGE_ID> \
  --server.vpcid=<VPC_ID> \
  --server.nics.1.subnet_id=<SUBNET_ID> \
  --server.availability_zone=la-north-2a \
  --server.root_volume.volumetype=GPSSD \
  --server.root_volume.size=50 \
  --server.data_volumes.1.size=100 \
  --server.data_volumes.1.volumetype=GPSSD \
  --server.security_groups.1.id=<SG_ID> \
  --server.key_name=my-keypair \
  --server.publicip.eip.iptype=5_bgp \
  --server.publicip.eip.bandwidth.size=10 \
  --server.publicip.eip.bandwidth.sharetype=PER \
  --server.publicip.delete_on_termination=true \
  --server.count=1 \
  --server.extendparam.chargingMode=postPaid
```

Key parameters:
- `--server.flavorRef`: Flavor ID (e.g. `ac8.xlarge.2`)
- `--server.imageRef`: Image ID (UUID from IMS ListImages)
- `--server.vpcid`: VPC ID
- `--server.nics.1.subnet_id`: Subnet ID for the primary NIC
- `--server.availability_zone`: AZ (e.g. `la-north-2a`)
- `--server.root_volume.volumetype`: `GPSSD`, `SSD`, `SAS`, `GPSSD2`, `ESSD2`
- `--server.root_volume.size`: System disk size in GB (1-1024)
- `--server.data_volumes.N.size/volumetype`: Data disks (10-32768 GB)
- `--server.key_name`: SSH key pair name (recommended over password)
- `--server.adminPass`: Initial password (alternative to key pair)
- `--server.publicip.eip.*`: Auto-create EIP with bandwidth
- `--server.publicip.eip.bandwidth.sharetype`: `PER` (dedicated) or `WHOLE` (shared)
- `--server.count`: Number of servers to create (max 100 for pay-per-use)
- `--server.extendparam.chargingMode`: `postPaid` (pay-per-use) or `prePaid` (yearly/monthly)
- `--server.security_groups.1.id`: Security group ID

### Password authentication (alternative to key pair)
```bash
--server.adminPass='MyP@ssw0rd123'  # 8-26 chars, 3+ char types
```

### User data (cloud-init)
```bash
# Base64-encode your script
USER_DATA=$(echo '#!/bin/bash
yum install -y nginx
systemctl start nginx' | base64 -w0)

hcloud ECS CreateServers ... --server.user_data="$USER_DATA"
```

## Step 5: Monitor Creation

```bash
# List servers
hcloud ECS ListServers --cli-region=la-north-2
# Via MCP: hcloud_list_servers(region="la-north-2")
# Filter: hcloud_list_servers(region="la-north-2", name="my-server", status="ACTIVE")

# Get server details
hcloud ECS ShowServer --cli-region=la-north-2 --server_id=<SERVER_ID>
# Via MCP: hcloud_show_server(region="la-north-2", server_id="<SERVER_ID>")

# List server interfaces (NICs)
hcloud ECS ShowServerInterfaces --cli-region=la-north-2 --server_id=<SERVER_ID>
# Via MCP: hcloud_list_server_interfaces(region="la-north-2", server_id="<SERVER_ID>")

# List block devices (volumes)
hcloud ECS ShowServerBlockDevice --cli-region=la-north-2 --server_id=<SERVER_ID>
# Via MCP: hcloud_list_server_block_devices(region="la-north-2", server_id="<SERVER_ID>")
```

Wait until status = `ACTIVE`. Creation takes 1-2 minutes.

## Volume Types

| Type | Description | Use Case |
|---|---|---|
| `GPSSD` | General Purpose SSD | Default, cost-effective |
| `GPSSD2` | GP SSD V2 (configurable IOPS) | Performance tuning |
| `SSD` | Ultra-high I/O | Databases, high IOPS |
| `ESSD2` | Ultra-high I/O V2 | Mission-critical |
| `SAS` | High I/O | General workloads |

## ECS Lifecycle

### Start/Stop/Reboot
```bash
hcloud ECS NovaStartServer --cli-region=la-north-2 --server_id=<SERVER_ID>
hcloud ECS NovaStopServer --cli-region=la-north-2 --server_id=<SERVER_ID>
hcloud ECS NovaRebootServer --cli-region=la-north-2 --server_id=<SERVER_ID>
```

### Change flavor (resize)
```bash
hcloud ECS ResizeServer --cli-region=la-north-2 \
  --server_id=<SERVER_ID> \
  --flavorRef=ac8.2xlarge.2
```

### Delete server
```bash
hcloud ECS DeleteServers --cli-region=la-north-2 --server_id=<SERVER_ID>
```

### List volumes
```bash
hcloud EVS ListVolumes --cli-region=la-north-2
# Via MCP: hcloud_list_volumes(region="la-north-2")
```

### List EIPs
```bash
hcloud EIP ListPublicIps --cli-region=la-north-2
# Via MCP: hcloud_list_public_ips(region="la-north-2")
```

## MCP Tools Reference

| MCP Tool | Description |
|---|---|
| `hcloud_list_servers` | List ECS servers (with filters) |
| `hcloud_show_server` | Get server details |
| `hcloud_list_flavors` | List available flavors |
| `hcloud_list_images` | List available images |
| `hcloud_list_keypairs` | List SSH key pairs |
| `hcloud_list_security_groups` | List security groups |
| `hcloud_show_security_group` | Get SG details |
| `hcloud_list_server_interfaces` | List NICs |
| `hcloud_list_server_block_devices` | List attached volumes |
| `hcloud_list_volumes` | List all EVS volumes |
| `hcloud_list_public_ips` | List EIPs |
| `hcloud_list_vpcs` | List VPCs |
| `hcloud_list_subnets` | List subnets |
| `hcloud_list_availability_zones` | List AZs |

## Troubleshooting

### Insufficient quota
```bash
# Check ECS quota
hcloud ECS ShowServerLimits --cli-region=la-north-2
# Via MCP: hcloud_show_server_limits(region="la-north-2")
```

### Flavor not available in AZ
- Check `cond:operation:az` in flavor extra_specs
- Some flavors are only in specific AZs (e.g. ac9 only in `la-north-2a`)

### Image not found
- Use `imagetype=gold` for public images
- Image ID must be UUID format
- Check image status is `active`

### Server stuck in BUILD
- Check VPC/subnet exist and are in the same region
- Verify security group exists
- Check job status: `hcloud ECS ShowJob --cli-region=<region> --job_id=<JOB_ID>`

## Current Environment (la-north-2)

- VPCs: `vpc-default-smb` (172.31.0.0/16), `vpc-openwebui` (192.168.0.0/16)
- Subnets: `subnet-default-smb` (172.31.0.0/20), `subnet-openwebui` (192.168.0.0/24)
- AZs: `la-north-2a`, `la-north-2b`, `la-north-2c`
- SGs: `sg-ecs-s01/s02/s03`, `default`, `sg-default-smb`
- No existing ECS servers, no keypairs, no EIPs
