---
name: drs-mysql-parallel-migration
description: 使用当前仓库的脚本执行华为云 DRS MySQL 并行迁移，覆盖环境校验、任务创建、预检查、启动同步、监控、切换前检查、切换后校验与回滚计划。
---

# DRS MySQL Parallel Migration

## 何时使用

- 需要用本仓库 `scripts/00-11` 自动化脚本执行或续跑 MySQL DRS 迁移。
- 需要把迁移执行过程沉淀为标准操作手册（含审批门禁和报告验收）。

## 边界与安全约束

- 只允许通过仓库脚本和配置执行迁移，不直接手工改写 DRS 请求结构。
- 目标库默认是“已存在实例”，禁止自动创建/删除/重建目标 RDS。
- 关键动作必须人工审批文件放行：
  - `approvals/APPROVED_CREATE_DRS_JOB`
  - `approvals/APPROVED_START_DRS_JOB`
  - `approvals/APPROVED_CUTOVER`

## 目录与关键文件

- 配置：`configs/migration.yaml`
- 凭据：`.env`（不提交）
- 执行脚本：`scripts/00_env_check.sh` 到 `scripts/11_post_cutover_validate.py`
- 回滚计划：`scripts/99_rollback_plan.py`
- 审批目录：`approvals/`
- 报告目录：`reports/`
- 日志目录：`logs/`

## 执行前准备

1. 进入任务目录并固定基准路径。

```bash
cd /root/ai_assit_migration/ai_assist_rds_migration/parallel_runs/db2
export MIGRATION_BASE_DIR=/root/ai_assit_migration/ai_assist_rds_migration/parallel_runs/db2
```

2. 加载 `.env`（仅在当前会话）。

```bash
set -a
source .env
set +a
```

3. 必填环境变量（`00_env_check.sh` 会校验）：
  - `HW_ACCESS_KEY` `HW_SECRET_KEY` `HW_PROJECT_ID` `HW_REGION`
  - `SRC_DB_HOST` `SRC_DB_PORT` `SRC_DB_USER` `SRC_DB_PASSWORD`
  - `TGT_DB_HOST` `TGT_DB_PORT` `TGT_DB_USER` `TGT_DB_PASSWORD`

4. 常用开关：
  - `DRY_RUN=false` 执行真实操作（默认 true）
  - `SKIP_DB_TCP_CHECK=true` 跳过执行机到 DB 的直连探测
  - `ALLOW_DRS_ONLY_PRECHECK=true` 允许在执行机无法直连 DB 时，仅依赖 DRS 连通性测试和 DRS 预检查作为硬门禁

## 标准执行流程（全量到增量）

按顺序执行：

```bash
bash scripts/00_env_check.sh
python3 scripts/01_db_precheck.py
python3 scripts/02_generate_drs_payload.py
touch approvals/APPROVED_CREATE_DRS_JOB
python3 scripts/03_create_drs_job.py
python3 scripts/04_wait_drs_job_ready.py
python3 scripts/05_test_connection.py
python3 scripts/06_run_precheck.py
touch approvals/APPROVED_START_DRS_JOB
python3 scripts/07_start_migration.py
python3 scripts/08_monitor_migration.py
```

切换窗口前后补充：

```bash
python3 scripts/09_create_compare_task.py
touch approvals/APPROVED_CUTOVER
python3 scripts/10_cutover_check.py
python3 scripts/11_post_cutover_validate.py
python3 scripts/99_rollback_plan.py
```

## 每步验收（脚本 -> 报告 -> 通过条件）

- `00_env_check.sh` -> `reports/env_check_report.json`
  - 通过：`status=SUCCESS`，且必填 env 变量均为 `SET`
- `01_db_precheck.py` -> `reports/db_precheck.json`
  - 通过：`status in [SUCCESS, WARNING]`（若启用 DRS-only 模式）
- `02_generate_drs_payload.py` -> `reports/drs_payload.json`
  - 通过：`status=SUCCESS` 且包含 `base_info/source_endpoint/target_endpoint/node_info`
- `03_create_drs_job.py` -> `reports/drs_job_create_report.json`
  - 通过：`status=SUCCESS` 且有 `details.job_id`
- `04_wait_drs_job_ready.py` -> `reports/drs_job_status_report.json`
  - 通过：`status=SUCCESS` 且任务状态进入 `CONFIGURATION` 或 `WAITING_FOR_START`
- `05_test_connection.py` -> `reports/connection_test_report.json`
  - 通过：`status=SUCCESS`（源/目标连接测试均成功）
- `06_run_precheck.py` -> `reports/precheck_report.json`
  - 通过：`status in [SUCCESS, WARNING]`，且无 FAIL 项
- `07_start_migration.py` -> `reports/migration_start_report.json`
  - 通过：`status=SUCCESS`
- `08_monitor_migration.py` -> `reports/migration_status_report.json`
  - 通过：`details.final_status=INCR_TRANS`
- `09_create_compare_task.py` -> `reports/compare_report.json`
  - 通过：建议 `status=SUCCESS`，至少拿到可解析的 compare 结果
- `10_cutover_check.py` -> `reports/cutover_check_report.json`
  - 通过：`cutover_ready=true`
- `11_post_cutover_validate.py` -> `reports/cutover_validation_report.json`
  - 通过：`status in [SUCCESS, WARNING]`（WARNING 需要业务确认）
- `99_rollback_plan.py` -> `reports/rollback_plan.json` + `reports/risk_list.json`
  - 通过：两份报告成功生成

## 续跑策略（避免重复执行）

1. 先看 `reports/migration_report.json` 的最后阶段和 `job_id`。
2. 若已有 `drs_job_create_report.json` 且包含 `job_id`，跳过 `02/03`。
3. 若 `migration_start_report.json` 已成功，跳过 `07`。
4. 若 `migration_status_report.json` 已是 `INCR_TRANS`，跳过 `08`，直接进入 `09/10/11`。
5. 任何阶段失败，优先读同名 `reports/*.json` 的 `errors`，再看 `logs/<step>_*.log` 最新文件。

## 当前 DB2 迁移过程总结（基于现有报告）

- 2026-06-12：完成环境检查、payload 生成、任务创建，得到 `job_id=23839644-0b92-404d-9655-e2ece0ejb101`。
- 2026-06-12 到 2026-06-13：连接测试与 DRS 预检查在重试后通过，预检查整体为 `WARNING`（存在磁盘容量告警）。
- 2026-06-13：在补齐前置报告与审批后，成功启动迁移任务。
- 2026-06-16：监控显示任务已进入 `INCR_TRANS`，增量延迟为 0 秒。
- 2026-06-16：`compare_report` 为 `WARNING`（未返回 compare task id），`cutover_check_report` 为 `FAILED`（compare 结果缺失且未提供 `APPROVED_CUTOVER`）。

## 常见问题处理

- `HostUnreachableException / Name or service not known`
  - 先重试同一步；若持续失败，核对执行机 DNS/出口网络与华为云 API 可达性。
- `db_precheck` 无法直连数据库
  - 在受限网络环境下可启用 `ALLOW_DRS_ONLY_PRECHECK=true`，并以 `05/06` 结果作为硬门禁。
- `wait_drs_job_ready` 超时
  - 不要直接重建任务，先确认 `drs_job_create_report.json` 的 `job_id` 仍有效，再单独重跑 `04`。
- `compare_report` 无任务 ID
  - 记录为 WARNING，切换前必须补齐对象/行数比对证据或进行人工抽样校验后再审批切换。
