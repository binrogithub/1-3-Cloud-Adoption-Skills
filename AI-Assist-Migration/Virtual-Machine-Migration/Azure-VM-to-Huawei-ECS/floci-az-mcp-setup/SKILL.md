---
name: floci-az-mcp-setup
description: Configure floci-az (local Azure emulator) + custom MCP server + Azure CLI in opencode. Use when setting up floci-az, configuring Azure CLI for local emulation, or interacting with Azure services locally via the MCP server or REST API. Note: @azure/mcp (official Microsoft MCP) is NOT compatible with floci-az because it does not support custom endpoint URLs — a custom Node.js MCP server is used instead.
---

# Floci-AZ + Azure CLI Setup for OpenCode

Run Azure operations from within opencode against a local floci-az emulator (no cloud costs, no network latency) using Azure CLI and REST API.

## Architecture

```
opencode ──MCP──→ floci-az-mcp (Node.js) ──→ floci-az (Docker :4577)
  └── 12 tools: az_call, az_subscriptions_list, az_resourcegroups_*, az_storage_*

opencode ──bash──→ az CLI ──→ Azure SDK (Python) ──→ floci-az (Docker :4577)
                                                               └──→ 20 Azure services emulated locally

opencode ──bash──→ curl ──→ REST API ──→ floci-az (Docker :4577)
```

**Important limitation**: The official `@azure/mcp` server (Microsoft) is a .NET native binary that uses `Azure.Identity` credential chain. It does NOT support custom endpoint URLs — only sovereign clouds (Public, China, US Gov). Therefore it cannot connect to floci-az. This skill provides a **custom Node.js MCP server** (`floci-az-mcp`) that wraps the floci-az REST API, plus Azure CLI (for Storage) and REST API (for ARM) as alternatives.

## Prerequisites

- **Docker** installed and running
- **floci CLI** binary v0.1.8+ (supports `floci az` subcommands)
- **Python 3.10+** for Azure CLI (installed in venv)

## Step 1: Verify floci CLI

```bash
floci version
# Should show: Floci CLI 0.1.8
```

## Step 2: Start Floci-AZ

```bash
floci az start      # Launch the Docker container (floci/floci-az:latest, port 4577)
floci az wait       # Wait until ready to accept requests
floci az status     # Show health and version
```

Floci-AZ runs at `http://localhost:4577` with:
- **Subscription**: `00000000-0000-0000-0000-000000000001`
- **Tenant**: `00000000-0000-0000-0000-000000000002`
- **Storage account**: `devstoreaccount1` (Azurite-compatible format)

### Selective service startup

Start only specific services to save resources:

```bash
floci az start --services=blob,queue,table,arm,cosmos,keyvault
```

### Persistent state

Persist emulator state across restarts:

```bash
floci az start --persist=/home/YOUR_USER/.floci/az-state
```

### Environment variables

```bash
eval $(floci az env)
# Exports:
# AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=<AZURE_STORAGE_EMULATOR_KEY>;BlobEndpoint=http://localhost.floci.io:4577/devstoreaccount1;QueueEndpoint=http://localhost.floci.io:4577/devstoreaccount1-queue;TableEndpoint=http://localhost.floci.io:4577/devstoreaccount1-table;
```

### Health check

```bash
curl -s http://localhost:4577/health | python3 -m json.tool
# Returns: {"status":"UP","version":"0.9.0","edition":"floci-az-always-free"}
```

## Step 3: Install Azure CLI

### Option A: Via pip in a virtual environment (no sudo required)

```bash
python3 -m venv ~/.local/azure-cli-venv
~/.local/azure-cli-venv/bin/pip install azure-cli
ln -sf ~/.local/azure-cli-venv/bin/az ~/.local/bin/az
```

### Option B: Via Microsoft's apt script (requires sudo)

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

Verify:

```bash
az version
# Should show: azure-cli 2.88.0
```

## Step 4: Configure Azure CLI for floci-az

### Storage operations (via connection string)

The Azure CLI can interact with floci-az Storage using the connection string. No cloud registration or login required:

```bash
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=<AZURE_STORAGE_EMULATOR_KEY>;BlobEndpoint=http://localhost:4577/devstoreaccount1;QueueEndpoint=http://localhost:4577/devstoreaccount1-queue;TableEndpoint=http://localhost:4577/devstoreaccount1-table;"

# Test: create a container
az storage container create --name my-container --connection-string "$AZURE_STORAGE_CONNECTION_STRING"

# List containers
az storage container list --connection-string "$AZURE_STORAGE_CONNECTION_STRING" -o table

# Upload a blob
echo "hello" > /tmp/test.txt
az storage blob upload --container-name my-container --name test.txt --file /tmp/test.txt --connection-string "$AZURE_STORAGE_CONNECTION_STRING"

# List blobs
az storage blob list --container-name my-container --connection-string "$AZURE_STORAGE_CONNECTION_STRING" -o table
```

### ARM operations (via REST API)

The Azure CLI requires HTTPS for ARM authentication endpoints, but floci-az uses HTTP. For ARM operations (resource groups, storage accounts, VMs, etc.), use `curl` directly:

```bash
SUB_ID="00000000-0000-0000-0000-000000000001"
API_VER="2021-04-01"

# Create a resource group
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB_ID}/resourceGroups/my-rg?api-version=${API_VER}" \
  -H "Content-Type: application/json" \
  -d '{"location":"eastus"}'

# List resource groups
curl -s "http://localhost:4577/subscriptions/${SUB_ID}/resourceGroups?api-version=${API_VER}" | python3 -m json.tool

# Create a storage account (ARM)
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB_ID}/resourceGroups/my-rg/providers/Microsoft.Storage/storageAccounts/mystore?api-version=2023-01-01" \
  -H "Content-Type: application/json" \
  -d '{"location":"eastus","sku":{"name":"Standard_LRS"},"kind":"StorageV2"}'

# List subscriptions
curl -s http://localhost:4577/subscriptions | python3 -m json.tool
```

## Step 5: Custom MCP Server (floci-az-mcp)

Since `@azure/mcp` cannot connect to floci-az, a custom Node.js MCP server is provided in `mcp-server/`. It exposes 12 tools that wrap the floci-az REST API.

### Installation

```bash
cd ~/.opencode/skills/floci-az-mcp-setup/mcp-server
npm install
```

### opencode.json Configuration

```json
{
  "mcp": {
    "azure": {
      "type": "local",
      "command": ["node", "/home/YOUR_USER/.opencode/skills/floci-az-mcp-setup/mcp-server/index.js"],
      "environment": {
        "FLOCI_AZ_ENDPOINT": "http://localhost:4577",
        "AZ_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000001"
      },
      "enabled": true,
      "timeout": 15000
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `az_call` | Generic REST API call (any method, any path) — escape hatch for all 20 services |
| `az_subscriptions_list` | List all subscriptions |
| `az_resourcegroups_list` | List resource groups in default subscription |
| `az_resourcegroups_create` | Create a resource group (name, location) |
| `az_resourcegroups_delete` | Delete a resource group |
| `az_resources_list` | List resources in a RG, optionally filtered by provider/type |
| `az_storage_containers_list` | List blob containers in devstoreaccount1 |
| `az_storage_container_create` | Create a blob container |
| `az_storage_container_delete` | Delete a blob container |
| `az_storage_blobs_list` | List blobs in a container |
| `az_storage_blob_upload` | Upload text content as a blob |
| `az_storage_blob_download` | Download a blob's content as text |

### Usage Examples (from opencode)

The tools are available as `azure_*` in opencode (e.g. `azure_az_call`, `azure_az_resourcegroups_list`). Use them directly — no bash or curl needed.

For services not covered by dedicated tools (Cosmos DB, Key Vault, Network, AKS, etc.), use `az_call` with the appropriate REST path:

```
# Example: Create a Key Vault via az_call
az_call(method="PUT", path="/subscriptions/.../resourceGroups/my-rg/providers/Microsoft.KeyVault/vaults/my-vault?api-version=2023-07-01", body={location:"eastus", properties:{...}})
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLOCI_AZ_ENDPOINT` | `http://localhost:4577` | floci-az base URL |
| `AZ_SUBSCRIPTION_ID` | `00000000-0000-0000-0000-000000000001` | Default subscription |
| `AZ_STORAGE_ACCOUNT` | `devstoreaccount1` | Storage account name |
| `AZ_STORAGE_KEY` | `Eby8vdM02x...` | Storage account key |

## Step 6: Why @azure/mcp Is NOT Compatible

The official `@azure/mcp` server (v3.0.0-beta.29, Microsoft, 114k downloads/week) cannot be used with floci-az because:

1. **Binary format**: It's a .NET native binary (C#), not Node.js. Distributed as platform-specific native binaries via npm optional dependencies.
2. **Authentication**: Uses `Azure.Identity` credential chain (Workload Identity → Managed Identity → Azure CLI → Interactive Browser). Requires real Azure AD tokens.
3. **No custom endpoints**: Only supports sovereign clouds (`AzureCloud`, `AzureChinaCloud`, `AzureUSGovernment`). The `AZURE_CLOUD` env var rejects URL-like values.
4. **HTTPS enforcement**: The Azure SDK for .NET enforces HTTPS for authentication endpoints. floci-az uses HTTP.

### Alternatives considered

| Option | Compatible? | Notes |
|--------|-------------|-------|
| `@azure/mcp` (official) | No | .NET binary, no custom endpoints |
| `azure-mcp` (Streen9) | No | Uses `DefaultAzureCredential`, no endpoint override |
| **Custom MCP server (`floci-az-mcp`)** | **Yes** | Node.js, wraps floci-az REST API, 12 tools |
| Azure CLI + connection string | **Yes (Storage)** | Works for Blob/Queue/Table Storage |
| REST API (curl) | **Yes (All services)** | Works for all 20 emulated services |

## Supported Services

Floci-AZ emulates 20 Azure services. All verified with REST API calls:

| Service | Access Method | Status |
|---------|--------------|--------|
| Blob Storage | Azure CLI (connection string) + REST | CRUD verified |
| Queue Storage | Azure CLI (connection string) + REST | Functional |
| Table Storage | Azure CLI (connection string) + REST | Functional |
| Cosmos DB | REST API | Functional |
| Key Vault | REST API | Functional |
| App Configuration | REST API | Functional |
| Functions | REST API + Docker | Functional |
| Event Hubs | REST API | Mocked (limited) |
| Service Bus | REST API | Mocked (on-demand) |
| AKS | REST API + k3s | Functional |
| VM | REST API | Mocked (limited) |
| Redis (Cache) | REST API + Valkey | Functional |
| ACR | REST API + registry:2 | Functional |
| Entra ID (AAD) | REST API (OIDC) | Functional (validate-tokens:false) |
| ARM | REST API | CRUD verified (RG, Storage Accounts) |
| Network | REST API | Functional (vnet, subnet, nic, nsg, dns) |
| Managed Identity | REST API (IMDS) | Functional |
| Event Grid | REST API | Functional |
| Monitor | REST API | Functional |
| Email (ACS) | REST API | Functional (captured in-memory) |

## Access Patterns

### Pattern 1: Azure CLI for Storage (connection string)

```bash
# Set the connection string
export AZURE_STORAGE_CONNECTION_STRING=$(floci az env | grep 'AZURE_STORAGE_CONNECTION_STRING=' | cut -d= -f2-)

# Blob operations
az storage container create --name my-container --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
az storage container list --connection-string "$AZURE_STORAGE_CONNECTION_STRING" -o table
az storage blob upload --container-name my-container --name file.txt --file /tmp/file.txt --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
az storage blob list --container-name my-container --connection-string "$AZURE_STORAGE_CONNECTION_STRING" -o table
az storage blob download --container-name my-container --name file.txt --file /tmp/out.txt --connection-string "$AZURE_STORAGE_CONNECTION_STRING"

# Queue operations
az storage queue create --name my-queue --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
az storage message put --queue-name my-queue --content "hello" --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
az storage message peek --queue-name my-queue --connection-string "$AZURE_STORAGE_CONNECTION_STRING"

# Table operations
az storage table create --name my-table --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
az storage entity insert --table-name my-table --entity "PartitionKey=pk RowKey=rk Value=hello" --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
```

### Pattern 2: REST API for ARM (curl)

```bash
SUB="00000000-0000-0000-0000-000000000001"

# Resource groups
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg?api-version=2021-04-01" -H "Content-Type: application/json" -d '{"location":"eastus"}'
curl -s "http://localhost:4577/subscriptions/${SUB}/resourceGroups?api-version=2021-04-01"

# Storage accounts (ARM)
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.Storage/storageAccounts/mystore?api-version=2023-01-01" -H "Content-Type: application/json" -d '{"location":"eastus","sku":{"name":"Standard_LRS"},"kind":"StorageV2"}'

# List all resources in a resource group
curl -s "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/resources?api-version=2021-04-01"

# Subscriptions
curl -s http://localhost:4577/subscriptions
```

### Pattern 3: REST API for Storage (direct)

```bash
# List containers (Blob API)
curl -s "http://localhost:4577/devstoreaccount1/?comp=list"

# Create container
curl -s -X PUT "http://localhost:4577/devstoreaccount1/my-container?restype=container"

# Upload blob
curl -s -X PUT "http://localhost:4577/devstoreaccount1/my-container/hello.txt" -H "x-ms-blob-type: BlockBlob" -d "Hello World"

# List blobs
curl -s "http://localhost:4577/devstoreaccount1/my-container?restype=container&comp=list"
```

### Pattern 4: REST API for other Azure services

#### Cosmos DB

```bash
# List Cosmos DB accounts (ARM)
curl -s "http://localhost:4577/subscriptions/${SUB}/providers/Microsoft.DocumentDB/databaseAccounts?api-version=2023-11-15"

# Create Cosmos DB account
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.DocumentDB/databaseAccounts/my-cosmos?api-version=2023-11-15" \
  -H "Content-Type: application/json" \
  -d '{"location":"eastus","kind":"GlobalDocumentDB","properties":{"databaseAccountOfferType":"Standard"}}'
```

#### Key Vault

```bash
# Create Key Vault (ARM)
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.KeyVault/vaults/my-vault?api-version=2023-07-01" \
  -H "Content-Type: application/json" \
  -d '{"location":"eastus","properties":{"sku":{"family":"A","name":"standard"},"tenantId":"00000000-0000-0000-0000-000000000002","accessPolicies":[]}}'

# List Key Vaults
curl -s "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.KeyVault/vaults?api-version=2023-07-01"
```

#### Network (VNet, Subnet, NSG)

```bash
# Create Virtual Network
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.Network/virtualNetworks/my-vnet?api-version=2024-03-01" \
  -H "Content-Type: application/json" \
  -d '{"location":"eastus","properties":{"addressSpace":{"addressPrefixes":["10.0.0.0/16"]}}}'

# List VNets
curl -s "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.Network/virtualNetworks?api-version=2024-03-01"

# Create Network Security Group
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.Network/networkSecurityGroups/my-nsg?api-version=2024-03-01" \
  -H "Content-Type: application/json" \
  -d '{"location":"eastus","properties":{"securityRules":[]}}'
```

#### Entra ID (Azure AD)

floci-az emulates Entra ID with `validate-tokens:false` — any token is accepted. No authentication needed for ARM calls.

```bash
# The ARM endpoint accepts any request without real auth headers
# All operations work without Bearer token or with a fake one:
curl -s -H "Authorization: Bearer fake-token" http://localhost:4577/subscriptions
```

#### AKS (Kubernetes)

```bash
# Create AKS cluster (ARM) — floci-az uses k3s under the hood
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.ContainerService/managedClusters/my-aks?api-version=2024-02-01" \
  -H "Content-Type: application/json" \
  -d '{"location":"eastus","properties":{"dnsPrefix":"my-aks","agentPoolProfiles":[{"name":"nodepool1","count":1,"vmSize":"Standard_DS2_v2","mode":"System"}]},"identity":{"type":"SystemAssigned"}}'

# List AKS clusters
curl -s "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.ContainerService/managedClusters?api-version=2024-02-01"
```

#### Event Grid

```bash
# Create Event Grid topic
curl -s -X PUT "http://localhost:4577/subscriptions/${SUB}/resourceGroups/my-rg/providers/Microsoft.EventGrid/topics/my-topic?api-version=2023-12-15-preview" \
  -H "Content-Type: application/json" \
  -d '{"location":"eastus","kind":"EventGrid","properties":{"inputSchema":"EventGridSchema"}}'
```

### Pattern 4: From opencode bash tool

Use the `bash` tool in opencode to run any of the above commands. For repeated operations, set the connection string as an environment variable:

```bash
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=<AZURE_STORAGE_EMULATOR_KEY>;BlobEndpoint=http://localhost:4577/devstoreaccount1;QueueEndpoint=http://localhost:4577/devstoreaccount1-queue;TableEndpoint=http://localhost:4577/devstoreaccount1-table;"
```

## Default Infrastructure

Floci-AZ provides:
- **Subscription**: `00000000-0000-0000-0000-000000000001` (display name: "floci-az local")
- **Tenant**: `00000000-0000-0000-0000-000000000002`
- **Storage account**: `devstoreaccount1` (Azurite-compatible, well-known key)
- **Entra ID**: OIDC with `validate-tokens:false` (accepts any token)
- **ARM**: Management plane at root (`/subscriptions`, `/providers`)

No resource groups, VMs, or key vaults exist by default — you must create them.

## Troubleshooting

### Floci-AZ not responding

```bash
floci az doctor       # Diagnose environment issues
floci az restart      # Stop and restart
floci az logs         # Check container logs
```

### Azure CLI login fails with HTTPS error

**Cause**: Azure CLI enforces HTTPS for authentication endpoints. floci-az uses HTTP.

**Fix**: Don't use `az login`. Use connection strings for Storage and REST API (curl) for ARM. See "Access Patterns" above.

### Azure CLI cloud registration fails

**Cause**: `az cloud register` with HTTP endpoints fails because the CLI validates that AD endpoints are HTTPS.

**Fix**: Don't register a custom cloud. Use connection strings and REST API directly.

### Port 4577 already in use

```bash
floci az start --port=4578  # Use different port
docker ps | grep 4577       # Check what's using the port
```

### Storage connection string not working

**Cause**: The `AZURE_STORAGE_CONNECTION_STRING` is not set or uses wrong endpoints.

**Fix**: 
```bash
eval $(floci az env)  # Set the correct connection string
az storage container list --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
```

Note: The connection string from `floci az env` uses `localhost.floci.io:4577` (resolved by an embedded DNS server inside the floci-az container). Both `localhost.floci.io:4577` and `localhost:4577` work for REST API calls from the host. For the Azure CLI connection string, use `localhost:4577` to avoid DNS resolution issues on some systems. If `localhost.floci.io` doesn't resolve, either add it to `/etc/hosts` pointing to `127.0.0.1` or replace it with `localhost` in the connection string.

### Docker container keeps restarting

```bash
docker logs floci-az 2>&1 | tail -50
floci az stop
docker system prune -f
floci az start
```

### `az` command not found

**Cause**: Azure CLI not in PATH.

**Fix**: 
```bash
ln -sf ~/.local/azure-cli-venv/bin/az ~/.local/bin/az
# Or add to PATH: export PATH="$HOME/.local/bin:$PATH"
```

## Quick Reference

### Files

| File | Purpose |
|------|---------|
| `/usr/local/bin/floci` | Floci CLI binary (v0.1.8+) |
| `~/.local/bin/az` | Azure CLI binary (symlink to venv) |
| `~/.local/azure-cli-venv/` | Azure CLI Python venv |
| `~/.opencode/skills/floci-az-mcp-setup/mcp-server/index.js` | Custom MCP server (12 tools) |
| `~/.opencode/skills/floci-az-mcp-setup/mcp-server/package.json` | MCP server dependencies |
| `~/.opencode/opencode.json` | OpenCode config |

### Commands

| Command | Purpose |
|---------|---------|
| `floci az start` | Launch floci-az container |
| `floci az stop` | Stop floci-az container |
| `floci az status` | Show health and version |
| `floci az services` | List available services |
| `floci az doctor` | Diagnose environment issues |
| `floci az env` | Print Azure env vars for floci-az |
| `floci az logs` | Fetch container logs |
| `floci az restart` | Stop and restart |
| `curl -s http://localhost:4577/health` | Health check |
| `az storage container list --connection-string "$CS"` | Test Storage via CLI |
| `curl -s http://localhost:4577/subscriptions` | Test ARM via REST |

### Key Identifiers

| Identifier | Value |
|------------|-------|
| Subscription ID | `00000000-0000-0000-0000-000000000001` |
| Tenant ID | `00000000-0000-0000-0000-000000000002` |
| Storage Account | `devstoreaccount1` |
| Storage Key | `<AZURE_STORAGE_EMULATOR_KEY>` |
| ARM Endpoint | `http://localhost:4577` |
| Blob Endpoint | `http://localhost:4577/devstoreaccount1` |
| Queue Endpoint | `http://localhost:4577/devstoreaccount1-queue` |
| Table Endpoint | `http://localhost:4577/devstoreaccount1-table` |

## Portability (Replicate on Another PC)

Minimal steps to set up floci-az + Azure CLI on a new machine:

1. **Install Docker** (if not present)
2. **Verify floci CLI** v0.1.8+: `floci version`
3. **Start floci-az**: `floci az start && floci az wait`
4. **Install Azure CLI**: `python3 -m venv ~/.local/azure-cli-venv && ~/.local/azure-cli-venv/bin/pip install azure-cli && ln -sf ~/.local/azure-cli-venv/bin/az ~/.local/bin/az`
5. **Set connection string**: `eval $(floci az env)`
6. **Verify Storage**: `az storage container create --name test --connection-string "$AZURE_STORAGE_CONNECTION_STRING"`
7. **Verify ARM**: `curl -s http://localhost:4577/subscriptions`

## Floci-AZ ↔ Huawei Cloud Mapping (for Migration Learning)

| Azure (floci-az) | Huawei Cloud | Notes |
|------------------|-------------|-------|
| AKS Cluster | CCE Cluster | Kubernetes control plane |
| AKS Node Pool | CCE Node Pool | Worker nodes |
| Azure Functions | FunctionGraph | Serverless functions |
| Blob Storage | OBS | Object storage |
| Cosmos DB | GeminiDB | Document/NoSQL DB |
| Azure SQL (via ARM) | RDS | Relational DB |
| Key Vault | DEW | Secrets/key management |
| Event Hubs | DMS | Event streaming |
| Service Bus | DMS | Message queue |
| Event Grid | EG | Event routing |
| Entra ID (AAD) | IAM | Identity management |
| Managed Identity | IAM Agency | Pod identity |
| Virtual Network | VPC | Networking (vnet→VPC, subnet→subnet) |
| Network Security Group | Security Group | 1:1 mapping |
| Public IP | EIP | Elastic IP |
| Azure DNS | DNS | DNS zones |
| Azure Monitor | CES + AOM | Monitoring |
| Azure Cache for Redis | DCS | Redis cache |
| ACR | SWR | Container registry |
| App Configuration | CCE ConfigMap | App config |
| ARM Templates | RFS / AOS | IaC |

## Comparison with AWS (floci) and GCP (floci-gcp) Setup

| Aspect | AWS (floci) | GCP (floci-gcp) | Azure (floci-az) |
|--------|-------------|-----------------|------------------|
| Port | 4566 | 4588 | 4577 |
| Image | floci/floci:latest | floci/floci-gcp:latest | floci/floci-az:latest |
| MCP server | @yawlabs/aws-mcp | gcp-mcp | floci-az-mcp (custom Node.js) |
| MCP tools | 25+ | 9 | 12 |
| CLI tool | aws CLI | gcloud CLI (optional) | az CLI |
| Auth | test/test (dummy) | No auth (emulator) | No auth (emulator) |
| Storage access | aws s3 ls | curl + env vars | MCP tools / az CLI / curl |
| ARM access | aws_aws_call | curl + REST | MCP az_call / curl + REST |
| Services | 50+ | 21 | 20 |
