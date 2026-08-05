---
name: floci-vpc-networking
description: VPC, subnets, security groups, route tables, NAT, IGW, and VPC peering on floci. Use when learning AWS networking, creating custom VPCs, or troubleshooting network configurations locally.
---

# VPC Networking on Floci

Learn AWS networking concepts with floci — VPCs, subnets, route tables, security groups, internet gateways, NAT gateways, and VPC peering.

## Prerequisites

- **Floci** running (`floci start && floci wait`)
- **AWS CLI** configured for floci

## Default VPC

Floci provides a default VPC out of the box:

```bash
aws ec2 describe-vpcs --query 'Vpcs[].{Id:VpcId, Cidr:CidrBlock}'
# vpc-default, 172.31.0.0/16

aws ec2 describe-subnets --query 'Subnets[].{Id:SubnetId, Cidr:CidrBlock, AZ:AvailabilityZone}'
# subnet-default-a  172.31.0.0/20   us-east-1a
# subnet-default-b  172.31.16.0/20  us-east-1b
# subnet-default-c  172.31.32.0/20  us-east-1c

aws ec2 describe-security-groups --query 'SecurityGroups[].{Id:GroupId, Name:GroupName}'
# sg-default, default
```

## Step 1: Create Custom VPC

```bash
# Create VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --query 'Vpc.VpcId' --output text

# Tag it
aws ec2 create-tags \
  --resources vpc-XXXXXXXX \
  --tags Key=Name,Value=my-vpc
```

### Enable DNS support and hostnames

```bash
aws ec2 modify-vpc-attribute --vpc-id vpc-XXXXXXXX --enable-dns-support
aws ec2 modify-vpc-attribute --vpc-id vpc-XXXXXXXX --enable-dns-hostnames
```

## Step 2: Create Subnets

### Public subnets (for load balancers, bastion)

```bash
# Subnet in AZ-a (public)
aws ec2 create-subnet \
  --vpc-id vpc-XXXXXXXX \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a

# Subnet in AZ-b (public)
aws ec2 create-subnet \
  --vpc-id vpc-XXXXXXXX \
  --cidr-block 10.0.2.0/24 \
  --availability-zone us-east-1b
```

### Private subnets (for app, DB)

```bash
# Subnet in AZ-a (private)
aws ec2 create-subnet \
  --vpc-id vpc-XXXXXXXX \
  --cidr-block 10.0.10.0/24 \
  --availability-zone us-east-1a

# Subnet in AZ-b (private)
aws ec2 create-subnet \
  --vpc-id vpc-XXXXXXXX \
  --cidr-block 10.0.20.0/24 \
  --availability-zone us-east-1b
```

### Tag subnets

```bash
aws ec2 create-tags --resources subnet-AAA --tags Key=Name,Value=public-a
aws ec2 create-tags --resources subnet-BBB --tags Key=Name,Value=public-b
aws ec2 create-tags --resources subnet-CCC --tags Key=Name,Value=private-a
aws ec2 create-tags --resources subnet-DDD --tags Key=Name,Value=private-b
```

## Step 3: Internet Gateway

```bash
# Create IGW
aws ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' --output text

# Attach to VPC
aws ec2 attach-internet-gateway \
  --internet-gateway-id igw-XXXXXXXX \
  --vpc-id vpc-XXXXXXXX
```

## Step 4: Route Tables

### Public route table (routes to IGW)

```bash
# Create route table
aws ec2 create-route-table \
  --vpc-id vpc-XXXXXXXX \
  --query 'RouteTable.RouteTableId' --output text

# Add default route to IGW
aws ec2 create-route \
  --route-table-id rtb-XXXXXXXX \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id igw-XXXXXXXX

# Associate public subnets
aws ec2 associate-route-table \
  --route-table-id rtb-XXXXXXXX \
  --subnet-id subnet-AAA

aws ec2 associate-route-table \
  --route-table-id rtb-XXXXXXXX \
  --subnet-id subnet-BBB
```

### Private route table (no internet access)

```bash
# Create private route table
aws ec2 create-route-table \
  --vpc-id vpc-XXXXXXXX \
  --query 'RouteTable.RouteTableId' --output text

# Associate private subnets
aws ec2 associate-route-table \
  --route-table-id rtb-YYYYYYYY \
  --subnet-id subnet-CCC

aws ec2 associate-route-table \
  --route-table-id rtb-YYYYYYYY \
  --subnet-id subnet-DDD
```

## Step 5: NAT Gateway (for private subnet internet access)

```bash
# Allocate Elastic IP
aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text

# Create NAT Gateway in a PUBLIC subnet
aws ec2 create-nat-gateway \
  --subnet-id subnet-AAA \
  --allocation-id eipalloc-XXXXXXXX

# Wait for available
aws ec2 describe-nat-gateways --nat-gateway-id nat-XXXXXXXX \
  --query 'NatGateways[].State'

# Add route to NAT in private route table
aws ec2 create-route \
  --route-table-id rtb-YYYYYYYY \
  --destination-cidr-block 0.0.0.0/0 \
  --nat-gateway-id nat-XXXXXXXX
```

## Step 6: Security Groups

### Web security group (HTTP/HTTPS)

```bash
aws ec2 create-security-group \
  --group-name web-sg \
  --description "Web tier" \
  --vpc-id vpc-XXXXXXXX

# Allow HTTP
aws ec2 authorize-security-group-ingress \
  --group-id sg-XXXXXXXX \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

# Allow HTTPS
aws ec2 authorize-security-group-ingress \
  --group-id sg-XXXXXXXX \
  --protocol tcp --port 443 --cidr 0.0.0.0/0
```

### App security group (from web only)

```bash
aws ec2 create-security-group \
  --group-name app-sg \
  --description "App tier" \
  --vpc-id vpc-XXXXXXXX

# Allow from web-sg on port 8080
aws ec2 authorize-security-group-ingress \
  --group-id sg-YYYYYYYY \
  --protocol tcp --port 8080 \
  --source-group sg-XXXXXXXX
```

### DB security group (from app only)

```bash
aws ec2 create-security-group \
  --group-name db-sg \
  --description "DB tier" \
  --vpc-id vpc-XXXXXXXX

# Allow from app-sg on port 5432
aws ec2 authorize-security-group-ingress \
  --group-id sg-ZZZZZZZZ \
  --protocol tcp --port 5432 \
  --source-group sg-YYYYYYYY
```

## Step 7: VPC Peering

```bash
# Create peering connection (floci default VPC ↔ custom VPC)
aws ec2 create-vpc-peering-connection \
  --vpc-id vpc-default \
  --peer-vpc-id vpc-XXXXXXXX

# Accept peering
aws ec2 accept-vpc-peering-connection \
  --vpc-peering-connection-id pcx-XXXXXXXX

# Add route in default VPC to custom VPC
aws ec2 create-route \
  --route-table-id <DEFAULT_RTB> \
  --destination-cidr-block 10.0.0.0/16 \
  --vpc-peering-connection-id pcx-XXXXXXXX

# Add route in custom VPC to default VPC
aws ec2 create-route \
  --route-table-id rtb-XXXXXXXX \
  --destination-cidr-block 172.31.0.0/16 \
  --vpc-peering-connection-id pcx-XXXXXXXX
```

## Step 8: Verify Everything

```bash
# VPC details
aws ec2 describe-vpcs --query 'Vpcs[].{Id:VpcId, Cidr:CidrBlock}'

# All subnets
aws ec2 describe-subnets --query 'Subnets[].{Id:SubnetId, Vpc:VpcId, Cidr:CidrBlock, AZ:AvailabilityZone}'

# Route tables and routes
aws ec2 describe-route-tables --query 'RouteTables[].{Id:RouteTableId, Vpc:VpcId, Routes:Routes[].{Dest:DestinationCidrBlock, Target:GatewayId}}'

# Security groups and rules
aws ec2 describe-security-groups --query 'SecurityGroups[].{Id:GroupId, Name:GroupName, Ingress:IpPermissions[].{Port:FromPort, Cidr:IpRanges[].CidrIp}}'

# NAT gateways
aws ec2 describe-nat-gateways --query 'NatGateways[].{Id:NatGatewayId, State:State, Subnet:SubnetId}'

# Internet gateways
aws ec2 describe-internet-gateways --query 'InternetGateways[].{Id:InternetGatewayId, Vpc:Attachments[].VpcId}'

# Peering connections
aws ec2 describe-vpc-peering-connections --query 'VpcPeeringConnections[].{Id:VpcPeeringConnectionId, Status:Status.Code}'
```

## Architecture Diagram

```
                    Internet
                       |
                   [IGW]
                       |
     ┌──────────────────────────────────┐
     │           VPC 10.0.0.0/16        │
     │                                  │
     │  ┌─── public-a ───┐  ┌─── public-b ───┐ │
     │  │ 10.0.1.0/24    │  │ 10.0.2.0/24    │ │
     │  │ [NAT Gateway]  │  │ [Load Balancer]│ │
     │  └────────────────┘  └────────────────┘ │
     │          │                      │        │
     │  ┌── private-a ──┐  ┌── private-b ──┐  │
     │  │ 10.0.10.0/24  │  │ 10.0.20.0/24  │  │
     │  │ [App Server]  │  │ [App Server]  │  │
     │  └───────────────┘  └───────────────┘  │
     │          │                      │        │
     │  ┌── DB-a ───────┐  ┌── DB-b ───────┐  │
     │  │ [Database]    │  │ [Database]    │  │
     │  └───────────────┘  └───────────────┘  │
     └──────────────────────────────────┘
```

## Floci Networking Quirks vs Real AWS

| Aspect | Real AWS | Floci |
|--------|----------|-------|
| Actual networking | Real ENIs, real routing | API only (no real traffic flow) |
| Internet Gateway | Real internet access | API only (no real connectivity) |
| NAT Gateway | Real NAT (charges per hour) | API only (no charges) |
| VPC Peering | Real peered routing | API only (no actual peering) |
| Security Groups | Enforced at ENI level | Not enforced (API only) |
| Elastic IPs | Real public IPs | API only (returns dummy IPs) |
| Subnet routing | Real route tables | API only |
| DNS | Route53 Resolver | API only |

## Troubleshooting

### `InvalidVpcID.NotFound`

**Cause**: VPC ID doesn't exist.

**Fix**: List VPCs first:
```bash
aws ec2 describe-vpcs --query 'Vpcs[].VpcId'
```

### `InvalidSubnetID.NotFound`

**Cause**: Subnet was deleted or belongs to different VPC.

**Fix**: Filter by VPC:
```bash
aws ec2 describe-subnets --filters Name=vpc-id,Values=vpc-XXXXXXXX
```

### Route creation fails

**Cause**: Target (IGW/NAT/PCX) doesn't exist or is in different VPC.

**Fix**: Verify target exists and belongs to same VPC.

### Security group rule already exists

**Cause**: Duplicate rule. Floci may not deduplicate.

**Fix**: Revoke first, then authorize:
```bash
aws ec2 revoke-security-group-ingress --group-id sg-XXX --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id sg-XXX --protocol tcp --port 80 --cidr 0.0.0.0/0
```

## Clean Up

```bash
# Delete in order: routes → NAT → IGW → subnets → SGs → VPC

# Get VPC ID
VPC_ID="vpc-XXXXXXXX"

# Delete NAT gateways
for nat in $(aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=$VPC_ID --query 'NatGateways[].NatGatewayId' --output text 2>/dev/null); do
  aws ec2 delete-nat-gateway --nat-gateway-id $nat
done

# Detach and delete IGW
for igw in $(aws ec2 describe-internet-gateways --filter Name=attachment.vpc-id,Values=$VPC_ID --query 'InternetGateways[].InternetGatewayId' --output text 2>/dev/null); do
  aws ec2 detach-internet-gateway --internet-gateway-id $igw --vpc-id $VPC_ID
  aws ec2 delete-internet-gateway --internet-gateway-id $igw
done

# Delete subnets
for sub in $(aws ec2 describe-subnets --filter Name=vpc-id,Values=$VPC_ID --query 'Subnets[].SubnetId' --output text 2>/dev/null); do
  aws ec2 delete-subnet --subnet-id $sub
done

# Delete security groups (not default)
for sg in $(aws ec2 describe-security-groups --filter Name=vpc-id,Values=$VPC_ID --query 'SecurityGroups[?GroupName!=`default`].GroupId' --output text 2>/dev/null); do
  aws ec2 delete-security-group --group-id $sg
done

# Delete VPC
aws ec2 delete-vpc --vpc-id $VPC_ID
```

## Quick Reference

### Commands

| Command | Purpose |
|---------|---------|
| `aws ec2 describe-vpcs` | List VPCs |
| `aws ec2 describe-subnets` | List subnets |
| `aws ec2 describe-route-tables` | List route tables |
| `aws ec2 describe-security-groups` | List security groups |
| `aws ec2 describe-internet-gateways` | List IGWs |
| `aws ec2 describe-nat-gateways` | List NAT gateways |
| `aws ec2 describe-vpc-peering-connections` | List peering connections |
| `aws ec2 create-vpc --cidr-block X` | Create VPC |
| `aws ec2 create-subnet --vpc-id V --cidr-block X` | Create subnet |
| `aws ec2 create-security-group --group-name N --vpc-id V` | Create SG |
