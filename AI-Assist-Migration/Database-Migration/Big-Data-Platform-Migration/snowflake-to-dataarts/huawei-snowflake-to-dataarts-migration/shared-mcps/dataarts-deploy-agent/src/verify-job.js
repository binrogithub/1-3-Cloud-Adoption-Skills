const fs = require("fs");
const path = require("path");
const https = require("https");
const config = require("./config");
const { buildSignedHeaders } = require("./huawei-signer");

const OUT_DIR = path.resolve(__dirname, "..", "out");
const V1_REQUEST_FILE = path.join(
  OUT_DIR,
  "dataarts_create_job_request.v1.dryrun.json"
);

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

async function signedGet(url, ak, sk, workspaceId) {
  const headers = {
    "Content-Type": "application/json",
    workspace: workspaceId,
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

function normalizeType(t) {
  if (!t) return t;
  const upper = t.toUpperCase().replace(/_/g, "");
  if (upper === "DLISQL") return "DLISQL";
  return t;
}

function cronSemanticallyMatch(a, b) {
  if (!a || !b) return false;
  if (a === b) return true;
  const strip = (s) => String(s).replace(/\s+/g, " ").trim();
  if (strip(a) === strip(b)) return true;
  const every5Patterns = [
    "*/5 * * * *",
    "0 0-59/5 * * * ?",
    "0 0/5 * * * ?",
    "0 5,10,15,20,25,30,35,40,45,50,55 * * * ?",
  ];
  const normA = strip(a);
  const normB = strip(b);
  if (every5Patterns.includes(normA) && every5Patterns.includes(normB)) return true;
  return false;
}

function compareJob(v1Request, apiJob) {
  const checks = [];

  const jobName = v1Request.name;
  const apiName = apiJob.name;
  if (apiName === undefined) {
    checks.push({ field: "job name", status: "WARN", expected: jobName, actual: "(not returned)", detail: "API did not return job name" });
  } else if (apiName === jobName) {
    checks.push({ field: "job name", status: "PASS", expected: jobName, actual: apiName, detail: "Matched" });
  } else {
    checks.push({ field: "job name", status: "FAIL", expected: jobName, actual: apiName, detail: "Mismatch" });
  }

  const expectedProcessType = v1Request.processType || "BATCH";
  const apiProcessType = apiJob.processType;
  if (apiProcessType === undefined) {
    checks.push({ field: "processType", status: "WARN", expected: expectedProcessType, actual: "(not returned)", detail: "API did not return processType" });
  } else if (apiProcessType === expectedProcessType) {
    checks.push({ field: "processType", status: "PASS", expected: expectedProcessType, actual: apiProcessType, detail: "Matched" });
  } else {
    checks.push({ field: "processType", status: "FAIL", expected: expectedProcessType, actual: apiProcessType, detail: "Mismatch" });
  }

  const expectedCron = v1Request.schedule && (v1Request.schedule.cron && v1Request.schedule.cron.expression || v1Request.schedule.cron);
  const apiSchedule = apiJob.schedule;
  if (!apiSchedule) {
    checks.push({ field: "schedule", status: "WARN", expected: expectedCron || "(none)", actual: "(not returned)", detail: "API did not return schedule" });
  } else {
    const apiCron = (apiSchedule.cron && apiSchedule.cron.expression) || apiSchedule.cron;
    if (expectedCron && apiCron && cronSemanticallyMatch(expectedCron, apiCron)) {
      checks.push({ field: "schedule", status: "PASS", expected: expectedCron, actual: apiCron, detail: "Semantically equivalent" });
    } else if (expectedCron && apiCron) {
      checks.push({ field: "schedule", status: "FAIL", expected: expectedCron, actual: apiCron, detail: "Mismatch" });
    } else {
      checks.push({ field: "schedule", status: "WARN", expected: expectedCron || "(none)", actual: apiCron || "(not returned)", detail: "Cannot compare schedule" });
    }
  }

  const expectedNodes = v1Request.nodes || [];
  const apiNodes = apiJob.nodes || [];

  if (apiJob.nodes === undefined) {
    checks.push({ field: "node count", status: "WARN", expected: String(expectedNodes.length), actual: "(not returned)", detail: "API did not return nodes" });
  } else if (apiNodes.length === expectedNodes.length) {
    checks.push({ field: "node count", status: "PASS", expected: String(expectedNodes.length), actual: String(apiNodes.length), detail: "Matched" });
  } else {
    checks.push({ field: "node count", status: "FAIL", expected: String(expectedNodes.length), actual: String(apiNodes.length), detail: "Mismatch" });
  }

  const expectedNames = expectedNodes.map((n) => n.name).sort();
  if (apiJob.nodes === undefined) {
    checks.push({ field: "node names", status: "WARN", expected: expectedNames.join(", "), actual: "(not returned)", detail: "API did not return nodes" });
  } else {
    const apiNames = apiNodes.map((n) => n.name).sort();
    if (JSON.stringify(apiNames) === JSON.stringify(expectedNames)) {
      checks.push({ field: "node names", status: "PASS", expected: expectedNames.join(", "), actual: apiNames.join(", "), detail: "Matched" });
    } else {
      checks.push({ field: "node names", status: "FAIL", expected: expectedNames.join(", "), actual: apiNames.join(", "), detail: "Mismatch" });
    }
  }

  const expectedTypes = expectedNodes.map((n) => normalizeType(n.type)).sort();
  if (apiJob.nodes === undefined) {
    checks.push({ field: "node types", status: "WARN", expected: expectedTypes.join(", "), actual: "(not returned)", detail: "API did not return nodes" });
  } else {
    const apiTypes = apiNodes.map((n) => normalizeType(n.type)).sort();
    if (JSON.stringify(apiTypes) === JSON.stringify(expectedTypes)) {
      checks.push({ field: "node types", status: "PASS", expected: expectedTypes.join(", "), actual: apiTypes.join(", "), detail: "Matched" });
    } else {
      checks.push({ field: "node types", status: "FAIL", expected: expectedTypes.join(", "), actual: apiTypes.join(", "), detail: "Mismatch" });
    }
  }

  if (apiJob.nodes === undefined) {
    checks.push({ field: "dependencies / preNodeName", status: "WARN", expected: "(from payload)", actual: "(not returned)", detail: "API did not return nodes" });
  } else {
    let depsMatch = true;
    const depDetails = [];
    for (const en of expectedNodes) {
      const an = apiNodes.find((n) => n.name === en.name);
      if (!an) {
        depsMatch = false;
        depDetails.push(`node "${en.name}" not found in API response`);
        continue;
      }
      const expectedDeps = (en.preNodeName || en.dependencies || []).sort();
      const apiDeps = ((an.preNodeName || an.dependencies || [])).sort();
      if (JSON.stringify(apiDeps) !== JSON.stringify(expectedDeps)) {
        depsMatch = false;
        depDetails.push(`node "${en.name}": expected [${expectedDeps}] got [${apiDeps}]`);
      }
    }
    if (depsMatch) {
      checks.push({ field: "dependencies / preNodeName", status: "PASS", expected: "(all matched)", actual: "(all matched)", detail: "All node dependencies match" });
    } else {
      checks.push({ field: "dependencies / preNodeName", status: "FAIL", expected: "(from payload)", actual: "(from API)", detail: depDetails.join("; ") });
    }
  }

  const sqlNodes = expectedNodes.filter((n) => n.properties && n.properties.sql);
  if (sqlNodes.length === 0) {
    checks.push({ field: "SQL node configuration", status: "WARN", expected: "(none in payload)", actual: "(N/A)", detail: "No SQL nodes in payload to compare" });
  } else if (apiJob.nodes === undefined) {
    checks.push({ field: "SQL node configuration", status: "WARN", expected: `(${sqlNodes.length} SQL nodes)`, actual: "(not returned)", detail: "API did not return nodes" });
  } else {
    let sqlMatch = true;
    let sqlCompared = 0;
    const sqlDetails = [];
    for (const en of sqlNodes) {
      const an = apiNodes.find((n) => n.name === en.name);
      if (!an) {
        sqlMatch = false;
        sqlDetails.push(`SQL node "${en.name}" not found in API response`);
        continue;
      }
      const apiProps = an.properties || [];
      const sqlProp = apiProps.find((p) => p.name === "sql");
      if (!sqlProp) {
        sqlDetails.push(`SQL node "${en.name}": sql property not returned by API`);
        continue;
      }
      sqlCompared++;
      const expectedSql = en.properties.sql.trim();
      const actualSql = (sqlProp.value || "").trim();
      if (actualSql !== expectedSql) {
        sqlMatch = false;
        sqlDetails.push(`SQL node "${en.name}": SQL content mismatch`);
      }
    }
    if (sqlCompared === 0 && sqlDetails.length > 0) {
      checks.push({ field: "SQL node configuration", status: "WARN", expected: `(${sqlNodes.length} SQL nodes)`, actual: "(sql not returned)", detail: sqlDetails.join("; ") });
    } else if (sqlMatch) {
      checks.push({ field: "SQL node configuration", status: "PASS", expected: `(${sqlCompared} compared)`, actual: `(${sqlCompared} matched)`, detail: "All comparable SQL nodes match" });
    } else {
      checks.push({ field: "SQL node configuration", status: "FAIL", expected: `(${sqlNodes.length} SQL nodes)`, actual: "(mismatch)", detail: sqlDetails.join("; ") });
    }
  }

  return checks;
}

function generateMarkdownReport({ timestamp, endpoint, projectIdMasked, workspaceIdMasked, jobName, httpStatus, checks, jobFound }) {
  const lines = [];
  lines.push("# Verify Job Report");
  lines.push("");
  lines.push(`**Timestamp:** ${timestamp}`);
  lines.push(`**Result:** ${jobFound ? "JOB FOUND" : "JOB NOT FOUND"}`);
  lines.push("");
  lines.push("## Environment");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| Endpoint | ${endpoint} |`);
  lines.push(`| project_id | ${projectIdMasked} |`);
  lines.push(`| workspace_id | ${workspaceIdMasked} |`);
  lines.push(`| job_name | ${jobName} |`);
  lines.push(`| HTTP Status | ${httpStatus} |`);
  lines.push("");

  if (jobFound && checks.length > 0) {
    lines.push("## Comparison Table");
    lines.push("");
    lines.push("| Field | Status | Expected | Actual | Detail |");
    lines.push("|-------|--------|----------|--------|--------|");
    for (const c of checks) {
      lines.push(`| ${c.field} | ${c.status} | ${c.expected} | ${c.actual} | ${c.detail} |`);
    }
    lines.push("");

    const passCount = checks.filter((c) => c.status === "PASS").length;
    const warnCount = checks.filter((c) => c.status === "WARN").length;
    const failCount = checks.filter((c) => c.status === "FAIL").length;

    lines.push("## Summary");
    lines.push("");
    lines.push(`| Status | Count |`);
    lines.push(`|--------|-------|`);
    lines.push(`| PASS | ${passCount} |`);
    lines.push(`| WARN | ${warnCount} |`);
    lines.push(`| FAIL | ${failCount} |`);
    lines.push("");
  } else if (!jobFound) {
    lines.push("## Result");
    lines.push("");
    lines.push("Job was not found via the DataArts API. No comparison performed.");
    lines.push("");
  }

  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **No create, update, delete, publish, start, or run operation was executed.**");
  lines.push(">");
  lines.push("> This command only called `GET /v1/{project_id}/jobs/{job_name}` (read-only).");
  lines.push("> It did NOT call POST, PUT, PATCH, or DELETE on any endpoint.");
  lines.push("> No write or destructive operation was executed.");
  lines.push("");

  return lines.join("\n");
}

async function main() {
  console.log("=== DataArts Deploy Agent: VERIFY JOB (read-only) ===\n");

  try {
    const env = config.load();
    config.validate(env);

    const endpointHost = `dayu-dlf.${env.HUAWEI_REGION}.myhuaweicloud.com`;
    const endpoint = `https://${endpointHost}`;
    const projectId = env.HUAWEI_PROJECT_ID;
    const workspaceId = env.DATAARTS_WORKSPACE_ID;
    const ak = env.HUAWEI_AK;
    const sk = env.HUAWEI_SK;

    console.log(`Endpoint:  ${endpoint}`);
    console.log(`Project:   ${maskId(projectId)}`);
    console.log(`Workspace: ${maskId(workspaceId)}`);
    console.log("");

    if (!fs.existsSync(V1_REQUEST_FILE)) {
      throw new Error(
        `Missing v1 dry-run request: ${V1_REQUEST_FILE}\nRun "npm run dry-run" first.`
      );
    }

    const v1Request = JSON.parse(fs.readFileSync(V1_REQUEST_FILE, "utf-8"));
    const v1Body = v1Request.body || v1Request;
    const jobName = v1Body.name;

    if (!jobName) {
      throw new Error("V1 request is missing job name.");
    }

    console.log(`Job name:  ${jobName}`);
    console.log("");

    const getJobUrl = `${endpoint}/v1/${projectId}/jobs/${encodeURIComponent(jobName)}`;
    console.log("Fetching job from DataArts API...");
    console.log(`  GET /v1/${maskId(projectId)}/jobs/${jobName}`);

    let result;
    try {
      result = await signedGet(getJobUrl, ak, sk, workspaceId);
    } catch (err) {
      throw new Error(`GET request failed: ${err.message}`);
    }

    console.log(`  Status: ${result.statusCode}`);

    const jobFound = result.statusCode >= 200 && result.statusCode < 300;
    let apiJob = null;
    let checks = [];

    if (jobFound) {
      try {
        apiJob = JSON.parse(result.body);
      } catch {
        throw new Error("Failed to parse API response body as JSON");
      }
      console.log("  Job found. Comparing against payload...");
      checks = compareJob(v1Body, apiJob);
    } else {
      console.log("  Job not found or unexpected status.");
    }

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const timestamp = new Date().toISOString();

    const passCount = checks.filter((c) => c.status === "PASS").length;
    const warnCount = checks.filter((c) => c.status === "WARN").length;
    const failCount = checks.filter((c) => c.status === "FAIL").length;

    const jsonReport = {
      timestamp,
      endpoint,
      project_id_masked: maskId(projectId),
      workspace_id_masked: maskId(workspaceId),
      job_name: jobName,
      http_status: result.statusCode,
      job_found: jobFound,
      checks,
      summary: { pass: passCount, warn: warnCount, fail: failCount },
      no_secrets_included: true,
      safety: {
        no_create: true,
        no_update: true,
        no_delete: true,
        no_publish: true,
        no_start: true,
        no_run: true,
        method: "GET",
        read_only: true,
      },
    };
    fs.writeFileSync(
      path.join(OUT_DIR, "verify_job_result.json"),
      JSON.stringify(jsonReport, null, 2),
      "utf-8"
    );

    const mdReport = generateMarkdownReport({
      timestamp,
      endpoint,
      projectIdMasked: maskId(projectId),
      workspaceIdMasked: maskId(workspaceId),
      jobName,
      httpStatus: result.statusCode,
      checks,
      jobFound,
    });
    fs.writeFileSync(
      path.join(OUT_DIR, "verify_job_report.md"),
      mdReport,
      "utf-8"
    );

    console.log("");
    if (jobFound && checks.length > 0) {
      console.log("=== Comparison Results ===");
      for (const c of checks) {
        console.log(`  [${c.status}] ${c.field}: ${c.detail}`);
      }
      console.log("");
      console.log(`Summary: PASS=${passCount} WARN=${warnCount} FAIL=${failCount}`);
    }
    console.log("");
    console.log("Safety: No create, update, delete, publish, start, or run operation was executed.");
    console.log("");
    console.log("Reports saved:");
    console.log(`  ${path.join(OUT_DIR, "verify_job_result.json")}`);
    console.log(`  ${path.join(OUT_DIR, "verify_job_report.md")}`);

    const hasFailure = failCount > 0;
    process.exit(hasFailure ? 1 : 0);
  } catch (err) {
    console.error(`VERIFY JOB FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
