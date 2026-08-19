# Database Migration

Complete toolkit for migrating and modernizing enterprise databases and data platforms to Huawei Cloud managed services. Covers relational databases, big data platforms, data warehouses, NoSQL, in-memory databases, and database usage operations.

---

## What This Package Covers

### The Problem

Enterprise database migration involves multiple dimensions:

- **Relational databases** (Oracle, SQL Server, PostgreSQL, MySQL) need schema adaptation, data replication, and cutover planning
- **Big data platforms** (Cloudera, Databricks, Teradata) require job migration, data landing, and parity validation
- **NoSQL and in-memory databases** (MongoDB, Redis, DynamoDB, CosmosDB) need data model mapping and API compatibility
- **Already-deployed instances** need operational support: finding, connecting, and exposing them publicly
- Each source-target combination has its own tool (DRS, UGO, Babelfish, OMS) and its own workflow

### The Solution: Skills Organized by Migration Domain

```
Database-Migration/
|
|-- Relational-Database-Migration/        Oracle/SQLServer/MySQL -> RDS/GaussDB
|   |-- huaweicloud-drs-migration/        DRS full+incremental replication
|   |-- huawei-postgresql-ecs-to-rds-drs/ PostgreSQL ECS -> RDS cross-region
|   |-- GaussDB-Adaptation-Skill/         SQL Server/PostgreSQL -> GaussDB
|   |-- Oracle-To-PostgreSQL-migration/   Oracle SQL -> PostgreSQL 17
|   +-- SQLServer-postgreSQL-babelfish/   SQL Server -> PostgreSQL via Babelfish
|
|-- Big-Data-Platform-Migration/          Cloudera/Databricks/Teradata -> MRS/DWS/OBS
|   |-- Cloudera-to-Huawei-MRS-Skill/     CDH -> MRS with OBS data landing
|   |-- Databricks-to-Huawei-Cloud-Skill/ Databricks -> MRS/OBS
|   |-- databricks-to-huawei-mrs-hudi/   Databricks CDC -> MRS + Hudi
|   |-- Teradata-to-Huawei-DWS-Skill/     Teradata -> DWS
|   |-- dws-cluster-deployment/           Deploy DWS clusters
|   |-- MRS-Deployment/                   Deploy MRS clusters
|   +-- snowflake-to-dataarts/            Snowflake -> DataArts Studio
|
|-- database-usage-operations/            Operate existing instances
|   +-- huawei-database-usage-operations/ Find, connect, bind EIP
|
|-- AWS-DocumentDB-to-Huawei-DDS/         DocumentDB -> DDS
|-- AWS-DynamoDB-to-Huawei-GeminiDB/      DynamoDB -> GeminiDB
|-- AWS-ElastiCache-to-Huawei-DCS/        ElastiCache -> DCS
+-- Azure-CosmosDB-to-Huawei-GeminiDB/    CosmosDB -> GeminiDB
```

---

## Migration Scenarios

### Relational Database Migration

Migrate relational databases (Oracle, SQL Server, PostgreSQL, MySQL) to Huawei Cloud managed databases (RDS, GaussDB, PostgreSQL) using DRS, UGO, and Babelfish.

| Skill | Source -> Target | Tool | Description |
|-------|-----------------|------|-------------|
| huaweicloud-drs-migration | External DB -> RDS | DRS | Full+incremental replication with Terraform automation and zero-downtime cutover |
| postgresql-ecs-to-rds-drs | PostgreSQL on ECS -> RDS | DRS | Cross-region migration with self-contained package and MCPs |
| GaussDB-Adaptation | SQL Server/PostgreSQL -> GaussDB | Manual | SQL dialect, driver, and bulk loading adaptation |
| Oracle-to-PostgreSQL-17 | Oracle -> PostgreSQL 17 | Manual | SQL dialect conversion, language/framework agnostic |
| SQLServer-Babelfish | SQL Server -> PostgreSQL | Babelfish | TDS protocol compatibility for finance workloads |

See [Relational-Database-Migration/README.md](./Relational-Database-Migration/README.md) for details.

### Big Data Platform Migration

Migrate big data platforms and data warehouses (Cloudera, Databricks, Teradata, Snowflake) to Huawei Cloud managed services (MRS, DWS, OBS, DataArts Studio).

| Skill | Source -> Target | Description |
|-------|-----------------|-------------|
| Cloudera-to-MRS | CDH/HDP -> MRS | Hadoop, Hive, Spark, Impala with OBS data landing and parity validation |
| Databricks-to-Huawei | Databricks -> MRS/OBS | Notebooks, tables, SQL warehouse flows, Spark pipelines |
| Databricks-to-MRS-Hudi | Databricks -> MRS+Hudi | CDC/Delta workflows to Apache Hudi |
| Teradata-to-DWS | Teradata -> DWS | Schema migration, data loading, report parity |
| dws-cluster-deployment | N/A -> DWS | Deploy DWS clusters with hcloud CLI |
| MRS-Deployment | N/A -> MRS | Deploy MRS clusters with any component combination |
| snowflake-to-dataarts | Snowflake -> DataArts | Snowflake SQL -> DataArts Studio with DAG conversion |

See [Big-Data-Platform-Migration/README.md](./Big-Data-Platform-Migration/README.md) for details.

### NoSQL and In-Memory Database Migration

Migrate NoSQL and in-memory databases from AWS and Azure to Huawei Cloud managed services.

| Directory | Source -> Target | Description |
|-----------|-----------------|-------------|
| AWS-DocumentDB-to-Huawei-DDS | AWS DocumentDB -> Huawei DDS | MongoDB-compatible document store migration |
| AWS-DynamoDB-to-Huawei-GeminiDB | AWS DynamoDB -> Huawei GeminiDB | Key-value store migration |
| AWS-ElastiCache-to-Huawei-DCS | AWS ElastiCache -> Huawei DCS | Redis-compatible in-memory cache migration |
| Azure-CosmosDB-to-Huawei-GeminiDB | Azure CosmosDB -> Huawei GeminiDB | Multi-model NoSQL migration |

### Database Usage Operations

Operate already-deployed database instances -- find, connect, and bind EIP for public access.

| Skill | Services | Description |
|-------|----------|-------------|
| huawei-database-usage-operations | RDS, DDS, GeminiDB, TaurusDB, GaussDB | Find instances, read connection details, assign EIP |

See [database-usage-operations/README.md](./database-usage-operations/README.md) for details.

---

## Installation

Each sub-scenario has its own installation instructions in its README. The general pattern:

### Option A: OpenCode

```bash
mkdir -p ~/.opencode/skills
cp -r <scenario>/<skill-name> ~/.opencode/skills/
```

### Option B: Hermes Agent

```bash
cp -r <scenario>/<skill-name> ~/.hermes/skills/database/
```

---

## Requirements

| Component | Requirement |
|------------|-----------|
| hcloud CLI | Installed and configured (for deployment and operations skills) |
| Terraform | Installed (for DRS migration and infrastructure provisioning) |
| Source database | Access credentials, network connectivity |
| Target | Huawei Cloud account with appropriate service permissions |
| AI Agent | OpenCode / Hermes / Claude Code (optional) |

---

*Domains: Relational, Big Data, NoSQL, In-Memory, Operations*
*Tools: DRS, UGO, Babelfish, OMS, hcloud CLI, Terraform*
*Target: Huawei Cloud RDS, GaussDB, DDS, GeminiDB, DCS, MRS, DWS, DataArts*
