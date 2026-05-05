# Migration Bundle: 2026-04-22-mx2-to-santiago

## Scenario

- Source region: `la-north-2` (Mexico City2)
- Target region: `la-south-2` (Santiago)
- Source VM input ID: `4fb3d857-aa08-4b79-8810-760cab680418`

## Pre-Migration Cleanup

- Resolved source SMS ID: `dceb9146-c28f-4596-8c42-a55b068c31d5`
- Deleted historical source-bound task:
  - `task_id = 073f5212-6175-4f65-9497-cdaeac0f4666`
  - `state = MIGRATE_SUCCESS`

## Migration Execution

- Normal `terraform apply -auto-approve` returned `No changes`.
- Forced execution command:
  - `terraform apply -replace=terraform_data.mgc_region_migration -auto-approve`
- New migration identifiers:
  - `migproject_id = 7a545883-187a-458d-aea0-6e665d295e2e`
  - `task_id = 5f044a0b-cf65-44b0-a816-9914c2b30c96`
  - `target_server_id = 7f110bb2-3332-4ef8-a19b-9013746b76a8`

## Result

- Terminal task state: `MIGRATE_SUCCESS`
- Terminal timestamp (CN): `2026-04-22 07:28:21 +0800`

## Postcheck Summary

- Target VPC name: `vpc-migration`
- Target server EIP: `119.8.149.199`
- Source/target security-group connectivity check: passed
- Task `progress`: remained `null` during RUNNING; completion determined by terminal `state`

## Included Files

- migration_result.json
- precheck_task_cleanup.json
- postcheck_network.json
- task_poll_latest.json
- SKILL.md
- runbook.md
- lessons-learned.md
- reuse-bundle.md

Generated from `/root/mgc-cross-region-migration/out`.
