---
name: database-discovery-and-assessment
description: 数据库发现与评估技能。适用于：(1) 发现和盘点现有数据库环境，(2) 评估数据库规模、性能和依赖关系，(3) 规划数据库迁移到云端，(4) 分析迁移复杂度和风险。Database discovery and assessment skill. Use when (1) Discovering and inventorying existing database environments, (2) Assessing database size, performance, and dependencies, (3) Planning database migration to cloud, (4) Analyzing migration complexity and risks.
---

# Database Discovery and Assessment / 数据库发现与评估

## Overview / 概述

This skill provides guidance for discovering, inventorying, and assessing database environments in preparation for cloud migration. It covers various database types, assessment methodologies, and risk analysis.

本技能提供发现、清点和评估数据库环境的指导，为云迁移做准备。涵盖多种数据库类型、评估方法和风险分析。

## Discovery Prerequisites / 发现前置条件

- Access to database servers (physical or virtual) / 可访问数据库服务器（物理或虚拟）
- Appropriate database client tools / 适当的数据库客户端工具
- Network access to database ports / 网络可访问数据库端口
- Assessment documentation templates / 评估文档模板

## Discovery Workflow / 发现工作流程

### 1. Database Inventory / 数据库清点

1. **Identify all database servers**: Locate all database instances across environment
   **识别所有数据库服务器**：定位环境中的所有数据库实例

2. **Document database types**: Record database engine types and versions
   **记录数据库类型**：记录数据库引擎类型和版本

3. **Catalog databases per server**: List all databases on each server
   **编目每个服务器的数据库**：列出每个服务器上的所有数据库

4. **Note deployment environment**: Distinguish prod, dev, test environments
   **记录部署环境**：区分生产、开发、测试环境

### 2. Database Sizing / 数据库规模评估

1. **Calculate database sizes**: Determine total data volume per database
   **计算数据库大小**：确定每个数据库的总数据量

```sql
-- SQL Server
SELECT 
    DB_NAME(database_id) AS DatabaseName,
    CAST(SUM(size) * 8 / 1024.0 AS DECIMAL(10,2)) AS SizeMB
FROM sys.master_files
GROUP BY database_id;
```

```sql
-- MySQL
SELECT 
    table_schema AS DatabaseName,
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS SizeMB
FROM information_schema.tables
GROUP BY table_schema;
```

2. **Estimate growth rate**: Analyze historical growth trends
   **估算增长率**：分析历史增长趋势

3. **Project future capacity**: Forecast storage needs for migration window
   **预测未来容量**：预测迁移窗口期的存储需求

### 3. Performance Assessment / 性能评估

1. **Capture performance metrics**: CPU, memory, IO utilization
   **捕获性能指标**：CPU、内存、IO 利用率

2. **Identify top queries**: Find most resource-intensive queries
   **识别高负载查询**：找出最消耗资源的查询

```sql
-- PostgreSQL
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 20;
```

3. **Check connection usage**: Analyze concurrent connection patterns
   **检查连接使用情况**：分析并发连接模式

4. **Review indexing strategy**: Assess index efficiency
   **审查索引策略**：评估索引效率

### 4. Dependency Mapping / 依赖关系映射

1. **Identify applications**: List all applications connecting to each database
   **识别应用**：列出连接到每个数据库的所有应用

2. **Document connection strings**: Record connection configurations
   **记录连接字符串**：记录连接配置

3. **Map data flows**: Identify upstream and downstream data dependencies
   **映射数据流**：识别上游和下游数据依赖

4. **Note business criticality**: Assess business impact of each database
   **记录业务关键性**：评估每个数据库的业务影响

### 5. Security Assessment / 安全评估

1. **Review user accounts**: Audit database user permissions
   **审查用户账户**：审计数据库用户权限

2. **Check encryption status**: Verify data-at-rest encryption
   **检查加密状态**：验证静态数据加密

3. **Assess backup procedures**: Review backup strategies and testing
   **评估备份程序**：审查备份策略和测试

4. **Identify sensitive data**: Locate PII, financial, or regulated data
   **识别敏感数据**：定位个人信息、金融或受监管数据

## Assessment Report Template / 评估报告模板

### Database Profile / 数据库档案

| Field / 字段 | Value / 值 |
|--------------|------------|
| Database Name / 数据库名 | |
| DBMS Type / 数据库类型 | |
| Version / 版本 | |
| Host / 主机 | |
| Port / 端口 | |
| Size (GB) / 大小 (GB) | |
| Environment / 环境 | |
| Business Criticality / 业务关键性 | |

### Migration Complexity Matrix / 迁移复杂度矩阵

| Factor / 因素 | Low / 低 | Medium / 中 | High / 高 |
|---------------|----------|-------------|-----------|
| Size / 大小 | < 100 GB | 100 - 500 GB | > 500 GB |
| Complexity / 复杂度 | Simple schema | Moderate complexity | Complex schema |
| Dependencies / 依赖性 | Few apps | Some dependencies | Many dependencies |
| Downtime tolerance / 停机容忍 | High | Medium | Low |

## Common Issues and Resolutions / 常见问题及解决

| Issue / 问题 | Cause / 原因 | Resolution / 解决方案 |
|--------------|--------------|----------------------|
| Hidden databases / 隐藏数据库 | Undocumented instances / 未记录的实例 | Comprehensive network scanning / 全面的网络扫描 |
| Circular dependencies / 循环依赖 | Complex data flows / 复杂数据流 | Use dependency analysis tools / 使用依赖分析工具 |
| Performance impact during assessment / 评估期间性能影响 | Heavy queries / 重查询 | Schedule during off-peak / 在低峰期安排 |
| Missing documentation / 缺少文档 | Legacy systems / 遗留系统 | Interview DBAs and developers / 访谈 DBA 和开发人员 |

## Assessment Tools / 评估工具

### Database-Specific Tools / 数据库特定工具
- **SQL Server**: DMVs, SQL Profiler, Database Tuning Advisor / DMV、SQL Profiler、数据库调优顾问
- **MySQL**: performance_schema, slow_query_log, pt-query-digest / performance_schema、slow_query_log、pt-query-digest
- **PostgreSQL**: pg_stat_statements, pgBadger, EXPLAIN ANALYZE / pg_stat_statements、pgBadger、EXPLAIN ANALYZE
- **Oracle**: AWR reports, ADDM, Statspack / AWR 报告、ADDM、Statspack

### Multi-Database Assessment / 多数据库评估
- **Huawei Cloud DMS**: Database Migration Service assessment / 数据库迁移服务评估
- **Database Explorer**: Third-party discovery tools / 第三方发现工具

## Best Practices / 最佳实践

1. **Automate discovery** where possible to ensure completeness / 尽可能自动化发现以确保完整性
2. **Validate findings** with DBAs and application owners / 与 DBA 和应用所有者验证发现
3. **Prioritize assessment** based on business criticality / 根据业务关键性优先评估
4. **Document assumptions** and known gaps in assessment report / 在评估报告中记录假设和已知差距
5. **Review and update** assessment periodically as environments change / 随着环境变化定期审查和更新评估
