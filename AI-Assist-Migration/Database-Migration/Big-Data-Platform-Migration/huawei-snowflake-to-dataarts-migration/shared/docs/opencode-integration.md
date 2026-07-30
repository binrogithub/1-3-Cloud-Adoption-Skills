# OpenCode Integration

## Configuration

Add to opencode.json:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "huaweicloud-maas/glm-5.1",
  "provider": {
    "huaweicloud-maas": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Huawei Cloud MaaS",
      "options": {
        "baseURL": "<MCP_SERVER_URL>",
        "apiKey": "<YOUR_MaaS_API_KEY>"
      }
    }
  },
  "skills": {
    "huawei-cce-cross-region-velero-migration": {
      "path": "<INSTALLATION_ROOT>/skills/huawei-cce-cross-region-velero-migration"
    },
    "huawei-postgresql-ecs-to-rds-drs-cross-region": {
      "path": "<INSTALLATION_ROOT>/skills/huawei-postgresql-ecs-to-rds-drs-cross-region"
    },
    "huawei-snowflake-to-dataarts-migration": {
      "path": "<INSTALLATION_ROOT>/skills/huawei-snowflake-to-dataarts-migration"
    },
    "mcp-capability-builder": {
      "path": "<INSTALLATION_ROOT>/shared-skills/mcp-capability-builder"
    }
  },
  "mcp": {
    "huaweicloud-pricing": {
      "type": "local",
      "enabled": true,
      "command": ["node", "<INSTALLATION_ROOT>/shared-mcps/huaweicloud-pricing/server.mjs"],
      "timeout": 30000
    },
    "huaweicloud-deploy": {
      "type": "local",
      "enabled": true,
      "command": ["node", "<INSTALLATION_ROOT>/shared-mcps/huaweicloud-deploy/server.mjs"],
      "timeout": 30000
    },
    "huaweicloud-drs": {
      "type": "local",
      "enabled": true,
      "command": ["node", "<INSTALLATION_ROOT>/shared-mcps/huaweicloud-drs/server.mjs"],
      "timeout": 60000
    },
    "huaweicloud-ticket": {
      "type": "local",
      "enabled": true,
      "command": ["node", "<INSTALLATION_ROOT>/shared-mcps/huaweicloud-ticket/server.mjs"],
      "timeout": 30000
    },
    "dataarts-deploy-agent": {
      "type": "local",
      "enabled": true,
      "command": ["node", "<INSTALLATION_ROOT>/shared-mcps/dataarts-deploy-agent/mcp-server.mjs"],
      "timeout": 30000
    },
    "playwright": {
      "type": "local",
      "enabled": true,
      "command": ["npx", "-y", "@playwright/mcp@latest"],
      "timeout": 30000
    }
  }
}
```

## Loading a Skill

In an OpenCode session:
```
skill huawei-postgresql-ecs-to-rds-drs-cross-region
```

The agent will load the SKILL.md instructions and follow the defined workflow.
