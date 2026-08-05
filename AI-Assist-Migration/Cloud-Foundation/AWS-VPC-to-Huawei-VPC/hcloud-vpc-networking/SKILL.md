---
name: hcloud-vpc-networking
description: VPC, subnets, security groups, route tables, NAT gateways, and EIPs on Huawei Cloud. Use when creating network infrastructure, configuring security groups, or setting up NAT/internet access.
---

# VPC Networking on Huawei Cloud

Create and manage VPC networking: VPCs, subnets, security groups, route tables, NAT gateways, and EIPs.

## Prerequisites

- **hcloud CLI** configured with AK/SK (see `hcloud-cli-setup` skill)

## AWS VPC ↔ Huawei Cloud VPC Mapping

| AWS VPC | Huawei Cloud VPC |
|---|---|
| VPC | VPC |
| Subnet | Subnet |
| Security Group | Security Group |
| Route Table | Route Table |
| Internet Gateway | VPC default route |
| NAT Gateway | NAT Gateway |
| Elastic IP | EIP |
| Network ACL | (not available, use SG) |
| VPC Peering | VPC Peering |

## Step 1: Create a VPC

```bash
hcloud VPC CreateVpc --cli-region=la-north-2 \
  --vpc.name=my-vpc \
  --vpc.cidr=192.168.0.0/16 \
  --vpc.description="My VPC for web services"
```

Valid CIDR ranges:
- `10.0.0.0/8` to `10.255.255.240/28`
- `172.16.0.0/12` to `172.31.255.240/28`
- `192.168.0.0/16` to `192.168.255.240/28`

### List VPCs
```bash
hcloud VPC ListVpcs --cli-region=la-north-2
# Via MCP: hcloud_list_vpcs(region="la-north-2")
# Get details: hcloud_show_vpc(region="la-north-2", vpc_id="<VPC_ID>")
```

## Step 2: Create a Subnet

```bash
hcloud VPC CreateSubnet --cli-region=la-north-2 \
  --subnet.vpc_id=<VPC_ID> \
  --subnet.name=my-subnet \
  --subnet.cidr=192.168.1.0/24 \
  --subnet.gateway_ip=192.168.1.1 \
  --subnet.availability_zone=la-north-2a \
  --subnet.primary_dns=100.125.1.250 \
  --subnet.secondary_dns=100.125.21.250
```

Key parameters:
- `--subnet.cidr`: Must be within VPC CIDR, mask <= 28
- `--subnet.gateway_ip`: Must be within subnet CIDR
- `--subnet.availability_zone`: AZ for the subnet
- `--subnet.primary_dns` / `secondary_dns`: DNS servers (Huawei default: 100.125.1.250, 100.125.21.250)
- `--subnet.dhcp_enable`: Default true

### List subnets
```bash
hcloud VPC ListSubnets --cli-region=la-north-2 --vpc_id=<VPC_ID>
# Via MCP: hcloud_list_subnets(region="la-north-2", vpc_id="<VPC_ID>")
# Get details: hcloud_show_subnet(region="la-north-2", subnet_id="<SUBNET_ID>")
```

## Step 3: Create Security Groups

### Create security group
```bash
hcloud VPC CreateSecurityGroup --cli-region=la-north-2 \
  --security_group.name=sg-web \
  --security_group.vpc_id=<VPC_ID>
```

### Add rules
```bash
# SSH (port 22)
hcloud VPC CreateSecurityGroupRule --cli-region=la-north-2 \
  --security_group_id=<SG_ID> \
  --security_group_rule.direction=ingress \
  --security_group_rule.ethertype=IPv4 \
  --security_group_rule.protocol=tcp \
  --security_group_rule.port_range_min=22 \
  --security_group_rule.port_range_max=22 \
  --security_group_rule.remote_ip_prefix=0.0.0.0/0

# HTTP (port 80)
hcloud VPC CreateSecurityGroupRule --cli-region=la-north-2 \
  --security_group_id=<SG_ID> \
  --security_group_rule.direction=ingress \
  --security_group_rule.ethertype=IPv4 \
  --security_group_rule.protocol=tcp \
  --security_group_rule.port_range_min=80 \
  --security_group_rule.port_range_max=80 \
  --security_group_rule.remote_ip_prefix=0.0.0.0/0

# HTTPS (port 443)
hcloud VPC CreateSecurityGroupRule --cli-region=la-north-2 \
  --security_group_id=<SG_ID> \
  --security_group_rule.direction=ingress \
  --security_group_rule.ethertype=IPv4 \
  --security_group_rule.protocol=tcp \
  --security_group_rule.port_range_min=443 \
  --security_group_rule.port_range_max=443 \
  --security_group_rule.remote_ip_prefix=0.0.0.0/0

# Allow all from within VPC
hcloud VPC CreateSecurityGroupRule --cli-region=la-north-2 \
  --security_group_id=<SG_ID> \
  --security_group_rule.direction=ingress \
  --security_group_rule.ethertype=IPv4 \
  --security_group_rule.protocol=tcp \
  --security_group_rule.port_range_min=1 \
  --security_group_rule.port_range_max=65535 \
  --security_group_rule.remote_ip_prefix=192.168.0.0/16
```

### List security groups
```bash
hcloud VPC ListSecurityGroups --cli-region=la-north-2
# Via MCP: hcloud_list_security_groups(region="la-north-2")
# Get details: hcloud_show_security_group(region="la-north-2", security_group_id="<SG_ID>")
# List rules: hcloud_list_security_group_rules(region="la-north-2", security_group_id="<SG_ID>")
```

## Step 4: Route Tables

Route tables control traffic routing. Each VPC has a default route table.

### List route tables
```bash
hcloud VPC ListRouteTables --cli-region=la-north-2 --vpc_id=<VPC_ID>
# Via MCP: hcloud_list_route_tables(region="la-north-2", vpc_id="<VPC_ID>")
```

### Create a custom route table
```bash
hcloud VPC CreateRouteTable --cli-region=la-north-2 \
  --routetable.name=my-routetable \
  --routetable.vpc_id=<VPC_ID>
```

### Add a route
```bash
hcloud VPC UpdateRouteTable --cli-region=la-north-2 \
  --routetable_id=<RT_ID> \
  --routetable.routes.1.destination=0.0.0.0/0 \
  --routetable.routes.1.nexthop=<NAT_GW_ID_OR_PEER_ID>
```

## Step 5: NAT Gateway (for internet access without EIP)

NAT gateways provide SNAT (outbound internet) and DNAT (port forwarding) for instances without EIPs.

### Create NAT gateway
```bash
hcloud NAT CreateNatGateway --cli-region=la-north-2 \
  --nat_gateway.name=my-nat-gw \
  --nat_gateway.router_id=<VPC_ID> \
  --nat_gateway.internal_network=<SUBNET_ID> \
  --nat_gateway.nat_gateway_flavor=1 \
  --nat_gateway.public_ip_id=<EIP_ID>
```

You need an EIP for the NAT gateway. Create one first (see Step 6).

### List NAT gateways
```bash
hcloud NAT ListNatGateways --cli-region=la-north-2
# Via MCP: hcloud_list_nat_gateways(region="la-north-2")
# Get details: hcloud_show_nat_gateway(region="la-north-2", nat_gateway_id="<NAT_ID>")
```

### Add SNAT rule (outbound internet for a subnet)
```bash
hcloud NAT CreateSnatRule --cli-region=la-north-2 \
  --nat_gateway_id=<NAT_ID> \
  --snat_rule.cidr=192.168.1.0/24 \
  --snat_rule.source_type=0
```

### List SNAT rules
```bash
hcloud NAT ListSnatRules --cli-region=la-north-2 --nat_gateway_id=<NAT_ID>
# Via MCP: hcloud_list_nat_gateway_snat_rules(region="la-north-2", nat_gateway_id="<NAT_ID>")
```

### Add DNAT rule (port forwarding)
```bash
hcloud NAT CreateDnatRule --cli-region=la-north-2 \
  --nat_gateway_id=<NAT_ID> \
  --dnat_rule.protocol=tcp \
  --dnat_rule.private_ip=192.168.1.10 \
  --dnat_rule.internal_service_port=80 \
  --dnat_rule.external_service_port=8080
```

### List DNAT rules
```bash
hcloud NAT ListDnatRules --cli-region=la-north-2 --nat_gateway_id=<NAT_ID>
# Via MCP: hcloud_list_nat_gateway_dnat_rules(region="la-north-2", nat_gateway_id="<NAT_ID>")
```

## Step 6: Elastic IPs (EIP)

### Create EIP
```bash
hcloud EIP CreatePublicip --cli-region=la-north-2 \
  --publicip.type=5_bgp \
  --bandwidth.name=my-bandwidth \
  --bandwidth.size=10 \
  --bandwidth.sharetype=PER \
  --bandwidth.chargemode=traffic
```

Key parameters:
- `--publicip.type=5_bgp`: BGP EIP (recommended)
- `--bandwidth.size`: 1-300 Mbit/s
- `--bandwidth.sharetype`: `PER` (dedicated) or `WHOLE` (shared)
- `--bandwidth.chargemode`: `traffic` (by traffic) or others

### List EIPs
```bash
hcloud EIP ListPublicIps --cli-region=la-north-2
# Via MCP: hcloud_list_public_ips(region="la-north-2")
# Get details: hcloud_show_public_ip(region="la-north-2", publicip_id="<EIP_ID>")
```

### Bind EIP to an ECS
```bash
hcloud EIP AssociatePublicip --cli-region=la-north-2 \
  --publicip_id=<EIP_ID> \
  --port_id=<NIC_PORT_ID>
```

### Unbind EIP
```bash
hcloud EIP DisassociatePublicip --cli-region=la-north-2 --publicip_id=<EIP_ID>
```

### Delete EIP
```bash
hcloud EIP DeletePublicip --cli-region=la-north-2 --publicip_id=<EIP_ID>
```

## Step 7: Bandwidths

### List bandwidths
```bash
hcloud EIP ListBandwidths --cli-region=la-north-2
# Via MCP: hcloud_list_bandwidths(region="la-north-2")
```

### Resize bandwidth
```bash
hcloud EIP UpdateBandwidth --cli-region=la-north-2 \
  --bandwidth_id=<BW_ID> \
  --bandwidth.size=20
```

## VPC Peering

### Create VPC peering connection
```bash
hcloud VPC CreateVpcPeering --cli-region=la-north-2 \
  --vpc_peering.name=my-peering \
  --vpc_peering.request_vpc_id=<VPC_A_ID> \
  --vpc_peering.accept_vpc_id=<VPC_B_ID>
```

### List peerings
```bash
hcloud VPC ListVpcPeerings --cli-region=la-north-2
```

## Cleanup

```bash
# Delete in reverse order of creation
hcloud NAT DeleteNatGateway --cli-region=la-north-2 --nat_gateway_id=<NAT_ID>
hcloud EIP DeletePublicip --cli-region=la-north-2 --publicip_id=<EIP_ID>
hcloud VPC DeleteSecurityGroup --cli-region=la-north-2 --security_group_id=<SG_ID>
hcloud VPC DeleteSubnet --cli-region=la-north-2 --vpc_id=<VPC_ID> --subnet_id=<SUBNET_ID>
hcloud VPC DeleteVpc --cli-region=la-north-2 --vpc_id=<VPC_ID>
```

## MCP Tools Reference

| MCP Tool | Description |
|---|---|
| `hcloud_list_vpcs` | List VPCs |
| `hcloud_show_vpc` | Get VPC details |
| `hcloud_list_subnets` | List subnets |
| `hcloud_show_subnet` | Get subnet details |
| `hcloud_list_security_groups` | List security groups |
| `hcloud_show_security_group` | Get SG details |
| `hcloud_list_security_group_rules` | List SG rules |
| `hcloud_list_route_tables` | List route tables |
| `hcloud_list_nat_gateways` | List NAT gateways |
| `hcloud_show_nat_gateway` | Get NAT gateway details |
| `hcloud_list_nat_gateway_snat_rules` | List SNAT rules |
| `hcloud_list_nat_gateway_dnat_rules` | List DNAT rules |
| `hcloud_list_public_ips` | List EIPs |
| `hcloud_show_public_ip` | Get EIP details |
| `hcloud_list_bandwidths` | List bandwidths |
| `hcloud_show_quota` | Get VPC quotas |

## Troubleshooting

### Subnet creation fails
- CIDR must be within VPC CIDR
- Gateway IP must be within subnet CIDR
- Subnet mask cannot be greater than 28
- Check VPC quota: `hcloud VPC ShowQuota --cli-region=<region>`

### Security group rule conflicts
- Rules are permissive (allow only, no deny)
- Multiple rules can overlap; most specific rule applies

### NAT gateway not working
- NAT gateway needs an EIP
- SNAT rule CIDR must match the subnet CIDR
- Route table must have a default route pointing to the NAT gateway

### EIP bind fails
- EIP must be in DOWN state to bind
- Target port (NIC) must exist and be in the same region

## Current Environment (la-north-2)

- VPCs: `vpc-default-smb` (172.31.0.0/16), `vpc-openwebui` (192.168.0.0/16)
- Subnets: `subnet-default-smb` (172.31.0.0/20), `subnet-openwebui` (192.168.0.0/24)
- AZs: `la-north-2a`, `la-north-2b`, `la-north-2c`
- SGs: `sg-ecs-s01/s02/s03`, `default`, `sg-default-smb`
- No NAT gateways, no EIPs
