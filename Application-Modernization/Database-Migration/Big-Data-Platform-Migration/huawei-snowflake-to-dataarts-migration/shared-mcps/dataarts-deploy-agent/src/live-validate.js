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

const FAILURE_TYPES = {
  AUTH_FAILURE: "AUTH_FAILURE",
  NETWORK_FAILURE: "NETWORK_FAILURE",
  WORKSPACE_FAILURE: "WORKSPACE_FAILURE",
  ENDPOINT_NOT_FOUND: "ENDPOINT_NOT_FOUND",
  PERMISSION_FAILURE: "PERMISSION_FAILURE",
  UNKNOWN_FAILURE: "UNKNOWN_FAILURE",
};

function maskId(id) {
  if (!id || id.length < 8) return "***";
  return id.slice(0, 4) + "***" + id.slice(-4);
}

function httpsRequest(url, options, timeoutMs = 15000) {
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

async function signedGet(url, ak, sk, workspaceId, projectId) {
  const headers = {
    "Content-Type": "application/json",
  };
  if (workspaceId) {
    headers.workspace = workspaceId;
  }

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

function classifyStatus(statusCode, isProbeOnly) {
  if (statusCode >= 200 && statusCode < 300) return null;
  if (statusCode === 401 || statusCode === 403)
    return FAILURE_TYPES.AUTH_FAILURE;
  if (statusCode === 404) {
    return isProbeOnly
      ? FAILURE_TYPES.ENDPOINT_NOT_FOUND
      : FAILURE_TYPES.ENDPOINT_NOT_FOUND;
  }
  if (statusCode === 400) return FAILURE_TYPES.WORKSPACE_FAILURE;
  return FAILURE_TYPES.UNKNOWN_FAILURE;
}

function classifyError(err) {
  const msg = (err.message || "").toLowerCase();
  if (
    msg.includes("econnrefused") ||
    msg.includes("enotfound") ||
    msg.includes("econnreset") ||
    msg.includes("request_timeout") ||
    msg.includes("etimedout")
  ) {
    return FAILURE_TYPES.NETWORK_FAILURE;
  }
  return FAILURE_TYPES.UNKNOWN_FAILURE;
}

async function probeEndpoint(env, endpointHost, apiPath, label) {
  const url = `https://${endpointHost}${apiPath}`;
  const result = {
    label,
    method: "GET",
    path: apiPath,
    url: url.replace(env.HUAWEI_AK, "***").replace(env.HUAWEI_SK, "***"),
    status: null,
    failure: null,
    interpretation: "",
    durationMs: null,
  };

  const start = Date.now();
  try {
    const res = await signedGet(
      url,
      env.HUAWEI_AK,
      env.HUAWEI_SK,
      env.DATAARTS_WORKSPACE_ID,
      env.HUAWEI_PROJECT_ID
    );
    result.durationMs = Date.now() - start;
    result.status = res.statusCode;

    if (res.statusCode >= 200 && res.statusCode < 300) {
      result.interpretation = "Endpoint reachable, auth accepted, workspace valid";
    } else if (res.statusCode === 401 || res.statusCode === 403) {
      result.failure = FAILURE_TYPES.AUTH_FAILURE;
      const bodyHint = (res.body || "").slice(0, 200);
      result.interpretation =
        res.statusCode === 401
          ? `Authentication failed: invalid AK/SK [${bodyHint}]`
          : `Forbidden: AK/SK valid but insufficient permissions [${bodyHint}]`;
    } else if (res.statusCode === 404) {
      result.failure = FAILURE_TYPES.ENDPOINT_NOT_FOUND;
      result.interpretation =
        "Endpoint or resource not found (may indicate wrong region, project, or API path)";
    } else if (res.statusCode === 400) {
      const bodyLower = (res.body || "").toLowerCase();
      if (
        bodyLower.includes("workspace") ||
        bodyLower.includes("space") ||
        bodyLower.includes("work_space")
      ) {
        result.failure = FAILURE_TYPES.WORKSPACE_FAILURE;
        result.interpretation =
          "Bad request likely due to invalid workspace ID";
      } else if (bodyLower.includes("does not exist") || bodyLower.includes("not found")) {
        result.interpretation = `Resource does not exist (expected pre-deploy): ${(res.body || "").slice(0, 150)}`;
      } else {
        result.failure = FAILURE_TYPES.UNKNOWN_FAILURE;
        result.interpretation = `Bad request (HTTP 400): ${res.body.slice(0, 200)}`;
      }
    } else {
      result.failure = classifyStatus(res.statusCode, true);
      result.interpretation = `Unexpected HTTP ${res.statusCode}`;
    }
  } catch (err) {
    result.durationMs = Date.now() - start;
    result.failure = classifyError(err);
    result.interpretation = `Network/transport error: ${err.message}`;
  }

  return result;
}

async function probeWithoutWorkspace(env, endpointHost, apiPath, label) {
  const url = `https://${endpointHost}${apiPath}`;
  const result = {
    label,
    method: "GET",
    path: apiPath,
    url: url.replace(env.HUAWEI_AK, "***").replace(env.HUAWEI_SK, "***"),
    status: null,
    failure: null,
    interpretation: "",
    durationMs: null,
  };

  const start = Date.now();
  try {
    const headers = { "Content-Type": "application/json" };
    const signed = buildSignedHeaders({
      method: "GET",
      url,
      headers,
      body: "",
      ak: env.HUAWEI_AK,
      sk: env.HUAWEI_SK,
    });
    const parsed = new URL(url);
    const res = await httpsRequest(
      url,
      {
        hostname: parsed.hostname,
        port: 443,
        path: parsed.pathname + parsed.search,
        method: "GET",
        headers: signed,
      },
      15000
    );
    result.durationMs = Date.now() - start;
    result.status = res.statusCode;

    if (res.statusCode >= 200 && res.statusCode < 300) {
      result.interpretation =
        "Endpoint reachable without workspace header, auth accepted";
    } else if (res.statusCode === 401 || res.statusCode === 403) {
      result.failure = FAILURE_TYPES.AUTH_FAILURE;
      result.interpretation = "Authentication failed without workspace header";
    } else if (res.statusCode === 404) {
      result.interpretation =
        "404 without workspace (not treated as credential failure)";
    } else if (res.statusCode === 400) {
      result.interpretation =
        "HTTP 400 without workspace header (workspace likely required)";
    } else {
      result.interpretation = `HTTP ${res.statusCode} without workspace header`;
    }
  } catch (err) {
    result.durationMs = Date.now() - start;
    result.failure = classifyError(err);
    result.interpretation = `Network/transport error: ${err.message}`;
  }

  return result;
}

function validateV1RequestMetadata(v1Request, projectId) {
  const issues = [];
  const body = v1Request.body || v1Request;
  if (!body.name) issues.push("Missing job name in v1 request");
  if (!body.processType) issues.push("Missing processType in v1 request");
  if (!Array.isArray(body.nodes))
    issues.push("Missing or invalid nodes array");
  return issues;
}

function generateMarkdownReport(env, endpointHost, probeResults, overall) {
  const lines = [];
  const ts = new Date().toISOString();

  lines.push("# Live Validation Report");
  lines.push("");
  lines.push(`**Timestamp:** ${ts}`);
  lines.push(`**Result:** ${overall.pass ? "PASS" : "FAIL"}`);
  lines.push("");
  lines.push(
    "> **No create, update, delete, or start operation was executed.**"
  );
  lines.push(
    "> This validation only performed safe, read-only HTTP GET probes."
  );
  lines.push("");

  lines.push("## Environment");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| Region | ${env.HUAWEI_REGION} |`);
  lines.push(`| Project ID | ${maskId(env.HUAWEI_PROJECT_ID)} |`);
  lines.push(`| Workspace ID | ${maskId(env.DATAARTS_WORKSPACE_ID)} |`);
  lines.push(`| AK (masked) | ***${env.HUAWEI_AK.slice(-4)} |`);
  lines.push(`| Endpoint Host | ${endpointHost} |`);
  lines.push("");

  lines.push("## API Paths Tested");
  lines.push("");
  lines.push("| Label | Method | Path | HTTP Status | Duration | Interpretation |");
  lines.push("|-------|--------|------|-------------|----------|----------------|");
  for (const r of probeResults) {
    lines.push(
      `| ${r.label} | ${r.method} | ${r.path} | ${r.status ?? "N/A"} | ${r.durationMs ?? "N/A"}ms | ${r.interpretation} |`
    );
  }
  lines.push("");

  lines.push("## Failure Classification");
  lines.push("");
  for (const type of Object.values(FAILURE_TYPES)) {
    const matching = probeResults.filter((r) => r.failure === type);
    if (matching.length > 0) {
      lines.push(
        `- **${type}**: ${matching.map((m) => `"${m.label}"`).join(", ")}`
      );
    }
  }
  const noneFailed = probeResults.every((r) => !r.failure);
  if (noneFailed) {
    lines.push("- No failures detected.");
  }
  lines.push("");

  lines.push("## Checks Summary");
  lines.push("");
  for (const c of overall.checks) {
    lines.push(`- [${c.pass ? "x" : " "}] ${c.name}${c.detail ? ` (${c.detail})` : ""}`);
  }
  lines.push("");

  lines.push("## What This Does NOT Do");
  lines.push("");
  lines.push("- Did NOT call `POST /v1/{project_id}/jobs`");
  lines.push("- Did NOT call `POST /v1/{project_id}/jobs/{job_name}/start`");
  lines.push("- Did NOT call any DELETE, PUT, or PATCH endpoint");
  lines.push("- Did NOT create, update, delete, or start any DataArts job");
  lines.push("- No write or destructive operation was executed");
  lines.push("");

  return lines.join("\n");
}

function generateJsonReport(env, endpointHost, probeResults, overall) {
  return {
    timestamp: new Date().toISOString(),
    result: overall.pass ? "PASS" : "FAIL",
    region: env.HUAWEI_REGION,
    project_id_masked: maskId(env.HUAWEI_PROJECT_ID),
    workspace_id_masked: maskId(env.DATAARTS_WORKSPACE_ID),
    endpoint_host: endpointHost,
    probes: probeResults.map((r) => ({
      label: r.label,
      method: r.method,
      path: r.path,
      status: r.status,
      failure: r.failure,
      interpretation: r.interpretation,
      duration_ms: r.durationMs,
    })),
    checks: overall.checks,
    no_write_operations: true,
    no_secrets_included: true,
  };
}

async function main() {
  console.log(
    "=== DataArts Deploy Agent: LIVE VALIDATION (read-only) ===\n"
  );

  try {
    const env = config.load();
    config.validate(env);

    const endpointHost = `dayu-dlf.${env.HUAWEI_REGION}.myhuaweicloud.com`;
    const projectId = env.HUAWEI_PROJECT_ID;
    const workspaceId = env.DATAARTS_WORKSPACE_ID;

    console.log(`Endpoint: https://${endpointHost}`);
    console.log(`Project: ${maskId(projectId)}`);
    console.log(`Workspace: ${maskId(workspaceId)}\n`);

    if (!fs.existsSync(V1_REQUEST_FILE)) {
      throw new Error(
        `Missing v1 dry-run request: ${V1_REQUEST_FILE}\nRun "npm run dry-run" first.`
      );
    }
    const v1Request = JSON.parse(fs.readFileSync(V1_REQUEST_FILE, "utf-8"));

    const v1Body = v1Request.body || v1Request;

    const metaIssues = validateV1RequestMetadata(v1Request, projectId);
    if (metaIssues.length > 0) {
      console.log("V1 request metadata issues:");
      for (const i of metaIssues) console.log(`  - ${i}`);
    } else {
      console.log("V1 request metadata: OK (matches POST /v1/{project_id}/jobs)");
    }
    console.log("");

    const probes = [];

    console.log("Probe 1: List jobs (with workspace header)...");
    const listJobsPath = `/v1/${projectId}/jobs?limit=1`;
    const probe1 = await probeEndpoint(
      env,
      endpointHost,
      listJobsPath,
      "list_jobs_with_workspace"
    );
    probes.push(probe1);
    console.log(
      `  Status: ${probe1.status ?? "N/A"} | ${probe1.interpretation} (${probe1.durationMs}ms)`
    );

    console.log("Probe 2: List jobs (without workspace header, --probe-only)...");
    const probe2 = await probeWithoutWorkspace(
      env,
      endpointHost,
      listJobsPath,
      "list_jobs_no_workspace"
    );
    probes.push(probe2);
    console.log(
      `  Status: ${probe2.status ?? "N/A"} | ${probe2.interpretation} (${probe2.durationMs}ms)`
    );

    console.log("Probe 3: Get specific job detail (with workspace header)...");
    const jobDetailPath = `/v1/${projectId}/jobs/${encodeURIComponent(v1Body.name)}`;
    const probe3 = await probeEndpoint(
      env,
      endpointHost,
      jobDetailPath,
      "get_job_detail"
    );
    probes.push(probe3);
    console.log(
      `  Status: ${probe3.status ?? "N/A"} | ${probe3.interpretation} (${probe3.durationMs}ms)`
    );

    console.log("");

    const checks = [];

    checks.push({
      name: "V1 request metadata valid",
      pass: metaIssues.length === 0,
      detail: metaIssues.length === 0 ? "OK" : metaIssues.join("; "),
    });

    const anyNetworkError = probes.some(
      (p) => p.failure === FAILURE_TYPES.NETWORK_FAILURE
    );
    checks.push({
      name: "Network connectivity",
      pass: !anyNetworkError,
      detail: anyNetworkError ? "NETWORK_FAILURE" : "OK",
    });

    const anyAuthFailure = probes.some(
      (p) => p.failure === FAILURE_TYPES.AUTH_FAILURE
    );
    checks.push({
      name: "AK/SK authentication",
      pass: !anyAuthFailure,
      detail: anyAuthFailure ? "AUTH_FAILURE" : "OK",
    });

    const wsProbe = probes[0];
    const wsFailure = wsProbe.failure === FAILURE_TYPES.WORKSPACE_FAILURE;
    checks.push({
      name: "Workspace access",
      pass: !wsFailure,
      detail: wsFailure
        ? "WORKSPACE_FAILURE"
        : wsProbe.status
          ? "OK"
          : "N/A",
    });

    const endpointNotFound = probes.every(
      (p) => p.failure === FAILURE_TYPES.ENDPOINT_NOT_FOUND
    );
    checks.push({
      name: "DataArts endpoint reachable",
      pass: !endpointNotFound,
      detail: endpointNotFound ? "ENDPOINT_NOT_FOUND" : "OK",
    });

    const anyPermissionFailure = probes.some(
      (p) => p.failure === FAILURE_TYPES.PERMISSION_FAILURE
    );
    checks.push({
      name: "List/read permissions",
      pass: !anyPermissionFailure,
      detail: anyPermissionFailure ? "PERMISSION_FAILURE" : "OK",
    });

    const atLeastOneSuccess = probes.some(
      (p) => p.status >= 200 && p.status < 300
    );
    checks.push({
      name: "At least one probe succeeded (2xx)",
      pass: atLeastOneSuccess,
      detail: atLeastOneSuccess ? "OK" : "No 2xx response received",
    });

    const overall = {
      pass: checks.every((c) => c.pass),
      checks,
    };

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const mdReport = generateMarkdownReport(
      env,
      endpointHost,
      probes,
      overall
    );
    fs.writeFileSync(
      path.join(OUT_DIR, "live_validation_report.md"),
      mdReport,
      "utf-8"
    );

    const jsonReport = generateJsonReport(
      env,
      endpointHost,
      probes,
      overall
    );
    fs.writeFileSync(
      path.join(OUT_DIR, "live_validation_result.json"),
      JSON.stringify(jsonReport, null, 2),
      "utf-8"
    );

    console.log("=== Checks ===");
    for (const c of checks) {
      console.log(
        `  [${c.pass ? "PASS" : "FAIL"}] ${c.name}${c.detail ? ` (${c.detail})` : ""}`
      );
    }
    console.log("");
    console.log(`Overall: ${overall.pass ? "PASS" : "FAIL"}`);
    console.log(
      `\nReports saved:\n  ${path.join(OUT_DIR, "live_validation_report.md")}\n  ${path.join(OUT_DIR, "live_validation_result.json")}`
    );
    console.log(
      "\nNo create, update, delete, or start operation was executed."
    );

    process.exit(overall.pass ? 0 : 1);
  } catch (err) {
    console.error(`LIVE VALIDATION FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
