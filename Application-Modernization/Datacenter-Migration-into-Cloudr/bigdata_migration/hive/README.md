Hive Data Migration Skill provides the capability for Hive data migration. Usage scenarios: This skill is used when users need to migrate Hive data, consult about migration-related issues, or query the status of migration tasks.
[Trigger Restrictions]
- When this skill is triggered, if the user explicitly expresses the intention to create a task, the task configuration steps must be strictly followed, and private information collection is prohibited.
- This skill is triggered only when the user intends to migrate **Hive** data. If the user does not explicitly specify the resource type for migration, further inquiry is required.

[Intent Recognition Trigger Rules]
This skill will be triggered when the user expresses the following intents:
[Main Scenario - Creating a Hive Migration Task]
- "Create a Hive migration task", "New Hive migration task"
- "Help me create a Hive migration", "Create a Hive migration task", "I want to migrate Hive", "I want to migrate Hive data", "Help me create Hive data"
- "Migrate Hive"

[Main Scenario - Migrating Hive Data to Huawei Cloud]
- "Migrate Hive data from Huawei Cloud MRS to Huawei Cloud MRS", "Migrate Hive data from MRS to MRS"

[Auxiliary Scenario - Configuration Consultation]
- "What configurations are required for Hive incremental migration?", "What configurations are needed for Hive incremental migration?", "What configuration items are required for Hive incremental migration?", "What should I fill in for Hive incremental migration?", "Hive incremental migration configuration items", "What configurations are needed for incremental migration of Hive?", "What configuration items are required for incremental migration of Hive?", "What are the configuration items for Hive incremental migration?"

[Exclusion Scenario - Not Triggered]
- The user only asks conceptual questions about migration principles, costs, restrictions, etc. (Answer directly without triggering this skill)
- The user explicitly states "just asking" or "just want to know" (Answer the question first, and then trigger this skill after confirming the need to create a task)
- The user only mentions migration, full migration, or incremental migration, without specifying that the data type is Hive
- The user mentions CDM migration but does not explicitly state it is a Hive migration

[Supported Migration Modes]
- Hive incremental migration: Full migration of Hive has been completed, and the latest data needs to be synchronized.

[Supported Migration Scenarios]
- Hive incremental migration.