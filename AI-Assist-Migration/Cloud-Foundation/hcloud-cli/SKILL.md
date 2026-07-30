---
name: hcloud-cli
description: Manage Huawei Cloud resources through KooCLI. Discover before acting — always query existing resources before creating. Use dryrun to validate, waiter to poll async operations.
license: MIT
compatibility: opencode
metadata:
  audience: cloud-engineers
  workflow: huaweicloud-operations
---

# Huawei Cloud CLI (KooCLI)

## Rules

1. **DISCOVER before ACT** — always query existing resources with `List`/`Show` operations before creating or modifying anything. Avoid duplicates. Reuse existing infrastructure when possible.
2. **DRYRUN before EXECUTE** — always `--dryrun` create/update/delete calls first. Show the user what will happen. Only execute after confirmation or when the user has explicitly asked to proceed.
3. **Never hardcode IDs** — use resource names to look up IDs via list operations, then reference the IDs. In Terraform output, use data blocks or resource references.
4. **Use JMESPath** — `--cli-query` to filter output and keep token usage minimal. Never dump full API responses when you only need a few fields.
5. **Use waiter** — `--cli-waiter` for async operations (ECS create, RDS create, CCE create, etc.). Never poll manually with sleep loops.
6. **Discover services dynamically** — `hcloud <Service> --help` to find operations; `hcloud <Service> <Operation> --help` to find parameters. Never guess API names or parameters.
7. **Batch independent queries** — call multiple independent list operations in parallel. Only serialize when there's a dependency (subnets need VPC ID, RDS flavors need engine).
8. **Batch questions** — ask related questions together, not one at a time.
9. **OBS is a separate tool** — `hcloud obs` is obsutil, not a standard hcloud API. It uses single-dash flags (`-flag=value`), `obs://bucket/key` URLs, its own config (`~/.obsutilconfig`), and has no JMESPath/JSON output. See [references/obs.md](references/obs.md).

## Quick Start

```bash
# Check CLI is available
hcloud version

# Verify authentication
hcloud configure test

# Discover available services
hcloud --help

# Discover operations for a service
hcloud ECS --help

# Discover parameters for an operation
hcloud ECS ListServersDetails --help

# List existing resources (the "snapshot")
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'

# Preview a create call without executing
hcloud --dryrun VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# Generate a parameter skeleton for complex operations
hcloud --skeleton ECS CreateServers

# Execute with waiter for async operations
hcloud ECS CreateServers --cli-region=la-north-2 --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' ...
```

## Core Pattern

```bash
hcloud <Service> <Operation> --param1=value1 --param2=value2
```

- **Service**: cloud service name (ECS, VPC, RDS, IAM, etc.)
- **Operation**: API operation name (ListServersDetails, CreateVpc, etc.)
- **Parameters**: `--param=value` format (always `--param=value`, never `--param value`)

### Parameter naming

- Simple params: `--name=demo-vpc`
- Nested params (body objects): `--vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16`
- Array params: `--nics.1.subnet_id=xxx --nics.1.vpc_id=yyy`
- JSON input for complex bodies: `--cli-jsonInput=./params.json`

## Global Options

```bash
# Preview without executing
hcloud --dryrun ECS CreateServers ...

# Generate parameter skeleton in JSON
hcloud --skeleton ECS CreateServers

# Debug mode — print full request/response
hcloud --debug ECS ListServersDetails --cli-region=la-north-2

# Region override
hcloud ECS ListServersDetails --cli-region=ap-southeast-1

# Profile override
hcloud ECS ListServersDetails --cli-profile=prod

# Output format
hcloud VPC ListVpcs --cli-output=json          # JSON (default for scripting)
hcloud VPC ListVpcs --cli-output=table         # ASCII table
hcloud VPC ListVpcs --cli-output=tsv           # Tab-separated

# JMESPath query — filter and project output
hcloud VPC ListVpcs --cli-query='vpcs[].{name:name,id:id}'

# Async polling
hcloud ECS CreateServers --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}'

# Row numbers in table output
hcloud VPC ListVpcs --cli-output=table --cli-output-num

# Custom endpoint
hcloud ECS ListServersDetails --cli-endpoint=https://ecs.custom.example.com

# Timeouts and retries
hcloud ECS ListServersDetails --cli-connect-timeout=10 --cli-read-timeout=30 --cli-retry-count=3

# Skip SSL verification (not recommended)
hcloud ECS ListServersDetails --cli-skip-secure-verify=true

# JSON input file for complex parameters
hcloud ECS CreateServers --cli-jsonInput=./create-ecs-params.json
```

## Discovery (the "snapshot")

Always query before acting. See [references/discovery.md](references/discovery.md) for full patterns.

```bash
# Networking
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'
hcloud VPC ListSubnets --cli-region=X --vpc_id=VPC_ID --cli-output=json --cli-query='subnets[].{name:name,id:id,cidr:cidr}'
hcloud VPC ListSecurityGroups --cli-region=X --cli-output=json --cli-query='security_groups[].{name:name,id:id}'
hcloud EIP ListPublicips --cli-region=X --cli-output=json

# Compute
hcloud ECS ListServersDetails --cli-region=X --cli-output=json --cli-query='servers[].{name:name,id:id,status:status,flavor:flavor.id}'
hcloud ECS ListFlavors --cli-region=X --cli-output=json --cli-query='flavors[].{id:id,vcpus:vcpus,ram:ram}'
hcloud IMS ListImages --cli-region=X --__imagetype=gold --__os_type=Linux --cli-output=json --cli-query='images[].{id:id,name:name}'

# Database
hcloud RDS ListDatastores --cli-region=X --database_name=MySQL --cli-output=json
hcloud RDS ListFlavors --cli-region=X --database_name=MySQL --cli-output=json

# IAM
hcloud IAM KeystoneListUsers --cli-output=json --cli-query='users[].{name:name,id:id}'
hcloud IAM KeystoneListProjects --cli-output=json --cli-query='projects[].{name:name,id:id}'
```

## Creation (with dryrun + waiter)

Always dryrun first. See [references/resource-creation.md](references/resource-creation.md) for full patterns.

```bash
# Step 1: Discover existing resources
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'

# Step 2: Dryrun the create
hcloud --dryrun VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# Step 3: Execute
hcloud VPC CreateVpc --cli-region=la-north-2 --vpc.name=demo-vpc --vpc.cidr=10.0.0.0/16

# Step 4: Verify
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-query='vpcs[?name==`demo-vpc`].{id:id,cidr:cidr}'
```

For async operations, add `--cli-waiter`:

```bash
hcloud ECS CreateServers --cli-region=la-north-2 \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID
```

## Profile & Config

See [references/profile-management.md](references/profile-management.md) for details.

```bash
# Initialize a profile (interactive)
hcloud configure init

# Set AK/SK and region
hcloud configure set --cli-profile=default --access-key=XXX --secret-key=YYY --region=la-north-2

# List profiles
hcloud configure list

# Show current profile
hcloud configure show

# Test connectivity
hcloud configure test

# Delete a profile
hcloud configure delete --cli-profile=old

# SSO authentication
hcloud configure sso
```

## Output & Filtering

```bash
# Full JSON output
hcloud VPC ListVpcs --cli-region=X --cli-output=json

# Project specific fields with JMESPath
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'

# Filter by name
hcloud VPC ListVpcs --cli-region=X --cli-output=json --cli-query='vpcs[?name==`prod-vpc`].{id:id,cidr:cidr}'

# Table output for human review
hcloud VPC ListVpcs --cli-region=X --cli-output=table --cli-output-num

# JMESPath with nested fields
hcloud ECS ListServersDetails --cli-region=X --cli-output=json --cli-query='servers[].{name:name,status:status,flavor:flavor.id,ips:addresses.private[0].addr}'
```

## Async Operations

See [references/waiter-patterns.md](references/waiter-patterns.md) for per-service patterns.

```bash
# Generic waiter pattern
hcloud <Service> <AsyncOperation> --cli-waiter='{"expr":"<jmespath>","to":"<target>","timeout":<seconds>,"interval":<seconds>}'

# ECS — wait for server to become ACTIVE
hcloud ECS CreateServers ... --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}'

# RDS — wait for instance to become ACTIVE
hcloud RDS CreateInstance ... --cli-waiter='{"expr":"instances[0].status","to":"ACTIVE","timeout":600}'

# CCE — wait for cluster to become Available
hcloud CCE CreateCluster ... --cli-waiter='{"expr":"status.phase","to":"Available","timeout":600}'
```

## OBS (Object Storage)

OBS is handled by obsutil — a separate tool with its own commands, config, and syntax. See [references/obs.md](references/obs.md) for full reference.

```bash
# Configure OBS separately (different from hcloud configure)
hcloud obs config -e=https://obs.la-north-2.myhuaweicloud.com -i=AK -k=SK

# List buckets
hcloud obs ls -s

# List objects in a bucket
hcloud obs ls obs://my-bucket/ -s

# Upload a file
hcloud obs cp ./file.txt obs://my-bucket/file.txt

# Upload a folder
hcloud obs cp ./folder/ obs://my-bucket/prefix/ -r

# Download
hcloud obs cp obs://my-bucket/file.txt ./file.txt

# Sync (incremental)
hcloud obs sync ./folder/ obs://my-bucket/prefix/

# Create bucket
hcloud obs mb obs://my-bucket -location=la-north-2

# Delete objects
hcloud obs rm obs://my-bucket/old-prefix/ -r -f

# Generate presigned URL
hcloud obs sign obs://my-bucket/file.txt -e=3600
```

## Debug & Meta

```bash
# Debug — print full request/response details
hcloud --debug ECS ListServersDetails --cli-region=la-north-2

# Download latest API metadata
hcloud meta download

# Clear cached metadata
hcloud meta clear

# Configure logging
hcloud log set
hcloud log show

# Update KooCLI
hcloud update

# Version
hcloud version
```

## System Commands

```bash
hcloud configure init     # Interactive profile setup
hcloud configure set      # Set profile values
hcloud configure list     # List all profiles
hcloud configure show     # Show current profile details
hcloud configure delete   # Delete a profile
hcloud configure test     # Test authentication
hcloud configure clear    # Clear all profiles
hcloud configure sso      # SSO authentication
hcloud meta download      # Download API metadata
hcloud meta clear         # Clear metadata cache
hcloud log set            # Configure logging
hcloud log show           # Show log config
hcloud update             # Update KooCLI
hcloud version            # Print version
hcloud auto-complete on   # Enable shell autocomplete
hcloud auto-complete off  # Disable shell autocomplete
```

## Examples

### Example: Discover and create ECS

```bash
# 1. Discover existing networking
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id,cidr:cidr}'
# → prod-vpc (10.0.0.0/16) id=e00f74ba-...

hcloud VPC ListSubnets --cli-region=la-north-2 --vpc_id=e00f74ba-59ec-4609-9522-981d8273522f --cli-output=json --cli-query='subnets[].{name:name,id:id,cidr:cidr}'

hcloud VPC ListSecurityGroups --cli-region=la-north-2 --cli-output=json --cli-query='security_groups[].{name:name,id:id}'

# 2. Discover compute options
hcloud ECS ListFlavors --cli-region=la-north-2 --availability_zone=la-north-2a --cli-output=json --cli-query='flavors[].{id:id,name:name,vcpus:vcpus,ram:ram}'

hcloud IMS ListImages --cli-region=la-north-2 --__imagetype=gold --__os_type=Linux --__platform=Ubuntu --cli-output=json --cli-query='images[].{id:id,name:name}'

# 3. Generate skeleton for create
hcloud --skeleton ECS CreateServers

# 4. Dryrun
hcloud --dryrun ECS CreateServers --cli-region=la-north-2 \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID

# 5. Execute with waiter
hcloud ECS CreateServers --cli-region=la-north-2 \
  --cli-waiter='{"expr":"server.status","to":"ACTIVE","timeout":300}' \
  --server.name=demo-ecs \
  --server.flavor_ref=c6.large.2 \
  --server.image_ref=IMAGE_ID \
  --server.availability_zone=la-north-2a \
  --nics.1.subnet_id=SUBNET_ID \
  --nics.1.vpc_id=VPC_ID \
  --security_groups.1.id=SG_ID

# 6. Verify
hcloud ECS ListServersDetails --cli-region=la-north-2 --name=demo-ecs --cli-output=json --cli-query='servers[].{name:name,id:id,status:status}'
```

### Example: Multi-region query

```bash
# Query the same resource across regions (parallel)
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
hcloud VPC ListVpcs --cli-region=ap-southeast-1 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
hcloud VPC ListVpcs --cli-region=eu-west-101 --cli-output=json --cli-query='vpcs[].{name:name,id:id}'
```

### Example: Find and delete a resource

```bash
# 1. Find by name
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`old-vpc`].id'

# 2. Dryrun delete
hcloud --dryrun VPC DeleteVpc --cli-region=la-north-2 --vpc_id=VPC_ID

# 3. Execute
hcloud VPC DeleteVpc --cli-region=la-north-2 --vpc_id=VPC_ID

# 4. Verify it's gone
hcloud VPC ListVpcs --cli-region=la-north-2 --cli-output=json --cli-query='vpcs[?name==`old-vpc`]'
```

### Example: Upload files to OBS

```bash
# 1. Configure OBS (if not already done)
hcloud obs config -e=https://obs.la-north-2.myhuaweicloud.com -i=AK -k=SK

# 2. List existing buckets
hcloud obs ls -s

# 3. Create bucket if needed
hcloud obs mb obs://my-bucket -location=la-north-2

# 4. Dryrun upload
hcloud obs cp ./data/ obs://my-bucket/data/ -r -dryRun

# 5. Upload
hcloud obs cp ./data/ obs://my-bucket/data/ -r

# 6. Verify
hcloud obs ls obs://my-bucket/data/ -s
```

## Specific tasks

* **Discovering services and operations** [references/service-discovery.md](references/service-discovery.md)
* **Querying existing resources** [references/discovery.md](references/discovery.md)
* **Creating, updating, and deleting resources** [references/resource-creation.md](references/resource-creation.md)
* **Async operation polling patterns** [references/waiter-patterns.md](references/waiter-patterns.md)
* **Profile and authentication management** [references/profile-management.md](references/profile-management.md)
* **Generating Terraform from CLI discoveries** [references/terraform-generation.md](references/terraform-generation.md)
* **Audit and compliance operations** [references/audit-compliance.md](references/audit-compliance.md)
* **OBS object storage (obsutil)** [references/obs.md](references/obs.md)
