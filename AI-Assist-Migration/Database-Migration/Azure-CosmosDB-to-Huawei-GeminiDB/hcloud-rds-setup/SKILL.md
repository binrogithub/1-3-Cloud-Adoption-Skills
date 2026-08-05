---
name: hcloud-rds-setup
description: RDS, DCS (Redis), and DDS (MongoDB) database setup on Huawei Cloud. Use when creating database instances, selecting flavors/storage, configuring backups, or troubleshooting RDS/DCS/DDS.
---

# Database Setup on Huawei Cloud

Create and manage RDS (relational), DCS (Redis), and DDS (MongoDB) database instances on Huawei Cloud.

## Prerequisites

- **hcloud CLI** configured with AK/SK (see `hcloud-cli-setup` skill)
- A **VPC** and **subnet** exist in the target region
- A **security group** with database port access

## AWS ↔ Huawei Cloud Database Mapping

| AWS Database | Huawei Cloud |
|---|---|
| RDS (MySQL/PostgreSQL/SQLServer) | RDS (MySQL/PostgreSQL/SQLServer/MariaDB) |
| ElastiCache (Redis) | DCS (Redis/Memcached) |
| DocumentDB | DDS (MongoDB) |
| DynamoDB | GeminiDB (Cassandra/MongoDB/InfluxDB/Redis) |
| Redshift | GaussDB(DWS) (Data Warehouse) |

## Part 1: RDS (Relational Database Service)

### Step 1: List Available Engines and Versions

```bash
# MySQL
hcloud RDS ListDatastores --@1.0 --cli-region=la-north-2 --database_name=MySQL
# Via MCP: hcloud_list_rds_datastores(region="la-north-2", database_name="MySQL")

# PostgreSQL
hcloud RDS ListDatastores@1.0 --cli-region=la-north-2 --database_name=PostgreSQL

# SQL Server
hcloud RDS ListDatastores@1.0 --cli-region=la-north-2 --database_name=SQLServer
```

Available MySQL versions (la-north-2): 8.0.43, 5.7.44

### Step 2: List Flavors

```bash
hcloud RDS ListFlavors --cli-region=la-north-2 --database_name=MySQL --version_name=8.0
# Via MCP: hcloud_list_rds_flavors(region="la-north-2", database_name="MySQL", version_name="8.0")
```

### Step 3: List Storage Types

```bash
hcloud RDS ListStorageTypes --cli-region=la-north-2 \
  --database_name=MySQL --version_name=8.0
# Via MCP: hcloud_list_rds_storage_types(region="la-north-2", database_name="MySQL", version_name="8.0")
```

Common storage types: `ULTRAHIGH` (SSD), `HIGH` (SAS), `ESSD` (ultra SSD), `SSD`.

### Step 4: Create RDS Instance

```bash
hcloud RDS CreateInstance --cli-region=la-north-2 \
  --name=my-rds-mysql \
  --datastore.type=MySQL \
  --datastore.version=8.0 \
  --flavorRef=rds.mysql.x1.large.2 \
  --volume.type=ULTRAHIGH \
  --volume.size=100 \
  --region=la-north-2 \
  --availability_zone=la-north-2a \
  --vpc_id=<VPC_ID> \
  --subnet_id=<SUBNET_ID> \
  --security_group_id=<SG_ID> \
  --password='<YOUR_ADMIN_PASSWORD>' \
  --backup_strategy.keep_days=7 \
  --backup_strategy.start_time=03:00-04:00
```

Key parameters:
- `--datastore.type`: `MySQL`, `PostgreSQL`, `SQLServer`, `MariaDB`
- `--datastore.version`: Engine version (e.g. `8.0`)
- `--flavorRef`: Flavor ID (CPU/RAM spec)
- `--volume.type`: `ULTRAHIGH`, `HIGH`, `ESSD`, `SSD`
- `--volume.size`: Disk size in GB (40-4000 for ULTRAHIGH)
- `--availability_zone`: AZ for the instance
- `--password`: Admin password (8-32 chars, 3+ char types)
- `--backup_strategy.keep_days`: Backup retention (days)
- `--backup_strategy.start_time`: Backup window

### Step 5: Manage RDS

```bash
# List instances
hcloud RDS ListInstances --cli-region=la-north-2
# Via MCP: hcloud_list_rds_instances(region="la-north-2")

# Get instance details
hcloud RDS ShowInstance --cli-region=la-north-2 --instance_id=<RDS_ID>

# List backups
hcloud RDS ListBackups --cli-region=la-north-2 --instance_id=<RDS_ID>
# Via MCP: hcloud_list_rds_backups(region="la-north-2", instance_id="<RDS_ID>")

# Create backup
hcloud RDS CreateBackup --cli-region=la-north-2 --instance_id=<RDS_ID> --name=my-backup

# Restart instance
hcloud RDS RestartInstance --cli-region=la-north-2 --instance_id=<RDS_ID>

# Delete instance
hcloud RDS DeleteInstance --cli-region=la-north-2 --instance_id=<RDS_ID>
```

### RDS HA (High Availability)

For HA, create with `--ha.enable=true --ha.replication_mode=async` (MySQL async semi-sync).
HA instances have primary + standby in different AZs.

---

## Part 2: DCS (Distributed Cache Service - Redis)

### Step 1: List Available AZs and Flavors

```bash
# DCS AZs
hcloud DCS ListAvailableZones --cli-region=la-north-2
# Via MCP: hcloud_list_dcs_available_zones(region="la-north-2")

# DCS flavors
hcloud DCS ListFlavors --cli-region=la-north-2
# Via MCP: hcloud_list_dcs_flavors(region="la-north-2")
```

DCS supports:
- **Redis** (single-node, master/standby, cluster)
- **Memcached** (single-node)

### Step 2: Create DCS Instance

```bash
hcloud DCS CreateInstance --cli-region=la-north-2 \
  --name=my-redis \
  --engine=redis \
  --engine_version=5.0 \
  --capacity=2 \
  --instance_type=1 \
  --vpc_id=<VPC_ID> \
  --subnet_id=<SUBNET_ID> \
  --security_group_id=<SG_ID> \
  --az_codes.1=la-north-2a \
  --password='<YOUR_ADMIN_PASSWORD>'
```

Key parameters:
- `--engine`: `redis` or `memcached`
- `--engine_version`: Redis `5.0`, `6.0`, `7.0`; Memcached `1.6`
- `--capacity`: Cache capacity in GB
- `--instance_type`: `0` (single), `1` (master/standby), `2` (cluster)
- `--az_codes`: AZ for the instance (for HA, specify 2 AZs)

### Step 3: Manage DCS

```bash
# List instances
hcloud DCS ListInstances --cli-region=la-north-2
# Via MCP: hcloud_list_dcs_instances(region="la-north-2")

# Get instance details
hcloud DCS ShowInstance --cli-region=la-north-2 --instance_id=<DCS_ID>
# Via MCP: hcloud_show_dcs_instance(region="la-north-2", instance_id="<DCS_ID>")

# Restart instance
hcloud DCS RestartInstance --cli-region=la-north-2 --instance_id=<DCS_ID>

# Delete instance
hcloud DCS DeleteInstance --cli-region=la-north-2 --instance_id=<DCS_ID>
```

---

## Part 3: DDS (Document Database Service - MongoDB)

### Step 1: List Flavors and Storage Types

```bash
# DDS flavors
hcloud DDS ListFlavors --cli-region=la-north-2 --engine=wiredTiger
# Via MCP: hcloud_list_dds_flavors(region="la-north-2", engine="wiredTiger")

# DDS storage types
hcloud DDS ListStorageTypes --cli-region=la-north-2 --engine=wiredTiger
# Via MCP: hcloud_list_dds_storage_types(region="la-north-2", engine="wiredTiger")
```

DDS engines: `wiredTiger` (MongoDB 4.0+), `rocksDB` (deprecated).

### Step 2: Create DDS Instance

```bash
hcloud DDS CreateInstance --cli-region=la-north-2 \
  --name=my-mongodb \
  --datastore.type=mongodb \
  --datastore.version=4.0 \
  --flavor.1.spec_code=dds.mongodb.s2.large.2 \
  --flavor.1.num=2 \
  --flavor.1.type=replica \
  --volume.type=ULTRAHIGH \
  --volume.size=100 \
  --region=la-north-2 \
  --availability_zone=la-north-2a \
  --vpc_id=<VPC_ID> \
  --subnet_id=<SUBNET_ID> \
  --security_group_id=<SG_ID> \
  --password='<YOUR_ADMIN_PASSWORD>' \
  --mode=ReplicaSet
```

Key parameters:
- `--datastore.type`: `mongodb`
- `--datastore.version`: `4.0`, `4.2`, `4.4`
- `--mode`: `ReplicaSet` or `Sharding`
- `--flavor.N.spec_code`: Flavor spec code
- `--flavor.N.num`: Number of nodes
- `--flavor.N.type`: `replica` or `shard` or `config`

### Step 3: Manage DDS

```bash
# List instances
hcloud DDS ListInstances --cli-region=la-north-2
# Via MCP: hcloud_list_dds_instances(region="la-north-2")

# Get instance details
hcloud DDS ShowInstance --cli-region=la-north-2 --instance_id=<DDS_ID>

# Delete instance
hcloud DDS DeleteInstance --cli-region=la-north-2 --instance_id=<DDS_ID>
```

---

## Security Group Configuration

Create SG rules for database access:

```bash
# MySQL (port 3306)
hcloud VPC CreateSecurityGroupRule --cli-region=la-north-2 \
  --security_group_id=<SG_ID> \
  --security_group_rule.direction=ingress \
  --security_group_rule.ethertype=IPv4 \
  --security_group_rule.protocol=tcp \
  --security_group_rule.port_range_min=3306 \
  --security_group_rule.port_range_max=3306 \
  --security_group_rule.remote_ip_prefix=192.168.0.0/16

# PostgreSQL (port 5432)
# ... port_range_min=5432 port_range_max=5432

# MongoDB (port 8635 for DDS)
# ... port_range_min=8635 port_range_max=8635

# Redis (port 6379)
# ... port_range_min=6379 port_range_max=6379
```

## MCP Tools Reference

| MCP Tool | Description |
|---|---|
| `hcloud_list_rds_datastores` | List RDS engine versions |
| `hcloud_list_rds_flavors` | List RDS flavors |
| `hcloud_list_rds_storage_types` | List RDS storage types |
| `hcloud_list_rds_instances` | List RDS instances |
| `hcloud_list_rds_backups` | List RDS backups |
| `hcloud_list_dcs_available_zones` | List DCS AZs |
| `hcloud_list_dcs_flavors` | List DCS flavors |
| `hcloud_list_dcs_instances` | List DCS instances |
| `hcloud_show_dcs_instance` | Get DCS instance details |
| `hcloud_list_dds_flavors` | List DDS flavors |
| `hcloud_list_dds_storage_types` | List DDS storage types |
| `hcloud_list_dds_instances` | List DDS instances |

## Troubleshooting

### RDS creation fails
- Check VPC/subnet/SG exist in the same region
- Verify flavor is available for the engine version
- Password must be 8-32 chars with 3+ char types
- Check RDS quota

### DCS creation fails
- Verify capacity is valid for the selected flavor
- For HA instances, specify 2 different AZs
- Redis password required (unless `--no_password=true` for VPC-only access)

### DDS creation fails
- Check flavor spec_code matches the engine
- ReplicaSet mode needs oddC 3 nodes minimum
- Sharding mode needs shard + config + mongos nodes

### Connection timeout
- Verify SG allows the database port from your IP/subnet
- For RDS: check `vpc_id` and `subnet_id` match your ECS network
- For DCS: ensure same VPC as the application
- Use private endpoint (not public) for VPC-internal access

## Current Environment (la-north-2)

- VPCs: `vpc-default-smb` (172.31.0.0/16), `vpc-openwebui` (192.168.0.0/16)
- Subnets: `subnet-default-smb` (172.31.0.0/20), `subnet-openwebui` (192.168.0.0/24)
- AZs: `la-north-2a`, `la-north-2b`, `la-north-2c`
- RDS MySQL versions: 8.0.43, 5.7.44
- No existing RDS, DCS, or DDS instances
