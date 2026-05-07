# Host Migration

This package captures a reusable Huawei Cloud host migration workflow for AI-assisted execution and troubleshooting. It focuses on cross-region ECS and on-prem VMware migration with an `SMS`-first policy, automatic rsync fallback when the source is SMS-incompatible, and packaged evidence for reruns and postmortems.

## Included Assets

- [skill/SKILL.md](./skill/SKILL.md): Main migration workflow, trigger rules, and error-handling policy
- [scripts/mgc_migrate.py](./scripts/mgc_migrate.py): Core migration orchestration logic
- [scripts/run_migration.sh](./scripts/run_migration.sh): Thin wrapper used by Terraform local-exec
- [skill/references/](./skill/references): Runbook, lessons learned, reuse bundle guidance, and migration summary
- [skill/bundles/](./skill/bundles): Archived migration evidence and reusable output bundles

## Typical Use

- Run Huawei Cloud MGC or SMS cross-region migration end to end with Terraform
- Troubleshoot migration errors such as `SMS.6504`, `SMS.6602`, `SMS.6603`, `SMS.6617`, `SMS.7605`, and `SMS.8115`
- Switch safely from SMS to rsync staged migration when the source OS is incompatible
- Reuse prior bundles for migration postmortems, runbook refinement, and replication
