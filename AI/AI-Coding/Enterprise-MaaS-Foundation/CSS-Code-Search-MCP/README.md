# CSS Code Search MCP

Deploy a Huawei Cloud CSS/OpenSearch code-search MCP server so that Claude Code (`claude-glm`) can search a GitHub repository's code and docs as native MCP tools.

## Quick Start

```bash
# Phase 1: Provision (from laptop):
export HWC_ACCESS_KEY_ID="..." HWC_SECRET_ACCESS_KEY="..." HWC_PROJECT_ID="..."
python3 scripts/provision_css_search.py
python3 scripts/poll_readiness.py css-search-*-state.json

# Phase 2: Deploy (from laptop):
bash scripts/deploy_css_mcp.sh css-search-*-state.json
```

Then add the printed MCP config to `~/.claude-glm-config/.claude.json` and restart `claude-glm`.

## MCP Tools

| Tool | Description |
|------|-------------|
| `mcp__css-search__search_code` | Search code/docs by query with category/skill filters |
| `mcp__css-search__list_skills` | List all categories and skills with doc counts |
| `mcp__css-search__get_file` | Retrieve full file content by repo path |

## Layout

```
SKILL.md                                   skill instructions
README.md                                  this file
scripts/
  provision_css_search.py                  Phase 1 - create CSS + ECS from scratch
  poll_readiness.py                        Phase 1 - wait for readiness, discover endpoints
  index_repo_to_css.py                     Phase 2 - repo → CSS bulk indexer
  deploy_css_mcp.sh                        Phase 2 - one-shot deploy script
assets/config/
  css_mcp_server.py                        FastMCP HTTP server (3 tools)
  css-mcp.service.example                  systemd unit
references/
  css-indexing.md                          indexing strategy and mapping
  mcp-transport.md                         FastMCP transport and nginx proxy
agents/
  openai.yaml                              skill interface definition
```

## Prerequisites

- Huawei Cloud AK/SK with ECS, EVS, EIP, VPC, CSS scope.
- Python 3.8+ with pip.
- `jq` for the deploy script.
