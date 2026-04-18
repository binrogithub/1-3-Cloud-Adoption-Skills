# GaussDB Adaptation Skill

This child skill package focuses on adapting SQL Server or vanilla PostgreSQL workloads to Huawei GaussDB and openGauss-compatible environments. It is intended for database migration scenarios where SQL dialect differences, driver and authentication behavior, and bulk-load replacement patterns must be resolved before application cutover.

## Included Assets

- [SKILL.md](./SKILL.md): Main skill definition, trigger conditions, and workflow guidance
- [references/](./references): SQL dialect mapping, connectivity guidance, bulk-load patterns, and common pitfalls
- [scripts/](./scripts): Audit and connection-probe helper scripts

## Typical Use

- Audit a codebase for GaussDB-incompatible SQL and application patterns
- Rewrite SQL Server or PostgreSQL syntax into working GaussDB-compatible SQL
- Validate driver choice and authentication mode against target GaussDB versions
- Verify end-to-end connectivity and bulk-load behavior before production migration
