# Local Cloud Emulators (floci) — Migration Toolkit

Run AWS, Azure, and GCP operations locally against [floci](https://github.com/nickvdyck/floci) emulators — no cloud costs, no network latency, no real credentials — then plan and practice migrations to Huawei Cloud.

## What is floci?

Floci is a local cloud emulator that runs AWS (50+ services), Azure (20 services), and GCP (21 services) in Docker containers on your machine. It provides REST-compatible APIs so that cloud CLIs, SDKs, and MCP servers work against local endpoints instead of real cloud accounts.

| Emulator | Port | Services | Docker Image |
|----------|------|----------|-------------|
| floci (AWS) | 4566 | 50+ | `floci/floci:latest` |
| floci-az (Azure) | 4577 | 20 | `floci/floci-az:latest` |
| floci-gcp (GCP) | 4588 | 21 | `floci/floci-gcp:latest` |

## Architecture

```
opencode ──MCP──→ cloud MCP server ──→ cloud SDK ──→ floci (Docker)
                                                              └──→ emulated services
```

Each emulator has a dedicated MCP server that exposes cloud operations as tools in opencode:

| Cloud | MCP Server | Tools | Setup Skill |
|-------|-----------|-------|-------------|
| AWS | `@yawlabs/aws-mcp` | 25+ | [floci-aws-mcp-setup/SKILL.md](./floci-aws-mcp-setup/SKILL.md) |
| Azure | `floci-az-mcp` (custom) | 12 | [floci-az-mcp-setup/SKILL.md](./floci-az-mcp-setup/SKILL.md) |
| GCP | `gcp-mcp` | 9 | [floci-gcp-mcp-setup/SKILL.md](./floci-gcp-mcp-setup/SKILL.md) |

## Setup

### Prerequisites (all clouds)

- **Docker** installed and running
- **Node.js v24+** via nvm
- **floci CLI** binary v0.1.8+

### AWS (floci)

```bash
floci start && floci wait        # Start emulator on port 4566
eval $(floci env)                # Export AWS env vars
npm install -g @yawlabs/aws-mcp  # Install MCP server
```

Configure opencode.json with the MCP entry. See [floci-aws-mcp-setup/SKILL.md](./floci-aws-mcp-setup/SKILL.md) for full instructions.

### Azure (floci-az)

```bash
floci az start && floci az wait  # Start emulator on port 4577
eval $(floci az env)             # Export Azure env vars
```

**Important**: The official `@azure/mcp` (Microsoft) does NOT work with floci-az because it requires HTTPS and real Azure AD tokens. A **custom Node.js MCP server** is provided in [floci-az-mcp-setup/mcp-server/](./floci-az-mcp-setup/mcp-server/).

```bash
cd floci-az-mcp-setup/mcp-server
npm install                      # Install MCP server dependencies
```

See [floci-az-mcp-setup/SKILL.md](./floci-az-mcp-setup/SKILL.md) for full instructions.

### GCP (floci-gcp)

```bash
floci gcp start && floci gcp wait  # Start emulator on port 4588
eval $(floci gcp env)              # Export GCP emulator env vars
npm install -g gcp-mcp             # Install MCP server
```

A fake service account key is required to prevent the MCP server from crashing. See [floci-gcp-mcp-setup/SKILL.md](./floci-gcp-mcp-setup/SKILL.md) for full instructions.

## Migration Scenarios

Each emulator supports discovering and creating cloud resources locally. Use these to practice migrations to Huawei Cloud without real cloud accounts.

### AWS (floci) → Huawei Cloud

| AWS Service (floci) | Huawei Cloud | Migration Type | Notes |
|---------------------|-------------|----------------|-------|
| EKS | CCE | Kubernetes | Control plane + node groups → node pools |
| EC2 | ECS | Virtual machine | Instance type mapping, EBS → EVS |
| ECR | SWR | Container registry | Image migration, re-tagging |
| RDS | RDS | Database | DRS for replication, dump/restore |
| S3 | OBS | Object storage | Bucket sync, lifecycle policies |
| DynamoDB | GeminiDB | NoSQL | Table structure, data export |
| Lambda | FunctionGraph | Serverless | Function code, triggers, layers |
| SQS | DMS | Message queue | Queue migration, consumer reconfiguration |
| ELB (ALB/NLB) | ELB | Load balancing | Listener, target group mapping |
| KMS | KMS | Key management | Key import, alias mapping |
| Secrets Manager | DEW | Secrets | Secret rotation policies |
| VPC + Subnets | VPC + Subnets | Networking | CIDR, route table, gateway mapping |
| Security Groups | Security Groups | Security | Rule-by-rule mapping |
| Route53 | DNS | DNS | Zone, record migration |
| CloudFormation | RFS / AOS | IaC | Template conversion |
| EBS | EVS | Block storage | Volume type, snapshot migration |
| IAM | IAM | Identity | Role → agency, policy mapping |

### Azure (floci-az) → Huawei Cloud

| Azure Service (floci-az) | Huawei Cloud | Migration Type | Notes |
|--------------------------|-------------|----------------|-------|
| AKS | CCE | Kubernetes | Cluster config, node pool mapping |
| Blob Storage | OBS | Object storage | Container → bucket, blob sync |
| Cosmos DB | GeminiDB | Document DB | Collection, partition key mapping |
| Azure SQL | RDS | Database | DRS, bacpac import |
| Azure Functions | FunctionGraph | Serverless | Function app, bindings conversion |
| Key Vault | DEW | Secrets | Key, secret migration |
| Event Hubs | DMS | Event streaming | Topic, consumer group mapping |
| Service Bus | DMS | Message queue | Queue, topic migration |
| ACR | SWR | Container registry | Image migration |
| VNet | VPC | Networking | Address space, subnet mapping |
| NSG | Security Group | Security | Rule mapping |
| Azure Cache for Redis | DCS | Redis | Instance migration, data sync |
| Entra ID (AAD) | IAM | Identity | User, group, app registration |
| ARM Templates | RFS / AOS | IaC | Template conversion |

### GCP (floci-gcp) → Huawei Cloud

| GCP Service (floci-gcp) | Huawei Cloud | Migration Type | Notes |
|-------------------------|-------------|----------------|-------|
| GKE | CCE | Kubernetes | Cluster config, node pool mapping |
| Cloud Run | CCE Volcano | Serverless containers | Service, revision migration |
| GCS | OBS | Object storage | Bucket sync, lifecycle |
| BigQuery | GaussDB (DWS) | Data warehouse | Dataset, table, view migration |
| Cloud SQL | RDS | Database | DRS, dump/restore |
| Firestore | GeminiDB | Document DB | Collection, document migration |
| Pub/Sub | DMS | Message queue | Topic, subscription migration |
| Secret Manager | DEW | Secrets | Secret migration |
| Cloud Functions | FunctionGraph | Serverless | Function, trigger conversion |
| KMS | KMS | Key management | Key ring, key migration |
| VPC | VPC | Networking | Network, subnet, firewall rules |
| Cloud Logging | LTS | Log management | Log group, stream mapping |
| Cloud Monitoring | CES | Monitoring | Metric, alarm mapping |

## Example: EKS (AWS) → CCE (Huawei Cloud)

### Step 1: Discover source infrastructure with floci

```bash
# Start floci
floci start && floci wait

# Create an EKS cluster locally
aws iam create-role --role-name eks-role --assume-role-policy-document file://trust-policy.json
aws eks create-cluster --name my-cluster --role-arn arn:aws:iam::000000000000:role/eks-role \
  --resources-vpc-config subnetIds=subnet-default-a,subnet-default-b,subnet-default-c

# List clusters
aws eks list-clusters
```

### Step 2: Analyze with opencode + MCP

Use the `aws_aws_call` MCP tool to inspect the EKS cluster configuration:

```
aws_aws_call(service="eks", operation="describe-cluster", params={name: "my-cluster"})
```

### Step 3: Plan migration to CCE

Map the EKS configuration to CCE equivalents:

| EKS Config | CCE Equivalent |
|-----------|----------------|
| Cluster name | CCE cluster name |
| Role ARN | IAM agency |
| Subnet IDs | CCE subnet IDs |
| Node group | Node pool |
| VPC | VPC |

### Step 4: Execute migration

Use existing CCE migration skills from this repository:

- [CCE Local to Cloud Migration](../../Application-Modernization/Container-Migration/cce-local-to-cloud/) — Kind → CCE
- [CCE Cross-Region Migration](../../Application-Modernization/Container-Migration/cce-cross-region-velero-migration/) — CCE → CCE (Velero)
- [Kind to CCE Migration](../../Application-Modernization/Container-Migration/kind-to-cce-migration/) — step-by-step

## Custom Azure MCP Server

The `floci-az-mcp` server in [floci-az-mcp-setup/mcp-server/](./floci-az-mcp-setup/mcp-server/) is a custom Node.js MCP server that wraps the floci-az REST API. It exposes 12 tools:

| Tool | Description |
|------|-------------|
| `az_call` | Generic REST API call (any method, any path) |
| `az_subscriptions_list` | List all subscriptions |
| `az_resourcegroups_list` | List resource groups |
| `az_resourcegroups_create` | Create a resource group |
| `az_resourcegroups_delete` | Delete a resource group |
| `az_resources_list` | List resources in a RG |
| `az_storage_containers_list` | List blob containers |
| `az_storage_container_create` | Create a blob container |
| `az_storage_container_delete` | Delete a blob container |
| `az_storage_blobs_list` | List blobs in a container |
| `az_storage_blob_upload` | Upload text as a blob |
| `az_storage_blob_download` | Download a blob's content |

### Why not @azure/mcp?

The official `@azure/mcp` (Microsoft) is a .NET native binary that:
1. Uses `Azure.Identity` credential chain (requires real Azure AD tokens)
2. Only supports sovereign clouds (Public, China, US Gov)
3. Enforces HTTPS for authentication endpoints
4. Cannot connect to floci-az (HTTP, no real auth)

The custom server bypasses all of these by directly calling the floci-az REST API.

## Comparison

| Aspect | AWS (floci) | Azure (floci-az) | GCP (floci-gcp) |
|--------|-------------|------------------|-----------------|
| Port | 4566 | 4577 | 4588 |
| Services | 50+ | 20 | 21 |
| MCP server | @yawlabs/aws-mcp | floci-az-mcp (custom) | gcp-mcp |
| MCP tools | 25+ | 12 | 9 |
| CLI | aws CLI | az CLI | gcloud (optional) |
| Auth | test/test (dummy) | No auth (emulator) | Fake SA key |
| Migration scenarios | 16 | 14 | 13 |
