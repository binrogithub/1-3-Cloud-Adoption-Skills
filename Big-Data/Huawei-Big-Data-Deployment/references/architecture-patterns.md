# Architecture Patterns

## 1. Minimal MRS cluster

Use for Hadoop, Hive, Spark, Ranger, and ClickHouse workshops.

```text
User -> Bastion/EIP -> Private Subnet -> MRS
                              |
                              +-> OBS bucket
```

## 2. CDM + MRS + OBS data lake

Use for ingestion and lake processing.

```text
External Sources -> CDM -> OBS Landing -> MRS Spark/Hive -> OBS Curated
```

## 3. MRS + DWS analytics warehouse

Use for batch processing and serving layer.

```text
OBS Raw -> MRS Spark/Hive -> OBS Curated -> DWS -> BI/API
```

## 4. DLI serverless lakehouse

Use when the user wants less infrastructure administration.

```text
OBS -> DLI Queue -> SQL/Spark jobs -> OBS/DWS
```

## 5. Full big data platform

Use for enterprise demo environments.

```text
Sources -> CDM/DataArts -> OBS -> MRS/DLI -> DWS -> BI/API
                      \-> Catalog/Governance later
```

## 6. CDM + DataArts + DWS + OBS

Use when the main story is orchestration and analytics.

```text
Sources -> CDM -> OBS -> DataFactory orchestration -> DWS
```

DataArts Studio is marked as planned/later in this skill because Terraform provider support should be validated before generating concrete resources.
