# Installation Guide

## Prerequisites

- Node.js 18+
- npm 9+
- Huawei Cloud account with appropriate IAM permissions
- OpenCode or Hermes agent runtime

## Install All MCPs

```bash
# Pricing MCP
cd <INSTALLATION_ROOT>/shared-mcps/huaweicloud-pricing
npm install

# Deploy MCP
cd <INSTALLATION_ROOT>/shared-mcps/huaweicloud-deploy
npm install

# DRS MCP (requires Playwright)
cd <INSTALLATION_ROOT>/shared-mcps/huaweicloud-drs
npm install
npx playwright install chromium

# Ticket MCP
cd <INSTALLATION_ROOT>/shared-mcps/huaweicloud-ticket
npm install

# DataArts Deploy Agent
cd <INSTALLATION_ROOT>/shared-mcps/dataarts-deploy-agent
npm install
```

## Verify Installation

```bash
# Test each MCP
node <INSTALLATION_ROOT>/shared-mcps/huaweicloud-pricing/server.mjs --help
node <INSTALLATION_ROOT>/shared-mcps/huaweicloud-deploy/server.mjs --help
node <INSTALLATION_ROOT>/shared-mcps/huaweicloud-drs/server.mjs --help
node <INSTALLATION_ROOT>/shared-mcps/huaweicloud-ticket/server.mjs --help
node <INSTALLATION_ROOT>/shared-mcps/dataarts-deploy-agent/mcp-server.mjs --help
```
