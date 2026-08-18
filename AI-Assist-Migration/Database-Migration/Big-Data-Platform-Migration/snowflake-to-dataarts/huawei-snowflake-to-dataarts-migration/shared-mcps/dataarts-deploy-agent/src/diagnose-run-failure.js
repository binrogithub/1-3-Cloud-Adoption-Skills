const fs = require("fs");
const path = require("path");
const https = require("https");
const config = require("./config");
const { buildSignedHeaders } = require("./huawei-signer");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

const FILES = {
  runImmediateResult: path.join(OUT_DIR, "run_immediate_job_result.json"),
  runtimeValidateResult: path.join(OUT_DIR, "runtime_validate_result.json"),
  runtimeValidateReport: path.join(OUT_DIR, "runtime_validate_report.md"),
  exportJobResult: path.join(OUT_DIR, "exported_job/export_job_definition_result.json"),
  v1DryrunRequest: path.join(OUT_DIR, "dataarts_create_job_request.v1.dryrun.json"),
  dliValidateResult: path.join(OUT_DIR, "dli_validate_demo_data_result.json"),
};

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

function assertSelectOnly(sql) {
  const trimmed = sql.trim().toUpperCase();
  if (!trimmed.startsWith("SELECT") && !trimmed.startsWith("SHOW")) {
    throw new Error(`SAFETY VIOLATION: SQL is not SELECT/SHOW: ${sql.trim().slice(0, 80)}`);
  }
}

function readJsonFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return null;
  }
}

function readTextFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return null;
  }
  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
}

async function fetchDataArtsInstanceDetail(endpoint, projectId, jobName, instanceId, workspaceId, ak, sk) {
  const url = `${endpoint}/v1/${projectId}/jobs/${encodeURIComponent(jobName)}/instances/${instanceId}`;
  console.log(`  GET /v1/${maskId(projectId)}/jobs/${jobName}/instances/${instanceId}`);
  const res = await signedGet(url, ak, sk, { workspace: workspaceId });
  console.log(`  HTTP ${res.statusCode}`);
  if (res.statusCode >= 200 && res.statusCode < 300) {
    try {
      return { success: true, data: JSON.parse(res.body), statusCode: res.statusCode };
    } catch {
      return { success: false, error: "Failed to parse response body", statusCode: res.statusCode };
    }
  }
  return { success: false, statusCode: res.statusCode, error: `HTTP ${res.statusCode}` };
}

async function fetchDataArtsInstanceFallback(endpoint, projectId, jobName, workspaceId, ak, sk) {
  const url = `${endpoint}/v1/${projectId}/jobs/instances/detail?jobName=${encodeURIComponent(jobName)}`;
  console.log(`  GET (fallback) /v1/${maskId(projectId)}/jobs/instances/detail?jobName=${jobName}`);
  const res = await signedGet(url, ak, sk, { workspace: workspaceId });
  console.log(`  HTTP ${res.statusCode}`);
  if (res.statusCode >= 200 && res.statusCode < 300) {
    try {
      return { success: true, data: JSON.parse(res.body), statusCode: res.statusCode };
    } catch {
      return { success: false, error: "Failed to parse fallback response body", statusCode: res.statusCode };
    }
  }
  return { success: false, statusCode: res.statusCode, error: `HTTP ${res.statusCode}` };
}

function extractNodeDetails(instanceData) {
  const nodes = instanceData.nodes || instanceData.taskDetails || instanceData.task_details || [];
  return nodes.map((n) => ({
    name: n.name || n.nodeName || n.node_name || "-",
    status: n.status || n.State || n.node_status || "-",
    errorCode: n.errorCode || n.error_code || n.errCode || null,
    errorMessage: n.errorMessage || n.error_msg || n.message || n.detail || null,
    startTime: n.startTime || n.start_time || n.executeStartTime || null,
    endTime: n.endTime || n.end_time || n.executeEndTime || null,
    logs: n.logs || n.log || n.logPath || null,
  }));
}

async function runDliSelectQuery(dliEndpoint, projectId, queueName, sql, currentdb, ak, sk) {
  const submitUrl = `${dliEndpoint}/v1.0/${projectId}/jobs/submit-job`;
  const requestBody = {
    queue_name: queueName,
    sql,
    currentdb,
  };
  const res = await signedPost(submitUrl, ak, sk, requestBody);
  if (res.statusCode >= 200 && res.statusCode < 300) {
    const body = JSON.parse(res.body);
    const jobId = body.job_id;
    if (jobId) {
      const pollResult = await pollDliJob(dliEndpoint, projectId, jobId, ak, sk);
      if (pollResult.status === "FINISHED") {
        const detail = await fetchDliJobDetail(dliEndpoint, projectId, jobId, ak, sk);
        const rows = extractDliRows(detail);
        return { success: true, status: pollResult.status, rows, error: null };
      }
      return { success: false, status: pollResult.status, rows: [], error: `DLI job ${pollResult.status}` };
    }
    if (body.error_code || body.error_msg) {
      return { success: false, status: null, rows: [], error: `${body.error_code || ""}: ${body.error_msg || ""}`.trim() };
    }
    return { success: false, status: null, rows: [], error: "No job_id returned" };
  }
  let errorMsg = `HTTP ${res.statusCode}`;
  try {
    const body = JSON.parse(res.body);
    if (body.error_code || body.error_msg) {
      errorMsg += ` — ${body.error_code || ""}: ${body.error_msg || ""}`.trim();
    }
  } catch {}
  return { success: false, status: null, rows: [], error: errorMsg };
}

async function pollDliJob(dliEndpoint, projectId, jobId, ak, sk) {
  const url = `${dliEndpoint}/v1.0/${projectId}/jobs?job_id=${jobId}&limit=1`;
  const start = Date.now();
  while (Date.now() - start < 120000) {
    try {
      const res = await signedGet(url, ak, sk);
      if (res.statusCode >= 200 && res.statusCode < 300) {
        const body = JSON.parse(res.body);
        const jobs = body.jobs || [];
        const job = jobs.find((j) => j.job_id === jobId);
        if (job) {
          const status = (job.status || "").toUpperCase();
          if (["FINISHED", "SUCCESS"].includes(status)) return { status: "FINISHED" };
          if (["FAILED", "ERROR"].includes(status)) return { status: "FAILED" };
          if (status === "CANCELLED") return { status: "CANCELLED" };
        }
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 5000));
  }
  return { status: "TIMEOUT" };
}

async function fetchDliJobDetail(dliEndpoint, projectId, jobId, ak, sk) {
  const url = `${dliEndpoint}/v1.0/${projectId}/jobs/${jobId}`;
  const res = await signedGet(url, ak, sk);
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw new Error(`DLI job detail fetch failed: HTTP ${res.statusCode}`);
  }
  return JSON.parse(res.body);
}

function extractDliRows(detail) {
  const rows = detail.rows || [];
  const schema = detail.schema || [];
  const columns = schema.map((s) => {
    if (typeof s === "object" && s !== null) return Object.keys(s)[0] || "?";
    return String(s);
  });
  if (!Array.isArray(rows) || rows.length === 0) return [];
  return rows.map((row) => {
    if (Array.isArray(row)) {
      const obj = {};
      columns.forEach((col, i) => { obj[col] = row[i]; });
      return obj;
    }
    return row;
  });
}

function classifyRootCause(nodeDetails, failedNode, v1Dryrun, exportResult) {
  const failedNodeDetail = nodeDetails.find((n) => n.name === failedNode);
  const errorMsg = (failedNodeDetail && failedNodeDetail.errorMessage) || "";
  const errorCode = (failedNodeDetail && failedNodeDetail.errorCode) || "";

  let nodeSql = null;
  if (v1Dryrun && v1Dryrun.body && v1Dryrun.body.nodes) {
    const nodeDef = v1Dryrun.body.nodes.find((n) => n.name === failedNode);
    if (nodeDef && nodeDef.properties) {
      const sqlProp = nodeDef.properties.find((p) => p.name === "sql");
      if (sqlProp) nodeSql = sqlProp.value;
    }
  }

  const sqlHasDdl = nodeSql && /(?:DROP|CREATE|ALTER|TRUNCATE)\s/i.test(nodeSql);
  const sqlHasDml = nodeSql && /(?:INSERT|UPDATE|DELETE|MERGE)\s/i.test(nodeSql);
  const sqlHasMultiStatement = nodeSql && /;\s*\n/i.test(nodeSql);

  const scriptRefMissing = exportResult && exportResult.sql_snippets_found === false;

  if (errorMsg || errorCode) {
    const msg = (errorMsg + " " + errorCode).toUpperCase();
    if (msg.includes("QUEUE") || msg.includes("RESOURCE") || msg.includes("POOL") || msg.includes("INSUFFICIENT")) {
      return { classification: "B", description: "DLI queue/resource binding issue", evidence: `Error: ${errorMsg || errorCode}` };
    }
    if (msg.includes("SCRIPT") || msg.includes("SNIPPET") || msg.includes("REFERENCE") || msg.includes("NOT FOUND") || msg.includes("MATERIALIZ")) {
      return { classification: "C", description: "DataArts script reference/materialization issue", evidence: `Error: ${errorMsg || errorCode}` };
    }
    if (msg.includes("PUBLISH") || msg.includes("LIFECYCLE") || msg.includes("DEPLOY")) {
      return { classification: "D", description: "Missing publish/lifecycle step", evidence: `Error: ${errorMsg || errorCode}` };
    }
    if (msg.includes("SYNTAX") || msg.includes("PARSE") || msg.includes("INVALID") || msg.includes("UNSUPPORTED")) {
      return { classification: "A", description: "SQL syntax/runtime issue", evidence: `Error: ${errorMsg || errorCode}` };
    }
  }

  if (sqlHasDdl && sqlHasMultiStatement) {
    return {
      classification: "A",
      description: "SQL syntax/runtime issue: multi-statement DDL+DML in single node",
      evidence: `Node '${failedNode}' SQL contains DDL (DROP/CREATE) with multiple statements separated by semicolons. DataArts DLI SQL nodes may not support multi-statement execution. SQL preview: ${(nodeSql || "").slice(0, 120)}...`,
    };
  }

  if (scriptRefMissing && sqlHasDdl) {
    return {
      classification: "C",
      description: "DataArts script reference/materialization issue: DDL SQL not materialized as script",
      evidence: `Export shows sql_snippets_found=false. Node '${failedNode}' contains DDL SQL that may require script materialization in DataArts Factory.`,
    };
  }

  if (sqlHasDdl) {
    return {
      classification: "A",
      description: "SQL syntax/runtime issue: DDL in DLI SQL node",
      evidence: `Node '${failedNode}' SQL contains DDL statements (DROP/CREATE). DataArts DLI SQL nodes may require scripts instead of inline DDL.`,
    };
  }

  if (scriptRefMissing) {
    return {
      classification: "C",
      description: "DataArts script reference/materialization issue",
      evidence: "Export shows sql_snippets_found=false. Script references may be broken or not materialized.",
    };
  }

  return { classification: "E", description: "Unknown", evidence: "No specific root cause indicator found from available data." };
}

function recommendFix(rootCause, failedNode, v1Dryrun) {
  switch (rootCause.classification) {
    case "A":
      return `Refactor node '${failedNode}': extract DDL/DML into a DataArts DLI SQL script (.sql file) and reference it by script path instead of inline SQL. DataArts DLI SQL nodes with inline multi-statement DDL (DROP+CREATE) often fail at runtime. Consider using a script resource or breaking into separate nodes.`;
    case "B":
      return `Check DLI queue binding for node '${failedNode}'. Ensure the queue exists, is running, and the job is configured to use the correct queue. Verify DLI queue permissions and resource allocation.`;
    case "C":
      return `Fix script references for node '${failedNode}'. Ensure all SQL scripts are properly created/uploaded in DataArts Factory before running the job. The job export shows sql_snippets_found=false, indicating scripts may not be materialized. Re-create the job with proper script references or use adapt-sql-for-demo-runtime to generate compatible scripts.`;
    case "D":
      return `Publish the job before running. The job may need to be published (deployed to production) in DataArts Factory before run-immediate can execute it successfully. Run the publish step first.`;
    default:
      return `Investigate the failure of node '${failedNode}' manually. Check DataArts Factory console for detailed logs, verify DLI database/table existence, and ensure all prerequisites are met.`;
  }
}

function generateMarkdownReport(data) {
  const lines = [];
  lines.push("# Diagnose Run Failure Report");
  lines.push("");
  lines.push(`**Timestamp:** ${data.timestamp}`);
  lines.push(`**Job Name:** ${data.job_name}`);
  lines.push(`**Instance ID:** ${data.instance_id}`);
  lines.push("");

  lines.push("## Failed Node");
  lines.push("");
  lines.push(`**Node:** ${data.failed_node}`);
  lines.push(`**Status:** ${data.failed_node_status}`);
  if (data.error_code) {
    lines.push(`**Error Code:** ${data.error_code}`);
  }
  if (data.error_message) {
    lines.push(`**Error Message:** ${data.error_message}`);
  }
  lines.push("");

  lines.push("## DataArts Instance Status");
  lines.push("");
  lines.push(`**Status:** ${data.dataarts_instance_status}`);
  if (data.dataarts_raw_status) {
    lines.push(`**Raw Status:** ${data.dataarts_raw_status}`);
  }
  lines.push("");

  if (data.node_statuses && data.node_statuses.length > 0) {
    lines.push("### Node-Level Status Table");
    lines.push("");
    lines.push("| Node | Status | Error Code | Error Message | Start Time | End Time |");
    lines.push("|------|--------|------------|--------------|------------|----------|");
    for (const n of data.node_statuses) {
      lines.push(`| ${n.name} | ${n.status} | ${n.errorCode || "-"} | ${(n.errorMessage || "-").slice(0, 80)} | ${n.startTime || "-"} | ${n.endTime || "-"} |`);
    }
    lines.push("");
  }

  if (data.dataarts_instance_detail_source) {
    lines.push(`**Detail Source:** ${data.dataarts_instance_detail_source}`);
    lines.push("");
  }

  if (data.raw_error_message) {
    lines.push("## Raw Error Message from DataArts");
    lines.push("");
    lines.push("```");
    lines.push(data.raw_error_message);
    lines.push("```");
    lines.push("");
  }

  lines.push("## Exported Job/Script Reference Summary");
  lines.push("");
  if (data.export_summary) {
    lines.push(`- **Export Successful:** ${data.export_summary.export_successful}`);
    lines.push(`- **All Nodes Found:** ${data.export_summary.all_nodes_found}`);
    lines.push(`- **SQL Snippets Found:** ${data.export_summary.sql_snippets_found}`);
    if (data.export_summary.node_names_in_export) {
      lines.push("- **Nodes in Export:**");
      for (const [name, found] of Object.entries(data.export_summary.node_names_in_export)) {
        lines.push(`  - ${name}: ${found ? "found" : "missing"}`);
      }
    }
    if (data.export_summary.sql_snippet_details) {
      lines.push("- **SQL Snippet Details:**");
      for (const d of data.export_summary.sql_snippet_details) {
        lines.push(`  - ${d.file}: length=${d.length}, hasSelect=${d.hasSelect}, hasInsert=${d.hasInsert}`);
      }
    }
  } else {
    lines.push("(no export data available)");
  }
  lines.push("");

  lines.push("## DLI Data State Summary");
  lines.push("");
  if (data.dli_data_state) {
    lines.push(`- **raw_orders_count:** ${data.dli_data_state.raw_orders_count}`);
    lines.push(`- **silver_orders_exists:** ${data.dli_data_state.silver_orders_exists}`);
    lines.push(`- **gold_daily_sales_exists:** ${data.dli_data_state.gold_daily_sales_exists}`);
    if (data.dli_data_state.tables_in_demo_migration) {
      lines.push("- **Tables in demo_migration:**");
      for (const t of data.dli_data_state.tables_in_demo_migration) {
        lines.push(`  - ${t}`);
      }
    }
    if (data.dli_data_state.show_tables_error) {
      lines.push(`- **SHOW TABLES Error:** ${data.dli_data_state.show_tables_error} (WARN, not FAIL)`);
    }
  } else {
    lines.push("(DLI checks not performed)");
  }
  lines.push("");

  lines.push("## Root Cause Classification");
  lines.push("");
  lines.push(`**Classification:** ${data.likely_root_cause.classification}`);
  lines.push(`**Description:** ${data.likely_root_cause.description}`);
  lines.push(`**Evidence:** ${data.likely_root_cause.evidence}`);
  lines.push("");

  lines.push("## Recommended Fix");
  lines.push("");
  lines.push(data.recommended_fix);
  lines.push("");

  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **No publish, start, run-immediate, update, delete, or non-SELECT DLI SQL was executed.**");
  lines.push(">");
  lines.push("> Only DataArts read-only GET APIs and DLI SELECT/SHOW statements were used.");
  lines.push("> No INSERT, UPDATE, DELETE, DROP, CREATE, MERGE, ALTER, or TRUNCATE was executed.");
  lines.push("> No `/run-immediate`, `/start`, `/publish`, PUT, PATCH, or DELETE endpoint was called.");
  lines.push("");

  return lines.join("\n");
}

async function main() {
  console.log("=== DataArts Deploy Agent: DIAGNOSE RUN FAILURE ===\n");

  const env = config.load();
  config.validate(env);

  const runImmediateResult = readJsonFile(FILES.runImmediateResult);
  const runtimeValidateResult = readJsonFile(FILES.runtimeValidateResult);
  const exportJobResult = readJsonFile(FILES.exportJobResult);
  const v1DryrunRequest = readJsonFile(FILES.v1DryrunRequest);
  const dliValidateResult = readJsonFile(FILES.dliValidateResult);

  if (!runImmediateResult) {
    throw new Error(`Missing: ${FILES.runImmediateResult}\nRun "npm run run-immediate-job" first.`);
  }
  if (!runtimeValidateResult) {
    throw new Error(`Missing: ${FILES.runtimeValidateResult}\nRun "npm run runtime-validate" first.`);
  }

  const jobName = runImmediateResult.job_name || runtimeValidateResult.job_name;
  let instanceId = null;
  if (runImmediateResult.execution_id) {
    const match = runImmediateResult.execution_id.match(/=(\d+)$/);
    instanceId = match ? match[1] : runImmediateResult.execution_id;
  }
  if (!instanceId && runtimeValidateResult.instance_id) {
    instanceId = String(runtimeValidateResult.instance_id);
  }
  if (!jobName || !instanceId) {
    throw new Error("Could not extract job_name or instance_id from result files.");
  }

  const failedNodeEntry = (runtimeValidateResult.node_execution_summary || []).find(
    (n) => n.status === "fail" || n.status === "FAIL" || n.status === "failed"
  );
  const failedNode = failedNodeEntry ? failedNodeEntry.name : null;
  const failedNodeStatus = failedNodeEntry ? failedNodeEntry.status : null;

  const downstreamNodes = (runtimeValidateResult.node_execution_summary || []).filter(
    (n) => n.name !== failedNode && (n.status === "manual-stop" || n.status === "MANUAL-STOP")
  );

  const existingError = runtimeValidateResult.dli_query_results
    ? runtimeValidateResult.dli_query_results
        .filter((q) => !q.success && q.error)
        .map((q) => `${q.name}: ${q.error}`)
    : [];

  console.log(`Job Name:       ${jobName}`);
  console.log(`Instance ID:    ${instanceId}`);
  console.log(`Failed Node:    ${failedNode || "(none)"}`);
  console.log(`Downstream:     ${downstreamNodes.map((n) => n.name).join(", ") || "(none)"}`);
  console.log("");

  const projectId = env.HUAWEI_PROJECT_ID;
  const workspaceId = env.DATAARTS_WORKSPACE_ID;
  const ak = env.HUAWEI_AK;
  const sk = env.HUAWEI_SK;
  const queueName = (env.DLI_QUEUE_NAME || "").trim();
  const dataartsEndpoint = `https://dayu-dlf.${env.HUAWEI_REGION}.myhuaweicloud.com`;
  const dliEndpoint = `https://dli.${env.HUAWEI_REGION}.myhuaweicloud.com`;

  console.log("[1/3] Fetching DataArts instance details (read-only)...\n");

  let nodeDetails = [];
  let instanceRawData = null;
  let instanceDetailSource = null;
  let dataartsRawStatus = null;
  let rawErrorMessage = null;
  let errorCode = null;
  let errorMessage = null;

  const directResult = await fetchDataArtsInstanceDetail(
    dataartsEndpoint, projectId, jobName, instanceId, workspaceId, ak, sk
  );

  if (directResult.success) {
    instanceRawData = directResult.data;
    instanceDetailSource = "direct";
    dataartsRawStatus = directResult.data.status || directResult.data.State || directResult.data.instanceStatus;
    nodeDetails = extractNodeDetails(directResult.data);
    console.log(`  Instance status: ${dataartsRawStatus}`);
    console.log(`  Nodes found: ${nodeDetails.length}`);
    if (nodeDetails.length > 0) {
      for (const n of nodeDetails) {
        console.log(`    ${n.name}: ${n.status}${n.errorCode ? ` (err: ${n.errorCode})` : ""}${n.errorMessage ? ` — ${n.errorMessage.slice(0, 100)}` : ""}`);
      }
    }
  } else {
    console.log(`  Direct endpoint failed: ${directResult.error}. Trying fallback...\n`);
    const fallbackResult = await fetchDataArtsInstanceFallback(
      dataartsEndpoint, projectId, jobName, workspaceId, ak, sk
    );
    if (fallbackResult.success) {
      instanceDetailSource = "fallback";
      const instances = fallbackResult.data.instances || fallbackResult.data.records || fallbackResult.data.data || [];
      const target = instances.find((inst) => {
        const id = inst.instanceId || inst.instance_id || inst.id;
        return String(id) === String(instanceId);
      });
      const instData = target || (instances.length > 0 ? instances[0] : null);
      if (instData) {
        instanceRawData = instData;
        dataartsRawStatus = instData.status || instData.State || instData.instanceStatus;
        nodeDetails = extractNodeDetails(instData);
        console.log(`  Instance status (fallback): ${dataartsRawStatus}`);
        console.log(`  Nodes found: ${nodeDetails.length}`);
      }
    } else {
      console.log(`  Fallback also failed: ${fallbackResult.error}`);
    }
  }

  if (failedNode && nodeDetails.length > 0) {
    const failedDetail = nodeDetails.find((n) => n.name === failedNode);
    if (failedDetail) {
      errorCode = failedDetail.errorCode;
      errorMessage = failedDetail.errorMessage;
      if (errorCode || errorMessage) {
        rawErrorMessage = [errorCode, errorMessage].filter(Boolean).join(" — ");
        console.log(`\n  Failed node error: ${rawErrorMessage}`);
      }
    }
  }

  if (!rawErrorMessage && existingError.length > 0) {
    rawErrorMessage = existingError.join("; ");
  }

  console.log("");

  console.log("[2/3] Running DLI SELECT-only checks...\n");

  let dliDataState = {};

  if (!queueName || queueName === "AUTO_DISCOVER") {
    console.log("  WARN: DLI_QUEUE_NAME not set. Skipping DLI checks.");
    dliDataState = { raw_orders_count: "N/A (queue not set)", silver_orders_exists: "unknown", gold_daily_sales_exists: "unknown" };
  } else {
    const rawOrdersQuery = {
      sql: "SELECT COUNT(*) AS raw_orders_count FROM demo_migration.raw_orders",
      currentdb: "demo_migration",
    };
    assertSelectOnly(rawOrdersQuery.sql);
    console.log(`  [1] raw_orders_count...`);
    let rawResult;
    try {
      rawResult = await runDliSelectQuery(dliEndpoint, projectId, queueName, rawOrdersQuery.sql, rawOrdersQuery.currentdb, ak, sk);
    } catch (err) {
      rawResult = { success: false, rows: [], error: err.message };
    }
    dliDataState.raw_orders_count = rawResult.success && rawResult.rows.length > 0 ? rawResult.rows[0].raw_orders_count : "N/A";
    console.log(`    raw_orders_count = ${dliDataState.raw_orders_count}`);

    const silverQuery = {
      sql: "SELECT COUNT(*) AS cnt FROM demo_migration.silver_orders",
      currentdb: "demo_migration",
    };
    assertSelectOnly(silverQuery.sql);
    console.log(`  [2] silver_orders existence...`);
    let silverResult;
    try {
      silverResult = await runDliSelectQuery(dliEndpoint, projectId, queueName, silverQuery.sql, silverQuery.currentdb, ak, sk);
    } catch (err) {
      silverResult = { success: false, rows: [], error: err.message };
    }
    dliDataState.silver_orders_exists = silverResult.success;
    if (!silverResult.success) {
      dliDataState.silver_orders_error = silverResult.error;
      console.log(`    silver_orders: does not exist or query failed (${silverResult.error})`);
    } else {
      console.log(`    silver_orders: exists (count = ${silverResult.rows.length > 0 ? silverResult.rows[0].cnt : 0})`);
    }

    const goldQuery = {
      sql: "SELECT COUNT(*) AS cnt FROM demo_migration.gold_daily_sales",
      currentdb: "demo_migration",
    };
    assertSelectOnly(goldQuery.sql);
    console.log(`  [3] gold_daily_sales existence...`);
    let goldResult;
    try {
      goldResult = await runDliSelectQuery(dliEndpoint, projectId, queueName, goldQuery.sql, goldQuery.currentdb, ak, sk);
    } catch (err) {
      goldResult = { success: false, rows: [], error: err.message };
    }
    dliDataState.gold_daily_sales_exists = goldResult.success;
    if (!goldResult.success) {
      dliDataState.gold_daily_sales_error = goldResult.error;
      console.log(`    gold_daily_sales: does not exist or query failed (${goldResult.error})`);
    } else {
      console.log(`    gold_daily_sales: exists (count = ${goldResult.rows.length > 0 ? goldResult.rows[0].cnt : 0})`);
    }

    const showTablesQuery = {
      sql: "SHOW TABLES IN demo_migration",
      currentdb: "demo_migration",
    };
    console.log(`  [4] SHOW TABLES IN demo_migration...`);
    try {
      assertSelectOnly(showTablesQuery.sql);
      let showResult;
      try {
        showResult = await runDliSelectQuery(dliEndpoint, projectId, queueName, showTablesQuery.sql, showTablesQuery.currentdb, ak, sk);
      } catch (err) {
        showResult = { success: false, rows: [], error: err.message };
      }
      if (showResult.success && showResult.rows.length > 0) {
        dliDataState.tables_in_demo_migration = showResult.rows.map((r) => r.table_name || r.TableName || JSON.stringify(r));
        console.log(`    Tables: ${dliDataState.tables_in_demo_migration.join(", ")}`);
      } else {
        dliDataState.show_tables_error = showResult.error || "No rows returned";
        console.log(`    WARN: SHOW TABLES not supported or failed: ${dliDataState.show_tables_error}`);
      }
    } catch (safetyErr) {
      dliDataState.show_tables_error = `Safety check: ${safetyErr.message}`;
      console.log(`    WARN: ${safetyErr.message}`);
    }
  }

  console.log("");

  console.log("[3/3] Classifying root cause and generating reports...\n");

  const rootCause = classifyRootCause(nodeDetails, failedNode, v1DryrunRequest, exportJobResult);
  const recommendedFix = recommendFix(rootCause, failedNode, v1DryrunRequest);

  console.log(`  Root Cause: [${rootCause.classification}] ${rootCause.description}`);
  console.log(`  Evidence: ${rootCause.evidence.slice(0, 200)}`);
  console.log(`  Recommended Fix: ${recommendedFix.slice(0, 200)}`);
  console.log("");

  const timestamp = new Date().toISOString();

  const nodeStatuses = nodeDetails.length > 0
    ? nodeDetails
    : (runtimeValidateResult.node_execution_summary || []).map((n) => ({
        name: n.name,
        status: n.status,
        errorCode: null,
        errorMessage: n.detail && n.detail !== "-" ? n.detail : null,
        startTime: null,
        endTime: null,
      }));

  const exportSummary = exportJobResult ? {
    export_successful: exportJobResult.export_successful,
    all_nodes_found: exportJobResult.all_nodes_found,
    sql_snippets_found: exportJobResult.sql_snippets_found,
    node_names_in_export: exportJobResult.node_names_in_export,
    sql_snippet_details: exportJobResult.sql_snippet_details,
  } : null;

  const reportData = {
    timestamp,
    job_name: jobName,
    instance_id: instanceId,
    failed_node: failedNode,
    failed_node_status: failedNodeStatus,
    dataarts_instance_status: runtimeValidateResult.dataarts_instance_status || "unknown",
    dataarts_raw_status: dataartsRawStatus || runtimeValidateResult.dataarts_raw_status,
    dataarts_instance_detail_source: instanceDetailSource,
    node_statuses: nodeStatuses,
    raw_error_message: rawErrorMessage,
    error_code: errorCode,
    error_message: errorMessage,
    export_summary: exportSummary,
    dli_data_state: dliDataState,
    likely_root_cause: rootCause,
    recommended_fix: recommendedFix,
  };

  const mdReport = generateMarkdownReport(reportData);

  const jsonResult = {
    status: "DIAGNOSED",
    job_name: jobName,
    instance_id: instanceId,
    failed_node: failedNode,
    node_statuses: nodeStatuses.map((n) => ({ name: n.name, status: n.status })),
    error_code: errorCode,
    error_message: errorMessage,
    likely_root_cause: rootCause,
    recommended_next_step: recommendedFix,
    safety: {
      no_publish: true,
      no_start: true,
      no_run_immediate: true,
      no_update: true,
      no_delete: true,
      only_readonly_dataarts_apis: true,
      only_dli_select_statements: true,
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

  const mdPath = path.join(OUT_DIR, "diagnose_run_failure_report.md");
  const jsonPath = path.join(OUT_DIR, "diagnose_run_failure_result.json");

  fs.writeFileSync(mdPath, mdReport, "utf-8");
  fs.writeFileSync(jsonPath, JSON.stringify(jsonResult, null, 2), "utf-8");

  console.log("=== Diagnose Run Failure Summary ===\n");
  console.log(`  Job Name:              ${jobName}`);
  console.log(`  Instance ID:           ${instanceId}`);
  console.log(`  Failed Node:           ${failedNode}`);
  console.log(`  Failed Node Status:    ${failedNodeStatus}`);
  console.log(`  Error Code:            ${errorCode || "(none)"}`);
  console.log(`  Error Message:         ${errorMessage || "(none)"}`);
  console.log(`  Root Cause:            [${rootCause.classification}] ${rootCause.description}`);
  console.log(`  Recommended Fix:       ${recommendedFix.slice(0, 150)}...`);
  console.log("");
  console.log("Safety: No publish, start, run-immediate, update, delete, or non-SELECT DLI SQL was executed.");
  console.log("Only DataArts read-only GET APIs and DLI SELECT/SHOW statements were used.");
  console.log("");
  console.log("Reports saved:");
  console.log(`  ${mdPath}`);
  console.log(`  ${jsonPath}`);
}

main().catch((err) => {
  console.error(`DIAGNOSE RUN FAILURE FAILED: ${err.message}`);
  process.exit(1);
});
