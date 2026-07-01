# Huawei Cloud Services Reference

## VPC and Subnet

Create isolated network foundations for big data services.

## Security Groups

Use separate security groups for:

- bastion
- MRS
- DWS
- DLI/CDM integration if required

## OBS

Use OBS as landing and lake storage.

Recommended prefixes:

```text
landing/
bronze/
silver/
gold/
scripts/
logs/
tmp/
```

## MRS

Use MRS for managed Hadoop ecosystem services.

Default components for this skill:

- Hadoop
- Hive
- Spark
- Ranger
- ClickHouse

## DWS

Use DWS as the analytics warehouse/serving layer.

Default:

- 3 nodes
- database name: `gaussdb`
- private-only access

## DLI

Use DLI General Purpose queue for serverless data processing patterns.

## CDM

Use CDM for data movement from relational databases, files, OBS, DLI, DWS, or external systems.

## DataArts Studio

Planned for later skill versions. For now, generate reference architecture and manual TODO sections unless provider support is confirmed.

## IAM Agency

Use agency-based access for service-to-service permissions, especially MRS/DLI access to OBS.

## ECS Bastion / Jump Host

Use a bastion to access private resources without exposing all services publicly.

## EIP

Attach EIP only to bastion by default.

## KMS

Use KMS for encryption keys when the pattern requires stronger security or encryption-by-default.
