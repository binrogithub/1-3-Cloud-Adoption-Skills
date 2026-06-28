Storage migration task creation skill. This skill uses multi-turn Q&A to guide users through HUAWEI Cloud OMS storage migration task setup, so users do not need to memorize API parameters.

[Intent Trigger Rules]
Trigger this skill when the user expresses the following intents:

[Primary Scenario - Create Migration Task]
- "Create a storage migration task", "Create a migration task", "New migration task"
- "Help me create a migration", "Create a migration task for me"
- "Migrate storage", "Migrate data", "Migrate files"
- "Object storage migration", "OBS migration", "S3 migration"
- "OMS migration", "OMS task", "Create OMS task"

[Primary Scenario - Migrate Data to HUAWEI Cloud]
- "Migrate from AWS to HUAWEI Cloud", "Migrate from Alibaba Cloud to HUAWEI Cloud"
- "Migrate from Tencent Cloud", "Migrate from Azure"
- "Move data to HUAWEI Cloud", "Cloud migration"
- "Cross-cloud migration", "Multi-cloud migration"

[Primary Scenario - Prefix Migration]
- "Prefix migration", "Migrate by prefix", "Migrate specified prefix"
- "Migrate files under a specific directory", "Migrate data with a specific prefix"
- "Only migrate selected prefixes", "Migrate data/ directory"

[Primary Scenario - Bucket-to-Bucket Migration]
- "Bucket-to-bucket migration", "Migrate between buckets"
- "Migrate between different buckets in the same cloud"

[Supporting Scenario - Migration Task Management]
- "View migration tasks", "My migration tasks"
- "Migration task status", "Migration progress"
- "View task configuration", "View config"

[Exclusion Scenario - Do Not Trigger]
- If the user only asks conceptual questions such as migration principles, costs, or limits, answer directly without triggering this skill.
- If the user clearly indicates "just asking" or "just learning first", answer first and trigger only after the user confirms they want to create a task.

[Response Scenario - Configuration Query]
- When the user asks "View task configuration", "View config", "Configuration details", or "What information have I entered", the AI must display a table of [Collected Task Data].

[Supported Migration Modes]
- Prefix migration: batch migrate objects by prefix matching.

[Supported Cloud Providers]
- AWS, Azure, Alibaba Cloud, Tencent Cloud, HUAWEI Cloud, QingCloud, Kingsoft Cloud, Baidu Cloud, Qiniu Cloud, UCloud, URL data source.
