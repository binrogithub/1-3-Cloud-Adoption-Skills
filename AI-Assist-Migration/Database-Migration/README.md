# Database Migration

This use case covers migration and modernization paths for enterprise databases and data platforms, including relational databases, big data platforms, and data warehouses. It also supports target-state decisions across managed and modern database services.

> **For deployment of big data infrastructure on Huawei Cloud** (MRS, DWS, DLI, OBS, DataArts Studio), see [Big-Data](../../Big-Data/README.md).

## Migration Scenarios

### Relational Database Migration

Migrate relational databases (Oracle, SQL Server, PostgreSQL, MySQL) to Huawei Cloud managed databases (RDS, GaussDB, PostgreSQL) using tools like DRS, UGO, and Babelfish.

- [huaweicloud-drs-migration](./Relational-Database-Migration/huaweicloud-drs-migration/SKILL.md): Migrate databases to Huawei Cloud RDS using DRS (Data Replication Service) with full+incremental replication, parameter alignment, and Terraform automation.
- [GaussDB Adaptation Skill](./Relational-Database-Migration/GaussDB-Adaptation-Skill/SKILL.md): Adapt SQL Server or PostgreSQL code to Huawei GaussDB (openGauss-based), covering SQL dialect, driver, and bulk loading differences.
- [Oracle to PostgreSQL 17 Migration](./Relational-Database-Migration/Oracle-To-PostgreSQL-migration-skill/SKILL.md): Convert Oracle SQL dialect to PostgreSQL 17 dialect, language/framework agnostic.
- [SQL Server Babelfish Finance Demo](./Relational-Database-Migration/SQLServer-postgreSQL-babelfish-finance-demo/SKILL.md): Migrate SQL Server workloads to PostgreSQL through Babelfish with TDS protocol compatibility.

See [Relational-Database-Migration/README.md](./Relational-Database-Migration/README.md) for details.

### Big Data Platform Migration

Migrate big data platforms and data warehouses (Cloudera, Databricks, Teradata) to Huawei Cloud managed services (MRS, DWS, OBS) with data landing, job migration, and parity validation.

- [Cloudera to Huawei MRS Migration](./Big-Data-Platform-Migration/Cloudera-to-Huawei-MRS-Skill/SKILL.md): Migrate CDH/HDP Hadoop, Hive, Spark, and Impala workloads to Huawei Cloud MRS with OBS data landing and parity validation.
- [Databricks to Huawei Cloud](./Big-Data-Platform-Migration/Databricks-to-Huawei-Cloud-Skill/SKILL.md): Migrate Databricks notebooks, tables, SQL warehouse flows, and Spark pipelines to OBS + MRS Spark.
- [Databricks to MRS Hudi Demo](./Big-Data-Platform-Migration/databricks-to-huawei-mrs-hudi-demo/SKILL.md): Migrate Databricks CDC/Delta workflows to MRS + OBS + Apache Hudi.
- [Teradata to Huawei DWS](./Big-Data-Platform-Migration/Teradata-to-Huawei-DWS-Skill/SKILL.md): Migrate Teradata to DWS with schema migration, data loading, report parity, and optimization.

See [Big-Data-Platform-Migration/README.md](./Big-Data-Platform-Migration/README.md) for details.

### NoSQL and In-Memory Database Migration

Migrate NoSQL and in-memory databases from AWS and Azure to Huawei Cloud managed database services (DDS, GeminiDB, DCS).

| Directory | Source | Target | Status |
|---|---|---|---|
