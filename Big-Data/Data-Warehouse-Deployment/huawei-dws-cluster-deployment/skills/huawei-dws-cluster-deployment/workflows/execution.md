# Execution Workflow

## Purpose

Execute the DWS cluster deployment after readiness validation and explicit approval.

## Inputs

- Architecture plan
- Readiness report (READY or READY_WITH_WARNINGS)
- Network resource IDs
- Secure credentials

## Steps

1. **Prepare network prerequisites** (if needed)
   - Create VPC/subnet/SG via huaweicloud-deploy MCP or hcloud CLI
   - Approval: Required for creation
   - Verification: Resources exist and are valid
   - Output: Network resource IDs

2. **Prepare secure credentials**
   - Establish password input mechanism (--cli-jsonInput or env var)
   - Approval: Required
   - Verification: Password not in shell history
   - Output: Credential handling plan

3. **Create cluster** (EXPLICIT APPROVAL REQUIRED)
   - Command: `hcloud DWS CreateCluster --cli-region=<REGION> --cluster.name=<NAME> --cluster.node_type=<TYPE> --cluster.number_of_node=<COUNT> --cluster.security_group_id=<SG_ID> --cluster.subnet_id=<SUBNET_ID> --cluster.user_name=<USERNAME> --cluster.user_pwd=<SECURE_INPUT> --cluster.vpc_id=<VPC_ID> [optional params]`
   - Approval: EXPLICIT REQUIRED
   - Verification: `hcloud DWS ListClusters --cli-region=<REGION>` shows new cluster
   - Output: Cluster ID, creation start time

4. **Poll cluster creation**
   - Command: `hcloud DWS ShowClusters --cli-region=<REGION>`
   - Approval: None
   - Verification: Cluster reaches operational state
   - Polling: interval, timeout, success/failure states
   - Output: Creation status

5. **Verify cluster**
   - Commands: ShowClusters, ListClusterDetails, ListClusterNodes
   - Approval: None
   - Verification: All parameters match expected
   - Output: Validation report

6. **Configure public access** (if requested, EXPLICIT APPROVAL REQUIRED)
   - Bind EIP
   - Configure security group rule
   - Approval: EXPLICIT REQUIRED
   - Verification: EIP bound, rule valid
   - Output: Public access configuration

7. **Verify connectivity** (MANUAL)
   - Test connection via psql/JDBC
   - Approval: Required
   - Verification: SELECT version() succeeds
   - Output: Connectivity result

8. **Create database and schemas** (MANUAL)
   - Execute SQL DDL
   - Approval: Required
   - Verification: Database and schemas exist
   - Output: Schema plan

9. **OBS data load** (if requested, MANUAL)
   - Create external tables
   - Execute INSERT SELECT
   - Approval: Required
   - Verification: Data loaded
   - Output: Load plan

10. **Configure snapshot policy** (EXPLICIT APPROVAL REQUIRED for write)
    - Create snapshot or configure schedule
    - Approval: Required
    - Verification: Snapshot/policy listed
    - Output: Snapshot policy report

## Outputs

- artifacts/dws-cluster-creation-request.json
- artifacts/dws-cluster-creation-status.md
- artifacts/dws-cluster-validation-report.md
- artifacts/dws-database-schema-plan.sql
- artifacts/dws-obs-load-plan.md
- artifacts/dws-snapshot-policy-report.md

## Stop Conditions

- CreateCluster rejected
- Cluster enters FAILED state
- Polling timeout
- Connectivity failure
- Any step requiring approval is denied

## Failure Handling

- Do NOT auto-delete failed cluster
- Do NOT auto-retry CreateCluster
- Report failure with details
- Preserve all artifacts for investigation
