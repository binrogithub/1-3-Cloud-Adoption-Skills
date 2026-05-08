# LiteLLM + SearXNG AI Coding Gateway — Single Huawei Cloud ECS

A reproducible single-host gateway for AI coding agents that:

- Fronts **Huawei Cloud MaaS** (`glm-5.1` etc.) with **LiteLLM** for multi-user
  keys, FinOps budgeting, request caching, and audit.
- Hosts **SearXNG** as a private meta-search and exposes it over a
  **bearer-authenticated remote MCP** (`web_search`, `fetch_url`).
- Plugs into **Claude Code** via `claude-code-router` (`claude-glm`) without
  disturbing the user's normal `claude` install (`CLAUDE_CONFIG_DIR` isolation).

The skill content is in [SKILL.md](SKILL.md). Read it first.

## Layout

```
SKILL.md                                       skill instructions
references/
  deployment-walkthrough.md                    chronological recipe
  aicoding-agent-integration.md                ccr + claude-glm + LiteLLM
  searxng-mcp.md                               FastMCP HTTP transport detail
  troubleshooting.md                           every issue we hit + fix
assets/config/
  litellm.env.example                          /etc/litellm/litellm.env
  litellm.config.yaml.example                  /etc/litellm/config.yaml
  litellm.service.example                      systemd unit
  searxng-docker-compose.yml                   /opt/searxng/docker-compose.yml
  searxng-settings.yml                         /opt/searxng/searxng/settings.yml
  searxng_mcp_server.py                        /opt/searxng-mcp/server.py
  searxng-mcp.service.example                  systemd unit
  claude-code-router.config.json.example       ~/.claude-code-router/config.json
  claude-glm-wrapper.sh.example                ~/.local/bin/claude-glm
scripts/
  install_litellm.sh                           run on ECS
  install_searxng_and_mcp.sh                   run on ECS
  wire_claude_glm.sh                           run on laptop
  validate_e2e.sh                              run on laptop
```

## One-shot deploy

```bash
# On the laptop:
export ECS_PUBLIC_IP=...
export LITELLM_MASTER_KEY="sk-$(openssl rand -hex 24)"
export REDIS_PWD=$(openssl rand -hex 16)
export PG_PWD=$(openssl rand -hex 16)
export MCP_TOKEN=$(openssl rand -hex 16)
export HUAWEI_MAAS_API_BASE='https://api-ap-southeast-1.modelarts-maas.com/openai/v1'
export HUAWEI_MAAS_API_KEY=...

scp scripts/install_litellm.sh scripts/install_searxng_and_mcp.sh root@$ECS_PUBLIC_IP:/root/

ssh root@$ECS_PUBLIC_IP \
    REDIS_PWD=$REDIS_PWD PG_PWD=$PG_PWD LITELLM_MASTER_KEY=$LITELLM_MASTER_KEY \
    HUAWEI_MAAS_API_BASE=$HUAWEI_MAAS_API_BASE HUAWEI_MAAS_API_KEY=$HUAWEI_MAAS_API_KEY \
    bash /root/install_litellm.sh

ssh root@$ECS_PUBLIC_IP MCP_TOKEN=$MCP_TOKEN bash /root/install_searxng_and_mcp.sh

# Open SG (4000, 8788) to your /32 here, by SDK or Console.

bash scripts/wire_claude_glm.sh
bash scripts/validate_e2e.sh
```

After this, `claude-glm` works end-to-end through LiteLLM and can call
`mcp__searxng__web_search`. Plain `claude` is unchanged.
