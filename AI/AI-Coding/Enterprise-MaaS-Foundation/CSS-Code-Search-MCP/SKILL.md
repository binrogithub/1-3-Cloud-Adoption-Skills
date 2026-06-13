---
name: css-code-search-mcp
description: Deploy a CSS/OpenSearch code-search MCP server on Huawei Cloud ECS from scratch, so that Claude Code (claude-glm) can search a GitHub repo's code and docs as native MCP tools. Use when the task is to provision a new Huawei Cloud CSS cluster and ECS, index a code repository into CSS, and expose it as a searchable MCP tool for AI coding agents.
---

# CSS Code Search MCP on Huawei Cloud ECS

Provision a Huawei Cloud CSS (OpenSearch) cluster, index a GitHub repository into it, and expose a FastMCP search server so that `claude-glm` (or any MCP client) can call `search_code`, `list_skills`, and `get_file` as native tools — all from a single skill in two phases.

## When to Use This Skill

- A team wants their Cloud Adoption Skills repo (or any code repo) searchable by AI coding agents without cloning the full repo locally.
- An AI coding agent needs fast, server-side code search across hundreds of files with metadata filtering (category, skill name, file extension).
- You are setting up a **new** ECS + CSS environment from zero and want search-as-a-tool from day one.
- You already have an ECS + CSS and want to add or re-index a code search MCP.

## Architecture

```
claude-glm (local laptop)
  └── mcpServers.css-search (type: http)
        ↓ HTTP/SSE
      nginx :8788/css/mcp          ← SG port, proxies both MCPs
        ↓
      FastMCP :8789                ← CSS Code Search MCP (bearer-auth)
        ↓
      CSS/OpenSearch :9200         ← Huawei Cloud CSS cluster
        └── index: <repo-name>     ← chunked repo files

ECS host
  ├── nginx :8788                  ← reverse proxy (SearXNG /mcp + CSS /css/mcp)
  ├── SearXNG MCP :18788          ← existing web search MCP (moved behind nginx)
  ├── CSS Code Search MCP :8789   ← this skill's FastMCP server
  └── CSS cluster                 ← 192.168.0.x:9200 (private subnet)
```

## Required Inputs

Confirm before starting:

- **Huawei Cloud AK/SK** with ECS, EVS, EIP, VPC, CSS create/list scope in the target region.
- **Huawei Cloud Region and Project ID** (e.g. `la-north-2` / `afc631438d8941d0b10aaa2cee2bf94c`).
- **GitHub repo URL** to index (e.g. `https://github.com/binrogithub/1-3-Cloud-Adoption-Skills`).
- **Allow-list CIDR** for the laptop calling the MCP (auto-detected if not provided).
- **MCP bearer token** — generated automatically by the deploy script.

## Core Rules

- **Never write AK/SK, MaaS keys, or bearer tokens into committed files.** Use env files with `0600` permissions or `$VAR_NAME` placeholders.
- **All exposed ports are CIDR-locked** to the operator's current outbound IP. Never widen to `0.0.0.0/0`.
- **Security group ports**: 22 (SSH), 4000 (LiteLLM), 8788 (nginx MCP proxy). Do not open 9200 externally.
- **Reuse the existing VPC/subnet** when the project is at the router/VPC quota.
- **CSS disk type**: prefer `COMMON`; fall back to `HIGH` if `CSS.0065 The disk has been sold out`.
- **Ubuntu ECS images often log in as `root`**, not `ubuntu`. Test both.
- **CSS creation is asynchronous**: poll cluster details until status is `200` and an endpoint is returned.
- **Chunk size**: 8000 chars with 500-char overlap balances context window usage and search precision.
- **nginx co-hosting**: if an existing MCP server (e.g. SearXNG) already uses port 8788, move it behind nginx on an internal port and route both by path prefix.

## Deployment Workflow

### Phase 1: Provision CSS + ECS

#### 1. Install SDK dependencies

```bash
pip install huaweicloudsdkcore huaweicloudsdkcss huaweicloudsdkvpc \
            huaweicloudsdkecs huaweicloudsdkiam
```

#### 2. Run the provisioner

```bash
export HWC_ACCESS_KEY_ID="..."
export HWC_SECRET_ACCESS_KEY="..."
export HWC_PROJECT_ID="afc631438d8941d0b10aaa2cee2bf94c"
export HWC_REGION="la-north-2"
export HWC_REPO_URL="https://github.com/binrogithub/1-3-Cloud-Adoption-Skills"

python3 scripts/provision_css_search.py
```

This creates:
- VPC/subnet/security group (or reuses existing if `HWC_VPC_ID`/`HWC_SUBNET_ID` set)
- CSS cluster (COMMON disk, auto-fallback to HIGH on `CSS.0065`)
- ECS with EIP (s6.xlarge.2, Ubuntu 22.04, 100GB SSD)
- SSH keypair
- State JSON: `css-search-<timestamp>-state.json`

#### 3. Poll for readiness

```bash
python3 scripts/poll_readiness.py css-search-<timestamp>-state.json
```

This waits for:
- CSS cluster status = 200 (available, typically 10-15 min)
- ECS status = ACTIVE (typically 2-3 min)

Then discovers and writes to state:
- `css_endpoint`: e.g. `http://192.168.0.57:9200`
- `ecs_public_ip`: e.g. `101.44.184.244`

### Phase 2: Index + MCP

#### 4. Deploy code search MCP

```bash
bash scripts/deploy_css_mcp.sh css-search-<timestamp>-state.json
```

This single script (reads state JSON):
- Verifies CSS connectivity from ECS
- Clones and indexes the repo into CSS
- Deploys the FastMCP server on port 8789
- Configures nginx reverse proxy on port 8788
- Prints the claude-glm MCP config

To index a different repo than the one in state:

```bash
bash scripts/deploy_css_mcp.sh css-search-*-state.json https://github.com/org/other-repo
```

#### 5. Register MCP in claude-glm

Add the printed config to `~/.claude-glm-config/.claude.json`:

```json
{
  "mcpServers": {
    "css-search": {
      "type": "http",
      "url": "http://<ECS_PUBLIC_IP>:8788/css/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_TOKEN>"
      }
    }
  }
}
```

Restart `claude-glm`. The three tools are now available:

| Tool | Description |
|------|-------------|
| `mcp__css-search__search_code` | Search indexed code/docs by query, with optional category/skill filter |
| `mcp__css-search__list_skills` | List all categories and skills with document counts |
| `mcp__css-search__get_file` | Retrieve full file content by repo path |

#### 6. Validate

```bash
# Test the MCP endpoint from the laptop:
curl -s -H "Authorization: Bearer $MCP_TOKEN" \
     -H "Accept: application/json, text/event-stream" \
     http://$ECS_PUBLIC_IP:8788/css/mcp

# Or use the MCP SDK:
python3 -c "
import asyncio
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

async def test():
    async with streamablehttp_client(
        url='http://$ECS_PUBLIC_IP:8788/css/mcp',
        headers={'Authorization': 'Bearer $MCP_TOKEN'},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f'{len(tools.tools)} tools:', [t.name for t in tools.tools])
            result = await session.call_tool('search_code', {'query': 'test', 'size': 1})
            print('Search works:', len(result.content) > 0)

asyncio.run(test())
"
```

## Re-indexing After Repo Updates

```bash
ssh -i $SSH_KEY root@$ECS_IP "
  cd /tmp && rm -rf $REPO_NAME
  git clone --depth 1 $REPO_URL
  python3 /opt/index_repo_to_css.py /tmp/$REPO_NAME http://<css_private_ip>:9200
"
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `CSS.0065 The disk has been sold out` | COMMON disk unavailable in AZ | `provision_css_search.py` auto-retries with HIGH |
| `VPC.0114 Quota exceeded for resources: ['router']` | VPC quota exhausted | Set `HWC_VPC_ID` and `HWC_SUBNET_ID` to reuse existing |
| CSS polling times out after 20 min | CSS creation failed (status 303) | Check cluster status in Huawei Cloud console; look for `failed_reason` |
| ECS polling times out | ECS creation failed | Check ECS status in console; verify flavor available in AZ |
| `curl :9200` returns connection refused from ECS | CSS not ready or IP changed | Scan subnet for port 9200; poll CSS cluster status |
| MCP returns `401 Unauthorized` | Wrong or missing bearer token | Verify `MCP_TOKEN` matches between server and client config |
| MCP returns `Missing session ID` | Using curl without SSE transport | This is normal; MCP clients (Claude Code) handle SSE natively |
| nginx `502 Bad Gateway` | MCP server crashed | Check `/var/log/css_mcp_server.log`; restart with systemd |
| SSH `Permission denied` | Wrong user or key | Try both `root` and `ubuntu`; verify key matches Huawei keypair |
| Search returns 0 results | Index not created or empty | Check `curl http://<css_ip>:9200/<index>/_count`; re-run indexer |

## Resources

- [scripts/provision_css_search.py](scripts/provision_css_search.py): Phase 1 — create CSS + ECS from scratch
- [scripts/poll_readiness.py](scripts/poll_readiness.py): Phase 1 — wait for CSS/ECS readiness, discover endpoints
- [scripts/index_repo_to_css.py](scripts/index_repo_to_css.py): Phase 2 — repo → CSS bulk indexer
- [scripts/deploy_css_mcp.sh](scripts/deploy_css_mcp.sh): Phase 2 — one-shot deploy (index + MCP + nginx)
- [assets/config/css_mcp_server.py](assets/config/css_mcp_server.py): FastMCP HTTP server with 3 tools
- [assets/config/css-mcp.service.example](assets/config/css-mcp.service.example): systemd unit
- [references/css-indexing.md](references/css-indexing.md): indexing strategy, chunking, and mapping details
- [references/mcp-transport.md](references/mcp-transport.md): FastMCP HTTP/SSE transport and nginx proxy notes
