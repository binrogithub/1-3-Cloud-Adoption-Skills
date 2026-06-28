# RDS MySQL DRS Migration Agent / RDS MySQL DRS 迁移 Agent

This repository provides a step-by-step automation flow for migrating MySQL to MySQL by Huawei Cloud DRS v5 SDK.  
本仓库提供基于华为云 DRS v5 SDK 的 MySQL 到 MySQL 分步迁移自动化流程。

---

## 中文说明（CN）

### 1. 运行机制概览

- 执行入口：`scripts/00` 到 `scripts/11`（以及 `99_rollback_plan.py`）。
- 运行状态目录：
  - `reports/`：每一步的 JSON 报告（后续步骤依赖前序报告）。
  - `logs/`：每个脚本/模块日志。
  - `approvals/`：人工审批闸门文件。
- 安全特性：
  - 默认 `DRY_RUN=true`，避免误执行真实变更。
  - 日志会自动脱敏。
  - 数据库查询仅允许只读 SQL。

### 2. 配置读取规则

- 运行时实际读取：
  - `.env`：AK/SK、数据库连接、运行开关。
  - `configs/migration.yaml`：DRS 任务参数（网络、规格、迁移范围、阈值）。
- 说明：`migration_config.yaml` 在当前实现中不是脚本运行时入口（作为参考配置）。

### 3. 依赖与准备

```bash
python3 -m pip install pyyaml pymysql huaweicloudsdkcore huaweicloudsdkdrs

cd /root/ai_assit_migration/ai_assist_rds_migration
export MIGRATION_BASE_DIR=$(pwd)

cp .env.example .env
# 编辑 .env
# 编辑 configs/migration.yaml
```

### 4. 关键环境变量

- 必填：
  - `HW_ACCESS_KEY` `HW_SECRET_KEY` `HW_PROJECT_ID` `HW_REGION`
  - `SRC_DB_HOST` `SRC_DB_PORT` `SRC_DB_USER` `SRC_DB_PASSWORD`
  - `TGT_DB_HOST` `TGT_DB_PORT` `TGT_DB_USER` `TGT_DB_PASSWORD`
- 常用开关：
  - `DRY_RUN`：默认 `true`，真实执行需设为 `false`。
  - `SKIP_DB_TCP_CHECK`：是否跳过 `00_env_check.sh` 的 TCP 检查。
  - `ALLOW_DRS_ONLY_PRECHECK`：默认 `true`，执行机不能直连 DB 时允许 `01` 以 WARNING 通过，并在 `05/06/07` 由 DRS 检查做硬门禁。
- 超时覆盖（可选）：
  - `WAIT_INITIAL_SEC` `WAIT_POLL_SEC` `WAIT_MAX_SEC`
  - `PRECHECK_POLL_SEC` `PRECHECK_MAX_WAIT_SEC`

### 5. 标准执行流程

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
python3 scripts/09_create_compare_task.py

touch approvals/APPROVED_CUTOVER
python3 scripts/10_cutover_check.py
python3 scripts/11_post_cutover_validate.py

python3 scripts/99_rollback_plan.py
```

### 6. 步骤与报告

| 步骤 | 脚本 | 作用 | 报告 |
|---|---|---|---|
| 00 | `scripts/00_env_check.sh` | 环境与网络检查 | `env_check_report.json` |
| 01 | `scripts/01_db_precheck.py` | 源/目标 DB 兼容性预检 | `db_precheck.json` |
| 02 | `scripts/02_generate_drs_payload.py` | 生成建任务 payload | `drs_payload.json` |
| 03 | `scripts/03_create_drs_job.py` | 创建 DRS 任务（需审批） | `drs_job_create_report.json` |
| 04 | `scripts/04_wait_drs_job_ready.py` | 等待任务可启动 | `drs_job_status_report.json` |
| 05 | `scripts/05_test_connection.py` | DRS 连接测试 | `connection_test_report.json` |
| 06 | `scripts/06_run_precheck.py` | DRS 预检查 | `precheck_report.json` |
| 07 | `scripts/07_start_migration.py` | 启动迁移（需审批） | `migration_start_report.json` |
| 08 | `scripts/08_monitor_migration.py` | 监控迁移至 `INCR_TRANS` | `migration_status_report.json` |
| 09 | `scripts/09_create_compare_task.py` | 对象/行数比对 | `compare_report.json` |
| 10 | `scripts/10_cutover_check.py` | 切换前就绪检查（需审批） | `cutover_check_report.json` |
| 11 | `scripts/11_post_cutover_validate.py` | 切换后校验 | `cutover_validation_report.json` |
| 99 | `scripts/99_rollback_plan.py` | 回滚预案与风险 | `rollback_plan.json`, `risk_list.json` |

总览报告：`reports/migration_report.json`。

### 7. 审批闸门

必须先创建审批文件，否则相关步骤直接退出：

- `approvals/APPROVED_CREATE_DRS_JOB`
- `approvals/APPROVED_START_DRS_JOB`
- `approvals/APPROVED_CUTOVER`

示例：

```bash
touch approvals/APPROVED_CREATE_DRS_JOB
```

### 8. 断点续跑建议

- 每步失败后可从失败步骤重跑。
- 后续步骤依赖 `reports/drs_job_create_report.json` 中的 `job_id`。
- 已创建任务后不要重复执行 `03`，避免重复建任务。

### 9. 重要边界

- 当前流程不包含自动执行 cutover API；`10_cutover_check.py` 仅做就绪检查。
- `db_client.py` 禁止 `DROP/DELETE/TRUNCATE/ALTER/INSERT/UPDATE/...`。
- `.env` 不应提交，迁移后建议轮换密钥和密码。

---

## English Guide (EN)

### 1. Workflow Overview

- Execution entry points: `scripts/00` to `scripts/11` (plus `99_rollback_plan.py`).
- Runtime state directories:
  - `reports/`: JSON report per step (later steps depend on earlier outputs).
  - `logs/`: logs from each script/module.
  - `approvals/`: manual approval gate files.
- Safety characteristics:
  - Default `DRY_RUN=true` to prevent accidental real operations.
  - Sensitive data masking in logs.
  - DB queries are read-only only.

### 2. Config Loading Rules

- Actual runtime inputs:
  - `.env`: AK/SK, DB connectivity, runtime switches.
  - `configs/migration.yaml`: DRS task parameters (network/spec/scope/thresholds).
- Note: `migration_config.yaml` is not the active runtime entry in current scripts (reference only).

### 3. Dependencies and Setup

```bash
python3 -m pip install pyyaml pymysql huaweicloudsdkcore huaweicloudsdkdrs

cd /root/ai_assit_migration/ai_assist_rds_migration
export MIGRATION_BASE_DIR=$(pwd)

cp .env.example .env
# Edit .env
# Edit configs/migration.yaml
```

### 4. Key Environment Variables

- Required:
  - `HW_ACCESS_KEY` `HW_SECRET_KEY` `HW_PROJECT_ID` `HW_REGION`
  - `SRC_DB_HOST` `SRC_DB_PORT` `SRC_DB_USER` `SRC_DB_PASSWORD`
  - `TGT_DB_HOST` `TGT_DB_PORT` `TGT_DB_USER` `TGT_DB_PASSWORD`
- Common switches:
  - `DRY_RUN`: default `true`; set `false` for real execution.
  - `SKIP_DB_TCP_CHECK`: skip TCP checks in `00_env_check.sh`.
  - `ALLOW_DRS_ONLY_PRECHECK`: default `true`; allows `01` warning pass if host cannot directly reach DB, then enforces DRS checks in `05/06/07`.
- Optional timeout overrides:
  - `WAIT_INITIAL_SEC` `WAIT_POLL_SEC` `WAIT_MAX_SEC`
  - `PRECHECK_POLL_SEC` `PRECHECK_MAX_WAIT_SEC`

### 5. Standard Execution Sequence

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
python3 scripts/09_create_compare_task.py

touch approvals/APPROVED_CUTOVER
python3 scripts/10_cutover_check.py
python3 scripts/11_post_cutover_validate.py

python3 scripts/99_rollback_plan.py
```

### 6. Steps and Reports

| Step | Script | Purpose | Report |
|---|---|---|---|
| 00 | `scripts/00_env_check.sh` | Env/network validation | `env_check_report.json` |
| 01 | `scripts/01_db_precheck.py` | Source/target DB compatibility precheck | `db_precheck.json` |
| 02 | `scripts/02_generate_drs_payload.py` | Build create-job payload | `drs_payload.json` |
| 03 | `scripts/03_create_drs_job.py` | Create DRS job (approval required) | `drs_job_create_report.json` |
| 04 | `scripts/04_wait_drs_job_ready.py` | Wait until job is start-ready | `drs_job_status_report.json` |
| 05 | `scripts/05_test_connection.py` | DRS connection tests | `connection_test_report.json` |
| 06 | `scripts/06_run_precheck.py` | DRS precheck and polling | `precheck_report.json` |
| 07 | `scripts/07_start_migration.py` | Start migration (approval required) | `migration_start_report.json` |
| 08 | `scripts/08_monitor_migration.py` | Monitor until `INCR_TRANS` | `migration_status_report.json` |
| 09 | `scripts/09_create_compare_task.py` | Object/row-count compare tasks | `compare_report.json` |
| 10 | `scripts/10_cutover_check.py` | Pre-cutover readiness (approval required) | `cutover_check_report.json` |
| 11 | `scripts/11_post_cutover_validate.py` | Post-cutover validation | `cutover_validation_report.json` |
| 99 | `scripts/99_rollback_plan.py` | Rollback plan and risks | `rollback_plan.json`, `risk_list.json` |

Aggregate report: `reports/migration_report.json`.

### 7. Approval Gates

Create these files before corresponding steps, otherwise scripts exit immediately:

- `approvals/APPROVED_CREATE_DRS_JOB`
- `approvals/APPROVED_START_DRS_JOB`
- `approvals/APPROVED_CUTOVER`

Example:

```bash
touch approvals/APPROVED_CREATE_DRS_JOB
```

### 8. Resume Strategy

- Re-run from the failed step based on generated reports.
- Downstream scripts rely on `job_id` in `reports/drs_job_create_report.json`.
- Do not run step `03` repeatedly after a job is already created.

### 9. Important Boundaries

- No automated cutover API execution is implemented; `10_cutover_check.py` is validation only.
- `db_client.py` blocks `DROP/DELETE/TRUNCATE/ALTER/INSERT/UPDATE/...`.
- Do not commit `.env`; rotate credentials after migration.

