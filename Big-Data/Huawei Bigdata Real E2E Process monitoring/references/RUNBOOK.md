# End-To-End Runbook

This reference records the full operational path used to deploy the Huawei Cloud SEC EDGAR big-data lifecycle monitoring POC. It is intentionally detailed and local-operator oriented. Do not paste secrets into commands or logs.

## 1. Goal And Architecture

Build a public monitoring website that shows a full big-data lifecycle:

1. Public SEC EDGAR filings are downloaded.
2. Raw files are streamed into Huawei OBS.
3. MRS Spark reads OBS raw, cleans/deduplicates/tags text, writes silver Parquet and gold aggregates.
4. Gold aggregate CSV is loaded into DWS.
5. Superset reads DWS and exposes BI reports.
6. A website shows progress, volumes, stage durations, and links to Superset.

Default region from the original run:

- Huawei Cloud region: `la-south-2`
- AZ: `la-south-2a`
- Public website: ECS + Nginx + EIP
- API: `server/monitor_api.py` on `127.0.0.1:8090`
- Superset: Docker on ECS, port `8088`

## 2. Credential Bootstrap

Use local DPAPI-encrypted files. Never commit or paste secrets.

Scripts:

- `scripts/huawei-cloud-credentials.ps1`
- `scripts/bigdata-service-passwords.ps1`
- `scripts/show-superset-credentials.ps1`

Saved local files:

- `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\credentials.xml`
- `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\bigdata-service-passwords.xml`
- `%LOCALAPPDATA%\Codex\huawei-cloud-bigdata\superset.xml`

PowerShell pattern to safely read a DPAPI secret:

```powershell
function ConvertFrom-LocalSecureString([SecureString]$SecureValue) {
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
  try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}
```

For user requests to reveal Superset password, prefer:

```powershell
$stored = Import-Clixml (Join-Path $env:LOCALAPPDATA 'Codex\huawei-cloud-bigdata\superset.xml')
$password = ConvertFrom-LocalSecureString $stored.Password
Set-Clipboard -Value $password
```

## 3. Terraform Provisioning

Important Terraform files:

- `infra/terraform/main.tf`: provider, OBS, networking, ECS.
- `infra/terraform/bigdata.tf`: DWS, MRS, MRS security-group ingress from ECS.
- `infra/terraform/variables.tf`: defaults and tunables.
- `infra/terraform/terraform.tfvars.example`: non-secret sample.
- `scripts/terraform-plan-secure.ps1`: loads secrets into environment and runs `terraform init` / `terraform plan -out tfplan`.
- `scripts/terraform-apply-existing-plan.ps1`: applies existing `tfplan`.

Typical flow:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\terraform-plan-secure.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\terraform-apply-existing-plan.ps1
```

If `terraform` is not on PATH, helper scripts check:

- `%LOCALAPPDATA%\Programs\Terraform\terraform.exe`
- Winget package location

Minimum useful POC variables from the original run:

- `enable_dws = true`
- `enable_mrs = true`
- `mrs_version = "MRS 3.5.0-LTS"`
- `mrs_components = ["DBService", "Hadoop", "Hive", "JobGateway", "Ranger", "Spark", "ZooKeeper"]`
- `mrs_master_node_count = 2`
- `mrs_core_node_count = 3`
- `mrs_master_flavor = "c6.4xlarge.4.linux.bigdata"`
- `mrs_core_flavor = "c6.4xlarge.4.linux.bigdata"`
- `mrs_root_volume_size = 600`
- `mrs_data_volume_size = 600`

Always re-check regional flavor and quota.

## 4. Network And Access

Expose only the web/Superset ECS publicly. Keep MRS/DWS private.

Useful ports:

- ECS public: 80, 443, 8088, SSH from current admin CIDR.
- ECS to MRS private: 22, 8088, 20009 if MRS Manager is needed.
- ECS to DWS private: DWS port, typically 8000.

When the user public IP changes:

1. Update `admin_cidr` in Terraform variables.
2. Re-run plan and apply.
3. Confirm SSH/Nginx/Superset access.

## 5. ECS Website And API

Files:

- `index.html`
- `app.js`
- `styles.css`
- `server/monitor_api.py`
- `deploy/bigdata-monitor-api.service`
- `deploy/nginx-monitor.conf`

Remote layout:

- Static site: `/var/www/bigdata-monitor`
- API script: `/opt/bigdata-monitor/server/monitor_api.py`
- Events file: `/var/lib/bigdata-monitor/events.jsonl`
- systemd service: `bigdata-monitor-api`

Deploy pattern:

```powershell
scp index.html app.js styles.css root@ECS_EIP:/var/www/bigdata-monitor/
scp server/monitor_api.py root@ECS_EIP:/opt/bigdata-monitor/server/monitor_api.py
ssh root@ECS_EIP 'systemctl restart bigdata-monitor-api && systemctl is-active bigdata-monitor-api'
```

Verify:

```powershell
curl.exe -s http://ECS_EIP/api/health
curl.exe -s http://ECS_EIP/api/status
```

If browser still shows old content, add a cache-busting query string:

```html
<script src="./app.js?v=YYYYMMDD-label"></script>
```

## 6. SEC EDGAR To OBS

Use `pipelines/sec_edgar_to_obs.py` instead of a local-only downloader to avoid storing 50GB on ECS.

Required env:

- `SEC_USER_AGENT`
- `HUAWEICLOUD_ACCESS_KEY`
- `HUAWEICLOUD_SECRET_KEY`
- `OBS_ENDPOINT`
- `OBS_BUCKET`

Set the required environment variables in the shell first, then run the command without echoing them:

```bash
python3 /opt/bigdata-monitor/pipelines/sec_edgar_to_obs.py \
  --bucket "$OBS_BUCKET" \
  --prefix raw/sec-edgar \
  --target-gb 50 \
  --start-year 2022 \
  --end-year 2025 \
  --monitor-api http://127.0.0.1:8090/api/events \
  --run-id sec-edgar-YYYYMMDD-50gb
```

Expected raw result from original run:

- `raw/sec-edgar/`: about 11,515 OBS objects
- Total bytes: about 50.02 GB
- Manifest: `raw/sec-edgar/manifests/...csv`

## 7. MRS Spark Processing

Script:

- `pipelines/spark_clean_financial_data.py`

Function:

- Reads text files from OBS raw.
- Adds `source_file`, `line_hash`, `form_type`, `risk_topic`, `ingest_date`.
- Deduplicates by line hash.
- Writes silver Parquet partitioned by date/form type.
- Writes gold aggregate by `ingest_date`, `form_type`, `risk_topic`.
- Optionally writes coalesced CSV for DWS loading.

SSH to MRS through ECS jump:

```powershell
$key = Join-Path $env:LOCALAPPDATA 'Codex\huawei-cloud-bigdata\ssh\bigdata-monitor-ed25519'
$kh = Join-Path $env:LOCALAPPDATA 'Codex\huawei-cloud-bigdata\ssh\known_hosts'
$proxy = "ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=$kh -i $key -W %h:%p root@ECS_EIP"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile="$kh" -i "$key" -o ProxyCommand="$proxy" root@MRS_MASTER_IP 'hostname'
```

MRS client env:

```bash
source /opt/Bigdata/client/bigdata_env
/opt/Bigdata/client/Spark/spark/bin/spark-submit ...
```

If MRS lacks an OBS agency, Spark OBS reads fail with provider errors. Workaround with job-level OBS credentials:

```bash
--conf spark.hadoop.fs.obs.security.provider=com.obs.services.BasicObsCredentialsProvider
--conf spark.hadoop.fs.obs.access.key=...
--conf spark.hadoop.fs.obs.secret.key=...
--conf spark.hadoop.fs.obs.endpoint=obs.la-south-2.myhuaweicloud.com
```

Do not print `ps -ef` or command lines while this job is running; the secret key may be visible in process args.

Progress checks:

```bash
pid=$(cat /var/run/bigdata-monitor/mrs-clean-50gb.pid 2>/dev/null || true)
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then echo "running"; else echo "not running"; fi
grep -a "END status=" /var/log/bigdata-monitor/mrs-clean-50gb.log | tail -1
source /opt/Bigdata/client/bigdata_env >/dev/null 2>&1 || true
yarn application -list -appStates ALL | sed -n '1,12p'
```

Successful original log pattern:

```text
END status=0 duration_seconds=1310 ...
```

Expected original outputs:

- `silver/sec-edgar/`: about 36.73 GB final committed objects.
- `gold/sec-edgar/topic_daily/`: tiny Parquet aggregate.
- `gold/sec-edgar/topic_daily_csv/`: tiny CSV aggregate, 25 rows.

## 8. OBS Validation

Use the Python OBS SDK with env credentials:

```python
from obs import ObsClient
client = ObsClient(access_key_id=AK, secret_access_key=SK, server=ENDPOINT)
resp = client.listObjects(bucket, prefix="raw/sec-edgar/", max_keys=1000)
```

Count all pages and sum object sizes. Validate:

- `raw/sec-edgar/`
- `silver/sec-edgar/`
- `gold/sec-edgar/topic_daily/`
- `gold/sec-edgar/topic_daily_csv/`

Ignore `.spark-staging-*` unless debugging a failed or partial Spark commit. For downstream DWS load, use only `gold/sec-edgar/topic_daily_csv/part-*.csv`.

## 9. DWS Schema And Load

Schema file:

- `sql/dws_schema.sql`

Key table:

```sql
finance_monitor.fact_financial_topic_daily (
  ingest_date date,
  form_type varchar(16),
  risk_topic varchar(64),
  line_count bigint,
  file_count bigint,
  loaded_at timestamp
)
```

Simple load strategy used in the POC:

1. Download gold CSV part from OBS to a temporary file.
2. Copy it to ECS.
3. Create temporary `/root/.pgpass` for DWS connection.
4. Run `psql \copy`.
5. Delete temp CSV and `.pgpass`.

Remote psql pattern:

```bash
psql -h DWS_PRIVATE_IP -p 8000 -U dbadmin -d gaussdb -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
DELETE FROM finance_monitor.fact_financial_topic_daily WHERE ingest_date = DATE 'YYYY-MM-DD';
\copy finance_monitor.fact_financial_topic_daily(ingest_date, form_type, risk_topic, line_count, file_count) FROM '/tmp/sec-edgar-topic-daily.csv' WITH (FORMAT csv, HEADER true);
COMMIT;
SELECT COUNT(*) AS rows_loaded, SUM(line_count) AS total_lines, SUM(file_count) AS total_files
FROM finance_monitor.fact_financial_topic_daily
WHERE ingest_date = DATE 'YYYY-MM-DD';
SQL
```

Original successful result:

- `COPY 25`
- 25 aggregate rows
- 282,740,086 total text lines
- 25,675 total file-count sum

## 10. Superset

Superset tasks:

1. Reset admin password to match local encrypted record if API login fails.
2. Install PostgreSQL DBAPI driver if missing.
3. Create DWS database connection.
4. Create dataset `finance_monitor.fact_financial_topic_daily`.
5. Create charts and dashboard.

If API login returns 401:

```bash
docker exec bigdata-monitor-superset superset fab reset-password --username admin --password "$PASSWORD"
```

If dataset creation fails with `No module named 'psycopg2'`, install into the runtime used by Superset:

```bash
docker exec -u root bigdata-monitor-superset /usr/local/bin/python3 -m pip install --no-cache-dir --target /app/.venv/lib/python3.10/site-packages psycopg2-binary
docker restart bigdata-monitor-superset
```

If charts fail with:

```text
'ascii' codec can't encode characters
```

Fix metric labels in chart `params`. Superset uses metric labels as SQL aliases; keep them ASCII:

- `line_count_sum`
- `file_count_sum`

Dashboard title can be English or localized, but SQL aliases should stay ASCII.

Validate chart data through `/api/v1/chart/data`; expect:

- Chart by form type/topic: 25 rows.
- Chart by form type: 5 rows.

## 11. Monitoring Events

API endpoint:

```text
POST http://ECS_EIP/api/events
```

Event shape:

```json
{
  "run_id": "mrs-clean-YYYYMMDD-50gb",
  "stage": "mrs",
  "status": "success",
  "bytes_in": 53703934790,
  "bytes_out": 39435831274,
  "rows_out": 25,
  "progress": 1.0,
  "duration_seconds": 1310,
  "volume": "silver 36.73 GB, gold CSV 25 rows",
  "message": "MRS Spark completed.",
  "event_time": 1778958598
}
```

On Windows PowerShell, post UTF-8 bytes to avoid corrupting non-ASCII:

```powershell
$json = $event | ConvertTo-Json -Compress
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
Invoke-RestMethod -Uri 'http://ECS_EIP/api/events' -Method Post -Body $bytes -ContentType 'application/json; charset=utf-8'
```

## 12. Frontend Localization

Files:

- `index.html`
- `app.js`
- `server/monitor_api.py`

For full English UI:

- Change static page text in `index.html`.
- Change fallback resources/status labels in `app.js`.
- Change API stage names/descriptions in `server/monitor_api.py`.
- Update Superset dashboard and chart titles through the Superset API.
- Add cache-busting to script URLs, for example `app.js?v=20260516-en2`.
- Verify the public `app.js` has no CJK characters:

```powershell
curl.exe -s http://ECS_EIP/app.js -o $env:TEMP\remote-app.js
$page = Get-Content -Raw $env:TEMP\remote-app.js
[regex]::IsMatch($page, '\p{IsCJKUnifiedIdeographs}')
```

## 13. Common Pitfalls

- Do not use destructive git commands in a dirty worktree.
- Do not inspect secret-containing temporary scripts in terminal output.
- Remove temporary Spark wrapper scripts that contain OBS credentials.
- Avoid `ps -ef` on MRS during secret-bearing Spark submissions.
- PowerShell here-strings can introduce CRLF; remote Bash scripts should use LF.
- MRS may not support SFTP; pipe files over SSH.
- MRS `hadoop`, `yarn`, and `spark-submit` may not be in PATH until `bigdata_env` is sourced.
- OBS object-store committers may emit 404 warnings while checking temporary directories; this is not necessarily failure.
- Browser cache can make the website look stale after deployment.
- Superset chart title localization is safe; metric labels used in SQL aliases should remain ASCII.

## 14. Final User Status Template

Use concise completion messages:

```text
The real pipeline is complete:
- OBS raw: 50.01 GB SEC EDGAR data
- MRS Spark: succeeded, silver/gold outputs created
- DWS: fact_financial_topic_daily loaded
- Superset: dataset, charts, and dashboard created
- Monitor: public site and /api/status show all stages healthy

Resources are still running and may continue to incur pay-per-use charges.
```
