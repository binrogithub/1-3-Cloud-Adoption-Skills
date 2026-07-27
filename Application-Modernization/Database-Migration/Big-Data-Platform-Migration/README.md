# Big Data Platform Migration

Migrate big data platforms and data warehouses to Huawei Cloud managed services (MRS, DWS, OBS) with data landing, job migration, and end-to-end parity validation.

## Skills

| Skill | Source → Target | Description |
|-------|----------------|-------------|
| [Cloudera to Huawei MRS](./Cloudera-to-Huawei-MRS-Skill/SKILL.md) | Cloudera/CDH → MRS | Migrate Hadoop, Hive, Spark, and Impala workloads to MRS with OBS data landing, external table migration, Spark SQL conversion, and parity validation. |
| [Databricks to Huawei Cloud](./Databricks-to-Huawei-Cloud-Skill/SKILL.md) | Databricks → MRS/OBS | Migrate notebooks, tables, SQL warehouse flows, and Spark pipelines to OBS + MRS Spark with open-format export and functional parity testing. |
| [Databricks to MRS Hudi Demo](./databricks-to-huawei-mrs-hudi-demo/SKILL.md) | Databricks CDC/Delta → MRS+Hudi | Migrate Databricks CDC/Delta workflows to MRS + OBS + Apache Hudi with synthetic data generation and smoke validation. |
| [Teradata to Huawei DWS](./Teradata-to-Huawei-DWS-Skill/SKILL.md) | Teradata → DWS | Migrate Teradata to DWS with source simulation, schema migration, CSV loading, report parity, optimization, and OBS parallel load templates. |

## Target Services

| Service | Type | Description |
|---------|------|-------------|
| **MRS** (MapReduce Service) | Big data platform | Managed Hadoop/Spark/Hive/HBase/Flink/Hudi clusters |
| **DWS** (Data Warehouse Service) | Data warehouse | Managed PostgreSQL-based warehouse, compatible with Teradata/Oracle |
| **OBS** (Object Storage Service) | Object storage | Data lake storage layer for MRS and DWS |

## Related

- For relational database migration (Oracle, SQL Server, PostgreSQL → RDS/GaussDB), see [Relational-Database-Migration](../Relational-Database-Migration/README.md).
- For big data platform deployment on Huawei Cloud, see [Big-Data](../../../Big-Data/README.md).
