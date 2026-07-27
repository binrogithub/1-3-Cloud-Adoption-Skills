# Capability Gap Report

## Date

2026-07-27

## Summary

Total gaps identified: 20
- MANUAL_STEP: 14
- EXTEND_EXISTING_MCP: 1
- NOT_REQUIRED: 3
- USE_EXISTING_TOOL: 0
- CREATE_NEW_MCP: 0
- BLOCKED: 1 (DRS pricing only — optional, does not block core migration)

## Gap Details

### huawei-cce-cross-region-velero-migration

| Gap ID | Phase | Capability Required | MCPs Evaluated | Decision | Evidence |
|---|---|---|---|---|---|
| GAP-CCE-001 | discovery | CCE cluster discovery | huaweicloud-deploy | MANUAL_STEP | CCE not in supported services |
| GAP-CCE-002 | execution | Velero backup/restore | all | MANUAL_STEP | No Velero MCP exists |
| GAP-CCE-003 | arch_validation | K8s version validation | all | MANUAL_STEP | No CCE MCP tool |
| GAP-CCE-004 | execution | StorageClass mapping | all | MANUAL_STEP | No CCE MCP tool |
| GAP-CCE-005 | cutover | DNS record migration | all | MANUAL_STEP | No DNS MCP tool |
| GAP-CCE-006 | execution | ELB/EIP cross-region migration | huaweicloud-deploy | MANUAL_STEP | No cross-region tool |
| GAP-CCE-007 | plan_generation | CCE Terraform generation | huaweicloud-deploy | EXTEND_EXISTING_MCP | CCE not in supported services |

### huawei-postgresql-ecs-to-rds-drs-cross-region

| Gap ID | Phase | Capability Required | MCPs Evaluated | Decision | Evidence |
|---|---|---|---|---|---|
| GAP-PG-001 | arch_validation | PostgreSQL config validation | huaweicloud-drs | MANUAL_STEP | No SSH tool in MCP |
| GAP-PG-002 | arch_validation | Extension compatibility | huaweicloud-drs | MANUAL_STEP | No PG extension tool |
| GAP-PG-003 | rollback | DRS task stop | huaweicloud-drs | MANUAL_STEP | No stop tool in MCP |
| GAP-PG-004 | execution | VPN connectivity | all | NOT_REQUIRED | OUT_OF_SCOPE_FOR_THIS_SCENARIO — public EIP is the supported architecture |
| GAP-PG-005 | cutover | App connection update | all | MANUAL_STEP | No app management tool |
| GAP-PG-006 | validation | DDL comparison | all | MANUAL_STEP | No schema comparison tool |
| GAP-PG-007 | validation | Row count validation | all | MANUAL_STEP | No data validation tool |

### huawei-snowflake-to-dataarts-migration

| Gap ID | Phase | Capability Required | MCPs Evaluated | Decision | Evidence |
|---|---|---|---|---|---|
| GAP-DA-001 | discovery | Snowflake source extraction | dataarts-deploy-agent | MANUAL_STEP | No Snowflake MCP |
| GAP-DA-002 | arch_validation | Schema mapping | dataarts-deploy-agent | MANUAL_STEP | No mapping tool |
| GAP-DA-003 | arch_validation | SQL compatibility analysis | dataarts-deploy-agent | MANUAL_STEP | No analysis tool |
| GAP-DA-004 | execution | Production migration flow | dataarts-deploy-agent | NOT_REQUIRED | Demo only |
| GAP-DA-005 | rollback | DataArts resource cleanup | dataarts-deploy-agent | MANUAL_STEP | No cleanup tool |
| GAP-DA-006 | execution | Incremental/delta migration | dataarts-deploy-agent | NOT_REQUIRED | Demo only |

### Cross-skill gaps

| Gap | Affected Skills | Decision | Evidence |
|---|---|---|---|
| DRS pricing | huawei-postgresql-ecs-to-rds-drs-cross-region | BLOCKED | resource_spec not found in BSS/OCE — affects cost estimation only, does not block core migration |

## Full Gap Review

### GAP-CCE-001 — CCE cluster discovery
- **Skill**: huawei-cce-cross-region-velero-migration
- **Migration phase**: discovery
- **Required capability**: Discover CCE cluster details (version, nodes, addons, workloads)
- **Existing MCPs evaluated**: huaweicloud-deploy (Terraform-based, no CCE API)
- **Tools evaluated**: GenerateTerraformFromArchitecture, RunTerraformPlan, ValidateTerraformConfiguration, ExplainTerraformPlan
- **Decision**: MANUAL_STEP
- **Evidence**: CCE is not in huaweicloud-deploy supported-services.json
- **Impact on scenario**: Discovery must be performed manually via console or CLI
- **Proposed owner**: Human operator
- **Recommended next action**: Use kubectl and CCE CLI for discovery; document results
- **Blocks core migration**: No (discovery is ASSISTED, not AUTOMATED)

### GAP-CCE-002 — Velero backup/restore
- **Skill**: huawei-cce-cross-region-velero-migration
- **Migration phase**: execution
- **Required capability**: Execute Velero backup on source and restore on target
- **Existing MCPs evaluated**: all (none provide Velero operations)
- **Tools evaluated**: N/A
- **Decision**: MANUAL_STEP
- **Evidence**: No Velero MCP exists in the ecosystem
- **Impact on scenario**: Core migration execution is entirely manual
- **Proposed owner**: Human operator
- **Recommended next action**: Execute Velero commands manually; document in runbook
- **Blocks core migration**: No (execution phase is MANUAL by design for this EXPERIMENTAL skill)

### GAP-CCE-003 — K8s version validation
- **Skill**: huawei-cce-cross-region-velero-migration
- **Migration phase**: architecture_validation
- **Required capability**: Validate Kubernetes version compatibility between source and target CCE
- **Existing MCPs evaluated**: all
- **Tools evaluated**: N/A
- **Decision**: MANUAL_STEP
- **Evidence**: No CCE MCP tool for version checks
- **Impact on scenario**: Version compatibility must be verified manually
- **Proposed owner**: Human operator
- **Recommended next action**: Compare kubectl version output; check CCE version support matrix
- **Blocks core migration**: No

### GAP-CCE-004 — StorageClass mapping
- **Skill**: huawei-cce-cross-region-velero-migration
- **Migration phase**: execution
- **Required capability**: Map StorageClasses from source to target cluster
- **Existing MCPs evaluated**: all
- **Tools evaluated**: N/A
- **Decision**: MANUAL_STEP
- **Evidence**: No CCE MCP tool for StorageClass operations
- **Impact on scenario**: StorageClass mapping must be configured manually in Velero ConfigMap
- **Proposed owner**: Human operator
- **Recommended next action**: Create Velero StorageClass mapping ConfigMap manually
- **Blocks core migration**: No

### GAP-CCE-005 — DNS record migration
- **Skill**: huawei-cce-cross-region-velero-migration
- **Migration phase**: cutover
- **Required capability**: Migrate DNS records to point to target cluster
- **Existing MCPs evaluated**: all
- **Tools evaluated**: N/A
- **Decision**: MANUAL_STEP
- **Evidence**: No DNS MCP exists
- **Impact on scenario**: DNS cutover is manual
- **Proposed owner**: Human operator
- **Recommended next action**: Update DNS records manually via DNS provider
- **Blocks core migration**: No

### GAP-CCE-006 — ELB/EIP cross-region migration
- **Skill**: huawei-cce-cross-region-velero-migration
- **Migration phase**: execution
- **Required capability**: Recreate ELB and EIP configuration in target region
- **Existing MCPs evaluated**: huaweicloud-deploy
- **Tools evaluated**: GenerateTerraformFromArchitecture (supports ELB/EIP but not cross-region workflow)
- **Decision**: MANUAL_STEP
- **Evidence**: No cross-region ELB/EIP migration tool
- **Impact on scenario**: ELB/EIP must be recreated manually in target region
- **Proposed owner**: Human operator
- **Recommended next action**: Use huaweicloud-deploy to generate Terraform for target ELB/EIP
- **Blocks core migration**: No

### GAP-CCE-007 — CCE Terraform generation (EXTEND_EXISTING_MCP)
- **Skill**: huawei-cce-cross-region-velero-migration
- **Migration phase**: plan_generation
- **Required capability**: Generate Terraform configuration for CCE clusters
- **Existing MCPs evaluated**: huaweicloud-deploy
- **Tools evaluated**: GenerateTerraformFromArchitecture
- **Decision**: EXTEND_EXISTING_MCP
- **Evidence**: CCE not in huaweicloud-deploy supported-services.json
- **Impact on scenario**: Terraform generation for CCE is not available
- **Proposed owner**: MCP developer
- **Recommended next action**: Extend huaweicloud-deploy to support CCE service type
- **Blocks core migration**: No (plan_generation is ASSISTED)

#### Extension Design for GAP-CCE-007

- **Target MCP**: huaweicloud-deploy
- **Proposed tool**: GenerateCceTerraformFromArchitecture (or extend GenerateTerraformFromArchitecture)
- **Input schema**:
  ```json
  {
    "architecture_id": "string (required)",
    "cce_config": {
      "cluster_name": "string",
      "version": "string",
      "flavor": "string",
      "node_count": "integer",
      "vpc_id": "string",
      "subnet_id": "string",
      "security_group_id": "string"
    }
  }
  ```
- **Output schema**:
  ```json
  {
    "files_created": ["versions.tf", "providers.tf", "variables.tf", "main.tf", "outputs.tf", "terraform.tfvars.example"],
    "architecture_id": "string"
  }
  ```
- **Read/write classification**: write_local (writes .tf files only, no cloud operations)
- **Approval requirement**: No (Terraform generation is non-destructive; apply is blocked by MCP design)
- **Expected side effects**: Creates .tf files in workspace directory
- **Unit test plan**: Test CCE architecture JSON → Terraform file generation; verify no secrets in output; validate generated .tf with terraform validate
- **Security considerations**: No credentials in generated files; .tfvars.example only; no cloud API calls
- **Status**: READY_FOR_REVIEW (draft design only, not implemented)

### GAP-PG-001 — PostgreSQL config validation
- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Migration phase**: architecture_validation
- **Required capability**: Validate PostgreSQL configuration (wal_level, replication slots, max_wal_senders)
- **Existing MCPs evaluated**: huaweicloud-drs
- **Tools evaluated**: drs_read_context (console-only, no SSH)
- **Decision**: MANUAL_STEP
- **Evidence**: No SSH tool in huaweicloud-drs MCP
- **Impact on scenario**: Source PostgreSQL config must be validated via manual SSH
- **Proposed owner**: Human operator (SSH to ECS)
- **Recommended next action**: SSH to ECS, run `SHOW wal_level; SHOW max_replication_slots; SHOW max_wal_senders;`
- **Blocks core migration**: No (pre-check catches misconfiguration, but pre-verification is recommended)

### GAP-PG-002 — Extension compatibility
- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Migration phase**: architecture_validation
- **Required capability**: Check PostgreSQL extension compatibility between source and RDS
- **Existing MCPs evaluated**: huaweicloud-drs
- **Tools evaluated**: drs_run_precheck (checks some compatibility but not all extensions)
- **Decision**: MANUAL_STEP
- **Evidence**: No PG extension comparison tool
- **Impact on scenario**: Extension compatibility must be checked manually
- **Proposed owner**: Human operator
- **Recommended next action**: Compare `SELECT * FROM pg_available_extensions;` on source and target
- **Blocks core migration**: No (DRS pre-check catches some incompatibilities)

### GAP-PG-003 — DRS task stop
- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Migration phase**: rollback
- **Required capability**: Stop/terminate a running DRS task
- **Existing MCPs evaluated**: huaweicloud-drs
- **Tools evaluated**: drs_get_task_status (read-only, no stop)
- **Decision**: MANUAL_STEP
- **Evidence**: No stop/terminate tool in huaweicloud-drs MCP
- **Impact on scenario**: DRS task stop requires manual console operation
- **Proposed owner**: Human operator (DRS console)
- **Recommended next action**: Stop task manually in DRS console; consider adding drs_stop_task tool
- **Blocks core migration**: No (rollback is MANUAL by design)

### GAP-PG-004 — VPN connectivity
- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Migration phase**: execution
- **Required capability**: VPN connectivity between regions
- **Existing MCPs evaluated**: all
- **Tools evaluated**: N/A
- **Decision**: NOT_REQUIRED
- **Evidence**: OUT_OF_SCOPE_FOR_THIS_SCENARIO — the supported architecture uses public EIP with /32 CIDR, Security Groups, and pg_hba.conf restrictions. VPN is not needed for this scenario.
- **Impact on scenario**: None — EIP architecture is intentional and supported
- **Proposed owner**: N/A
- **Recommended next action**: None — do not attempt to design, create, or recommend VPN for this scenario
- **Blocks core migration**: No

### GAP-PG-005 — App connection update
- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Migration phase**: cutover
- **Required capability**: Update application connection strings to point to target RDS
- **Existing MCPs evaluated**: all
- **Tools evaluated**: N/A
- **Decision**: MANUAL_STEP
- **Evidence**: No application management MCP
- **Impact on scenario**: Application cutover is manual
- **Proposed owner**: Human operator
- **Recommended next action**: Update connection strings in application configuration; restart application
- **Blocks core migration**: No (cutover is MANUAL by design)

### GAP-PG-006 — DDL comparison
- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Migration phase**: validation
- **Required capability**: Compare DDL structure between source and target
- **Existing MCPs evaluated**: all
- **Tools evaluated**: N/A
- **Decision**: MANUAL_STEP
- **Evidence**: No schema comparison tool
- **Impact on scenario**: DDL validation must be performed manually (e.g., pg_dump --schema-only diff)
- **Proposed owner**: Human operator
- **Recommended next action**: Use pg_dump to compare schemas; use DAS for visual comparison
- **Blocks core migration**: No

### GAP-PG-007 — Row count validation
- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Migration phase**: validation
- **Required capability**: Compare row counts between source and target tables
- **Existing MCPs evaluated**: all
- **Tools evaluated**: N/A
- **Decision**: MANUAL_STEP
- **Evidence**: No data validation tool
- **Impact on scenario**: Row count validation must be performed manually
- **Proposed owner**: Human operator
- **Recommended next action**: Run COUNT(*) queries on both source and target; compare results
- **Blocks core migration**: No

### GAP-DA-001 — Snowflake source extraction
- **Skill**: huawei-snowflake-to-dataarts-migration
- **Migration phase**: discovery
- **Required capability**: Extract schema and task graph from Snowflake
- **Existing MCPs evaluated**: dataarts-deploy-agent
- **Tools evaluated**: snowflake_dataarts_demo_plan (requires pre-extracted artifacts)
- **Decision**: MANUAL_STEP
- **Evidence**: No Snowflake MCP for source extraction
- **Impact on scenario**: Snowflake extraction must be done manually (Snowflake UI, SnowSQL, or SHARE)
- **Proposed owner**: Human operator
- **Recommended next action**: Use SnowSQL or Snowflake UI to export task graph and SQL
- **Blocks core migration**: No (demo flow accepts pre-extracted artifacts)

### GAP-DA-002 — Schema mapping
- **Skill**: huawei-snowflake-to-dataarts-migration
- **Migration phase**: architecture_validation
- **Required capability**: Map Snowflake schema to DataArts Factory model
- **Existing MCPs evaluated**: dataarts-deploy-agent
- **Tools evaluated**: snowflake_dataarts_demo_plan (generates plan but mapping is manual)
- **Decision**: MANUAL_STEP
- **Evidence**: No automated mapping tool
- **Impact on scenario**: Schema mapping decisions are manual
- **Proposed owner**: Human operator
- **Recommended next action**: Review and adjust SQL adaptation manually
- **Blocks core migration**: No

### GAP-DA-003 — SQL compatibility analysis
- **Skill**: huawei-snowflake-to-dataarts-migration
- **Migration phase**: architecture_validation
- **Required capability**: Analyze SQL compatibility between Snowflake and DLI
- **Existing MCPs evaluated**: dataarts-deploy-agent
- **Tools evaluated**: snowflake_dataarts_demo_plan (provides adaptation but not compatibility scoring)
- **Decision**: MANUAL_STEP
- **Evidence**: No SQL analysis tool
- **Impact on scenario**: SQL compatibility must be reviewed manually
- **Proposed owner**: Human operator
- **Recommended next action**: Review adapted SQL; test in DLI; fix incompatibilities
- **Blocks core migration**: No

### GAP-DA-004 — Production migration flow
- **Skill**: huawei-snowflake-to-dataarts-migration
- **Migration phase**: execution
- **Required capability**: Production-grade migration execution
- **Existing MCPs evaluated**: dataarts-deploy-agent
- **Tools evaluated**: snowflake_dataarts_demo_run, snowflake_dataarts_demo_start
- **Decision**: NOT_REQUIRED
- **Evidence**: Skill scope is demo/POC only
- **Impact on scenario**: None — demo flow is the intended scope
- **Proposed owner**: N/A
- **Recommended next action**: N/A
- **Blocks core migration**: No

### GAP-DA-005 — DataArts resource cleanup
- **Skill**: huawei-snowflake-to-dataarts-migration
- **Migration phase**: rollback
- **Required capability**: Clean up DataArts resources created during migration
- **Existing MCPs evaluated**: dataarts-deploy-agent
- **Tools evaluated**: N/A (no cleanup tool)
- **Decision**: MANUAL_STEP
- **Evidence**: No cleanup/delete tool in dataarts-deploy-agent
- **Impact on scenario**: DataArts resources must be cleaned up manually
- **Proposed owner**: Human operator
- **Recommended next action**: Delete DataArts jobs and DLI tables manually via console
- **Blocks core migration**: No

### GAP-DA-006 — Incremental/delta migration
- **Skill**: huawei-snowflake-to-dataarts-migration
- **Migration phase**: execution
- **Required capability**: Incremental or delta migration support
- **Existing MCPs evaluated**: dataarts-deploy-agent
- **Tools evaluated**: N/A
- **Decision**: NOT_REQUIRED
- **Evidence**: Skill scope is demo/POC only; incremental migration is not in scope
- **Impact on scenario**: None
- **Proposed owner**: N/A
- **Recommended next action**: N/A
- **Blocks core migration**: No

### Cross-skill gap: DRS pricing
- **Skill**: huawei-postgresql-ecs-to-rds-drs-cross-region
- **Migration phase**: cost_estimation (optional)
- **Required capability**: Price DRS migration tasks
- **Existing MCPs evaluated**: huaweicloud-pricing
- **Tools evaluated**: EstimateTemplateOnDemandPrice, EstimateTemplatePeriodPrice (DRS resource_spec not found)
- **Decision**: BLOCKED
- **Evidence**: DRS resource_spec not found in BSS/OCE pricing catalog
- **Impact on scenario**: Affects cost estimation only. Does NOT block: discovery, readiness, DRS creation, prechecks, execution, validation, cutover, or rollback.
- **Proposed owner**: Huawei Cloud (BSS/OCE catalog gap)
- **Recommended next action**: Request DRS pricing support from Huawei Cloud; use manual cost estimation as workaround
- **Blocks core migration**: No

## New MCP Decisions

No new MCP was required at this time. All gaps can be addressed by:
- MANUAL_STEP (14 gaps)
- EXTEND_EXISTING_MCP (1 gap: CCE support in deploy MCP)
- NOT_REQUIRED (3 gaps: demo-only features + VPN out of scope)
- BLOCKED (1 gap: DRS pricing — optional, does not block core migration)

## Core Migration Blockers

None. No gap blocks the core migration workflow for any skill.
