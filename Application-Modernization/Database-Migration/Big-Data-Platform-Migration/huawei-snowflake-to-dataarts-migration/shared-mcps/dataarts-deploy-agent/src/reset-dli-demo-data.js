const fs = require("fs");
const path = require("path");
const https = require("https");
const config = require("./config");
const { buildSignedHeaders } = require("./huawei-signer");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

const SQL_STEPS = [
  {
    name: "DROP TABLE IF EXISTS demo_migration.gold_daily_sales",
    sql: "DROP TABLE IF EXISTS demo_migration.gold_daily_sales;",
    currentdb: null,
  },
  {
    name: "DROP TABLE IF EXISTS demo_migration.silver_orders",
    sql: "DROP TABLE IF EXISTS demo_migration.silver_orders;",
    currentdb: null,
  },
  {
    name: "DROP TABLE IF EXISTS demo_migration.raw_orders",
    sql: "DROP TABLE IF EXISTS demo_migration.raw_orders;",
    currentdb: null,
  },
  {
    name: "DROP TABLE IF EXISTS demo_migration.task_audit",
    sql: "DROP TABLE IF EXISTS demo_migration.task_audit;",
    currentdb: null,
  },
  {
    name: "CREATE DATABASE IF NOT EXISTS demo_migration",
    sql: "CREATE DATABASE IF NOT EXISTS demo_migration;",
    currentdb: null,
  },
  {
    name: "CREATE TABLE demo_migration.raw_orders",
    sql: `CREATE TABLE demo_migration.raw_orders (
  order_id INT,
  customer_id INT,
  order_date DATE,
  order_amount DECIMAL(12,2),
  ingested_at TIMESTAMP
);`,
    currentdb: "demo_migration",
  },
  {
    name: "INSERT INTO demo_migration.raw_orders",
    sql: `INSERT INTO demo_migration.raw_orders
VALUES
  (1, 101, DATE '2026-06-20', 120.50, CURRENT_TIMESTAMP()),
  (2, 102, DATE '2026-06-20', 300.00, CURRENT_TIMESTAMP()),
  (3, 101, DATE '2026-06-21', 80.25, CURRENT_TIMESTAMP()),
  (4, 103, DATE '2026-06-21', 450.10, CURRENT_TIMESTAMP()),
  (5, 104, DATE '2026-06-21', 99.99, CURRENT_TIMESTAMP());`,
    currentdb: "demo_migration",
  },
  {
    name: "CREATE TABLE demo_migration.task_audit",
    sql: `CREATE TABLE demo_migration.task_audit (
  pipeline_name STRING,
  step_name STRING,
  status STRING,
  message STRING,
  created_at TIMESTAMP
);`,
    currentdb: "demo_migration",
  },
];

const POLL_INTERVAL_MS = 5000;
const POLL_TIMEOUT_MS = 300000;

function maskId(id) {
  if (!id || id.length < 8) return "***";
  return id.slice(0, 4) + "***" + id.slice(-4);
}

function httpsRequest(url, options, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      req.destroy(new Error("REQUEST_TIMEOUT"));
    }, timeoutMs);

    const req = https.request(url, options, (res) => {
      clearTimeout(timer);
      let body = "";
      res.on("data", (chunk) => (body += chunk));
      res.on("end", () => {
        resolve({ statusCode: res.statusCode, headers: res.headers, body });
      });
    });

    req.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });

    if (options.body) {
      req.write(options.body);
    }
    req.end();
  });
}

async function signedPost(url, ak, sk, requestBody) {
  const bodyStr = JSON.stringify(requestBody);
  const headers = {
    "Content-Type": "application/json",
  };

  const signed = buildSignedHeaders({
    method: "POST",
    url,
    headers,
    body: bodyStr,
    ak,
    sk,
  });

  const parsed = new URL(url);
  const options = {
    hostname: parsed.hostname,
    port: 443,
    path: parsed.pathname + parsed.search,
    method: "POST",
    headers: signed,
    body: bodyStr,
  };

  return httpsRequest(url, options, 180000);
}

async function signedGet(url, ak, sk) {
  const headers = {
    "Content-Type": "application/json",
  };

  const signed = buildSignedHeaders({
    method: "GET",
    url,
    headers,
    body: "",
    ak,
    sk,
  });

  const parsed = new URL(url);
  const options = {
    hostname: parsed.hostname,
    port: 443,
    path: parsed.pathname + parsed.search,
    method: "GET",
    headers: signed,
  };

  return httpsRequest(url, options);
}

function extractJobIdFromTimeout(body) {
  try {
    const parsed = JSON.parse(body);
    const msg = parsed.error_msg || "";
    const match = msg.match(/id[:\s]*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i);
    if (match) return match[1];
  } catch {
  }
  return null;
}

function sanitizeDliResponse(body) {
  try {
    const parsed = JSON.parse(body);
    const safe = {};
    if (parsed.job_id) safe.job_id = parsed.job_id;
    if (parsed.job_mode) safe.job_mode = parsed.job_mode;
    if (parsed.status) safe.status = parsed.status;
    if (parsed.message) safe.message = parsed.message;
    if (parsed.error_code) safe.error_code = parsed.error_code;
    if (parsed.error_msg) safe.error_msg = parsed.error_msg;
    if (parsed.job_id && parsed.status) {
      safe.submitted = true;
    }
    return safe;
  } catch {
    return { raw_length: body.length, parse_error: true };
  }
}

async function pollJobStatus(endpoint, projectId, jobId, ak, sk) {
  const url = `${endpoint}/v1.0/${projectId}/jobs?job_id=${jobId}&limit=1`;
  const start = Date.now();

  while (Date.now() - start < POLL_TIMEOUT_MS) {
    try {
      const res = await signedGet(url, ak, sk);
      if (res.statusCode >= 200 && res.statusCode < 300) {
        const body = JSON.parse(res.body);
        const jobs = body.jobs || [];
        const job = jobs.find((j) => j.job_id === jobId);
        if (job) {
          const status = (job.status || "").toUpperCase();
          if (status === "FINISHED" || status === "SUCCESS") {
            return { finished: true, status: "FINISHED", body: job };
          }
          if (status === "FAILED" || status === "ERROR") {
            return { finished: true, status: "FAILED", body: job };
          }
          if (status === "CANCELLED") {
            return { finished: true, status: "CANCELLED", body: job };
          }
          if (status === "RUNNING" || status === "SUBMITTING" || status === "PENDING") {
            console.log(`    ... ${status} (${Math.round((Date.now() - start) / 1000)}s)`);
          }
        }
      }
    } catch {
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }

  return { finished: false, status: "TIMEOUT" };
}

function generateMarkdownReport(data) {
  const lines = [];

  lines.push("# DLI Demo Data Reset Report");
  lines.push("");
  lines.push(`**Timestamp:** ${data.timestamp}`);
  lines.push(`**Status:** ${data.status}`);
  lines.push("");

  lines.push("## Environment");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| Endpoint | ${data.endpoint} |`);
  lines.push(`| Project ID | ${data.project_id_masked} |`);
  lines.push(`| DLI Queue | ${data.queue_name} |`);
  lines.push("");

  lines.push("## SQL Execution Order");
  lines.push("");
  lines.push("| # | Step | HTTP Status | DLI Status | Result |");
  lines.push("|---|------|-------------|------------|--------|");

  for (let i = 0; i < data.executed_steps.length; i++) {
    const s = data.executed_steps[i];
    lines.push(`| ${i + 1} | ${s.name} | ${s.http_status || "N/A"} | ${s.dli_status || "N/A"} | ${s.success ? "OK" : "FAIL"} |`);
  }
  lines.push("");

  lines.push("## DLI Responses (sanitized)");
  lines.push("");
  for (const s of data.executed_steps) {
    lines.push(`### ${s.name}`);
    lines.push("");
    lines.push("```json");
    lines.push(JSON.stringify(s.dli_response, null, 2));
    lines.push("```");
    lines.push("");
  }

  lines.push("## Summary");
  lines.push("");
  lines.push(`- **Total steps:** ${data.executed_steps.length}`);
  lines.push(`- **Succeeded:** ${data.succeeded_steps.length}`);
  lines.push(`- **Failed:** ${data.failed_steps.length}`);
  if (data.first_failure) {
    lines.push(`- **First failure:** ${data.first_failure.name} — ${data.first_failure.error}`);
  }
  lines.push("");

  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **Only demo_migration demo tables were reset.**");
  lines.push("> **No DataArts publish/start/run operation was executed.**");
  lines.push("> **No DataArts job was modified or deleted.**");
  lines.push(">");
  lines.push("> - No DataArts `/publish` API was called.");
  lines.push("> - No DataArts `/start` API was called.");
  lines.push("> - No DataArts `/run-immediate` API was called.");
  lines.push("> - No DELETE, PUT, or PATCH requests were made to any Huawei Cloud API.");
  lines.push("> - Only `POST /v1.0/{project_id}/jobs/submit-job` (DLI SQL) was used.");
  lines.push("> - All DROP and CREATE operations were scoped to `demo_migration` only.");
  lines.push("");

  return lines.join("\n");
}

async function main() {
  console.log("=== DataArts Deploy Agent: RESET DLI DEMO DATA ===\n");

  const args = process.argv.slice(2);
  if (!args.includes("--confirm")) {
    console.log("ABORTED: --confirm flag is required.");
    console.log("");
    console.log("This command drops and recreates demo tables in demo_migration, then inserts fresh data.");
    console.log("To proceed, run:");
    console.log("  npm run reset-dli-demo-data -- --confirm");
    console.log("");
    console.log("Safety: No API calls were made. No SQL was executed.");
    process.exit(1);
  }

  try {
    console.log("[1/5] Loading and validating configuration...\n");

    const env = config.load();
    config.validate(env);

    const region = env.HUAWEI_REGION;
    const projectId = env.HUAWEI_PROJECT_ID;
    const ak = env.HUAWEI_AK;
    const sk = env.HUAWEI_SK;
    const queueName = (env.DLI_QUEUE_NAME || "").trim();

    if (!queueName || queueName === "AUTO_DISCOVER") {
      throw new Error("Set DLI_QUEUE_NAME=default before executing DLI SQL.");
    }

    const endpointHost = `dli.${region}.myhuaweicloud.com`;
    const endpoint = `https://${endpointHost}`;

    console.log(`  Endpoint:  ${endpoint}`);
    console.log(`  Region:    ${region}`);
    console.log(`  Project:   ${maskId(projectId)}`);
    console.log(`  Queue:     ${queueName}`);
    console.log("");

    console.log("[2/5] Submitting SQL to DLI...\n");

    const submitUrl = `${endpoint}/v1.0/${projectId}/jobs/submit-job`;

    const executedSteps = [];
    const succeededSteps = [];
    const failedSteps = [];
    let firstFailure = null;

    for (let i = 0; i < SQL_STEPS.length; i++) {
      const step = SQL_STEPS[i];
      console.log(`  [${i + 1}/${SQL_STEPS.length}] ${step.name}`);

      const requestBody = {
        queue_name: queueName,
        sql: step.sql,
      };
      if (step.currentdb) {
        requestBody.currentdb = step.currentdb;
      }

      let httpStatus = null;
      let dliResponse = null;
      let dliStatus = null;
      let success = false;
      let error = null;

      try {
        const res = await signedPost(submitUrl, ak, sk, requestBody);
        httpStatus = res.statusCode;
        dliResponse = sanitizeDliResponse(res.body);

        console.log(`    HTTP ${httpStatus}`);

        if (httpStatus >= 200 && httpStatus < 300) {
          const jobId = dliResponse.job_id;
          const respStatus = (dliResponse.status || "").toUpperCase();
          const jobMode = (dliResponse.job_mode || "").toLowerCase();

          if (jobId && jobMode === "sync" && (respStatus === "FINISHED" || respStatus === "SUCCESS")) {
            console.log(`    Job ID: ${jobId} (sync) — ${respStatus}`);
            dliStatus = "FINISHED";
            success = true;
          } else if (jobId) {
            console.log(`    Job ID: ${jobId} — polling for completion...`);
            const pollResult = await pollJobStatus(endpoint, projectId, jobId, ak, sk);
            dliStatus = pollResult.status;
            console.log(`    Job status: ${dliStatus}`);

            if (dliStatus === "FINISHED") {
              success = true;
            } else {
              error = `DLI job ${dliStatus}`;
            }
          } else {
            if (dliResponse.error_code || dliResponse.error_msg) {
              error = `${dliResponse.error_code || ""}: ${dliResponse.error_msg || ""}`.trim();
            } else {
              success = true;
              dliStatus = "SUBMITTED";
            }
          }
        } else if (httpStatus === 408) {
          const timeoutJobId = extractJobIdFromTimeout(res.body);
          if (timeoutJobId) {
            console.log(`    HTTP 408 (sync timeout) — Job ID: ${timeoutJobId} — polling for completion...`);
            const pollResult = await pollJobStatus(endpoint, projectId, timeoutJobId, ak, sk);
            dliStatus = pollResult.status;
            dliResponse = { ...dliResponse, job_id: timeoutJobId, polled_after_timeout: true };
            console.log(`    Job status: ${dliStatus}`);
            if (dliStatus === "FINISHED") {
              success = true;
            } else {
              error = `DLI job ${dliStatus} (after sync timeout)`;
            }
          } else {
            error = `HTTP 408 sync timeout, no job_id found`;
          }
        } else {
          error = `HTTP ${httpStatus}`;
          if (dliResponse.error_code || dliResponse.error_msg) {
            error += ` — ${dliResponse.error_code || ""}: ${dliResponse.error_msg || ""}`.trim();
          }
        }
      } catch (err) {
        error = `Request error: ${err.message}`;
        dliResponse = { error: err.message };
      }

      const record = {
        name: step.name,
        http_status: httpStatus,
        dli_status: dliStatus,
        dli_response: dliResponse,
        success,
        error,
      };

      executedSteps.push(record);

      if (success) {
        succeededSteps.push(step.name);
        console.log(`    OK`);
      } else {
        failedSteps.push(step.name);
        if (!firstFailure) {
          firstFailure = { name: step.name, error };
        }
        console.log(`    FAIL: ${error}`);
        console.log("");
        console.log("  Stopping on first failure. Remaining SQL steps will NOT be executed.");
        break;
      }

      console.log("");
    }

    console.log("[3/5] Generating report...\n");

    const timestamp = new Date().toISOString();

    const status = failedSteps.length === 0 ? "SUCCESS" : "FAILURE";

    const jsonResult = {
      timestamp,
      status,
      queue_name: queueName,
      executed_steps: executedSteps.map((s) => s.name),
      succeeded_steps: succeededSteps,
      failed_steps: failedSteps,
      first_failure: firstFailure,
      safety: {
        only_demo_migration_reset: true,
        no_dataarts_publish: true,
        no_dataarts_start: true,
        no_dataarts_run_immediate: true,
        no_dataarts_job_modified: true,
        no_dataarts_job_deleted: true,
        only_dli_sql_submit: true,
      },
    };

    const mdData = {
      timestamp,
      status,
      endpoint,
      project_id_masked: maskId(projectId),
      queue_name: queueName,
      executed_steps: executedSteps,
      succeeded_steps: succeededSteps,
      failed_steps: failedSteps,
      first_failure: firstFailure,
    };

    const mdReport = generateMarkdownReport(mdData);

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const jsonPath = path.join(OUT_DIR, "reset_dli_demo_data_result.json");
    const mdPath = path.join(OUT_DIR, "reset_dli_demo_data_report.md");

    fs.writeFileSync(jsonPath, JSON.stringify(jsonResult, null, 2), "utf-8");
    fs.writeFileSync(mdPath, mdReport, "utf-8");

    console.log(`  [WRITE] out/reset_dli_demo_data_result.json`);
    console.log(`  [WRITE] out/reset_dli_demo_data_report.md`);
    console.log("");

    console.log("[4/5] Summary\n");

    console.log(`  Status:     ${status}`);
    console.log(`  Executed:   ${executedSteps.length}`);
    console.log(`  Succeeded:  ${succeededSteps.length}`);
    console.log(`  Failed:     ${failedSteps.length}`);
    if (firstFailure) {
      console.log(`  First fail: ${firstFailure.name} — ${firstFailure.error}`);
    }
    console.log("");

    console.log("[5/5] Safety\n");
    console.log("  Only demo_migration demo tables were reset.");
    console.log("  No DataArts publish/start/run operation was executed.");
    console.log("  No DataArts job was modified or deleted.");
    console.log("");
    console.log("Reports saved:");
    console.log(`  ${mdPath}`);
    console.log(`  ${jsonPath}`);

    process.exit(status === "SUCCESS" ? 0 : 1);
  } catch (err) {
    console.error(`RESET DLI DEMO DATA FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
