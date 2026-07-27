# Prerequisites

## Source (ECS + PostgreSQL)
- Huawei Cloud ECS with PostgreSQL installed
- PostgreSQL version compatible with target RDS version
- wal_level = logical
- max_replication_slots >= 1
- max_wal_senders >= 1
- Replication user created with appropriate permissions
- pg_hba.conf allows replication connections from DRS EIP
- Security Group allows PostgreSQL port from DRS EIP (/32 CIDR)
- Database to migrate identified

## Target (RDS for PostgreSQL)
- Huawei Cloud RDS for PostgreSQL instance created
- PostgreSQL version compatible with source
- Database created on RDS instance
- Security Group allows PostgreSQL port from DRS

## DRS
- huaweicloud-drs MCP configured and operational
- Playwright installed (required by DRS MCP)
- DRS service available in target region
- Sufficient DRS quota for task creation

## MCP
- huaweicloud-drs MCP configured
- (Optional) huaweicloud-pricing MCP for cost estimation
- (Optional) huaweicloud-ticket MCP for support
