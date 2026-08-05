---
name: floci-multicloud
description: Floci multi-cloud emulators for Azure and GCP alongside AWS. Use when setting up local Azure or GCP emulators, or testing multi-cloud scenarios.
---

# Floci Multi-Cloud (Azure + GCP)

Floci provides a unified CLI for three cloud emulators: AWS, Azure, and GCP. Each runs in its own Docker container on a separate port.

## Architecture

```
                    floci CLI (unified)
                   /        |          \
            floci (AWS)  floci az (Azure)  floci gcp (GCP)
            port 4566    port 4577         port 4588
            floci/floci  floci/floci-az    floci/floci-gcp
            ✅ running   ❌ not started    ❌ not started
```

## Prerequisites

- **Docker** running
- **floci CLI** installed (`/usr/local/bin/floci`)
- Disk space for additional Docker images (~200MB each)

## AWS Emulator (already configured)

```bash
floci start          # Port 4566
floci status
floci services       # 69 services
```

See `floci-aws-mcp-setup` skill for full AWS setup.

## Azure Emulator

### Start

```bash
floci az start       # Port 4577 (default)
floci az wait        # Wait until ready
floci az status      # Check health
```

#### Start options

```bash
floci az start --port 4578           # Custom port
floci az start --services storage,cosmos  # Enable only specific services
floci az start --persist ~/.floci-az-state  # Persistent state directory
floci az start --pull always         # Force image pull (always|missing|never)
floci az start --detach              # Return immediately without waiting
floci az start --image floci/floci-az:dev  # Custom image
```

### Environment

```bash
floci az env         # Print Azure env vars
# Exports: AZURE_ENDPOINT_URL, AZURE_TENANT_ID, etc.
eval $(floci az env)
```

### Services

```bash
floci az services    # List available Azure services
```

### Logs and diagnostics

```bash
floci az logs --tail 50
floci az doctor
```

### Restart, version, config

```bash
floci az restart     # Stop and restart
floci az version     # CLI + server version + image digest
floci az config show # Show active configuration
```

### Stop

```bash
floci az stop                    # Stop container
floci az stop --remove           # Also remove container (-r)
floci az stop --timeout 30       # Wait 30s before force kill (default: 10)
```

### Supported Azure services (expected)

| Service | Azure API | Notes |
|---------|-----------|-------|
| Storage | Blob, Queue, Table | Equivalent to S3, SQS, DynamoDB |
| Cosmos DB | SQL, MongoDB, Gremlin | Multi-model DB |
| Functions | Serverless | Equivalent to Lambda |
| Key Vault | Secrets, keys | Equivalent to KMS + Secrets Manager |
| Service Bus | Queues, topics | Equivalent to SQS + SNS |
| Event Grid | Events | Equivalent to EventBridge |
| Resource Manager | IaC | Equivalent to CloudFormation |
| Virtual Network | VNet, subnets | Equivalent to VPC |
| App Service | Web apps | Equivalent to ECS + ALB |

### Connect with Azure CLI

```bash
# Install Azure CLI (if not present)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Configure for floci
az cloud register --name floci \
  --endpoint-resource-manager http://localhost:4577

az cloud set --name floci
az login --use-device-code

# Test
az group list
az storage account list
```

## GCP Emulator

### Start

```bash
floci gcp start      # Port 4588 (default)
floci gcp wait       # Wait until ready
floci gcp status     # Check health
```

#### Start options

```bash
floci gcp start --port 4589           # Custom port
floci gcp start --services storage,firestore  # Enable only specific services
floci gcp start --persist ~/.floci-gcp-state   # Persistent state directory
floci gcp start --pull always         # Force image pull (always|missing|never)
floci gcp start --detach              # Return immediately without waiting
floci gcp start --image floci/floci-gcp:dev  # Custom image
```

### Environment

```bash
floci gcp env        # Print GCP env vars
# Exports: GCP_ENDPOINT_URL, GCP_PROJECT, etc.
eval $(floci gcp env)
```

### Services

```bash
floci gcp services   # List available GCP services
```

### Logs and diagnostics

```bash
floci gcp logs --tail 50
floci gcp doctor
```

### Restart, version, config

```bash
floci gcp restart     # Stop and restart
floci gcp version     # CLI + server version + image digest
floci gcp config show # Show active configuration
```

### Stop

```bash
floci gcp stop                    # Stop container
floci gcp stop --remove           # Also remove container (-r)
floci gcp stop --timeout 30       # Wait 30s before force kill (default: 10)
```

### Supported GCP services (expected)

| Service | GCP API | Notes |
|---------|---------|-------|
| Cloud Storage | gsutil | Equivalent to S3 |
| Firestore | NoSQL | Equivalent to DynamoDB |
| Cloud Functions | Serverless | Equivalent to Lambda |
| Cloud KMS | Key management | Equivalent to KMS |
| Pub/Sub | Messaging | Equivalent to SNS/SQS |
| Cloud Build | CI/CD | Equivalent to CodeBuild |
| Cloud Run | Containers | Equivalent to ECS Fargate |
| Compute Engine | VMs | Equivalent to EC2 |
| VPC | Networking | Equivalent to VPC |
| Secret Manager | Secrets | Equivalent to Secrets Manager |

### Connect with gcloud CLI

```bash
# Install gcloud CLI (if not present)
# https://cloud.google.com/sdk/docs/install

# Configure for floci
gcloud config set api_endpoint_overrides/cloudresourcemanager http://localhost:4588

# Test
gcloud projects list
gcloud storage ls
```

## Multi-Cloud: All Three Running

```bash
# Start all
floci start && floci wait
floci az start && floci az wait
floci gcp start && floci gcp wait

# Check all
floci status
floci az status
floci gcp status

# Stop all
floci stop
floci az stop
floci gcp stop
```

### Port assignments

| Emulator | Port | Image |
|----------|------|-------|
| AWS | 4566 | `floci/floci:latest` |
| Azure | 4577 | `floci/floci-az:latest` |
| GCP | 4588 | `floci/floci-gcp:latest` |

## Verification

### Verify AWS emulator

```bash
floci status
floci services
aws s3 ls                      # Should return empty (no buckets)
curl -s http://localhost:4566/_localstack/health | python3 -m json.tool
```

### Verify Azure emulator

```bash
floci az status
floci az services
curl -s http://localhost:4577/health | python3 -m json.tool  # If endpoint exists
# With Azure CLI configured:
az group list 2>/dev/null || echo "Azure CLI not configured for floci"
```

### Verify GCP emulator

```bash
floci gcp status
floci gcp services
curl -s http://localhost:4588/health | python3 -m json.tool  # If endpoint exists
# With gcloud CLI configured:
gcloud projects list 2>/dev/null || echo "gcloud CLI not configured for floci"
```

### Verify all three at once

```bash
echo "=== AWS ==="  && floci status    2>&1 | grep -E 'Container|Reachable'
echo "=== Azure ===" && floci az status  2>&1 | grep -E 'Container|Reachable'
echo "=== GCP ==="   && floci gcp status 2>&1 | grep -E 'Container|Reachable'
```

## Docker Containers

```bash
# All floci containers
docker ps | grep floci

# Expected when all running:
# floci           (AWS, port 4566)
# floci-az        (Azure, port 4577)
# floci-gcp       (GCP, port 4588)
# + child containers (ECR, EKS, etc.)
```

## Configuration

### Profiles

```bash
# Create named profiles
floci config profile create aws-dev
floci config profile create az-test

# Use profile
floci start --profile aws-dev
floci az start --profile az-test

# List profiles
floci config profile list
```

### Default product

```bash
# Set default (bare commands use this)
floci config default-product aws   # default
floci config default-product az
floci config default-product gcp
```

## Cross-Cloud Testing Patterns

### Pattern 1: Same app, different clouds

Deploy the same application to AWS, Azure, and GCP emulators to test cloud-agnostic code:

```bash
# AWS: S3 bucket
aws s3 mb s3://test-bucket

# Azure: Storage container (if az running)
az storage container create --name test-container

# GCP: Storage bucket (if gcp running)
gcloud storage buckets create gs://test-bucket
```

### Pattern 2: Migration testing

Test migration logic between clouds:

```bash
# Create data in AWS S3
aws s3 cp data.json s3://source-bucket/

# Read from S3, write to Azure Blob
# (custom migration script)

# Verify in Azure
az storage blob list --container-name dest-container
```

### Pattern 3: Multi-cloud IaC

Use Terraform to deploy to multiple clouds:

```hcl
# AWS provider (floci)
provider "aws" {
  endpoint_url = "http://localhost:4566"
  region       = "us-east-1"
  access_key   = "test"
  secret_key   = "test"
}

# Azure provider (floci-az)
provider "azurerm" {
  # Configure for floci-az endpoint
}
```

## Floci Multi-Cloud Quirks

| Aspect | AWS | Azure | GCP |
|--------|-----|-------|-----|
| Maturity | Stable (1.5.33) | Newer | Newer |
| Services | 69 | TBD | TBD |
| Docker-backed | Lambda, RDS, EKS, etc. | TBD | TBD |
| CLI | `aws` | `az` | `gcloud` |
| Auth | `test/test` | TBD | TBD |
| LocalStack compat | Yes | No | No |

## Troubleshooting

### `floci az start` fails with "image not found"

**Cause**: The `floci/floci-az` Docker image hasn't been published yet or isn't available for your platform.

**Fix**:
```bash
floci az doctor
docker pull floci/floci-az:latest
```

### Port conflict

**Cause**: Another service is using port 4577 or 4588.

**Fix**: Check and kill the process, or use a different port:
```bash
lsof -i :4577
floci az start --port 4578  # If custom port supported
```

### Azure/GCP CLI not installed

```bash
# Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# GCP CLI
# See: https://cloud.google.com/sdk/docs/install
```

## Clean Up

### Stop all emulators

```bash
floci stop
floci az stop
floci gcp stop
```

### Stop and remove all containers

```bash
floci stop --remove
floci az stop --remove
floci gcp stop --remove
```

### Remove Docker images (free disk space)

```bash
docker rmi floci/floci:latest       2>/dev/null
docker rmi floci/floci-az:latest    2>/dev/null
docker rmi floci/floci-gcp:latest   2>/dev/null
```

### Full teardown (containers + child containers + images)

```bash
# Stop everything
floci stop --remove 2>/dev/null
floci az stop --remove 2>/dev/null
floci gcp stop --remove 2>/dev/null

# Remove any child containers (ECR, EKS, RDS, etc.)
docker ps -a --filter "name=floci" --format '{{.Names}}' | xargs -r docker rm -f

# Remove images
docker images --filter "reference=floci/*" --format '{{.Repository}}:{{.Tag}}' | xargs -r docker rmi -f
```

## Quick Reference

### Commands

| Command | Purpose |
|---------|---------|
| `floci start` | Start AWS emulator (4566) |
| `floci az start` | Start Azure emulator (4577) |
| `floci gcp start` | Start GCP emulator (4588) |
| `floci az start --services storage,cosmos` | Start Azure with only specific services |
| `floci az start --persist <dir>` | Start Azure with persistent state |
| `floci az start --detach` | Start Azure without waiting for readiness |
| `floci az status` | Azure emulator status |
| `floci gcp status` | GCP emulator status |
| `floci az services` | List Azure services |
| `floci gcp services` | List GCP services |
| `floci az env` | Azure env vars |
| `floci gcp env` | GCP env vars |
| `floci az logs` | Azure emulator logs |
| `floci gcp logs` | GCP emulator logs |
| `floci az restart` | Restart Azure emulator |
| `floci gcp restart` | Restart GCP emulator |
| `floci az version` | Azure CLI + server version + image digest |
| `floci gcp version` | GCP CLI + server version + image digest |
| `floci az stop` | Stop Azure emulator |
| `floci gcp stop` | Stop GCP emulator |
| `floci az stop --remove` | Stop Azure and remove container |
| `floci az stop --timeout 30` | Stop Azure with custom timeout |
| `floci config default-product az` | Set Azure as default |
| `floci config profile create <name>` | Create named profile |
| `floci config profile list` | List profiles |

### Output format

All commands accept `-o text|json|yaml` for structured output:

```bash
floci az status -o json
floci gcp services -o yaml
```

### Files

| File/Dir | Purpose |
|----------|---------|
| `/usr/local/bin/floci` | Floci CLI binary |
| `~/.floci/profiles/` | Named configuration profiles |
| `~/.floci-az-state/` | Azure persistent state (if `--persist` used) |
| `~/.floci-gcp-state/` | GCP persistent state (if `--persist` used) |

## Portability (Replicate on Another PC)

Minimal steps to set up floci multi-cloud on a new machine:

1. **Install Docker** (if not present)
2. **Install floci CLI**: download binary to `/usr/local/bin/floci`, `chmod +x`
3. **Start AWS emulator**: `floci start && floci wait`
4. **Start Azure emulator**: `floci az start && floci az wait`
5. **Start GCP emulator**: `floci gcp start && floci gcp wait`
6. **Install Azure CLI** (optional): `curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`
7. **Install gcloud CLI** (optional): see https://cloud.google.com/sdk/docs/install
8. **Configure Azure CLI for floci**: `az cloud register --name floci --endpoint-resource-manager http://localhost:4577 && az cloud set --name floci && az login --use-device-code`
9. **Configure gcloud CLI for floci**: `gcloud config set api_endpoint_overrides/cloudresourcemanager http://localhost:4588`
10. **Verify**: `floci status`, `floci az status`, `floci gcp status`
