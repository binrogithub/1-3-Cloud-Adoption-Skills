# Scenario 1: OpenCode Setup for Huawei Cloud AI-Assisted Infrastructure

## Overview

This scenario demonstrates how to set up [OpenCode](https://opencode.ai) as an AI coding agent for Huawei Cloud infrastructure development. OpenCode is connected to Huawei Cloud MaaS (Model as a Service) for LLM inference, and two MCP servers that give the AI agent the ability to **see** your cloud and **write** correct infrastructure code:

- **HCloud MCP** — A custom MCP server wrapping KooCLI with 90 read-only discovery tools across 18 Huawei Cloud services, plus a CLI escape hatch for operational actions.
- **Terraform MCP** — HashiCorp's official Terraform MCP server for provider/module registry access, schema discovery, and version lookups.

The result: an AI agent that discovers real cloud resources, writes correct Terraform code with valid IDs and parameters, and performs day-2 operational actions — all through natural conversation.

## Architecture

```
User (Terminal)
    |
    v
OpenCode (AI Agent)
    |
    +-- MCP Protocol (stdio)
    |   +-- HCloud MCP --> hcloud CLI (KooCLI + obsutil) --> Huawei Cloud
    |   +-- Terraform MCP --> Terraform Registry --> Provider schemas, modules
    |
    +-- Huawei Cloud MaaS --> DeepSeek-V4-Flash, GLM-5.1, etc.
```

## What's Included

| Path | Description |
|------|-------------|
| `opencode.json` | Example OpenCode configuration with MaaS models and MCP servers (API keys sanitized) |
| `tasks.md` | Step-by-step setup guide: WSL, Terraform, Docker, KooCLI, OpenCode, MCP servers |
| `hcloud-mcp-server/` | Source code of the custom Huawei Cloud MCP server (Python) |
| `hcloud-mcp-server/src/tools/` | 18 service modules: ECS, VPC, RDS, CCE, ELB, EVS, IMS, IAM, etc. |
| `hcloud-mcp-server/tests/` | Test suite for the MCP server |
| `skills/huaweicloud-terraform-planner/SKILL.md` | Skill that orchestrates schema discovery + cloud discovery + Terraform generation |

## Setup Steps

### 1. Install prerequisites (WSL + Ubuntu)

```bash
wsl --install -d Ubuntu
```

### 2. Install Terraform, Docker, KooCLI, OpenCode

See `tasks.md` for the complete installation sequence. Key commands:

```bash
# Terraform
sudo apt install terraform

# Docker Engine
sudo apt install docker-ce docker-ce-cli containerd.io

# KooCLI (Huawei Cloud CLI)
curl -LO "https://ap-southeast-3-hwcloudcli.obs.ap-southeast-3.myhuaweicloud.com/cli/latest/huaweicloud-cli-linux-amd64.tar.gz"
tar -zxvf huaweicloud-cli-linux-amd64.tar.gz
sudo mv hcloud /usr/local/bin/

# OpenCode
curl -fsSL https://opencode.ai/install | bash
```

### 3. Configure KooCLI with Huawei Cloud credentials

```bash
hcloud configure init  # Enter AK/SK
hcloud obs config -i=<AK> -k=<SK> -e=https://obs.<REGION>.myhuaweicloud.com
```

### 4. Install the HCloud MCP server

```bash
cd hcloud-mcp-server
pip install -e .
```

### 5. Configure OpenCode

Subscribe to Huawei Cloud MaaS models in the console, get your API key, and create `~/.opencode/opencode.json` using `opencode.json` from this directory as a template. Replace `YOUR_TFE_TOKEN` and `YOUR_MAAS_API_KEY` with your actual credentials.

### 6. Start building

```bash
opencode
> Write Terraform for an RDS instance in la-north-2
> List all VPCs in my account
> Restart the prod-api server
```

## HCloud MCP Server

The custom MCP server (`hcloud-mcp-server/`) is a Python package that wraps KooCLI into MCP tools. It provides:

- **90 read-only tools** across 18 services (ECS, VPC, RDS, CCE, ELB, EVS, IMS, IAM, NAT, EIP, DCS, DDS, DNS, KMS, SMN, CES, OBS, AS)
- **1 CLI escape hatch** (`hcloud_cli`) for write operations and commands not covered by structured tools
- Destructive operations require `confirm=true` and run with `--dryrun` by default

### Supported Services

| Service | Tools | Coverage |
|---------|-------|----------|
| ECS | 8 | Servers, Flavors, AZs |
| VPC | 9 | VPCs, Subnets, Security Groups |
| ELB | 9 | Load Balancers, Listeners, Pools |
| IAM | 8 | Users, Groups, Policies |
| AS | 7 | Scaling Groups, Configs, Policies |
| CCE | 6 | Clusters, Nodes, Node Pools |
| RDS | 5 | Instances, Flavors, Storage Types |
| EVS | 5 | Volumes, Snapshots |
| IMS | 4 | Images, OS Versions |
| NAT | 4 | Gateways, SNAT, DNAT |
| DCS | 4 | Redis, Flavors, AZs |
| EIP | 4 | Public IPs, Quotas |
| CES | 4 | Alarms, Metrics |
| OBS | 3 | Buckets, Objects |
| DNS | 3 | Zones, Record Sets |
| DDS | 3 | MongoDB, Flavors |
| KMS | 2 | Keys, Details |
| SMN | 2 | Topics, Subscriptions |

## Related Skills

- [huaweicloud-terraform-planner](../../Cloud-Foundation/Automation-and-IaC/huaweicloud-terraform-planner/SKILL.md) — Orchestrates schema discovery from Terraform MCP and cloud discovery from HCloud MCP to generate correct Terraform code.

## Video Reference

This scenario corresponds to the training video `configurationopencode.mp4` (not included in the repository).
