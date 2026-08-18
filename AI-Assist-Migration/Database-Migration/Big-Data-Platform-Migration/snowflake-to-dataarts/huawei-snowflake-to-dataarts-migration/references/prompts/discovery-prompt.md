# Discovery Prompt

You are performing discovery for a Snowflake to DataArts migration.

Given:
- Job name: {{job_name}}
- Artifact directory: {{artifact_dir}}
- DLI queue: {{dli_queue}}

Execute:
1. snowflake_dataarts_demo_plan({ job_name, artifact_dir, dli_queue })
2. snowflake_dataarts_demo_status({ job_name })

Report the migration scope and any existing run state.
