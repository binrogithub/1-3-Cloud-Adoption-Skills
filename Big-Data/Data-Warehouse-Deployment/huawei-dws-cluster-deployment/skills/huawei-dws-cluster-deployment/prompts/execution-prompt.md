# DWS Cluster Execution Prompt

## Instructions

You are executing a DWS cluster deployment. This phase includes WRITE operations that require explicit approval.

## Preconditions

1. Discovery phase MUST be completed
2. Readiness check MUST be READY or READY_WITH_WARNINGS
3. Architecture plan MUST be approved
4. Explicit approval MUST be received before any write operation

## Rules

1. Execute ONE phase at a time
2. Use secure password input (--cli-jsonInput or protected env var)
3. Verify after EVERY write operation
4. Stop if cluster enters FAILED state
5. Stop if polling timeout is reached
6. Never auto-delete or auto-restore
7. Never include passwords in logs or artifacts

## Steps

1. **Prepare network prerequisites** (if needed)
   - Requires: approval for creation
   - Verify: resources exist after creation

2. **Create cluster** (EXPLICIT APPROVAL REQUIRED)
   - Command: `hcloud DWS CreateCluster ...`
   - Verify: `hcloud DWS ListClusters` shows new cluster

3. **Poll cluster creation**
   - Command: `hcloud DWS ShowClusters`
   - Until: operational state or failure or timeout

4. **Verify cluster**
   - Commands: ShowClusters, ListClusterDetails, ListClusterNodes
   - Verify: all parameters match

5. **Configure public access** (if requested, APPROVAL REQUIRED)
   - Verify: EIP bound, SG rule valid

6. **Verify connectivity** (MANUAL)
   - Test: psql/JDBC connection

7. **Create database and schemas** (MANUAL, APPROVAL REQUIRED)
   - Execute: SQL DDL

8. **OBS data load** (if requested, MANUAL, APPROVAL REQUIRED)
   - Create: external tables
   - Execute: INSERT SELECT

9. **Configure snapshot policy** (APPROVAL REQUIRED)
   - Command: `hcloud DWS CreateSnapshot`
   - Verify: `hcloud DWS ListSnapshots`

10. **Operational validation**
    - Verify: health, connectivity, storage, monitoring

11. **Generate final report**

## Stop Conditions

- Approval denied
- Cluster FAILED state
- Polling timeout
- Connectivity failure
- Any unrecoverable error
