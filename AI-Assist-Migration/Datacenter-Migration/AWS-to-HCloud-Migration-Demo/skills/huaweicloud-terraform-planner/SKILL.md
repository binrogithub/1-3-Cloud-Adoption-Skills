---
name: huaweicloud-terraform-planner
description: Plan and write Terraform for Huawei Cloud by discovering real values from the live cloud and asking the user for decisions. Never guesses — always verifies with the latest provider schema.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: terraform-huaweicloud
---

# Huawei Cloud Terraform Planner

Always get the latest schema — the provider evolves fast and training data is always outdated. Discover real values from the cloud. Only ask about what the user hasn't already told you. Use data blocks, not hardcoded IDs.

## Rules

1. **ALWAYS get schema from Terraform MCP** — the `huaweicloud` provider changes rapidly. Your training data is stale. Every resource, every time.
2. **ALWAYS get the latest provider version** — call `terraform_get_latest_provider_version(namespace="huaweicloud", name="huaweicloud")` before writing any code.
3. **NEVER hardcode resource IDs** — use `data` blocks for existing resources and resource references for created resources. See Data Block Map below.
4. **Only discover and ask about GAPS** — if the user said "MySQL 8.0 in the prod VPC", don't ask which engine or which VPC. Parse their intent first.
5. **Batch parallel discoveries** — call multiple independent HCloud tools at once. Only serialize when there's a dependency (subnets need VPC, RDS flavors need engine).
6. **Batch questions** — ask related questions together, not one at a time.
7. **Recommend defaults** — when intent is clear but value isn't specified, recommend a sensible default and show alternatives.
8. **Reuse existing infrastructure** — before creating new VPCs/subnets/SGs, check if existing ones match. Ask "use existing X or create new?" Default to reuse.
9. **Don't ask when only 1 option** — just use it and tell the user.

## Workflow

### Step 1: PARSE INTENT

Extract from the user's request:

- **Region** — required. Ask if not specified.
- **Resource type(s)** — what to create (ECS, RDS, ELB, CCE, VPC, etc.)
- **Already specified** — any values the user provided directly (engine, version, VPC name, subnet name, flavor, AZ, storage type, volume size, HA mode, etc.)
- **Gaps** — required values the user did NOT specify. These need discovery.

Example: `"RDS MySQL 8.0 with HA, 100GB ULTRAHIGH, in prod-vpc, db-subnet, rds-sg, la-north-2a standby la-north-2b"` →

- Region: not specified → **ask**
- Engine: MySQL, Version: 8.0 → **already given**
- HA: yes, primary AZ: la-north-2a, standby AZ: la-north-2b → **already given**
- Storage: ULTRAHIGH, Size: 100GB → **already given**
- VPC: prod-vpc, Subnet: db-subnet, SG: rds-sg → **already given** (but verify they exist)
- Flavor: not specified → **discover + ask**

### Step 2: SCHEMA (always, no exceptions)

For **every** resource type:

1. `terraform_get_latest_provider_version(namespace="huaweicloud", name="huaweicloud")` → latest version
2. `terraform_search_providers(provider_name="huaweicloud", provider_namespace="huaweicloud", service_slug="<resource>", provider_document_type="resources")` → find doc
3. `terraform_get_provider_details(provider_doc_id="<id>")` → full schema with required + optional params

Also search for **data sources** (`provider_document_type="data-sources"`) to find available data blocks for referencing existing resources.

This is mandatory even for resources you think you know. The provider changes between versions — params get renamed, deprecated, or added.

### Step 3: DISCOVER (only gaps)

For each value the user did NOT specify, call the corresponding HCloud MCP tool from the Discovery Map below.

**Batch independent calls in parallel:**
```
// All independent — call simultaneously:
hcloud_list_flavors(region="la-north-2")
hcloud_list_images(imagetype="gold", os_type="Linux")
hcloud_list_availability_zones(region="la-north-2")
hcloud_list_vpcs(region="la-north-2")
hcloud_list_security_groups(region="la-north-2")
```

**Then call dependent ones:**
```
// Subnets depend on VPC choice:
hcloud_list_subnets(vpc_id="<chosen-vpc-id>")
```

**When the user specified a name** (e.g. "prod-vpc"), find it by name in the list results. If found, note its name for the data block. If not found, tell the user and ask.

**When the user specified an ID directly**, verify it exists by checking the list results.

### Step 4: ASK (only gaps)

Only ask about values that are:
- NOT already specified by the user
- Have multiple options
- Cannot be reasonably inferred from intent

**Format questions clearly:**
- Flavors: show `name — N vCPU, M GB` and recommend based on workload
- Images: show `OS Version (arch)` and recommend latest LTS
- AZs: show zone names
- VPCs: show `name (CIDR)`
- Subnets: show `name (CIDR)`
- Security Groups: show `name`
- Storage types: show type name

**Batch related questions.** Instead of 6 separate asks, do one:
```
"I found these options for your RDS instance:
 • Flavors: [list with recommendation]
 • Availability zones: [list]
 Which would you like?"
```

### Step 5: WRITE

Write complete Terraform code with:

1. **Provider block** — with the latest version from Step 2
2. **Data blocks** — for all existing resources being referenced (images, VPCs, subnets, security groups). See Data Block Map below.
3. **Resource blocks** — for resources being created. Reference data blocks or other resources, never hardcode IDs.
4. **Outputs** — useful outputs (instance IDs, IPs, endpoints) for each resource

**Critical: Data blocks vs hardcoded IDs**

NEVER hardcode an ID like `image_id = "b1eecdf6-..."` or `security_group_ids = ["7d730547-..."]`.

Instead, write a data block and reference it:
```hcl
data "huaweicloud_images_image" "ubuntu" {
  name        = "Ubuntu 24.04 server 64bit"
  visibility  = "public"
  most_recent = true
}

resource "huaweicloud_compute_instance" "web" {
  image_id = data.huaweicloud_images_image.ubuntu.id
}
```

For resources being CREATED (not referenced), use resource references:
```hcl
resource "huaweicloud_vpc" "main" { ... }
resource "huaweicloud_vpc_subnet" "main" {
  vpc_id = huaweicloud_vpc.main.id
}
```

Then offer: `terraform init && terraform plan`

## Data Block Map

When referencing existing resources, always use data blocks. When creating resources, use resource references. Never hardcode IDs.

| What | Data Block | How to reference | Example |
|------|-----------|-----------------|---------|
| Image | `data "huaweicloud_images_image"` | `data.huaweicloud_images_image.<name>.id` | `name = "Ubuntu 24.04 server 64bit", visibility = "public", most_recent = true` |
| VPC | `data "huaweicloud_vpc"` | `data.huaweicloud_vpc.<name>.id` | `name = "prod-vpc"` |
| Subnet | `data "huaweicloud_vpc_subnet"` | `data.huaweicloud_vpc_subnet.<name>.id` | `name = "db-subnet"` |
| Security Group | `data "huaweicloud_networking_secgroup"` | `data.huaweicloud_networking_secgroup.<name>.id` | `name = "default"` |
| Availability Zones | `data "huaweicloud_availability_zones"` | `data.huaweicloud_availability_zones.<name>.names[0]` | `state = "available"` |
| Key Pair | **No data block** — use string directly | `"my-key"` | Key pair names are stable strings |
| RDS Flavor | **No data block** — use string directly | `"rds.mysql.x1.large.2"` | Flavor names are stable strings |
| Storage Type | **No data block** — use string directly | `"ULTRAHIGH"` | Storage type names are stable strings |
| ECS Flavor | **No data block** — use string directly | `"c6.large.2"` | Flavor names are stable strings |

**How to decide:**
- If a `data` source exists in the provider → use it
- If the value is a stable string name (flavor, storage type) → use it directly
- If the resource is being created in the same config → use resource reference (`huaweicloud_vpc.main.id`)
- If the resource already exists outside this config → use data block

## Discovery Map

Generic map of "what you need" → "which HCloud tool to call". Compose these based on the resource schema from Step 2. Discovery confirms what exists so you can write correct data block filters.

| Need | Tool | Dependencies |
|------|------|-------------|
| VPC | `hcloud_list_vpcs` | — |
| Subnet | `hcloud_list_subnets` | `vpc_id` (after VPC chosen) |
| Security Group | `hcloud_list_security_groups` | — |
| ECS Flavor | `hcloud_list_flavors` | — |
| RDS Flavor | `hcloud_list_rds_flavors` | `database_name` (after engine chosen) |
| Image | `hcloud_list_images` | — |
| Availability Zone | `hcloud_list_availability_zones` | — |
| Key Pair | `hcloud_list_keypairs` | — |
| RDS Datastore | `hcloud_list_rds_datastores` | `database_name` |
| RDS Storage | `hcloud_list_rds_storage_types` | `database_name`, `version_name` |
| ELB Flavor | `hcloud_list_elb_flavors` | — |
| DCS Flavor | `hcloud_list_dcs_flavors` | — |
| DCS AZ | `hcloud_list_dcs_available_zones` | — |
| DDS Flavor | `hcloud_list_dds_flavors` | — |
| DDS Storage | `hcloud_list_dds_storage_types` | — |

**How to use this:** Look at the resource schema from Step 2. For each required parameter that the user didn't specify, find its type in this map and call the tool. If "Dependencies" shows a value, that value must be resolved first. Use the discovered names/values to write data block filters.

## Provider Block

Always include. Get version from `terraform_get_latest_provider_version(namespace="huaweicloud", name="huaweicloud")`.

```hcl
terraform {
  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = "~> X.Y.Z"
    }
  }
}

provider "huaweicloud" {
  region = "<region>"
}
```

## Examples

### ECS with Ubuntu 24.04

**User:** "Create a VPC, subnet, and ECS with latest Ubuntu 24.04 in la-north-2"

**Agent:**
1. **PARSE:** Region=la-north-2, Resources=VPC+subnet+ECS, OS=Ubuntu 24.04. **Gaps: flavor, AZ, security group, key pair**
2. **SCHEMA:** Get schemas for `huaweicloud_vpc`, `huaweicloud_vpc_subnet`, `huaweicloud_compute_instance` from Terraform MCP. Also get data sources for `huaweicloud_images_image`, `huaweicloud_availability_zones`. Latest provider: 1.91.0.
3. **DISCOVER:** Batch: `hcloud_list_flavors`, `hcloud_list_images(imagetype="gold", os_type="Linux")`, `hcloud_list_availability_zones`, `hcloud_list_security_groups`, `hcloud_list_keypairs`.
4. **ASK:** "Which flavor, AZ, security group, and key pair?" with recommendations.
5. **WRITE:**
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

data "huaweicloud_images_image" "ubuntu" {
  name        = "Ubuntu 24.04 server 64bit"
  visibility  = "public"
  most_recent = true
}

resource "huaweicloud_vpc" "main" {
  name = "vpc-demo"
  cidr = "192.168.0.0/16"
}

resource "huaweicloud_vpc_subnet" "main" {
  name       = "subnet-demo"
  vpc_id     = huaweicloud_vpc.main.id
  cidr       = "192.168.0.0/24"
  gateway_ip = "192.168.0.1"
}

resource "huaweicloud_networking_secgroup" "main" {
  name = "sg-demo"
}

resource "huaweicloud_compute_instance" "main" {
  name               = "ecs-ubuntu2404"
  flavor_id          = "c6.large.2"
  image_id           = data.huaweicloud_images_image.ubuntu.id
  availability_zone  = "la-north-2a"
  security_group_ids = [huaweicloud_networking_secgroup.main.id]

  network {
    uuid = huaweicloud_vpc_subnet.main.id
  }
}
```

### RDS with HA (detailed request)

**User:** "I need an RDS MySQL 8.0 with HA, 100GB ULTRAHIGH, in prod-vpc, db-subnet, rds-sg, la-north-2a standby la-north-2b"

**Agent:**
1. **PARSE:** Region=la-north-2, engine=MySQL, version=8.0, HA=yes, storage=ULTRAHIGH, size=100, vpc=prod-vpc, subnet=db-subnet, sg=rds-sg, AZ=la-north-2a/2b. **Gap: flavor_ref**
2. **SCHEMA:** Get `huaweicloud_rds_instance` schema from Terraform MCP. Latest provider: 1.91.0.
3. **DISCOVER:** Only the gap — `hcloud_list_rds_flavors(region="la-north-2", database_name="MySQL")`. Also verify VPC/subnet/SG exist.
4. **ASK:** "Which flavor? Recommended: rds.mysql.x1.large.2 (4 vCPU, 16 GB) for HA."
5. **WRITE:** Uses `data` blocks for VPC, subnet, and security group instead of hardcoded IDs.
