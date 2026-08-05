---
name: hcloud-cli-setup
description: Configure hcloud CLI (KooCLI) and MCP server in opencode for Huawei Cloud. Use when setting up hcloud, configuring AK/SK authentication, selecting regions/projects, or troubleshooting hcloud CLI connectivity.
---

# Huawei Cloud CLI (hcloud) Setup for OpenCode

Manage Huawei Cloud infrastructure from within opencode using the `hcloud` CLI (KooCLI v7.2.12+) and the structured MCP tools (`hcloud_hcloud_*`).

## Architecture

```
opencode ──MCP──→ hcloud MCP server ──→ hcloud CLI (KooCLI) ──→ Huawei Cloud API
                       └── structured tools (hcloud_list_servers, hcloud_list_vpcs, etc.)
                       └── generic CLI tool (hcloud_cli) for any operation
                       └── OBS tools (hcloud_obs_ls, hcloud_obs_cat, hcloud_obs_stat)
```

**Two interfaces**: (1) structured MCP tools for common read operations, (2) generic `hcloud_cli` tool for any CLI operation including writes.

## Prerequisites

- **hcloud CLI** (KooCLI) installed at `/usr/local/bin/hcloud`
- **Huawei Cloud account** with AK/SK credentials
- **Project ID** from IAM console

## Step 1: Install hcloud CLI

```bash
# Download KooCLI from Huawei Cloud
# https://support.huaweicloud.com/usermanual-hcli/hcli_01_0001.html
curl -L -o /usr/local/bin/hcloud <hcloud-download-url>
chmod +x /usr/local/bin/hcloud

# Verify
hcloud --version
# Should show: hcloud 7.2.12 or later
```

## Step 2: Configure Authentication

hcloud uses AK/SK (Access Key / Secret Key) authentication. Configure once:

```bash
# Interactive configuration (recommended)
hcloud configure set
# Prompts for:
#   - AK (Access Key ID, e.g. "AKTPxxxxxxxxxxxxxx")
#   - SK (Secret Access Key)
#   - Region (e.g. "la-north-2", "cn-north-4", "ap-southeast-1")

# Or non-interactive
hcloud configure set --cli-access-key=AKTPxxxxxxxxxxxxxx \
                     --cli-secret-key=xxxxxxxxxxxxxxxxxxxxxxxx \
                     --cli-region=la-north-2
```

Verify authentication:

```bash
# List IAM domains (validates AK/SK)
hcloud IAM ListAuthDomains

# Get caller identity
hcloud STS GetCallerIdentity
```

## Step 3: Region and Project Selection

Huawei Cloud regions are named differently from AWS. Common regions:

| Region Code | Location | Notes |
|-------------|----------|-------|
| `la-north-2` | Mexico | Latin America North 2 |
| `cn-north-4` | Beijing-4 | China mainland |
| `cn-east-3` | Shanghai-1 | China mainland |
| `ap-southeast-1` | Hong Kong | Asia Pacific |
| `ap-southeast-2` | Singapore | Asia Pacific |
| `eu-west-1` | Ireland | Europe |
| `sa-brazil-1` | Sao Paulo | South America |

Set default region:

```bash
hcloud configure set --cli-region=la-north-2
```

List projects (IAM projects scope resources):

```bash
# Via MCP
hcloud_list_projects()

# Via CLI
hcloud IAM ListProjects
```

Project ID is required for some operations. Find it in the console or from the API response. Example: `87c1f98546014799bef9d5a56db6dc60`.

## Step 4: Using hcloud CLI

### CLI Syntax

```bash
# List all services
hcloud --help

# List operations for a service
hcloud ECS --help

# Show parameters for an operation
hcloud ECS CreateServers --help

# Execute an operation
hcloud ECS CreateServers --cli-region=la-north-2 --param1=value1 --param2=value2
```

**Key conventions:**
- Parameters use `--param=value` format (equals sign required)
- JSON output is forced automatically (`--cli-output=json`)
- Region specified via `--cli-region=<region>` or set globally
- Destructive operations need `confirm=true` in MCP or run without `--dryrun` in CLI

### Common CLI Patterns

```bash
# List servers in a region
hcloud ECS ListServers --cli-region=la-north-2

# List VPCs
hcloud VPC ListVpcs --cli-region=la-north-2

# List security groups
hcloud VPC ListSecurityGroups --cli-region=la-north-2

# List CCE clusters
hcloud CCE ListClusters --cli-region=la-north-2

# List RDS instances
hcloud RDS ListInstances --cli-region=la-north-2

# List OBS buckets
hcloud obs ls --cli-region=la-north-2
```

## Step 5: Using MCP Tools in OpenCode

The hcloud MCP server provides two types of tools:

### Structured Tools (Read Operations)

Pre-built tools for common queries. Examples:

```
# List ECS servers
hcloud_list_servers(region="la-north-2")

# List VPCs
hcloud_list_vpcs(region="la-north-2")

# List CCE clusters
hcloud_list_cce_clusters(region="la-north-2")

# List RDS instances
hcloud_list_rds_instances(region="la-north-2")

# List security groups
hcloud_list_security_groups(region="la-north-2")

# List images (public Linux images)
hcloud_list_images(region="la-north-2", imagetype="gold", os_type="Linux")

# List flavors (ECS instance types)
hcloud_list_flavors(region="la-north-2")

# List availability zones
hcloud_list_availability_zones(region="la-north-2")

# List keypairs
hcloud_list_keypairs(region="la-north-2")

# List subnets (optionally filtered by VPC)
hcloud_list_subnets(region="la-north-2", vpc_id="...")
```

### Generic CLI Tool (Any Operation)

For operations not covered by structured tools:

```
# Read operation
hcloud_cli(command="IAM ListUsers")

# Write operation (needs confirm=true)
hcloud_cli(command="ECS CreateServers --cli-region=la-north-2 --...", confirm=true)

# OBS operations
hcloud_cli(command="obs ls --cli-region=la-north-2")
hcloud_cli(command="obs cp /local/file obs://bucket/key --cli-region=la-north-2", confirm=true)
```

### OBS-Specific Tools

```
# List buckets or objects
hcloud_obs_ls(region="la-north-2")
hcloud_obs_ls(region="la-north-2", bucket="my-bucket", prefix="folder/")

# View object content (text files)
hcloud_obs_cat(region="la-north-2", bucket="my-bucket", key="config.txt")

# Show bucket/object properties
hcloud_obs_stat(region="la-north-2", bucket="my-bucket")
hcloud_obs_stat(region="la-north-2", bucket="my-bucket", key="file.txt")
```

## Step 6: OBS (Object Storage) with obsutil

OBS uses a separate tool (`obsutil`) for file operations:

```bash
# List buckets
hcloud obs ls --cli-region=la-north-2

# List objects in a bucket
hcloud obs ls obs://my-bucket --cli-region=la-north-2

# Upload a file
hcloud obs cp /local/file.txt obs://my-bucket/file.txt --cli-region=la-north-2

# Download a file
hcloud obs cp obs://my-bucket/file.txt /local/file.txt --cli-region=la-north-2

# Sync a directory (like aws s3 sync)
hcloud obs sync /local/dir/ obs://my-bucket/dir/ --cli-region=la-north-2

# Delete an object
hcloud obs rm obs://my-bucket/file.txt --cli-region=la-north-2  # needs confirm=true in MCP

# Show bucket properties
hcloud obs stat obs://my-bucket --cli-region=la-north-2
```

OBS is S3-compatible. You can also use `aws s3` commands with the OBS endpoint:

```bash
aws s3 ls --endpoint-url=https://obs.la-north-2.myhuaweicloud.com
```

## Step 7: Verify Your Setup

Run these checks to confirm everything works:

```bash
# 1. CLI version
hcloud --version

# 2. Authentication
hcloud IAM ListAuthDomains

# 3. Region access (list VPCs)
hcloud VPC ListVpcs --cli-region=la-north-2

# 4. OBS access
hcloud obs ls --cli-region=la-north-2

# 5. Available services count
hcloud --help | wc -l
```

Via MCP tools:

```
hcloud_list_vpcs(region="la-north-2")          # Should return VPCs
hcloud_list_availability_zones(region="la-north-2")  # Should return AZs
hcloud_list_flavors(region="la-north-2")       # Should return flavors
```

## Current Environment (la-north-2)

| Resource | Count | Details |
|----------|-------|---------|
| VPCs | 2 | `vpc-default-smb` (172.31.0.0/16), `vpc-openwebui` (192.168.0.0/16) |
| Subnets | 2 | `subnet-default-smb` (172.31.0.0/20), `subnet-openwebui` (192.168.0.0/24) |
| Security Groups | 5 | `sg-ecs-s01`, `sg-ecs-s02`, `sg-ecs-s03`, `default`, `sg-default-smb` |
| ECS Servers | 0 | None running |
| CCE Clusters | 0 | None created |
| KeyPairs | 0 | None configured |
| EIPs | 0 | None allocated |
| AZs | 3 | `la-north-2a`, `la-north-2b`, `la-north-2c` |

## Available Volume Types

| Type | Description | AZs |
|------|-------------|-----|
| ESSD | Enhanced SSD | la-north-2a, la-north-2b |
| GPSSD2 | General Purpose SSD v2 | All 3 AZs |
| GPSSD | General Purpose SSD | All 3 AZs |
| SSD | Solid State Drive | All 3 AZs |
| SAS | High I/O SSD | All 3 AZs |

## Common Available Images (la-north-2)

| Image | Platform | Status |
|-------|----------|--------|
| Huawei Cloud EulerOS 2.0 Standard 64 bit | EulerOS | Active |
| CentOS 7.9 64bit | CentOS | EOL |
| CentOS 8.0/8.1/8.2 64bit | CentOS | EOL |

Use `hcloud_list_images(region="la-north-2", imagetype="gold", os_type="Linux")` to get current image IDs.

## Troubleshooting

### Authentication Errors

```
Error: AK/SK authentication failed
```
- Verify AK/SK in `hcloud configure set`
- Ensure AK is not disabled in IAM console
- Check that AK has permissions for the target project

### Region Errors

```
Error: Region not found
```
- Verify region code with `hcloud configure set --cli-region=<region>`
- Ensure your account has access to the region

### OBS Errors

```
Error: obsutil not found
```
- OBS commands use obsutil bundled with hcloud. Reinstall hcloud if missing.
- For S3-compatible access, use `aws s3` with `--endpoint-url=https://obs.<region>.myhuaweicloud.com`

### Destructive Operation Confirmation

In MCP, destructive operations (Delete, Remove, Revoke, Detach) require `confirm=true`. Without it, the command runs in `--dryrun` mode. For OBS commands without dry-run support (rm, abort, mb), `confirm=true` is mandatory.

## AWS ↔ Huawei Cloud Quick Reference

| AWS CLI | hcloud CLI |
|---------|-----------|
| `aws configure` | `hcloud configure set` |
| `aws sts get-caller-identity` | `hcloud STS GetCallerIdentity` |
| `aws ec2 describe-vpcs` | `hcloud VPC ListVpcs --cli-region=...` |
| `aws ec2 describe-instances` | `hcloud ECS ListServers --cli-region=...` |
| `aws s3 ls` | `hcloud obs ls --cli-region=...` |
| `aws eks list-clusters` | `hcloud CCE ListClusters --cli-region=...` |

See the `aws-huaweicloud-migration` skill for the full service mapping.
