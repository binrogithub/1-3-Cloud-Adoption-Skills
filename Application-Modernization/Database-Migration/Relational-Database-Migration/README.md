# Relational Database Migration

Migrate relational databases to Huawei Cloud managed database services (RDS, GaussDB, PostgreSQL) using DRS, UGO, Babelfish, and manual SQL adaptation.

## Skills

| Skill | Source → Target | Tool | Description |
|-------|----------------|------|-------------|
| [huaweicloud-drs-migration](./huaweicloud-drs-migration/SKILL.md) | External DB → RDS | DRS | Migrate databases using Data Replication Service with full+incremental replication, Terraform automation, and zero-downtime cutover. |
| [GaussDB Adaptation](./GaussDB-Adaptation-Skill/SKILL.md) | SQL Server/PostgreSQL → GaussDB | Manual | Adapt SQL dialect, driver, and bulk loading patterns for GaussDB (openGauss-based). Covers real production port landmines. |
| [Oracle to PostgreSQL 17](./Oracle-To-PostgreSQL-migration-skill/SKILL.md) | Oracle → PostgreSQL 17 | Manual | Convert Oracle SQL dialect to PostgreSQL 17 dialect. Language/framework agnostic with pattern scanning and transformation. |
| [SQL Server Babelfish Demo](./SQLServer-postgreSQL-babelfish-finance-demo/SKILL.md) | SQL Server → PostgreSQL | Babelfish | Migrate SQL Server workloads to PostgreSQL through Babelfish with TDS protocol compatibility. Finance demo with parity validation. |

## Migration Tools

| Tool | Purpose |
|------|---------|
| **DRS** (Data Replication Service) | Online database migration with minimal downtime, full+incremental replication |
| **UGO** (Database Migration Tool) | Schema evaluation and migration, syntax conversion |
| **Babelfish** | PostgreSQL extension for SQL Server TDS protocol compatibility |

## Related

- For big data platform migration (Cloudera, Databricks, Teradata → MRS/DWS), see [Big-Data-Platform-Migration](../Big-Data-Platform-Migration/README.md).
- For database deployment on Huawei Cloud, see [Big-Data](../../../Big-Data/README.md).
