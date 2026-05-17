---
name: huawei-cloud-sec-edgar-bigdata-poc
description: Deploy, operate, document, or troubleshoot the Huawei Cloud SEC EDGAR big-data lifecycle monitoring POC using OBS, MRS Spark, DWS, ECS, Superset, Terraform, PowerShell credential bootstrap, pipeline scripts, DWS loading, and the monitoring website. Use when Codex needs to reproduce this end-to-end environment, explain the scripts, continue deployment, fix failures, English/localize the websites, or create BI dashboards for the SEC EDGAR financial-topic dataset.
---

# Huawei Cloud SEC EDGAR Big Data POC

## Core Rule

Never embed Huawei Cloud AK/SK, account passwords, DWS/MRS passwords, Superset passwords, SSH private keys, or Terraform state secrets in this skill, code, docs, logs, screenshots, or chat. Load secrets only from environment variables, DPAPI-encrypted local XML, SSH agent/key files, or cloud secret services. Do not print command lines that contain Spark OBS access-key/secret-key settings.

Use this skill together with any broader Huawei Cloud big-data architecture or migration skill that fits the user's scenario.

## Repository Shape

The working repo used for the original POC was:

`C:\Users\Matebook\Documents\Codex\2026-05-13\ai-bi-1-1-obs-mrs`

Important repo areas:

- `infra/terraform/`: Huawei Cloud OBS, VPC, subnet, ECS, EIP, DWS, MRS, security-group rules.
- `scripts/`: credential bootstrap, Terraform secure plan/apply helpers, Superset credential lookup.
- `deploy/`: Nginx, systemd API service, Superset install helper.
- `server/monitor_api.py`: small lifecycle status API on `127.0.0.1:8090`.
- `pipelines/sec_edgar_to_obs.py`: stream SEC EDGAR public filings to OBS raw.
- `pipelines/spark_clean_financial_data.py`: MRS Spark raw-to-silver/gold job.
- `sql/dws_schema.sql`: DWS serving schema.
- `index.html`, `app.js`, `styles.css`: public monitoring website.

Read `references/RUNBOOK.md` for the full end-to-end deployment, commands, and troubleshooting record.

## End-To-End Workflow

1. Bootstrap credentials locally.
   - Run `scripts/huawei-cloud-credentials.ps1` for Huawei Cloud and Superset inputs.
   - Run `scripts/bigdata-service-passwords.ps1` for DWS/MRS service passwords.
   - Store secrets under `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\*.xml` with DPAPI.
   - Keep `terraform.tfvars` free of plaintext passwords.

2. Provision cloud infrastructure.
   - Use Terraform under `infra/terraform`.
   - Plan through `scripts/terraform-plan-secure.ps1`; apply through `scripts/terraform-apply-existing-plan.ps1`.
   - Region default for this POC is `la-south-2`.
   - Use pay-per-use resources for POC.
   - Confirm Huawei Cloud quotas, current flavor names, and price before applying.

3. Deploy the monitoring website and API.
   - ECS hosts Nginx, static website, Superset, and `bigdata-monitor-api`.
   - Nginx serves `/` and proxies `/api` to `127.0.0.1:8090`.
   - API reads `/var/lib/bigdata-monitor/events.jsonl`.

4. Stream public data into OBS.
   - Use `pipelines/sec_edgar_to_obs.py`.
   - Required env: `SEC_USER_AGENT`, `HUAWEICLOUD_ACCESS_KEY`, `HUAWEICLOUD_SECRET_KEY`, `OBS_ENDPOINT`, `OBS_BUCKET`.
   - Target layout: `raw/sec-edgar/...`; write a manifest under `raw/sec-edgar/manifests/`.
   - Emit `download` and `obs` monitor events to `/api/events`.

5. Run MRS Spark processing.
   - Copy or stage `pipelines/spark_clean_financial_data.py`.
   - Read `obs://BUCKET/raw/sec-edgar/`.
   - Write silver Parquet to `obs://BUCKET/silver/sec-edgar/`.
   - Write gold Parquet and CSV to `obs://BUCKET/gold/sec-edgar/topic_daily*`.
   - Emit `mrs` monitor events.

6. Load DWS.
   - Initialize `finance_monitor` schema with `sql/dws_schema.sql`.
   - Load gold CSV into `finance_monitor.fact_financial_topic_daily`.
   - Use temporary `.pgpass` on ECS only when needed; delete it immediately.
   - Emit `dws` monitor events.

7. Configure Superset.
   - Run Superset on ECS, exposed on port `8088`.
   - Install PostgreSQL driver inside the Superset runtime if missing.
   - Create database connection to DWS, dataset `finance_monitor.fact_financial_topic_daily`, charts, and dashboard.
   - Use ASCII metric aliases in chart params; titles may be localized, but SQL aliases should stay ASCII.
   - Emit `bi` monitor events.

8. Validate every layer.
   - Monitoring website: `GET /`.
   - API: `GET /api/health`, `GET /api/status`.
   - OBS object counts and byte sizes.
   - MRS wrapper log and YARN application state.
   - DWS row counts.
   - Superset chart data API.

## Resource Baseline

This POC used a minimum practical baseline:

- ECS web/Superset: small 2 vCPU / 4 GB class with EIP.
- OBS: Standard bucket for raw/silver/gold.
- MRS: Spark/Hive-capable cluster, 2 masters + 3 cores, bigdata Linux flavors, 600 GB root/data disks in the tested region.
- DWS: 3-node smallest available DWS shape in the selected region.
- Superset: Docker on ECS, private DWS connectivity.

Treat these as POC-only starting points. Reconfirm current Huawei Cloud regional availability before deploying.

## Verification Checklist

Use these checks before saying the pipeline is complete:

- Raw OBS data is at or above the target byte size.
- MRS log contains `END status=0`.
- YARN application final state is `SUCCEEDED`.
- Gold CSV exists under `gold/sec-edgar/topic_daily_csv/part-*.csv`.
- DWS fact table returns nonzero rows.
- `/api/status` shows all five stages as `success`.
- Superset dashboard opens and both charts query successfully.
- Public website has no stale localized text after any requested language change.

## Troubleshooting Memory

Key failures from the original run:

- Terraform missing: install or use `%LOCALAPPDATA%\Programs\Terraform\terraform.exe`; helper scripts resolve this path.
- Public IP changed: update `admin_cidr` and reapply security-group rules.
- MRS flavor/component mismatch: use actual regional MRS `3.5.0-LTS` components and `.linux.bigdata` flavors.
- MRS OBS connector agency failure: use job-level Basic OBS credentials if no MRS agency is configured, but never print command lines containing the secret key.
- MRS SFTP unavailable: copy files to MRS via SSH pipe instead of `scp`/SFTP.
- CRLF in remote shell scripts: convert to LF and avoid fragile backslash continuations.
- Stale PID files: check both PID liveness and `END status=` in log.
- Superset `No module named psycopg2`: install `psycopg2-binary` into the Superset runtime site-packages and restart.
- Superset `'ascii' codec can't encode characters`: chart metric labels are used as SQL aliases; change metric labels to ASCII.
- Browser still shows old text: add a cache-busting query string to `app.js`.
- PowerShell encoding can corrupt Chinese JSON: send JSON as UTF-8 bytes when posting events.

## User-Facing Defaults

When explaining the resulting dashboard:

- `form_type` is SEC filing type: `10-K`, `10-Q`, `8-K`, `20-F`, `6-K`.
- `risk_topic` is a simple keyword-derived tag: `credit`, `liquidity`, `rate`, `loan`, `general`.
- `line_count_sum` is the number of cleaned text lines matching a group.
- `file_count_sum` is the number of filings represented by a group.
- This is a POC classification, not an investment signal.

## When Continuing The Original Environment

Use local encrypted secret locations:

- `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\credentials.xml`
- `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\bigdata-service-passwords.xml`
- `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\superset.xml`
- `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\ssh\bigdata-monitor-ed25519`
- `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\ssh\known_hosts`

Never expose values read from these files. For password display requests, prefer copying to the local clipboard instead of writing the password in chat.
