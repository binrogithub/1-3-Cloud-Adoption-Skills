---
name: floci-aws-mcp-setup
description: Configure floci (local AWS emulator) + @yawlabs/aws-mcp server in opencode. Use when setting up floci, configuring AWS CLI for local emulation, or troubleshooting the MCP connection to floci.
---

# Floci + AWS MCP Setup for OpenCode

Run AWS operations from within opencode against a local floci emulator (no cloud costs, no network latency) using the `@yawlabs/aws-mcp` MCP server.

## Architecture

```
opencode ──stdio──→ node @yawlabs/aws-mcp/dist/index.js ──→ AWS SDK v3 ──→ floci (Docker :4566)
                                                                     └──→ 50+ AWS services emulated locally
```

**Key constraint**: `npx -y @yawlabs/aws-mcp@latest` does NOT work (swallows stdio, produces no output). The MCP server must be launched via `node` with an absolute path to `dist/index.js`.

## Prerequisites

- **Docker** installed and running
- **Node.js v24+** via nvm (for `@yawlabs/aws-mcp`)
- **floci CLI** binary (native ELF, ~52MB)

## Step 1: Install floci CLI

Floci is distributed as a native binary. Download and install:

```bash
# Option A: Direct download (replace URL with latest release)
curl -L -o /usr/local/bin/floci <floci-release-url>
chmod +x /usr/local/bin/floci

# Option B: If already available as a package
# (floci may be installed via its own installer script)
```

Verify:

```bash
floci version
# Should show: Floci CLI 0.1.x, Server: 1.5.x (floci-always-free)
```

## Step 2: Start Floci

```bash
floci start      # Launch the Docker container (floci/floci:latest, port 4566)
floci wait       # Wait until ready to accept requests
floci status     # Show health and version
```

Floci runs at `http://localhost:4566` with dummy credentials `test/test` and region `us-east-1`.

### Default infrastructure

Floci provides a default VPC `vpc-default` with 3 subnets:
- `subnet-default-a` — 172.31.0.0/20, us-east-1a
- `subnet-default-b` — 172.31.16.0/20, us-east-1b
- `subnet-default-c` — 172.31.32.0/20, us-east-1c

No IAM roles, keypairs, or security groups exist by default — you must create them.

### Environment variables

```bash
eval $(floci env)
# Exports: AWS_ENDPOINT_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
```

## Step 3: Install AWS CLI v2

```bash
# Install to ~/.local/aws-cli/v2/
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install --install-dir ~/.local/aws-cli/v2/current --bin-dir ~/.local/bin

# Verify
aws --version
# Should show: aws-cli/2.x.x
```

### Configure AWS CLI for floci

Create `~/.aws/config`:

```ini
[default]
region = us-east-1
endpoint_url = http://localhost:4566
```

Create `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = test
aws_secret_access_key = test
```

Verify:

```bash
aws s3 ls          # Should return empty (no buckets yet)
aws dynamodb list-tables  # Should return empty
```

## Step 4: Install @yawlabs/aws-mcp

```bash
npm install -g @yawlabs/aws-mcp
```

Verify:

```bash
npm list -g @yawlabs/aws-mcp
# Should show: @yawlabs/aws-mcp@1.5.x
```

Find the absolute path to the entry point:

```bash
NODE_GLOBAL=$(npm root -g)
echo "${NODE_GLOBAL}/@yawlabs/aws-mcp/dist/index.js"
# Example: /home/YOUR_USER/.nvm/versions/node/v24.16.0/lib/node_modules/@yawlabs/aws-mcp/dist/index.js
```

## Step 5: Configure opencode.json

Add the `aws` MCP entry to `~/.opencode/opencode.json` (or `~/.config/opencode/opencode.jsonc`):

```json
{
  "mcp": {
    "aws": {
      "type": "local",
      "command": [
        "node",
        "/home/YOUR_USER/.nvm/versions/node/v24.16.0/lib/node_modules/@yawlabs/aws-mcp/dist/index.js"
      ],
      "environment": {
        "AWS_ENDPOINT_URL": "http://localhost:4566",
        "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test"
      },
      "enabled": true,
      "timeout": 10000
    }
  }
}
```

Replace `/home/YOUR_USER/` with your actual home directory and the Node version path with your nvm path.

**CRITICAL**: Do NOT use `["npx", "-y", "@yawlabs/aws-mcp@latest"]` — it swallows stdio and produces no output. Always use `node` with the absolute path to `dist/index.js`.

## Step 6: Verify

### Floci running

```bash
floci status
# Should show: running, edition floci-always-free
```

### AWS CLI works

```bash
aws s3 mb s3://test-bucket
aws s3 ls
aws s3 rb s3://test-bucket
```

### MCP server works from opencode

1. Restart opencode
2. The MCP should connect and expose 25+ AWS tools prefixed with `aws_`:
   - `aws_aws_whoami` — verify identity (account 000000000000)
   - `aws_aws_call` — run arbitrary AWS API operations
   - `aws_aws_resource_get` / `aws_aws_resource_list` — Cloud Control API reads
   - `aws_aws_resource_create` / `aws_aws_resource_update` / `aws_aws_resource_delete` — Cloud Control API writes
   - `aws_aws_paginate` — paginated list operations
   - `aws_aws_logs_tail` — CloudWatch Logs tailing
   - `aws_aws_metrics_query` — CloudWatch metrics
   - `aws_aws_session_set` / `aws_aws_session_get` — session management

## Supported Services

Floci emulates 50+ AWS services. Key services for migration learning:

| Service | API | Status |
|---------|-----|--------|
| S3 | `s3api` | running |
| DynamoDB | `dynamodb` | running |
| SQS | `sqs` | running |
| SNS | `sns` | running |
| Lambda | `lambda` | running |
| API Gateway | `apigateway` / `apigatewayv2` | running |
| IAM | `iam` | running |
| EC2 | `ec2` | running |
| ECS | `ecs` | running |
| ECR | `ecr` | running |
| EKS | `eks` | running |
| RDS | `rds` / `rds-data` | running |
| CloudFormation | `cloudformation` | running |
| KMS | `kms` | running |
| Secrets Manager | `secretsmanager` | running |
| Step Functions | `stepfunctions` | running |
| Route53 | `route53` | running |
| Autoscaling | `autoscaling` | running |
| ELB | `elasticloadbalancing` | running |
| CloudWatch | `logs` / `monitoring` | running |
| SSM | `ssm` | running |
| Kinesis | `kinesis` | running |
| Cognito | `cognito-idp` | running |
| Bedrock | `bedrock-runtime` | running |
| CloudFront | `cloudfront` | running |
| EventBridge | `events` / `scheduler` | running |
| CodeBuild | `codebuild` | running |
| CodePipeline | `codepipeline` | running |

Full list: `curl -s http://localhost:4566/_localstack/health | python3 -m json.tool`

## Access Patterns

### Pattern 1: AWS CLI direct

```bash
aws s3 ls
aws dynamodb create-table --table-name test --attribute-definitions ...
aws eks list-clusters
```

### Pattern 2: MCP tools from opencode

Use `aws_aws_call` for any AWS API operation:

```
aws_aws_call(service="s3api", operation="list-buckets")
aws_aws_call(service="dynamodb", operation="list-tables")
aws_aws_call(service="eks", operation="list-clusters")
```

Use `aws_aws_resource_list` / `aws_aws_resource_get` for Cloud Control API:

```
aws_aws_resource_list(typeName="AWS::S3::Bucket")
aws_aws_resource_get(typeName="AWS::IAM::Role", identifier="MyRole")
```

Use `aws_aws_paginate` for large result sets:

```
aws_aws_paginate(service="s3api", operation="list-objects-v2", params={Bucket: "my-bucket"})
```

### Pattern 3: floci env for external tools

```bash
eval $(floci env)
# Now any AWS SDK/tool will point to floci
```

## Troubleshooting

### `npx -y @yawlabs/aws-mcp` produces no output

**Cause**: npx swallows stdio when launching the MCP server.

**Fix**: Use `node` with absolute path in `opencode.json`:

```json
"command": ["node", "/path/to/@yawlabs/aws-mcp/dist/index.js"]
```

### Floci not responding

```bash
floci doctor       # Diagnose environment issues
floci restart      # Stop and restart
floci logs         # Check container logs
```

### Port 4566 already in use

```bash
floci config       # Manage configuration (change port if needed)
docker ps | grep 4566  # Check what's using the port
```

### EKS create-cluster timeout

**Cause**: Invalid parameters (empty `subnetIds`, non-existent `roleArn`).

**Fix**: Create IAM role first, then use valid subnet IDs from the default VPC:

```bash
# Create IAM role
aws iam create-role --role-name eks-cluster-role --assume-role-policy-document file://trust-policy.json

# Create cluster with valid params
aws eks create-cluster --name my-cluster --role-arn arn:aws:iam::000000000000:role/eks-cluster-role \
  --resources-vpc-config subnetIds=subnet-default-a,subnet-default-b,subnet-default-c
```

### MCP tools not appearing in opencode

1. Verify `opencode.json` is valid JSON: `python3 -m json.tool ~/.opencode/opencode.json`
2. Verify the `node` path exists: `ls -la /path/to/@yawlabs/aws-mcp/dist/index.js`
3. Verify floci is running: `floci status`
4. Restart opencode

### Docker container keeps restarting

```bash
docker logs floci 2>&1 | tail -50
floci stop
docker system prune -f
floci start
```

## Quick Reference

### Files

| File | Purpose |
|------|---------|
| `/usr/local/bin/floci` | Floci CLI binary (v0.1.x) |
| `~/.aws/config` | AWS CLI config (region + endpoint_url) |
| `~/.aws/credentials` | AWS CLI creds (test/test) |
| `~/.local/bin/aws` | AWS CLI v2 binary (symlink) |
| `~/.local/aws-cli/v2/current/` | AWS CLI v2 installation |
| `~/.opencode/opencode.json` | OpenCode config with `mcp.aws` entry |
| `~/.nvm/versions/node/v24.16.0/lib/node_modules/@yawlabs/aws-mcp/dist/index.js` | MCP server entry point |

### Commands

| Command | Purpose |
|---------|---------|
| `floci start` | Launch floci container |
| `floci stop` | Stop floci container |
| `floci status` | Show health and version |
| `floci services` | List available services |
| `floci doctor` | Diagnose environment issues |
| `floci env` | Print AWS env vars for floci |
| `floci logs` | Fetch container logs |
| `floci restart` | Stop and restart |
| `aws s3 ls` | Test AWS CLI against floci |
| `curl -s http://localhost:4566/_localstack/health \| python3 -m json.tool` | Full health check |

### MCP Tools (25+)

| Tool | Purpose |
|------|---------|
| `aws_aws_whoami` | Verify identity |
| `aws_aws_call` | Arbitrary AWS API operation |
| `aws_aws_paginate` | Paginated list operation |
| `aws_aws_resource_get` | Read resource via Cloud Control API |
| `aws_aws_resource_list` | List resources via Cloud Control API |
| `aws_aws_resource_create` | Create resource via Cloud Control API |
| `aws_aws_resource_update` | Update resource via Cloud Control API |
| `aws_aws_resource_delete` | Delete resource via Cloud Control API |
| `aws_aws_resource_diff` | Dry-run resource update preview |
| `aws_aws_logs_tail` | Tail CloudWatch Logs |
| `aws_aws_metrics_query` | Query CloudWatch metrics |
| `aws_aws_session_set` | Set default profile/region |
| `aws_aws_session_get` | Show current session |
| `aws_aws_iam_simulate` | Simulate IAM permissions |
| `aws_aws_multi_region` | Run operation across regions |
| `aws_aws_script` | Run JS snippet orchestrating multiple tools |
| `aws_aws_assume_role` | STS AssumeRole |
| `aws_aws_docs_search` | Search AWS documentation |
| `aws_aws_docs_read` | Read AWS documentation page |

## Portability (Replicate on Another PC)

Minimal steps to set up floci + AWS MCP on a new machine:

1. **Install Docker** (if not present)
2. **Install Node.js v24+** via nvm: `nvm install 24`
3. **Install floci CLI**: download binary to `/usr/local/bin/floci`, `chmod +x`
4. **Start floci**: `floci start && floci wait`
5. **Install AWS CLI v2**: download and install to `~/.local/`
6. **Configure AWS CLI**: create `~/.aws/config` and `~/.aws/credentials` with `test/test` and `endpoint_url=http://localhost:4566`
7. **Install MCP server**: `npm install -g @yawlabs/aws-mcp`
8. **Find entry point**: `echo "$(npm root -g)/@yawlabs/aws-mcp/dist/index.js"`
9. **Configure opencode**: add `mcp.aws` entry to `~/.opencode/opencode.json` with `node` + absolute path
10. **Verify**: `floci status`, `aws s3 ls`, restart opencode and check `aws_aws_whoami`

## Floci ↔ Huawei Cloud Mapping (for Migration Learning)

| AWS (floci) | Huawei Cloud | Notes |
|-------------|-------------|-------|
| EKS Cluster | CCE Cluster | Kubernetes control plane |
| EKS Node Group | CCE Node Pool | Worker nodes |
| EKS Fargate | CCE Volcano | Serverless pods |
| EBS | EVS | Block storage |
| ECR | SWR | Container registry |
| ALB / NLB | ELB | Load balancing |
| IAM Role + IRSA | IAM Agency | Pod identity |
| CloudWatch Container Insights | CES + AOM | Monitoring |
| VPC + Subnets | VPC + Subnets | Networking (1:1) |
| Security Groups | Security Groups | 1:1 mapping |
| Route53 | DNS | DNS zones |
| S3 | OBS | Object storage |
| DynamoDB | GeminiDB | NoSQL |
| RDS | RDS | Relational DB |
| Lambda | FunctionGraph | Serverless functions |
| SQS | DMS | Message queue |
| KMS | KMS | Key management |
| Secrets Manager | DEW | Secrets |
| CloudFormation | RFS / AOS | IaC |
