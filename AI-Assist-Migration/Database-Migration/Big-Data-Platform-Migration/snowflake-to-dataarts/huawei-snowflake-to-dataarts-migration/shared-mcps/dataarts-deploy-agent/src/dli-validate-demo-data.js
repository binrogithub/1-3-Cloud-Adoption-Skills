const fs = require("fs");
const path = require("path");
const https = require("https");
const config = require("./config");
const { buildSignedHeaders } = require("./huawei-signer");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

const POLL_INTERVAL_MS = 5000;
const POLL_TIMEOUT_MS = 300000;

const VALIDATION_QUERIES = [
  {
    name: "raw_orders_count",
    sql: "SELECT COUNT(*) AS raw_orders_count FROM demo_migration.raw_orders",
    currentdb: "demo_migration",
  },
  {
    name: "task_audit_count",
    sql: "SELECT COUNT(*) AS task_audit_count FROM demo_migration.task_audit",
    currentdb: "demo_migration",
  },
  {
    name: "raw_orders_by_date",
    sql: "SELECT order_date, COUNT(*) AS order_count, SUM(order_amount) AS total_amount FROM demo_migration.raw_orders GROUP BY order_date ORDER BY order_date",
    currentdb: "demo_migration",
  },
];

function assertSelectOnly(sql) {
  const trimmed = sql.trim().toUpperCase();
  if (!trimmed.startsWith("SELECT")) {
    throw new Error(`SAFETY VIOLATION: SQL is not SELECT: ${sql.trim().slice(0, 80)}`);
  }
}

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

async function pollJobUntilFinished(endpoint, projectId, jobId, ak, sk) {
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
            return { finished: true, status: "FINISHED" };
          }
          if (status === "FAILED" || status === "ERROR") {
            return { finished: true, status: "FAILED" };
          }
          if (status === "CANCELLED") {
            return { finished: true, status: "CANCELLED" };
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

async function fetchJobResult(endpoint, projectId, jobId, ak, sk) {
  const url = `${endpoint}/v1.0/${projectId}/jobs/${jobId}`;
  const res = await signedGet(url, ak, sk);
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw new Error(`Job detail fetch failed: HTTP ${res.statusCode}`);
  }
  return JSON.parse(res.body);
}

function extractRowsFromJobDetail(detail) {
  const rows = detail.rows || [];
  const schema = detail.schema || [];
  const columns = schema.map((s) => {
    if (typeof s === "object" && s !== null) {
      return Object.keys(s)[0] || "?";
    }
    return String(s);
  });
  if (!Array.isArray(rows) || rows.length === 0) {
    return { columns, rows: [] };
  }
  const parsedRows = rows.map((row) => {
    if (Array.isArray(row)) {
      const obj = {};
      columns.forEach((col, i) => {
        obj[col] = row[i];
      });
      return obj;
    }
    return row;
  });
  return { columns, rows: parsedRows };
}

function validateResults(queryResults) {
  const checks = [];

  const rawOrdersResult = queryResults.find((q) => q.name === "raw_orders_count");
  if (rawOrdersResult && rawOrdersResult.rows && rawOrdersResult.rows.length > 0) {
    const count = Number(rawOrdersResult.rows[0].raw_orders_count);
    if (count === 5) {
      checks.push({ check: "raw_orders_count = 5", result: "PASS", actual: count });
    } else {
      checks.push({ check: "raw_orders_count = 5", result: "FAIL", actual: count, expected: 5 });
    }
  } else {
    checks.push({ check: "raw_orders_count = 5", result: "FAIL", actual: "no data", expected: 5 });
  }

  const taskAuditResult = queryResults.find((q) => q.name === "task_audit_count");
  if (taskAuditResult && taskAuditResult.rows && taskAuditResult.rows.length > 0) {
    const count = Number(taskAuditResult.rows[0].task_audit_count);
    if (count >= 0) {
      checks.push({ check: "task_audit_count >= 0", result: "PASS", actual: count });
    } else {
      checks.push({ check: "task_audit_count >= 0", result: "FAIL", actual: count });
    }
  } else {
    checks.push({ check: "task_audit_count >= 0", result: "FAIL", actual: "no data" });
  }

  const byDateResult = queryResults.find((q) => q.name === "raw_orders_by_date");
  if (byDateResult && byDateResult.rows && byDateResult.rows.length > 0) {
    const row20260620 = byDateResult.rows.find(
      (r) => String(r.order_date).startsWith("2026-06-20")
    );
    if (row20260620) {
      const oc = Number(row20260620.order_count);
      const ta = Number(row20260620.total_amount);
      if (oc === 2 && Math.abs(ta - 420.5) < 0.01) {
        checks.push({ check: "2026-06-20: order_count=2, total_amount=420.50", result: "PASS", actual: { order_count: oc, total_amount: ta } });
      } else {
        checks.push({ check: "2026-06-20: order_count=2, total_amount=420.50", result: "FAIL", actual: { order_count: oc, total_amount: ta }, expected: { order_count: 2, total_amount: 420.5 } });
      }
    } else {
      checks.push({ check: "2026-06-20: order_count=2, total_amount=420.50", result: "FAIL", actual: "row not found" });
    }

    const row20260621 = byDateResult.rows.find(
      (r) => String(r.order_date).startsWith("2026-06-21")
    );
    if (row20260621) {
      const oc = Number(row20260621.order_count);
      const ta = Number(row20260621.total_amount);
      if (oc === 3 && Math.abs(ta - 630.34) < 0.01) {
        checks.push({ check: "2026-06-21: order_count=3, total_amount=630.34", result: "PASS", actual: { order_count: oc, total_amount: ta } });
      } else {
        checks.push({ check: "2026-06-21: order_count=3, total_amount=630.34", result: "FAIL", actual: { order_count: oc, total_amount: ta }, expected: { order_count: 3, total_amount: 630.34 } });
      }
    } else {
      checks.push({ check: "2026-06-21: order_count=3, total_amount=630.34", result: "FAIL", actual: "row not found" });
    }
  } else {
    checks.push({ check: "2026-06-20: order_count=2, total_amount=420.50", result: "FAIL", actual: "no data" });
    checks.push({ check: "2026-06-21: order_count=3, total_amount=630.34", result: "FAIL", actual: "no data" });
  }

  return checks;
}

function computeOverallStatus(checks, queryExecResults) {
  const allQueriesOk = queryExecResults.every((q) => q.success);
  const allChecksPass = checks.every((c) => c.result === "PASS");
  const anyCheckFail = checks.some((c) => c.result === "FAIL");

  if (!allQueriesOk) return "FAIL";
  if (allChecksPass) return "PASS";
  if (anyCheckFail) return "FAIL";
  return "WARN";
}

function generateMarkdownReport(data) {
  const lines = [];

  lines.push("# DLI Demo Data Validation Report");
  lines.push("");
  lines.push(`**Timestamp:** ${data.timestamp}`);
  lines.push(`**Overall Status:** ${data.overall_status}`);
  lines.push("");

  lines.push("## Environment");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| Endpoint | ${data.endpoint} |`);
  lines.push(`| Project ID | ${data.project_id_masked} |`);
  lines.push(`| DLI Queue | ${data.queue_name} |`);
  lines.push("");

  lines.push("## SQL Statements Executed");
  lines.push("");
  lines.push("| # | Name | SQL (truncated) | HTTP Status | DLI Status | Success |");
  lines.push("|---|------|-----------------|-------------|------------|---------|");
  for (let i = 0; i < data.query_results.length; i++) {
    const q = data.query_results[i];
    const sqlShort = q.sql.length > 60 ? q.sql.slice(0, 57) + "..." : q.sql;
    lines.push(`| ${i + 1} | ${q.name} | \`${sqlShort}\` | ${q.http_status || "N/A"} | ${q.dli_status || "N/A"} | ${q.success ? "OK" : "FAIL"} |`);
  }
  lines.push("");

  lines.push("## Query Results");
  lines.push("");
  for (const q of data.query_results) {
    lines.push(`### ${q.name}`);
    lines.push("");
    if (q.rows && q.rows.length > 0) {
      const cols = Object.keys(q.rows[0]);
      lines.push("| " + cols.join(" | ") + " |");
      lines.push("| " + cols.map(() => "---").join(" | ") + " |");
      for (const row of q.rows) {
        lines.push("| " + cols.map((c) => row[c] !== undefined && row[c] !== null ? row[c] : "NULL").join(" | ") + " |");
      }
    } else {
      lines.push("(no rows returned)");
    }
    lines.push("");
  }

  lines.push("## Validation Checks");
  lines.push("");
  lines.push("| Check | Result | Actual | Expected |");
  lines.push("|-------|--------|--------|----------|");
  for (const c of data.checks) {
    const actual = typeof c.actual === "object" ? JSON.stringify(c.actual) : String(c.actual);
    const expected = c.expected !== undefined ? (typeof c.expected === "object" ? JSON.stringify(c.expected) : String(c.expected)) : "-";
    lines.push(`| ${c.check} | ${c.result} | ${actual} | ${expected} |`);
  }
  lines.push("");

  const passCount = data.checks.filter((c) => c.result === "PASS").length;
  const failCount = data.checks.filter((c) => c.result === "FAIL").length;
  const warnCount = data.checks.filter((c) => c.result === "WARN").length;

  lines.push("## Summary");
  lines.push("");
  lines.push(`- **Overall Status:** ${data.overall_status}`);
  lines.push(`- **Queries executed:** ${data.query_results.length}`);
  lines.push(`- **Checks PASS:** ${passCount}`);
  lines.push(`- **Checks FAIL:** ${failCount}`);
  lines.push(`- **Checks WARN:** ${warnCount}`);
  lines.push("");

  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **Only SELECT statements were executed. No DataArts publish/start/run was executed.**");
  lines.push(">");
  lines.push("> - No INSERT, UPDATE, DELETE, DROP, or CREATE statements were executed.");
  lines.push("> - No DataArts API was called.");
  lines.push("> - No DataArts `/publish`, `/start`, or `/run-immediate` endpoint was used.");
  lines.push("> - Only `POST /v1.0/{project_id}/jobs/submit-job` (DLI SQL) with SELECT queries was used.");
  lines.push("> - All SQL was validated as SELECT-only before submission.");
  lines.push("");

  return lines.join("\n");
}

async function main() {
  console.log("=== DataArts Deploy Agent: DLI VALIDATE DEMO DATA (read-only SELECT only) ===\n");

  try {
    const env = config.load();
    config.validate(env);

    const region = env.HUAWEI_REGION;
    const projectId = env.HUAWEI_PROJECT_ID;
    const ak = env.HUAWEI_AK;
    const sk = env.HUAWEI_SK;
    const queueName = (env.DLI_QUEUE_NAME || "").trim();

    if (!queueName || queueName === "AUTO_DISCOVER") {
      throw new Error("Set DLI_QUEUE_NAME (e.g. default) before running validation.");
    }

    const endpointHost = `dli.${region}.myhuaweicloud.com`;
    const endpoint = `https://${endpointHost}`;

    console.log(`Endpoint:  ${endpoint}`);
    console.log(`Region:    ${region}`);
    console.log(`Project:   ${maskId(projectId)}`);
    console.log(`Queue:     ${queueName}`);
    console.log("");

    console.log("[1/4] Safety check: verifying all SQL is SELECT-only...\n");
    for (const q of VALIDATION_QUERIES) {
      assertSelectOnly(q.sql);
      console.log(`  [OK] ${q.name}: starts with SELECT`);
    }
    console.log("");

    console.log("[2/4] Submitting validation queries to DLI...\n");

    const submitUrl = `${endpoint}/v1.0/${projectId}/jobs/submit-job`;
    const queryResults = [];

    for (let i = 0; i < VALIDATION_QUERIES.length; i++) {
      const q = VALIDATION_QUERIES[i];
      console.log(`  [${i + 1}/${VALIDATION_QUERIES.length}] ${q.name}`);

      const requestBody = {
        queue_name: queueName,
        sql: q.sql,
        currentdb: q.currentdb,
      };

      let httpStatus = null;
      let dliStatus = null;
      let success = false;
      let error = null;
      let rows = [];

      try {
        const res = await signedPost(submitUrl, ak, sk, requestBody);
        httpStatus = res.statusCode;
        console.log(`    HTTP ${httpStatus}`);

        if (httpStatus >= 200 && httpStatus < 300) {
          const body = JSON.parse(res.body);
          const jobId = body.job_id;
          const respStatus = (body.status || "").toUpperCase();

          if (jobId) {
            console.log(`    Job ID: ${jobId} — polling for completion...`);
            const pollResult = await pollJobUntilFinished(endpoint, projectId, jobId, ak, sk);
            dliStatus = pollResult.status;
            console.log(`    Job status: ${dliStatus}`);

            if (dliStatus === "FINISHED") {
              try {
                const detail = await fetchJobResult(endpoint, projectId, jobId, ak, sk);
                const extracted = extractRowsFromJobDetail(detail);
                rows = extracted.rows;
                success = true;
                console.log(`    Rows returned: ${rows.length}`);
                if (rows.length > 0) {
                  console.log(`    Sample: ${JSON.stringify(rows[0])}`);
                }
              } catch (fetchErr) {
                error = `Job finished but result fetch failed: ${fetchErr.message}`;
              }
            } else {
              error = `DLI job ${dliStatus}`;
            }
          } else {
            if (body.error_code || body.error_msg) {
              error = `${body.error_code || ""}: ${body.error_msg || ""}`.trim();
            } else {
              error = "No job_id returned";
            }
          }
        } else if (httpStatus === 408) {
          let parsed;
          try { parsed = JSON.parse(res.body); } catch { parsed = {}; }
          const msg = parsed.error_msg || "";
          const match = msg.match(/id[:\s]*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i);
          if (match) {
            const timeoutJobId = match[1];
            console.log(`    HTTP 408 — Job ID: ${timeoutJobId} — polling...`);
            const pollResult = await pollJobUntilFinished(endpoint, projectId, timeoutJobId, ak, sk);
            dliStatus = pollResult.status;
            if (dliStatus === "FINISHED") {
              try {
                const detail = await fetchJobResult(endpoint, projectId, timeoutJobId, ak, sk);
                const extracted = extractRowsFromJobDetail(detail);
                rows = extracted.rows;
                success = true;
                console.log(`    Rows returned: ${rows.length}`);
              } catch (fetchErr) {
                error = `Job finished but result fetch failed: ${fetchErr.message}`;
              }
            } else {
              error = `DLI job ${dliStatus} (after timeout)`;
            }
          } else {
            error = "HTTP 408 sync timeout, no job_id found";
          }
        } else {
          error = `HTTP ${httpStatus}`;
          try {
            const body = JSON.parse(res.body);
            if (body.error_code || body.error_msg) {
              error += ` — ${body.error_code || ""}: ${body.error_msg || ""}`.trim();
            }
          } catch {
          }
        }
      } catch (err) {
        error = `Request error: ${err.message}`;
      }

      queryResults.push({
        name: q.name,
        sql: q.sql,
        http_status: httpStatus,
        dli_status: dliStatus,
        success,
        error,
        rows,
      });

      if (success) {
        console.log(`    OK`);
      } else {
        console.log(`    FAIL: ${error}`);
      }
      console.log("");
    }

    console.log("[3/4] Validating results against expected values...\n");

    const checks = validateResults(queryResults);

    for (const c of checks) {
      const icon = c.result === "PASS" ? "✓" : "✗";
      console.log(`  [${icon}] ${c.check}: ${c.result} (actual: ${JSON.stringify(c.actual)})`);
    }
    console.log("");

    const overallStatus = computeOverallStatus(checks, queryResults);

    console.log(`  Overall: ${overallStatus}`);
    console.log("");

    console.log("[4/4] Generating reports...\n");

    const timestamp = new Date().toISOString();

    const jsonReport = {
      timestamp,
      overall_status: overallStatus,
      endpoint,
      project_id_masked: maskId(projectId),
      queue_name: queueName,
      query_results: queryResults.map((q) => ({
        name: q.name,
        sql: q.sql,
        http_status: q.http_status,
        dli_status: q.dli_status,
        success: q.success,
        error: q.error,
        rows: q.rows,
      })),
      checks,
      safety: {
        only_select_statements: true,
        no_insert: true,
        no_update: true,
        no_delete: true,
        no_drop: true,
        no_create: true,
        no_dataarts_publish: true,
        no_dataarts_start: true,
        no_dataarts_run_immediate: true,
        no_dataarts_api_called: true,
        all_sql_validated_as_select: true,
      },
      no_secrets_included: true,
    };

    const mdData = {
      timestamp,
      overall_status: overallStatus,
      endpoint,
      project_id_masked: maskId(projectId),
      queue_name: queueName,
      query_results: queryResults.map((q) => ({
        name: q.name,
        sql: q.sql,
        http_status: q.http_status,
        dli_status: q.dli_status,
        success: q.success,
        error: q.error,
        rows: q.rows,
      })),
      checks,
    };

    const mdReport = generateMarkdownReport(mdData);

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const jsonPath = path.join(OUT_DIR, "dli_validate_demo_data_result.json");
    const mdPath = path.join(OUT_DIR, "dli_validate_demo_data_report.md");

    fs.writeFileSync(jsonPath, JSON.stringify(jsonReport, null, 2), "utf-8");
    fs.writeFileSync(mdPath, mdReport, "utf-8");

    console.log(`  [WRITE] out/dli_validate_demo_data_result.json`);
    console.log(`  [WRITE] out/dli_validate_demo_data_report.md`);
    console.log("");

    console.log("=== Validation Result ===");
    console.log(`  Overall:    ${overallStatus}`);
    console.log(`  Queries:    ${queryResults.length}`);
    console.log(`  Passed:     ${checks.filter((c) => c.result === "PASS").length}`);
    console.log(`  Failed:     ${checks.filter((c) => c.result === "FAIL").length}`);
    console.log("");
    console.log("Safety: Only SELECT statements were executed. No DataArts publish/start/run was executed.");
    console.log("");
    console.log("Reports saved:");
    console.log(`  ${mdPath}`);
    console.log(`  ${jsonPath}`);

    process.exit(overallStatus === "PASS" ? 0 : 1);
  } catch (err) {
    console.error(`DLI VALIDATE DEMO DATA FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
