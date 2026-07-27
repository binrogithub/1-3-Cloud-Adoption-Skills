# Service Discovery

Discover available services, operations, and parameters dynamically. Never guess API names — always look them up.

## The Discovery Hierarchy

```
hcloud --help                          → List all services
hcloud <Service> --help                → List all operations for a service
hcloud <Service> <Operation> --help    → Show parameters, types, required/optional
hcloud --skeleton <Service> <Operation> → Generate parameter JSON template
```

## Step 1: Find the service

```bash
hcloud --help
```

This lists all available services. Services are named by their short code (ECS, VPC, RDS, IAM, etc.).

### Service categories (for navigation, not exhaustive)

| Category | Services |
|----------|----------|
| **Compute** | ECS, BMS, AS, CCE, CCI, FunctionGraph, Workspace |
| **Networking** | VPC, EIP, ELB, NAT, VPN, VPCEP, ER, ESW, DNS, GA |
| **Storage** | EVS, OBS, SFS, SFSTurbo, CBR, CBS |
| **Database** | RDS, DDS, DCS, DDM, GaussDB, GaussDBforNoSQL, GaussDBforopenGauss |
| **Security** | IAM, KMS, CSMS, HSS, WAF, CFW, Anti-DDoS, SecMaster, CBH |
| **Governance** | Organizations, IdentityCenter, EPS, TMS, RMS, Config, CTS |
| **Monitoring** | CES, AOM, LTS, SMN, APM |
| **DevOps** | CodeArtsRepo, CodeArtsBuild, CodeArtsDeploy, CodeArtsPipeline, CodeArtsCheck, CloudBuild |
| **Data** | DLI, DIS, DRS, MRS, CSS, DWS, DataArtsStudio |
| **Media** | VOD, MPC, Live, OCR, FRS, Moderation, SIS |
| **IoT** | IoTDA, IoTDM |
| **Other** | IMS, DeH, CDM, ROMA, SWR, SCM, SMS, UGO, COC, CAE |

If you're unsure which service handles a resource, check the [Huawei Cloud API Explorer](https://console-intl.huaweicloud.com/apiexplorer) or search by keyword:

```bash
# List all services and grep for a keyword
hcloud --help 2>&1 | grep -i "dns"
```

## Step 2: Find operations

```bash
hcloud ECS --help
```

This lists all available operations for the service. Operation names follow patterns:

| Pattern | Meaning | Example |
|---------|---------|---------|
| `List*` / `List*Details` | Query/list resources | `ListServersDetails`, `ListVpcs` |
| `Show*` | Get details of a single resource | `ShowServer`, `ShowVpc` |
| `Create*` | Create a resource | `CreateServers`, `CreateVpc` |
| `Update*` / `Change*` / `Modify*` | Update a resource | `UpdateServer`, `ChangeServerOsWithCloudInit` |
| `Delete*` | Delete a resource | `DeleteServers`, `DeleteVpc` |
| `Batch*` | Batch operation | `BatchStartServers`, `BatchDeleteServerTags` |
| `Attach*` / `Detach*` | Attach/detach resources | `AttachServerVolume`, `DetachServerVolume` |
| `Add*` / `Remove*` | Add/remove from collection | `AddFirewallRules`, `RemoveFirewallRules` |
| `Associate*` / `Disassociate*` | Associate/disassociate | `AssociateRouteTable` |
| `Enable*` / `Disable*` | Enable/disable | `EnableEnterpriseProject` |
| `Keystone*` | IAM-specific (Keystone API) | `KeystoneListUsers`, `KeystoneCreateRole` |

### Multi-version APIs

Some operations have version suffixes. The default version is used if no suffix is specified:

```bash
# Default version (v3)
hcloud VPC ListVpcs --cli-region=X

# Explicit version
hcloud VPC ListVpcs/v2 --cli-region=X
```

When you see a message like "ListVpcs is a multi-version API, where the version (v3) is default", you can optionally specify a different version.

## Step 3: Find parameters

```bash
hcloud ECS CreateServers --help
```

This shows all parameters with:

- **required/optional** — whether the parameter is mandatory
- **type** — string, integer, boolean, array
- **location** — path, query, body, header
- **description** — what the parameter does, valid values, constraints

### Parameter patterns

```bash
# Simple parameter
--name=demo-vpc

# Nested body parameter (dot notation)
--vpc.name=demo-vpc
--vpc.cidr=10.0.0.0/16
--vpc.description="Demo VPC"

# Array elements (1-indexed)
--nics.1.subnet_id=xxx
--nics.1.vpc_id=yyy
--nics.2.subnet_id=zzz
--nics.2.vpc_id=www

# Security groups array
--security_groups.1.id=SG_ID

# Tags
--tags.1.key=env
--tags.1.value=prod

# Boolean
--vpc.enable_network_address_usage_metrics=true

# Integer
--limit=100
--offset=0
```

### Required vs optional

Focus on **required** parameters first. Optional parameters have sensible defaults. The `--help` output marks each parameter as `required` or `optional`.

## Step 4: Generate skeleton

For complex operations with many nested parameters, generate a JSON skeleton:

```bash
hcloud --skeleton ECS CreateServers
```

This creates a JSON file with all parameters (required and optional) as placeholders. Edit the file and use it:

```bash
hcloud ECS CreateServers --cli-region=la-north-2 --cli-jsonInput=./ECS_CreateServers_en-*.json
```

### Skeleton workflow

```bash
# 1. Generate skeleton
hcloud --skeleton VPC CreateVpc
# → Created: VPC_CreateVpc_en-20260622.json

# 2. Edit the skeleton — fill in required values, remove unused optional params
# (use Read + Edit tools)

# 3. Dryrun with the skeleton
hcloud --dryrun VPC CreateVpc --cli-region=la-north-2 --cli-jsonInput=./VPC_CreateVpc_en-20260622.json

# 4. Execute
hcloud VPC CreateVpc --cli-region=la-north-2 --cli-jsonInput=./VPC_CreateVpc_en-20260622.json
```

## Common discovery patterns

### Find the right operation for a task

```bash
# "How do I list ECS instances?"
hcloud ECS --help 2>&1 | grep -i "list.*server"
# → ListServersDetails, ListCloudServers

# "How do I resize an ECS?"
hcloud ECS --help 2>&1 | grep -i "resize"
# → BatchResizeServers, ListResizeFlavors

# "How do I create a security group rule?"
hcloud VPC --help 2>&1 | grep -i "security.*rule"
# → BatchCreateSecurityGroupRules, CreateSecurityGroupRule
```

### Find required parameters for an operation

```bash
hcloud RDS CreateInstance --help 2>&1 | grep "required"
```

### Check if an operation supports a parameter

```bash
hcloud ECS CreateServers --help 2>&1 | grep -i "key_name"
```

## Best practices

1. **Always discover before acting** — even if you think you know the API, run `--help` to confirm. APIs evolve between versions.
2. **Use skeleton for complex creates** — it's faster than manually constructing nested `--param=value` chains.
3. **Use dryrun to validate** — catch parameter errors before executing.
4. **Check for multi-version APIs** — if you get unexpected results, try a different API version.
5. **Use `--cli-query` to keep output small** — discovery commands can return large responses. Filter with JMESPath.
