const fs = require("fs");
const path = require("path");
const https = require("https");
const config = require("./config");
const { buildSignedHeaders } = require("./huawei-signer");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

const RUN_IMMEDIATE_RESULT = path.join(OUT_DIR, "run_immediate_job_result.json");
const DLI_VALIDATE_RESULT = path.join(OUT_DIR, "dli_validate_demo_data_result.json");
const V1_DRYRUN_REQUEST = path.join(OUT_DIR, "dataarts_create_job_request.v1.dryrun.json");

const DATAARTS_POLL_INTERVAL_MS = 10000;
const DATAARTS_POLL_TIMEOUT_MS = 300000;
const DLI_POLL_INTERVAL_MS = 5000;
const DLI_POLL_TIMEOUT_MS = 300000;

const DLI_VALIDATION_QUERIES = [
  {
    name: "raw_orders_count",
    sql: "SELECT COUNT(*) AS raw_orders_count FROM demo_migration.raw_orders",
    currentdb: "demo_migration",
  },
  {
    name: "silver_orders_count",
    sql: "SELECT COUNT(*) AS silver_orders_count FROM demo_migration.silver_orders",
    currentdb: "demo_migration",
  },
  {
    name: "gold_daily_sales_count",
    sql: "SELECT COUNT(*) AS gold_daily_sales_count FROM demo_migration.gold_daily_sales",
    currentdb: "demo_migration",
  },
  {
    name: "task_audit_success_count",
    sql: "SELECT COUNT(*) AS task_audit_success_count FROM demo_migration.task_audit WHERE status = 'SUCCESS'",
    currentdb: "demo_migration",
  },
  {
    name: "gold_daily_sales_detail",
    sql: "SELECT order_date, order_count, total_amount FROM demo_migration.gold_daily_sales ORDER BY order_date",
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

async function signedGet(url, ak, sk, extraHeaders = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...extraHeaders,
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

function classifyInstanceStatus(status) {
  if (!status) return "unknown";
  const s = String(status).toUpperCase().trim();
  if (["SUCCESS", "SUCCEEDED"].includes(s)) return "success";
  if (["FAILED", "FAIL", "ERROR", "EXCEPTION"].includes(s)) return "failed";
  if (["CANCELLED", "CANCELED"].includes(s)) return "canceled";
  if (["RUNNING", "SUBMITTING", "PENDING", "WAITING", "QUEUED", "DISPATCHING"].includes(s)) return "running";
  if (["TIMEOUT", "TIMED_OUT"].includes(s)) return "timeout";
  return "unknown";
}

async function fetchDataArtsInstanceStatus(endpoint, projectId, jobName, instanceId, workspaceId, ak, sk) {
  const url = `${endpoint}/v1/${projectId}/jobs/${encodeURIComponent(jobName)}/instances/${instanceId}`;
  console.log(`  GET /v1/${maskId(projectId)}/jobs/${jobName}/instances/${instanceId}`);

  const res = await signedGet(url, ak, sk, { workspace: workspaceId });
  console.log(`  HTTP ${res.statusCode}`);

  if (res.statusCode >= 200 && res.statusCode < 300) {
    try {
      const body = JSON.parse(res.body);
      return { success: true, data: body, source: "direct" };
    } catch {
      return { success: false, error: "Failed to parse response body", source: "direct" };
    }
  }
  return { success: false, statusCode: res.statusCode, error: `HTTP ${res.statusCode}`, source: "direct" };
}

async function fetchDataArtsInstanceFallback(endpoint, projectId, jobName, instanceId, workspaceId, ak, sk) {
  const url = `${endpoint}/v1/${projectId}/jobs/instances/detail?jobName=${encodeURIComponent(jobName)}`;
  console.log(`  GET (fallback) /v1/${maskId(projectId)}/jobs/instances/detail?jobName=${jobName}`);

  const res = await signedGet(url, ak, sk, { workspace: workspaceId });
  console.log(`  HTTP ${res.statusCode}`);

  if (res.statusCode >= 200 && res.statusCode < 300) {
    try {
      const body = JSON.parse(res.body);
      return { success: true, data: body, source: "fallback" };
    } catch {
      return { success: false, error: "Failed to parse fallback response body", source: "fallback" };
    }
  }
  return { success: false, statusCode: res.statusCode, error: `HTTP ${res.statusCode}`, source: "fallback" };
}

function extractInstanceInfo(data, instanceId, source) {
  if (source === "direct") {
    const status = data.status || data.State || data.instanceStatus;
    const classified = classifyInstanceStatus(status);
    const nodes = data.nodes || data.taskDetails || [];
    return { status: classified, rawStatus: status, nodes, instanceData: data };
  }

  if (source === "fallback") {
    const instances = data.instances || data.records || data.data || [];
    const target = instances.find((inst) => {
      const id = inst.instanceId || inst.instance_id || inst.id;
      return String(id) === String(instanceId);
    });

    if (target) {
      const status = target.status || target.State || target.instanceStatus;
      const classified = classifyInstanceStatus(status);
      const nodes = target.nodes || target.taskDetails || [];
      return { status: classified, rawStatus: status, nodes, instanceData: target };
    }

    if (instances.length > 0) {
      const latest = instances[0];
      const status = latest.status || latest.State || latest.instanceStatus;
      const classified = classifyInstanceStatus(status);
      const nodes = latest.nodes || latest.taskDetails || [];
      return { status: classified, rawStatus: status, nodes, instanceData: latest, note: "Used first instance (instanceId match not found)" };
    }

    return { status: "unknown", rawStatus: null, nodes: [], instanceData: null, note: "No instances in fallback response" };
  }

  return { status: "unknown", rawStatus: null, nodes: [], instanceData: null };
}

async function pollDataArtsInstance(endpoint, projectId, jobName, instanceId, workspaceId, ak, sk) {
  const start = Date.now();
  console.log(`  Polling every ${DATAARTS_POLL_INTERVAL_MS / 1000}s up to ${DATAARTS_POLL_TIMEOUT_MS / 1000}s...\n`);

  while (Date.now() - start < DATAARTS_POLL_TIMEOUT_MS) {
    const result = await fetchDataArtsInstanceStatus(endpoint, projectId, jobName, instanceId, workspaceId, ak, sk);

    if (result.success) {
      const info = extractInstanceInfo(result.data, instanceId, "direct");
      if (info.status !== "running") {
        return info;
      }
      const elapsed = Math.round((Date.now() - start) / 1000);
      console.log(`    ... still running (${elapsed}s)`);
    } else {
      console.log(`    ... direct endpoint failed, trying fallback`);
      const fallback = await fetchDataArtsInstanceFallback(endpoint, projectId, jobName, instanceId, workspaceId, ak, sk);
      if (fallback.success) {
        const info = extractInstanceInfo(fallback.data, instanceId, "fallback");
        if (info.status !== "running") {
          return info;
        }
        const elapsed = Math.round((Date.now() - start) / 1000);
        console.log(`    ... still running via fallback (${elapsed}s)`);
      }
    }

    await new Promise((r) => setTimeout(r, DATAARTS_POLL_INTERVAL_MS));
  }

  return { status: "timeout", rawStatus: "TIMEOUT", nodes: [], instanceData: null };
}

async function pollDliJobUntilFinished(endpoint, projectId, jobId, ak, sk) {
  const url = `${endpoint}/v1.0/${projectId}/jobs?job_id=${jobId}&limit=1`;
  const start = Date.now();

  while (Date.now() - start < DLI_POLL_TIMEOUT_MS) {
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
        }
      }
    } catch {
    }
    await new Promise((r) => setTimeout(r, DLI_POLL_INTERVAL_MS));
  }

  return { finished: false, status: "TIMEOUT" };
}

async function fetchDliJobResult(endpoint, projectId, jobId, ak, sk) {
  const url = `${endpoint}/v1.0/${projectId}/jobs/${jobId}`;
  const res = await signedGet(url, ak, sk);
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw new Error(`DLI job detail fetch failed: HTTP ${res.statusCode}`);
  }
  return JSON.parse(res.body);
}

function extractRowsFromDliJobDetail(detail) {
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

async function runDliQuery(dliEndpoint, projectId, queueName, query, ak, sk) {
  const submitUrl = `${dliEndpoint}/v1.0/${projectId}/jobs/submit-job`;
  const requestBody = {
    queue_name: queueName,
    sql: query.sql,
    currentdb: query.currentdb,
  };

  const res = await signedPost(submitUrl, ak, sk, requestBody);
  const httpStatus = res.statusCode;

  if (httpStatus >= 200 && httpStatus < 300) {
    const body = JSON.parse(res.body);
    const jobId = body.job_id;

    if (jobId) {
      const pollResult = await pollDliJobUntilFinished(dliEndpoint, projectId, jobId, ak, sk);
      if (pollResult.status === "FINISHED") {
        const detail = await fetchDliJobResult(dliEndpoint, projectId, jobId, ak, sk);
        const extracted = extractRowsFromDliJobDetail(detail);
        return { success: true, httpStatus, dliStatus: pollResult.status, rows: extracted.rows, error: null };
      }
      return { success: false, httpStatus, dliStatus: pollResult.status, rows: [], error: `DLI job ${pollResult.status}` };
    }

    if (body.error_code || body.error_msg) {
      return { success: false, httpStatus, dliStatus: null, rows: [], error: `${body.error_code || ""}: ${body.error_msg || ""}`.trim() };
    }
    return { success: false, httpStatus, dliStatus: null, rows: [], error: "No job_id returned" };
  }

  if (httpStatus === 408) {
    let parsed;
    try { parsed = JSON.parse(res.body); } catch { parsed = {}; }
    const msg = parsed.error_msg || "";
    const match = msg.match(/id[:\s]*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i);
    if (match) {
      const timeoutJobId = match[1];
      const pollResult = await pollDliJobUntilFinished(dliEndpoint, projectId, timeoutJobId, ak, sk);
      if (pollResult.status === "FINISHED") {
        const detail = await fetchDliJobResult(dliEndpoint, projectId, timeoutJobId, ak, sk);
        const extracted = extractRowsFromDliJobDetail(detail);
        return { success: true, httpStatus, dliStatus: pollResult.status, rows: extracted.rows, error: null };
      }
      return { success: false, httpStatus, dliStatus: pollResult.status, rows: [], error: `DLI job ${pollResult.status} (after timeout)` };
    }
    return { success: false, httpStatus, dliStatus: null, rows: [], error: "HTTP 408 sync timeout, no job_id found" };
  }

  let errorMsg = `HTTP ${httpStatus}`;
  try {
    const body = JSON.parse(res.body);
    if (body.error_code || body.error_msg) {
      errorMsg += ` — ${body.error_code || ""}: ${body.error_msg || ""}`.trim();
    }
  } catch {
  }
  return { success: false, httpStatus, dliStatus: null, rows: [], error: errorMsg };
}

function validateDliResults(queryResults) {
  const checks = [];

  const rawResult = queryResults.find((q) => q.name === "raw_orders_count");
  if (rawResult && rawResult.rows && rawResult.rows.length > 0) {
    const count = Number(rawResult.rows[0].raw_orders_count);
    if (count === 5) {
      checks.push({ check: "raw_orders_count = 5", result: "PASS", actual: count, expected: 5 });
    } else {
      checks.push({ check: "raw_orders_count = 5", result: "FAIL", actual: count, expected: 5 });
    }
  } else {
    checks.push({ check: "raw_orders_count = 5", result: "FAIL", actual: "no data", expected: 5 });
  }

  const silverResult = queryResults.find((q) => q.name === "silver_orders_count");
  if (silverResult && silverResult.rows && silverResult.rows.length > 0) {
    const count = Number(silverResult.rows[0].silver_orders_count);
    if (count === 5) {
      checks.push({ check: "silver_orders_count = 5", result: "PASS", actual: count, expected: 5 });
    } else {
      checks.push({ check: "silver_orders_count = 5", result: "FAIL", actual: count, expected: 5 });
    }
  } else {
    checks.push({ check: "silver_orders_count = 5", result: "FAIL", actual: "no data", expected: 5 });
  }

  const goldResult = queryResults.find((q) => q.name === "gold_daily_sales_count");
  if (goldResult && goldResult.rows && goldResult.rows.length > 0) {
    const count = Number(goldResult.rows[0].gold_daily_sales_count);
    if (count === 2) {
      checks.push({ check: "gold_daily_sales_count = 2", result: "PASS", actual: count, expected: 2 });
    } else {
      checks.push({ check: "gold_daily_sales_count = 2", result: "FAIL", actual: count, expected: 2 });
    }
  } else {
    checks.push({ check: "gold_daily_sales_count = 2", result: "FAIL", actual: "no data", expected: 2 });
  }

  const auditResult = queryResults.find((q) => q.name === "task_audit_success_count");
  if (auditResult && auditResult.rows && auditResult.rows.length > 0) {
    const count = Number(auditResult.rows[0].task_audit_success_count);
    if (count >= 1) {
      checks.push({ check: "task_audit_success_count >= 1", result: "PASS", actual: count, expected: ">=1" });
    } else {
      checks.push({ check: "task_audit_success_count >= 1", result: "FAIL", actual: count, expected: ">=1" });
    }
  } else {
    checks.push({ check: "task_audit_success_count >= 1", result: "FAIL", actual: "no data", expected: ">=1" });
  }

  const detailResult = queryResults.find((q) => q.name === "gold_daily_sales_detail");
  if (detailResult && detailResult.rows && detailResult.rows.length > 0) {
    const row20260620 = detailResult.rows.find(
      (r) => String(r.order_date).startsWith("2026-06-20")
    );
    if (row20260620) {
      const oc = Number(row20260620.order_count);
      const ta = Number(row20260620.total_amount);
      if (oc === 2 && Math.abs(ta - 420.5) < 0.01) {
        checks.push({ check: "2026-06-20: order_count=2, total_amount=420.50", result: "PASS", actual: { order_count: oc, total_amount: ta }, expected: { order_count: 2, total_amount: 420.5 } });
      } else {
        checks.push({ check: "2026-06-20: order_count=2, total_amount=420.50", result: "FAIL", actual: { order_count: oc, total_amount: ta }, expected: { order_count: 2, total_amount: 420.5 } });
      }
    } else {
      checks.push({ check: "2026-06-20: order_count=2, total_amount=420.50", result: "FAIL", actual: "row not found", expected: { order_count: 2, total_amount: 420.5 } });
    }

    const row20260621 = detailResult.rows.find(
      (r) => String(r.order_date).startsWith("2026-06-21")
    );
    if (row20260621) {
      const oc = Number(row20260621.order_count);
      const ta = Number(row20260621.total_amount);
      if (oc === 3 && Math.abs(ta - 630.34) < 0.01) {
        checks.push({ check: "2026-06-21: order_count=3, total_amount=630.34", result: "PASS", actual: { order_count: oc, total_amount: ta }, expected: { order_count: 3, total_amount: 630.34 } });
      } else {
        checks.push({ check: "2026-06-21: order_count=3, total_amount=630.34", result: "FAIL", actual: { order_count: oc, total_amount: ta }, expected: { order_count: 3, total_amount: 630.34 } });
      }
    } else {
      checks.push({ check: "2026-06-21: order_count=3, total_amount=630.34", result: "FAIL", actual: "row not found", expected: { order_count: 3, total_amount: 630.34 } });
    }
  } else {
    checks.push({ check: "2026-06-20: order_count=2, total_amount=420.50", result: "FAIL", actual: "no data", expected: { order_count: 2, total_amount: 420.5 } });
    checks.push({ check: "2026-06-21: order_count=3, total_amount=630.34", result: "FAIL", actual: "no data", expected: { order_count: 3, total_amount: 630.34 } });
  }

  return checks;
}

function generateMarkdownReport(data) {
  const lines = [];

  lines.push("# Runtime Validation Report");
  lines.push("");
  lines.push(`**Timestamp:** ${data.timestamp}`);
  lines.push(`**Job Name:** ${data.job_name}`);
  lines.push(`**Instance ID:** ${data.instance_id}`);
  lines.push("");

  lines.push("## DataArts Instance Status");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| Instance Status | ${data.dataarts_instance_status} |`);
  if (data.dataarts_raw_status) {
    lines.push(`| Raw Status | ${data.dataarts_raw_status} |`);
  }
  if (data.dataarts_instance_note) {
    lines.push(`| Note | ${data.dataarts_instance_note} |`);
  }
  lines.push("");

  if (data.node_execution_summary && data.node_execution_summary.length > 0) {
    lines.push("### Node Execution Summary");
    lines.push("");
    lines.push("| Node | Status | Detail |");
    lines.push("|------|--------|--------|");
    for (const node of data.node_execution_summary) {
      lines.push(`| ${node.name || "-"} | ${node.status || "-"} | ${node.detail || "-"} |`);
    }
    lines.push("");
  }

  lines.push("## DLI Validation Queries");
  lines.push("");

  if (data.dli_validation_skipped) {
    lines.push("> DLI validation was skipped because the DataArts instance did not succeed.");
    lines.push("> Use `--allow-dli-check-on-failure` to run DLI checks regardless.");
    lines.push("");
  } else {
    lines.push("| # | Query Name | SQL (truncated) | HTTP | DLI Status | Success |");
    lines.push("|---|------------|-----------------|------|------------|---------|");
    for (let i = 0; i < data.dli_query_results.length; i++) {
      const q = data.dli_query_results[i];
      const sqlShort = q.sql.length > 50 ? q.sql.slice(0, 47) + "..." : q.sql;
      lines.push(`| ${i + 1} | ${q.name} | \`${sqlShort}\` | ${q.http_status || "N/A"} | ${q.dli_status || "N/A"} | ${q.success ? "OK" : "FAIL"} |`);
    }
    lines.push("");

    lines.push("### Query Results");
    lines.push("");
    for (const q of data.dli_query_results) {
      lines.push(`**${q.name}:**`);
      lines.push("");
      if (q.rows && q.rows.length > 0) {
        const cols = Object.keys(q.rows[0]);
        lines.push("| " + cols.join(" | ") + " |");
        lines.push("| " + cols.map(() => "---").join(" | ") + " |");
        for (const row of q.rows) {
          lines.push("| " + cols.map((c) => row[c] !== undefined && row[c] !== null ? row[c] : "NULL").join(" | ") + " |");
        }
      } else {
        lines.push("(no rows)");
      }
      lines.push("");
    }
  }

  lines.push("## Validation Checks (Expected vs Actual)");
  lines.push("");
  lines.push("| Check | Result | Actual | Expected |");
  lines.push("|-------|--------|--------|----------|");
  for (const c of data.checks) {
    const actual = typeof c.actual === "object" ? JSON.stringify(c.actual) : String(c.actual);
    const expected = c.expected !== undefined ? (typeof c.expected === "object" ? JSON.stringify(c.expected) : String(c.expected)) : "-";
    lines.push(`| ${c.check} | ${c.result} | ${actual} | ${expected} |`);
  }
  lines.push("");

  lines.push("## Table Counts");
  lines.push("");
  lines.push("| Table | Expected Count | Actual Count | Result |");
  lines.push("|-------|----------------|--------------|--------|");
  for (const tc of data.table_counts) {
    lines.push(`| ${tc.table} | ${tc.expected} | ${tc.actual} | ${tc.result} |`);
  }
  lines.push("");

  if (data.gold_aggregates && data.gold_aggregates.length > 0) {
    lines.push("## Gold Aggregates");
    lines.push("");
    lines.push("| Date | Expected order_count | Actual order_count | Expected total_amount | Actual total_amount | Result |");
    lines.push("|------|---------------------|-------------------|----------------------|--------------------|--------|");
    for (const ga of data.gold_aggregates) {
      lines.push(`| ${ga.date} | ${ga.expected_order_count} | ${ga.actual_order_count} | ${ga.expected_total_amount} | ${ga.actual_total_amount} | ${ga.result} |`);
    }
    lines.push("");
  }

  const passCount = data.pass_count;
  const warnCount = data.warn_count;
  const failCount = data.fail_count;

  lines.push("## Summary");
  lines.push("");
  lines.push(`- **PASS:** ${passCount}`);
  lines.push(`- **WARN:** ${warnCount}`);
  lines.push(`- **FAIL:** ${failCount}`);
  lines.push(`- **Overall Status:** ${data.overall_status}`);
  lines.push("");

  lines.push("### Equivalence Conclusion");
  lines.push("");
  if (data.equivalence_result === "EQUIVALENT") {
    lines.push("> **The DataArts runtime result is functionally equivalent to the Snowflake result.**");
  } else if (data.equivalence_result === "NOT_EQUIVALENT") {
    lines.push("> **The DataArts runtime result is NOT functionally equivalent to the Snowflake result.**");
  } else {
    lines.push(`> **Equivalence: ${data.equivalence_result}**`);
  }
  lines.push("");

  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **No publish, scheduled start, update, delete, or additional run-immediate operation was executed.**");
  lines.push(">");
  lines.push("> Only DataArts read-only APIs and DLI SELECT statements were used.");
  lines.push("> - `GET /v1/{project_id}/jobs/{job_name}/instances/{instance_id}` (read-only)");
  lines.push("> - `GET /v1/{project_id}/jobs/instances/detail` (read-only fallback)");
  lines.push("> - `POST /v1.0/{project_id}/jobs/submit-job` (DLI SELECT only, validated before submission)");
  lines.push(">");
  lines.push("> No INSERT, UPDATE, DELETE, DROP, CREATE, MERGE, ALTER, or TRUNCATE was executed.");
  lines.push("> No `/run-immediate`, `/start`, `/publish`, PUT, PATCH, or DELETE endpoint was called.");
  lines.push("");

  return lines.join("\n");
}

async function main() {
  console.log("=== DataArts Deploy Agent: RUNTIME VALIDATE ===\n");

  const args = process.argv.slice(2);
  const allowDliOnFailure = args.includes("--allow-dli-check-on-failure");

  try {
    const env = config.load();
    config.validate(env);

    if (!fs.existsSync(RUN_IMMEDIATE_RESULT)) {
      throw new Error(`Missing: ${RUN_IMMEDIATE_RESULT}\nRun "npm run run-immediate-job -- --confirm" first.`);
    }
    if (!fs.existsSync(V1_DRYRUN_REQUEST)) {
      throw new Error(`Missing: ${V1_DRYRUN_REQUEST}\nRun "npm run dry-run" first.`);
    }

    const runImmediateResult = JSON.parse(fs.readFileSync(RUN_IMMEDIATE_RESULT, "utf-8"));
    const v1Dryrun = JSON.parse(fs.readFileSync(V1_DRYRUN_REQUEST, "utf-8"));

    const jobName = runImmediateResult.job_name;
    const executionIdField = runImmediateResult.execution_id;

    if (!jobName) {
      throw new Error("Could not extract job_name from run_immediate_job_result.json");
    }

    let instanceId = null;
    if (executionIdField) {
      const match = executionIdField.match(/=(\d+)$/);
      if (match) {
        instanceId = match[1];
      } else {
        instanceId = executionIdField;
      }
    }

    if (!instanceId) {
      throw new Error("Could not extract instance_id from run_immediate_job_result.json");
    }

    const projectId = env.HUAWEI_PROJECT_ID;
    const workspaceId = env.DATAARTS_WORKSPACE_ID;
    const ak = env.HUAWEI_AK;
    const sk = env.HUAWEI_SK;
    const queueName = (env.DLI_QUEUE_NAME || "").trim();

    if (!queueName || queueName === "AUTO_DISCOVER") {
      throw new Error("Set DLI_QUEUE_NAME (e.g. default) before running runtime validation.");
    }

    const dataartsEndpoint = `https://dayu-dlf.${env.HUAWEI_REGION}.myhuaweicloud.com`;
    const dliEndpoint = `https://dli.${env.HUAWEI_REGION}.myhuaweicloud.com`;

    console.log(`DataArts Endpoint:  ${dataartsEndpoint}`);
    console.log(`DLI Endpoint:       ${dliEndpoint}`);
    console.log(`Project:            ${maskId(projectId)}`);
    console.log(`Workspace:          ${maskId(workspaceId)}`);
    console.log(`Job name:           ${jobName}`);
    console.log(`Instance ID:        ${instanceId}`);
    console.log(`DLI Queue:          ${queueName}`);
    console.log("");

    console.log("[1/3] Checking DataArts job instance status...\n");

    let instanceInfo = await fetchDataArtsInstanceStatus(dataartsEndpoint, projectId, jobName, instanceId, workspaceId, ak, sk);

    let extractedInfo;
    if (instanceInfo.success) {
      extractedInfo = extractInstanceInfo(instanceInfo.data, instanceId, "direct");
      if (extractedInfo.status === "running") {
        console.log("  Instance is still running. Polling...\n");
        extractedInfo = await pollDataArtsInstance(dataartsEndpoint, projectId, jobName, instanceId, workspaceId, ak, sk);
      }
    } else {
      console.log("  Direct endpoint did not return useful status. Trying fallback...\n");
      const fallback = await fetchDataArtsInstanceFallback(dataartsEndpoint, projectId, jobName, instanceId, workspaceId, ak, sk);
      if (fallback.success) {
        extractedInfo = extractInstanceInfo(fallback.data, instanceId, "fallback");
        if (extractedInfo.status === "running") {
          console.log("  Instance is still running (fallback). Polling...\n");
          extractedInfo = await pollDataArtsInstance(dataartsEndpoint, projectId, jobName, instanceId, workspaceId, ak, sk);
        }
      } else {
        throw new Error(`Could not retrieve instance status from either direct or fallback endpoint.`);
      }
    }

    const dataartsStatus = extractedInfo.status;
    const dataartsRawStatus = extractedInfo.rawStatus;
    const nodeExecSummary = (extractedInfo.nodes || []).map((n) => ({
      name: n.name || n.nodeName || "-",
      status: n.status || n.State || "-",
      detail: n.message || n.errorMsg || "-",
    }));

    console.log(`  DataArts instance status: ${dataartsStatus} (raw: ${dataartsRawStatus || "N/A"})`);
    if (nodeExecSummary.length > 0) {
      console.log("  Node execution:");
      for (const n of nodeExecSummary) {
        console.log(`    ${n.name}: ${n.status} — ${n.detail}`);
      }
    }
    console.log("");

    const isFailedStatus = ["failed", "canceled", "timeout"].includes(dataartsStatus);

    if (isFailedStatus && !allowDliOnFailure) {
      console.log("  DataArts instance did not succeed. Skipping DLI validation.");
      console.log("  Use --allow-dli-check-on-failure to run DLI checks anyway.\n");
    }

    let dliQueryResults = [];
    let dliChecks = [];
    let dliValidationStatus = "SKIPPED";
    let dliValidationSkipped = false;

    if (!isFailedStatus || allowDliOnFailure) {
      console.log("[2/3] Running DLI SELECT validation queries...\n");

      console.log("  Safety check: verifying all SQL is SELECT-only...\n");
      for (const q of DLI_VALIDATION_QUERIES) {
        assertSelectOnly(q.sql);
        console.log(`  [OK] ${q.name}: starts with SELECT`);
      }
      console.log("");

      for (let i = 0; i < DLI_VALIDATION_QUERIES.length; i++) {
        const q = DLI_VALIDATION_QUERIES[i];
        console.log(`  [${i + 1}/${DLI_VALIDATION_QUERIES.length}] ${q.name}`);

        let result;
        try {
          result = await runDliQuery(dliEndpoint, projectId, queueName, q, ak, sk);
        } catch (err) {
          result = { success: false, httpStatus: null, dliStatus: null, rows: [], error: err.message };
        }

        dliQueryResults.push({
          name: q.name,
          sql: q.sql,
          http_status: result.httpStatus,
          dli_status: result.dliStatus,
          success: result.success,
          error: result.error,
          rows: result.rows,
        });

        if (result.success) {
          console.log(`    OK — rows: ${result.rows.length}`);
          if (result.rows.length > 0) {
            console.log(`    Sample: ${JSON.stringify(result.rows[0])}`);
          }
        } else {
          console.log(`    FAIL: ${result.error}`);
        }
        console.log("");
      }

      console.log("  Validating DLI results against expected values...\n");
      dliChecks = validateDliResults(dliQueryResults);

      for (const c of dliChecks) {
        const icon = c.result === "PASS" ? "OK" : "FAIL";
        console.log(`  [${icon}] ${c.check}: ${c.result} (actual: ${JSON.stringify(c.actual)})`);
      }
      console.log("");

      const allQueriesOk = dliQueryResults.every((q) => q.success);
      const allChecksPass = dliChecks.every((c) => c.result === "PASS");
      const anyCheckFail = dliChecks.some((c) => c.result === "FAIL");

      if (!allQueriesOk) dliValidationStatus = "FAIL";
      else if (allChecksPass) dliValidationStatus = "PASS";
      else if (anyCheckFail) dliValidationStatus = "FAIL";
      else dliValidationStatus = "WARN";
    } else {
      dliValidationSkipped = true;
      dliChecks = [];
    }

    console.log("[3/3] Generating reports...\n");

    const allChecks = [
      { check: `DataArts instance status = success`, result: dataartsStatus === "success" ? "PASS" : "FAIL", actual: dataartsStatus, expected: "success" },
      ...dliChecks,
    ];

    const passCount = allChecks.filter((c) => c.result === "PASS").length;
    const warnCount = allChecks.filter((c) => c.result === "WARN").length;
    const failCount = allChecks.filter((c) => c.result === "FAIL").length;

    const overallStatus = failCount > 0 ? "FAIL" : (warnCount > 0 ? "WARN" : "PASS");

    const tableCounts = [];
    const rawQ = dliQueryResults.find((q) => q.name === "raw_orders_count");
    tableCounts.push({
      table: "demo_migration.raw_orders",
      expected: 5,
      actual: rawQ && rawQ.rows && rawQ.rows.length > 0 ? Number(rawQ.rows[0].raw_orders_count) : "N/A",
      result: rawQ && rawQ.rows && rawQ.rows.length > 0 && Number(rawQ.rows[0].raw_orders_count) === 5 ? "PASS" : "FAIL",
    });
    const silverQ = dliQueryResults.find((q) => q.name === "silver_orders_count");
    tableCounts.push({
      table: "demo_migration.silver_orders",
      expected: 5,
      actual: silverQ && silverQ.rows && silverQ.rows.length > 0 ? Number(silverQ.rows[0].silver_orders_count) : "N/A",
      result: silverQ && silverQ.rows && silverQ.rows.length > 0 && Number(silverQ.rows[0].silver_orders_count) === 5 ? "PASS" : "FAIL",
    });
    const goldQ = dliQueryResults.find((q) => q.name === "gold_daily_sales_count");
    tableCounts.push({
      table: "demo_migration.gold_daily_sales",
      expected: 2,
      actual: goldQ && goldQ.rows && goldQ.rows.length > 0 ? Number(goldQ.rows[0].gold_daily_sales_count) : "N/A",
      result: goldQ && goldQ.rows && goldQ.rows.length > 0 && Number(goldQ.rows[0].gold_daily_sales_count) === 2 ? "PASS" : "FAIL",
    });
    const auditQ = dliQueryResults.find((q) => q.name === "task_audit_success_count");
    tableCounts.push({
      table: "demo_migration.task_audit (SUCCESS)",
      expected: ">=1",
      actual: auditQ && auditQ.rows && auditQ.rows.length > 0 ? Number(auditQ.rows[0].task_audit_success_count) : "N/A",
      result: auditQ && auditQ.rows && auditQ.rows.length > 0 && Number(auditQ.rows[0].task_audit_success_count) >= 1 ? "PASS" : "FAIL",
    });

    const goldAggregates = [];
    const detailQ = dliQueryResults.find((q) => q.name === "gold_daily_sales_detail");
    if (detailQ && detailQ.rows) {
      const r20 = detailQ.rows.find((r) => String(r.order_date).startsWith("2026-06-20"));
      if (r20) {
        const oc = Number(r20.order_count);
        const ta = Number(r20.total_amount);
        goldAggregates.push({
          date: "2026-06-20",
          expected_order_count: 2,
          actual_order_count: oc,
          expected_total_amount: 420.5,
          actual_total_amount: ta,
          result: oc === 2 && Math.abs(ta - 420.5) < 0.01 ? "PASS" : "FAIL",
        });
      }
      const r21 = detailQ.rows.find((r) => String(r.order_date).startsWith("2026-06-21"));
      if (r21) {
        const oc = Number(r21.order_count);
        const ta = Number(r21.total_amount);
        goldAggregates.push({
          date: "2026-06-21",
          expected_order_count: 3,
          actual_order_count: oc,
          expected_total_amount: 630.34,
          actual_total_amount: ta,
          result: oc === 3 && Math.abs(ta - 630.34) < 0.01 ? "PASS" : "FAIL",
        });
      }
    }

    let equivalenceResult;
    if (overallStatus === "PASS") {
      equivalenceResult = "EQUIVALENT";
    } else if (overallStatus === "FAIL") {
      equivalenceResult = "NOT_EQUIVALENT";
    } else {
      equivalenceResult = "INCONCLUSIVE";
    }

    const timestamp = new Date().toISOString();

    const reportData = {
      timestamp,
      job_name: jobName,
      instance_id: instanceId,
      dataarts_instance_status: dataartsStatus,
      dataarts_raw_status: dataartsRawStatus,
      dataarts_instance_note: extractedInfo.note || null,
      node_execution_summary: nodeExecSummary,
      dli_validation_skipped: dliValidationSkipped,
      dli_query_results: dliQueryResults.map((q) => ({
        name: q.name,
        sql: q.sql,
        http_status: q.http_status,
        dli_status: q.dli_status,
        success: q.success,
        error: q.error,
        rows: q.rows,
      })),
      checks: allChecks,
      table_counts: tableCounts,
      gold_aggregates: goldAggregates,
      pass_count: passCount,
      warn_count: warnCount,
      fail_count: failCount,
      overall_status: overallStatus,
      equivalence_result: equivalenceResult,
    };

    const mdReport = generateMarkdownReport(reportData);

    const jsonReport = {
      status: overallStatus,
      job_name: jobName,
      instance_id: instanceId,
      dataarts_instance_status: dataartsStatus,
      dataarts_raw_status: dataartsRawStatus,
      node_execution_summary: nodeExecSummary,
      dli_validation_status: dliValidationStatus,
      dli_query_results: dliQueryResults.map((q) => ({
        name: q.name,
        sql: q.sql,
        http_status: q.http_status,
        dli_status: q.dli_status,
        success: q.success,
        error: q.error,
        rows: q.rows,
      })),
      table_counts: tableCounts,
      gold_aggregates: goldAggregates,
      equivalence_result: equivalenceResult,
      pass_count: passCount,
      warn_count: warnCount,
      fail_count: failCount,
      checks: allChecks,
      safety: {
        no_publish: true,
        no_scheduled_start: true,
        no_update: true,
        no_delete: true,
        no_run_immediate: true,
        no_start: true,
        only_readonly_dataarts_apis: true,
        only_dli_select_statements: true,
        all_sql_validated_as_select: true,
        no_insert: true,
        no_update_sql: true,
        no_delete_sql: true,
        no_drop: true,
        no_create: true,
        no_merge: true,
        no_alter: true,
        no_truncate: true,
      },
      timestamp,
      no_secrets_included: true,
    };

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const mdPath = path.join(OUT_DIR, "runtime_validate_report.md");
    const jsonPath = path.join(OUT_DIR, "runtime_validate_result.json");

    fs.writeFileSync(mdPath, mdReport, "utf-8");
    fs.writeFileSync(jsonPath, JSON.stringify(jsonReport, null, 2), "utf-8");

    console.log("=== Runtime Validation Summary ===\n");
    console.log(`  Job Name:              ${jobName}`);
    console.log(`  Instance ID:           ${instanceId}`);
    console.log(`  DataArts Status:       ${dataartsStatus}`);
    console.log(`  DLI Validation:        ${dliValidationStatus}`);
    console.log(`  Overall:               ${overallStatus}`);
    console.log(`  Equivalence:           ${equivalenceResult}`);
    console.log(`  PASS:                  ${passCount}`);
    console.log(`  WARN:                  ${warnCount}`);
    console.log(`  FAIL:                  ${failCount}`);
    console.log("");
    console.log("Safety: No publish, scheduled start, update, delete, or additional run-immediate operation was executed.");
    console.log("Only DataArts read-only APIs and DLI SELECT statements were used.");
    console.log("");
    console.log("Reports saved:");
    console.log(`  ${mdPath}`);
    console.log(`  ${jsonPath}`);

    process.exit(overallStatus === "FAIL" ? 1 : 0);
  } catch (err) {
    console.error(`RUNTIME VALIDATE FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
