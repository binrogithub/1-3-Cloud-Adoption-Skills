# Terraform Generation from CLI Discoveries

Translate KooCLI query results into Terraform HCL code. This is a standalone guide — no external skill dependencies.

## The pattern: CLI discovery → HCL code

Every resource in Terraform follows one of two patterns:

1. **Data block** — referencing an existing resource discovered via CLI
2. **Resource block** — creating a new resource (use CLI to validate parameters)

## Step 1: Discover existing resources

Use KooCLI to query the cloud and collect the values needed for data blocks:

```bash
# VPC
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`prod-vpc`].{id:id,name:name,cidr:cidr}'

# Subnet
hcloud VPC ListSubnets --cli-region=la-north-2 --vpc_id=VPC_ID --cli-output=json --cli-query='subnets[?name==`db-subnet`].{id:id,name:name,cidr:cidr}'

# Security Group
hcloud VPC ListSecurityGroups --cli-region=la-north-2 --cli-output=json --cli-query='security_groups[?name==`rds-sg`].{id:id,name:name}'

# Image
hcloud IMS ListImages --cli-region=la-north-2 --__imagetype=gold --__os_type=Linux --__platform=Ubuntu --cli-output=json --cli-query='images[?name==`Ubuntu 24.04 server 64bit`].{id:id,name:name}'

# Availability Zones
hcloud ECS ListServerAzInfo --cli-region=la-north-2 --cli-output=json --cli-query='azs[].zone'
```

## Step 2: Write data blocks for existing resources

Convert CLI discoveries into Terraform data blocks. **Never hardcode IDs.**

```hcl
data "huaweicloud_vpc" "prod" {
  name = "prod-vpc"
}

data "huaweicloud_vpc_subnet" "db" {
  name = "db-subnet"
  vpc_id = data.huaweicloud_vpc.prod.id
}

data "huaweicloud_networking_secgroup" "rds" {
  name = "rds-sg"
}

data "huaweicloud_images_image" "ubuntu" {
  name        = "Ubuntu 24.04 server 64bit"
  visibility  = "public"
  most_recent = true
}

data "huaweicloud_availability_zones" "available" {
  state = "available"
}
```

## Step 3: Write resource blocks for new resources

Use `--dryrun` and `--skeleton` to validate parameters, then write the HCL:

```bash
# Validate with dryrun
hcloud --dryrun ECS CreateServers --cli-region=la-north-2 \
  --server.name=web-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID
```

Then write the resource block referencing data blocks:

```hcl
resource "huaweicloud_compute_instance" "web" {
  name               = "web-ecs"
  flavor_id          = "c6.large.2"
  image_id           = data.huaweicloud_images_image.ubuntu.id
  availability_zone  = data.huaweicloud_availability_zones.available.names[0]
  security_group_ids = [data.huaweicloud_networking_secgroup.rds.id]

  network {
    uuid = data.huaweicloud_vpc_subnet.db.id
  }
}
```

## Data block reference

| Resource | Data block type | Key filter(s) | Reference |
|----------|----------------|---------------|-----------|
| VPC | `data "huaweicloud_vpc"` | `name` | `data.huaweicloud_vpc.<name>.id` |
| Subnet | `data "huaweicloud_vpc_subnet"` | `name`, `vpc_id` | `data.huaweicloud_vpc_subnet.<name>.id` |
| Security Group | `data "huaweicloud_networking_secgroup"` | `name` | `data.huaweicloud_networking_secgroup.<name>.id` |
| Image | `data "huaweicloud_images_image"` | `name`, `visibility`, `most_recent` | `data.huaweicloud_images_image.<name>.id` |
| Availability Zones | `data "huaweicloud_availability_zones"` | `state` | `data.huaweicloud_availability_zones.<name>.names[N]` |
| Key Pair | No data block | Use string directly | `"my-key-pair"` |
| RDS Flavor | No data block | Use string directly | `"rds.mysql.x1.large.2"` |
| ECS Flavor | No data block | Use string directly | `"c6.large.2"` |
| Storage Type | No data block | Use string directly | `"ULTRAHIGH"` |

## Resource block patterns

### VPC + Subnet + Security Group

```hcl
resource "huaweicloud_vpc" "main" {
  name = "demo-vpc"
  cidr = "10.0.0.0/16"
}

resource "huaweicloud_vpc_subnet" "main" {
  name       = "demo-subnet"
  vpc_id     = huaweicloud_vpc.main.id
  cidr       = "10.0.0.0/24"
  gateway_ip = "10.0.0.1"
}

resource "huaweicloud_networking_secgroup" "main" {
  name = "demo-sg"
}

resource "huaweicloud_networking_secgroup_rule" "ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = huaweicloud_networking_secgroup.main.id
}
```

### ECS

```hcl
resource "huaweicloud_compute_instance" "web" {
  name               = "web-ecs"
  flavor_id          = "c6.large.2"
  image_id           = data.huaweicloud_images_image.ubuntu.id
  availability_zone  = "la-north-2a"
  key_pair           = "my-key"
  security_group_ids = [huaweicloud_networking_secgroup.main.id]

  network {
    uuid = huaweicloud_vpc_subnet.main.id
  }
}
```

### RDS

```hcl
resource "huaweicloud_rds_instance" "main" {
  name               = "demo-rds"
  flavor             = "rds.mysql.x1.large.2"
  availability_zone  = "la-north-2a"
  security_group_id  = huaweicloud_networking_secgroup.main.id
  subnet_id          = huaweicloud_vpc_subnet.main.id
  vpc_id             = huaweicloud_vpc.main.id

  db {
    type     = "MySQL"
    version  = "8.0"
  }

  volume {
    type = "ULTRAHIGH"
    size = 100
  }

  ha_replication_mode = "semisync"
}
```

### ELB

```hcl
resource "huaweicloud_elb_loadbalancer" "main" {
  name          = "demo-elb"
  vip_subnet_id = huaweicloud_vpc_subnet.main.id
  type          = "External"
}

resource "huaweicloud_elb_listener" "http" {
  name            = "http-listener"
  protocol        = "HTTP"
  protocol_port   = 80
  loadbalancer_id = huaweicloud_elb_loadbalancer.main.id
}
```

## Provider block

Always include. Get the latest version from the Terraform registry or provider docs.

```hcl
terraform {
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> 1.91.0"
    }
  }
}

provider "huaweicloud" {
  region = "la-north-2"
}
```

## Outputs

Always add outputs for created resources:

```hcl
output "ecs_id" {
  value = huaweicloud_compute_instance.web.id
}

output "ecs_public_ip" {
  value = huaweicloud_compute_instance.web.access_ip_v4
}

output "rds_endpoint" {
  value = huaweicloud_rds_instance.main.private_ips[0]
}
```

## CLI → HCL translation rules

| CLI pattern | HCL pattern |
|-------------|-------------|
| `hcloud VPC ListVpcs` → found by name | `data "huaweicloud_vpc"` with `name = "..."` |
| `hcloud IMS ListImages` → found by name | `data "huaweicloud_images_image"` with `name`, `visibility`, `most_recent` |
| `--dryrun` validated params | `resource` block with same params |
| Nested `--vpc.name=X --vpc.cidr=Y` | `resource "huaweicloud_vpc" { name = X, cidr = Y }` |
| Array `--nics.1.subnet_id=X` | `network { uuid = X }` block |
| Hardcoded ID `--vpc_id=abc-123` | Reference: `vpc_id = huaweicloud_vpc.main.id` or `data.huaweicloud_vpc.prod.id` |
| JMESPath query result | `for_each` or `count` with data source |

## Workflow summary

```bash
# 1. Discover existing resources
hcloud VPC ListVpcs ...
hcloud VPC ListSubnets ...
hcloud VPC ListSecurityGroups ...

# 2. Validate create parameters
hcloud --dryrun ECS CreateServers ...

# 3. Write Terraform code (data blocks for existing, resource blocks for new)

# 4. Init and plan
terraform init
terraform plan
```
