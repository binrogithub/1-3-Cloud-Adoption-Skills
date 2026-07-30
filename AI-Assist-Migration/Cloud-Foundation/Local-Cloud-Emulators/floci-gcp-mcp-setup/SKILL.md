---
name: floci-gcp-mcp-setup
description: Configure floci-gcp (local GCP emulator) + gcp-mcp server in opencode. Use when setting up floci-gcp, configuring GCP client libraries for local emulation, or troubleshooting the MCP connection to floci-gcp.
---

# Floci-GCP + GCP MCP Setup for OpenCode

Run GCP operations from within opencode against a local floci-gcp emulator (no cloud costs, no network latency) using the `gcp-mcp` MCP server.

## Architecture

```
opencode ──stdio──→ node gcp-mcp/bin.js ──→ @google-cloud/* SDK ──→ floci-gcp (Docker :4588)
                                                                     └──→ 21 GCP services emulated locally
```

**Key concept**: The `@google-cloud/*` Node.js client libraries respect standard GCP emulator environment variables (`STORAGE_EMULATOR_HOST`, `PUBSUB_EMULATOR_HOST`, etc.). By setting these in the MCP server's environment, the libraries automatically route requests to floci-gcp instead of real GCP.

**MCP server**: `gcp-mcp` v1.0.2 by eniayomi (github.com/eniayomi/gcp-mcp, 200+ stars). Node.js/TypeScript server using `@google-cloud/*` SDKs. 9 tools including `run-gcp-code` (arbitrary TS execution against GCP APIs).

## Prerequisites

- **Docker** installed and running
- **Node.js v24+** via nvm (for `gcp-mcp`)
- **floci CLI** binary v0.1.8+ (supports `floci gcp` subcommands)

## Step 1: Verify floci CLI

```bash
floci version
# Should show: Floci CLI 0.1.8, Server: 0.5.0 (community)
```

## Step 2: Start Floci-GCP

```bash
floci gcp start      # Launch the Docker container (floci/floci-gcp:latest, port 4588)
floci gcp wait       # Wait until ready to accept requests
floci gcp status     # Show health and version
```

Floci-GCP runs at `http://localhost:4588` with default project `floci-local`.

### Selective service startup

Start only specific services to save resources:

```bash
floci gcp start --services=gcs,pubsub,firestore,secretmanager
```

### Persistent state

Persist emulator state across restarts:

```bash
floci gcp start --persist=/home/YOUR_USER/.floci/gcp-state
```

### Environment variables

```bash
eval $(floci gcp env)
# Exports:
# STORAGE_EMULATOR_HOST=http://localhost:4588
# PUBSUB_EMULATOR_HOST=localhost:4588
# FIRESTORE_EMULATOR_HOST=localhost:4588
# DATASTORE_EMULATOR_HOST=localhost:4588
# SECRET_MANAGER_EMULATOR_HOST=localhost:4588
```

### Health check

```bash
curl -s http://localhost:4588/_floci-gcp/health | python3 -m json.tool
# Returns version and all 21 services with "running" status
```

## Step 3: Create Fake Service Account Key (Required)

The `gcp-mcp` server uses `GoogleAuth` from `google-auth-library` which requires credentials before any operation. Without credentials, the server crashes on the first tool call. A fake service account key file prevents the crash — the server starts, and emulator env vars route the actual API calls to floci-gcp.

```bash
# Generate RSA key pair
openssl genrsa -out /tmp/floci-gcp-key.pem 2048

# Create the service account key JSON
python3 -c "
import json
with open('/tmp/floci-gcp-key.pem') as f:
    key = f.read()
json.dump({
    'type': 'service_account',
    'project_id': 'floci-local',
    'private_key_id': 'fake-key-id',
    'private_key': key,
    'client_email': 'floci@floci-local.iam.gserviceaccount.com',
    'client_id': 'fake-client-id',
    'auth_uri': 'http://localhost:4588',
    'token_uri': 'http://localhost:4588/o/oauth2/token',
    'auth_provider_x509_cert_url': 'http://localhost:4588',
    'client_x509_cert_url': 'http://localhost:4588'
}, open('/tmp/floci-gcp-sa-key.json', 'w'), indent=2)
"
```

This file is **free** and uses a self-signed RSA key. The `google-auth-library` accepts it as valid credentials format, preventing the server from crashing. Actual API calls are routed to floci-gcp via the emulator env vars.

## Step 4: Install gcp-mcp

```bash
npm install -g gcp-mcp
```

Verify:

```bash
npm list -g gcp-mcp
# Should show: gcp-mcp@1.0.2
```

Find the absolute path to the entry point:

```bash
NODE_GLOBAL=$(npm root -g)
echo "${NODE_GLOBAL}/gcp-mcp/bin.js"
# Example: /home/YOUR_USER/.nvm/versions/node/v24.18.0/lib/node_modules/gcp-mcp/bin.js
```

The `bin.js` file loads `index.ts` via `tsx/cjs` — it requires Node.js to run (not npx, which swallows stdio).

## Step 5: Configure opencode.json

Add the `gcp` MCP entry to `~/.opencode/opencode.json`:

```json
{
  "mcp": {
    "gcp": {
      "type": "local",
      "command": [
        "node",
        "/home/YOUR_USER/.nvm/versions/node/v24.18.0/lib/node_modules/gcp-mcp/bin.js"
      ],
      "environment": {
        "STORAGE_EMULATOR_HOST": "http://localhost:4588",
        "PUBSUB_EMULATOR_HOST": "localhost:4588",
        "FIRESTORE_EMULATOR_HOST": "localhost:4588",
        "DATASTORE_EMULATOR_HOST": "localhost:4588",
        "SECRET_MANAGER_EMULATOR_HOST": "localhost:4588",
        "GOOGLE_CLOUD_PROJECT": "floci-local",
        "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/floci-gcp-sa-key.json"
      },
      "enabled": true,
      "timeout": 15000
    }
  }
}
```

Replace `/home/YOUR_USER/` with your actual home directory and the Node version path with your nvm path.

**CRITICAL**: 
- Do NOT use `["npx", "-y", "gcp-mcp"]` — it swallows stdio. Always use `node` with the absolute path to `bin.js`.
- Set `GOOGLE_APPLICATION_CREDENTIALS` to `/tmp/floci-gcp-sa-key.json` (the fake SA key from Step 3). Without this, the server crashes on the first tool call because `GoogleAuth` cannot find credentials.
- The emulator env vars (`STORAGE_EMULATOR_HOST`, etc.) are what make the `@google-cloud/*` libraries route to floci-gcp instead of real GCP.

## Step 6: Verify

### Floci-GCP running

```bash
floci gcp status
# Should show: running, edition community, version 0.5.0
```

### REST API works directly

```bash
# Create a GCS bucket
curl -s -X POST http://localhost:4588/storage/v1/b \
  -H "Content-Type: application/json" \
  -d '{"name":"test-bucket"}'

# List buckets
curl -s http://localhost:4588/storage/v1/b

# Create a Pub/Sub topic
curl -s -X PUT http://localhost:4588/v1/projects/floci-local/topics/my-topic

# List topics
curl -s http://localhost:4588/v1/projects/floci-local/topics

# Create a BigQuery dataset
curl -s -X POST http://localhost:4588/bigquery/v2/projects/floci-local/datasets \
  -H "Content-Type: application/json" \
  -d '{"datasetReference":{"datasetId":"my_ds"},"location":"US"}'

# Create a Secret Manager secret
curl -s -X POST "http://localhost:4588/v1/projects/floci-local/secrets?secretId=my-secret" \
  -H "Content-Type: application/json" \
  -d '{"replication":{"automatic":{}}}'
```

### MCP server works from opencode

1. Restart opencode
2. The MCP should connect and expose GCP tools:
   - `gcp_run-gcp-code` — execute arbitrary TypeScript against GCP APIs (escape hatch)
   - `gcp_list-projects` — list GCP projects
   - `gcp_select-project` — select active project
   - `gcp_get-billing-info` — get billing info
   - `gcp_get-cost-forecast` — get cost forecast
   - `gcp_get-billing-budget` — get billing budget
   - `gcp_list-gke-clusters` — list GKE clusters
   - `gcp_list-sql-instances` — list Cloud SQL instances
   - `gcp_get-logs` — query Cloud Logging

## Supported Services

Floci-GCP emulates 21 GCP services. All verified with REST API calls:

| Service | REST API Path | Emulator Env Var | SDK Support | Status |
|---------|--------------|------------------|-------------|--------|
| Cloud Storage (GCS) | `/storage/v1/` | `STORAGE_EMULATOR_HOST` | Native | CRUD verified |
| Pub/Sub | `/v1/projects/{p}/topics` | `PUBSUB_EMULATOR_HOST` | Native | CRUD verified |
| Firestore | `/v1/projects/{p}/databases` | `FIRESTORE_EMULATOR_HOST` | Native | Running |
| Datastore | `/v1/projects/{p}` | `DATASTORE_EMULATOR_HOST` | Native | Running |
| Secret Manager | `/v1/projects/{p}/secrets` | `SECRET_MANAGER_EMULATOR_HOST` | Native | CRUD verified |
| BigQuery | `/bigquery/v2/projects/{p}/` | — | Via run-gcp-code | CRUD verified |
| GKE | `/v1/projects/{p}/locations/-/clusters` | — | Via run-gcp-code | Running |
| Cloud Run | `/v2/projects/{p}/locations/{l}/services` | — | Via run-gcp-code | Running |
| Cloud SQL | `/v1/projects/{p}/instances` | — | Via run-gcp-code | Running |
| Cloud Functions | — | — | Via run-gcp-code | Running |
| IAM | `/v1/projects/{p}/serviceAccounts` | — | Via run-gcp-code | Running |
| Resource Manager | `/v1/projects` | — | Via run-gcp-code | Running |
| Logging | — | — | Via run-gcp-code | Running |
| Monitoring | — | — | Via run-gcp-code | Running |
| KMS | — | — | Via run-gcp-code | Running |
| Cloud Tasks | — | — | Via run-gcp-code | Running |
| Scheduler | — | — | Via run-gcp-code | Running |
| Eventarc | — | — | Via run-gcp-code | Running |
| Firebase Auth | — | — | Via run-gcp-code | Running |
| Kafka | — | — | REST only | Running |
| Service Usage | — | — | REST only | Running |

**"Native" SDK support** means the `@google-cloud/*` library automatically uses the emulator when the env var is set. **"Via run-gcp-code"** means the service is accessible through the `run-gcp-code` MCP tool by constructing a client with a custom `apiEndpoint`.

## Access Patterns

### Pre-configured clients in run-gcp-code

The `run-gcp-code` tool executes code inside a VM sandbox. `require()` is NOT available — use the pre-configured clients directly:

| Variable | Client Class | Services |
|----------|-------------|----------|
| `storage` | `Storage` | Cloud Storage (GCS) — works via `STORAGE_EMULATOR_HOST` |
| `compute` | `InstancesClient` | Compute Engine — fails gracefully (no emulator env var) |
| `functions` | `CloudFunctionsServiceClient` | Cloud Functions — fails gracefully |
| `run` | `ServicesClient` | Cloud Run — fails gracefully |
| `bigquery` | `BigQuery` | BigQuery — fails gracefully |
| `resourceManager` | `ProjectsClient` | Resource Manager — fails gracefully |
| `container` | `ClusterManagerClient` | GKE — fails gracefully |
| `logging` | `Logging` | Cloud Logging — fails gracefully |
| `sql` | `SqlInstancesServiceClient` | Cloud SQL — fails gracefully |

Additional variables available: `selectedProject` (string), `selectedRegion` (string), `retry` (async fn), `help` (fn returning docs).

### Pattern 1: MCP tools from opencode

Use `gcp_run-gcp-code` with pre-configured clients (most powerful):

```
gcp_run-gcp-code(code="const [buckets] = await storage.getBuckets(); return buckets.map(b => b.name);", projectId="floci-local")
```

```
gcp_run-gcp-code(code="const [bucket] = await storage.createBucket('my-bucket'); return bucket.name;", projectId="floci-local")
```

Use specific tools for common operations:

```
gcp_list-projects()
gcp_list-gke-clusters()
gcp_list-sql-instances()
gcp_get-logs(filter="severity>=ERROR")
```

### MCP Tool Behavior Against floci-gcp

| Tool | Behavior | Notes |
|------|----------|-------|
| `gcp_run-gcp-code` (storage) | Works | CRUD via `STORAGE_EMULATOR_HOST` |
| `gcp_run-gcp-code` (bigquery, container, logging, sql) | Fails gracefully | Returns error, server stays alive |
| `gcp_list-projects` | Returns `{"projects":[]}` | Error caught, returns empty list |
| `gcp_select-project` | Works (sets project) | But subsequent tool calls may fail if no emulator env var |
| `gcp_list-gke-clusters` | Fails gracefully | `UNAUTHENTICATED` — no emulator env var for GKE |
| `gcp_list-sql-instances` | Fails gracefully | `UNAUTHENTICATED` — no emulator env var for Cloud SQL |
| `gcp_get-logs` | Fails gracefully | `UNAUTHENTICATED` — no emulator env var for Logging |
| `gcp_get-billing-info` | Fails gracefully | No emulator for Billing API |
| `gcp_get-cost-forecast` | Fails gracefully | No emulator for Billing API |
| `gcp_get-billing-budget` | Fails gracefully | No emulator for Billing API |

**Key takeaway**: Only services with emulator env var support (Storage, Pub/Sub, Firestore, Datastore, Secret Manager) work via MCP. For all other services, use REST API (curl) directly against floci-gcp.

### Pattern 2: REST API direct (curl)

```bash
# Storage
curl -s http://localhost:4588/storage/v1/b
curl -s -X POST http://localhost:4588/storage/v1/b -H "Content-Type: application/json" -d '{"name":"my-bucket"}'

# Pub/Sub
curl -s http://localhost:4588/v1/projects/floci-local/topics
curl -s -X PUT http://localhost:4588/v1/projects/floci-local/topics/my-topic

# BigQuery
curl -s http://localhost:4588/bigquery/v2/projects/floci-local/datasets

# Secret Manager
curl -s http://localhost:4588/v1/projects/floci-local/secrets

# GKE
curl -s http://localhost:4588/v1/projects/floci-local/locations/-/clusters

# IAM
curl -s http://localhost:4588/v1/projects/floci-local/serviceAccounts

# Cloud SQL
curl -s http://localhost:4588/v1/projects/floci-local/instances
```

### Pattern 3: floci env for external tools

```bash
eval $(floci gcp env)
# Now any GCP SDK/tool will point to floci-gcp
```

### Pattern 4: REST API for services without emulator env var support

For services without native emulator env var support (BigQuery, GKE, Cloud SQL, etc.), use REST API (curl) directly instead of `run-gcp-code`:

```bash
# BigQuery - list datasets
curl -s http://localhost:4588/bigquery/v2/projects/floci-local/datasets

# BigQuery - create dataset
curl -s -X POST http://localhost:4588/bigquery/v2/projects/floci-local/datasets \
  -H "Content-Type: application/json" \
  -d '{"datasetReference":{"datasetId":"my_ds"},"location":"US"}'

# GKE - list clusters
curl -s http://localhost:4588/v1/projects/floci-local/locations/-/clusters

# Cloud SQL - list instances
curl -s http://localhost:4588/v1/projects/floci-local/instances

# IAM - list service accounts
curl -s http://localhost:4588/v1/projects/floci-local/serviceAccounts

# Cloud Run - list services
curl -s http://localhost:4588/v2/projects/floci-local/locations/us-central1/services
```

**Note**: `run-gcp-code` cannot use `require()` to create custom clients — the VM sandbox doesn't expose it. Use the pre-configured clients (which work for Storage) or fall back to REST API (curl) for everything else.

## Troubleshooting

### `npx -y gcp-mcp` produces no output

**Cause**: npx swallows stdio when launching the MCP server.

**Fix**: Use `node` with absolute path in `opencode.json`:

```json
"command": ["node", "/path/to/gcp-mcp/bin.js"]
```

### Floci-GCP not responding

```bash
floci gcp doctor       # Diagnose environment issues
floci gcp restart      # Stop and restart
floci gcp logs         # Check container logs
```

### Port 4588 already in use

```bash
floci gcp start --port=4589  # Use different port
docker ps | grep 4588        # Check what's using the port
```

### MCP tools not appearing in opencode

1. Verify `opencode.json` is valid JSON: `python3 -m json.tool ~/.opencode/opencode.json`
2. Verify the `node` path exists: `ls -la /path/to/gcp-mcp/bin.js`
3. Verify floci-gcp is running: `floci gcp status`
4. Restart opencode

### Authentication errors from gcp-mcp

**Cause**: The SDK is trying to use real GCP credentials and the fake SA key is not set up.

**Fix**: Create the fake SA key file (Step 3) and set `GOOGLE_APPLICATION_CREDENTIALS=/tmp/floci-gcp-sa-key.json` in the MCP environment. This prevents the server from crashing. Services with emulator env var support (Storage, Pub/Sub, Firestore, Datastore, Secret Manager) will work; others will fail gracefully without crashing the server.

### `run-gcp-code` fails with API connection error

**Cause**: The service doesn't have a native emulator env var, so the SDK tries to connect to real GCP.

**Fix**: Construct the client with `apiEndpoint: 'localhost:4588'` in the code:

```typescript
const client = new SomeClient({apiEndpoint: 'localhost:4588', projectId: 'floci-local'});
```

### Docker container keeps restarting

```bash
docker logs floci-gcp 2>&1 | tail -50
floci gcp stop
docker system prune -f
floci gcp start
```

## Quick Reference

### Files

| File | Purpose |
|------|---------|
| `/usr/local/bin/floci` | Floci CLI binary (v0.1.8+) |
| `~/.opencode/opencode.json` | OpenCode config with `mcp.gcp` entry |
| `~/.nvm/versions/node/v24.18.0/lib/node_modules/gcp-mcp/bin.js` | MCP server entry point |

### Commands

| Command | Purpose |
|---------|---------|
| `floci gcp start` | Launch floci-gcp container |
| `floci gcp stop` | Stop floci-gcp container |
| `floci gcp status` | Show health and version |
| `floci gcp services` | List available services |
| `floci gcp doctor` | Diagnose environment issues |
| `floci gcp env` | Print GCP env vars for floci-gcp |
| `floci gcp logs` | Fetch container logs |
| `floci gcp restart` | Stop and restart |
| `curl -s http://localhost:4588/_floci-gcp/health` | Full health check |

### MCP Tools (9)

| Tool | Purpose |
|------|---------|
| `gcp_run-gcp-code` | Execute arbitrary TypeScript against GCP APIs |
| `gcp_list-projects` | List GCP projects |
| `gcp_select-project` | Select active project |
| `gcp_get-billing-info` | Get billing account info |
| `gcp_get-cost-forecast` | Get cost forecast |
| `gcp_get-billing-budget` | Get billing budget |
| `gcp_list-gke-clusters` | List GKE clusters |
| `gcp_list-sql-instances` | List Cloud SQL instances |
| `gcp_get-logs` | Query Cloud Logging |

### Emulator Environment Variables

| Variable | Services | Format |
|----------|----------|--------|
| `STORAGE_EMULATOR_HOST` | Cloud Storage | `http://localhost:4588` |
| `PUBSUB_EMULATOR_HOST` | Pub/Sub | `localhost:4588` |
| `FIRESTORE_EMULATOR_HOST` | Firestore | `localhost:4588` |
| `DATASTORE_EMULATOR_HOST` | Datastore | `localhost:4588` |
| `SECRET_MANAGER_EMULATOR_HOST` | Secret Manager | `localhost:4588` |
| `GOOGLE_CLOUD_PROJECT` | All | `floci-local` |

## Portability (Replicate on Another PC)

Minimal steps to set up floci-gcp + GCP MCP on a new machine:

1. **Install Docker** (if not present)
2. **Install Node.js v24+** via nvm: `nvm install 24`
3. **Verify floci CLI** v0.1.8+: `floci version`
4. **Start floci-gcp**: `floci gcp start && floci gcp wait`
5. **Create fake SA key**: `openssl genrsa -out /tmp/floci-gcp-key.pem 2048` + Python script (see Step 3)
6. **Install MCP server**: `npm install -g gcp-mcp`
7. **Find entry point**: `echo "$(npm root -g)/gcp-mcp/bin.js"`
8. **Configure opencode**: add `mcp.gcp` entry to `~/.opencode/opencode.json` with `node` + absolute path + emulator env vars + `GOOGLE_APPLICATION_CREDENTIALS=/tmp/floci-gcp-sa-key.json`
9. **Verify**: `floci gcp status`, `curl -s http://localhost:4588/storage/v1/b`, restart opencode

## Floci-GCP ↔ Huawei Cloud Mapping (for Migration Learning)

| GCP (floci-gcp) | Huawei Cloud | Notes |
|-----------------|-------------|-------|
| GKE Cluster | CCE Cluster | Kubernetes control plane |
| GKE Node Pool | CCE Node Pool | Worker nodes |
| Cloud Run | CCE Volcano | Serverless containers |
| Cloud Storage (GCS) | OBS | Object storage |
| BigQuery | GaussDB(DWS) | Data warehouse |
| Cloud SQL | RDS | Relational DB |
| Firestore | GeminiDB | Document DB |
| Pub/Sub | DMS | Message queue |
| Secret Manager | DEW | Secrets |
| KMS | KMS | Key management |
| Cloud Functions | FunctionGraph | Serverless functions |
| IAM | IAM | Identity management |
| VPC (via Resource Manager) | VPC | Networking |
| Cloud Logging | LTS | Log management |
| Cloud Monitoring | CES | Monitoring |
| Cloud Tasks | DCS | Task queue |

## Comparison with AWS (floci) Setup

| Aspect | AWS (floci) | GCP (floci-gcp) |
|--------|-------------|-----------------|
| Port | 4566 | 4588 |
| Image | floci/floci:latest | floci/floci-gcp:latest |
| MCP server | @yawlabs/aws-mcp | gcp-mcp |
| MCP entry point | dist/index.js | bin.js |
| Auth | test/test (dummy) | Fake SA key (free, self-signed RSA) |
| Env var mechanism | AWS_ENDPOINT_URL | *_EMULATOR_HOST vars |
| Services | 50+ | 21 |
| Native SDK support | All services | Storage, Pub/Sub, Firestore, Datastore, Secret Manager |
| Escape hatch | aws_aws_call | gcp_run-gcp-code |
