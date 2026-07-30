const fs = require("fs");
const path = require("path");
const https = require("https");
const config = require("./config");
const { buildSignedHeaders } = require("./huawei-signer");

const OUT_DIR = path.resolve(__dirname, "..", "out");

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

async function signedRequest({ method, url, headers, body, ak, sk }) {
  const signed = buildSignedHeaders({ method, url, headers, body, ak, sk });
  const parsed = new URL(url);
  const options = {
    hostname: parsed.hostname,
    port: 443,
    path: parsed.pathname + parsed.search,
    method,
    headers: signed,
    body: body || "",
  };
  return httpsRequest(url, options);
}

function isJobNotExist(statusCode, responseBody) {
  const bodyLower = (responseBody || "").toLowerCase();
  if (statusCode === 400 && (bodyLower.includes("dlf.0100") || bodyLower.includes("does not exist") || bodyLower.includes("not found"))) {
    return true;
  }
  if (statusCode === 404) return true;
  return false;
}

function generateMarkdownReport({ timestamp, endpoint, projectIdMasked, workspaceIdMasked, jobName, httpStatus, responseSummary, executionId, asyncResponse, safetyStatement }) {
  const lines = [];
  lines.push("# Run-Immediate Job Report");
  lines.push("");
  lines.push(`**Timestamp:** ${timestamp}`);
  lines.push(`**Result:** ${httpStatus >= 200 && httpStatus < 300 ? "RUN-IMMEDIATE TRIGGERED" : "RUN-IMMEDIATE FAILED"}`);
  lines.push("");
  lines.push("## Environment");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| Endpoint | ${endpoint} |`);
  lines.push(`| project_id | ${projectIdMasked} |`);
  lines.push(`| workspace_id | ${workspaceIdMasked} |`);
  lines.push(`| job_name | ${jobName} |`);
  lines.push("");
  lines.push("## Execution Result");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| HTTP Status | ${httpStatus} |`);
  lines.push(`| Response Summary | ${responseSummary} |`);
  if (executionId) {
    lines.push(`| Execution/Run ID | ${executionId} |`);
  }
  if (asyncResponse) {
    lines.push(`| Async Response | ${asyncResponse} |`);
  }
  lines.push("");
  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **No publish, no scheduled start, no update, no delete operation was executed.**");
  lines.push(">");
  lines.push("> This command only called:");
  lines.push("> - `GET /v1/{project_id}/jobs/{job_name}` (preflight, read-only)");
  lines.push(`> - \`POST /v1/{project_id}/jobs/${jobName}/run-immediate\` (one-time execution)`);
  lines.push(">");
  lines.push("> It did NOT call `/start`, `/publish`, any PUT, PATCH, or DELETE endpoint.");
  lines.push("> No recurring schedule was enabled.");
  lines.push("> No job definition was updated or overwritten.");
  lines.push("");

  return lines.join("\n");
}

async function main() {
  console.log("=== DataArts Deploy Agent: RUN-IMMEDIATE JOB ===\n");

  const args = process.argv.slice(2);
  if (!args.includes("--confirm")) {
    console.error("ABORTED: --confirm flag is required.");
    console.error("");
    console.error("This command will trigger a one-time execution of the DataArts job.");
    console.error("To proceed, run:");
    console.error("  npm run run-immediate-job -- --confirm");
    process.exit(1);
  }

  try {
    const env = config.load();
    config.validate(env);

    const jobName = env.DATAARTS_JOB_NAME;
    if (!jobName) {
      throw new Error("DATAARTS_JOB_NAME is not set. Provide it via --job-name CLI arg, MCP argument, or env var.");
    }

    const endpointHost = `dayu-dlf.${env.HUAWEI_REGION}.myhuaweicloud.com`;
    const endpoint = `https://${endpointHost}`;
    const projectId = env.HUAWEI_PROJECT_ID;
    const workspaceId = env.DATAARTS_WORKSPACE_ID;
    const ak = env.HUAWEI_AK;
    const sk = env.HUAWEI_SK;

    console.log(`Endpoint:  ${endpoint}`);
    console.log(`Project:   ${maskId(projectId)}`);
    console.log(`Workspace: ${maskId(workspaceId)}`);
    console.log(`Job name:  ${jobName}`);
    console.log("");

    console.log("[1/3] Preflight: Checking if job exists...\n");
    const getJobUrl = `${endpoint}/v1/${projectId}/jobs/${encodeURIComponent(jobName)}`;
    console.log(`  GET /v1/${maskId(projectId)}/jobs/${jobName}`);

    const getHeaders = {
      "Content-Type": "application/json",
      workspace: workspaceId,
    };

    let preflightResult;
    try {
      preflightResult = await signedRequest({
        method: "GET",
        url: getJobUrl,
        headers: getHeaders,
        body: "",
        ak,
        sk,
      });
    } catch (err) {
      throw new Error(`Preflight request failed: ${err.message}`);
    }

    console.log(`  Status: ${preflightResult.statusCode}`);

    if (isJobNotExist(preflightResult.statusCode, preflightResult.body)) {
      throw new Error(`Job "${jobName}" not found (HTTP ${preflightResult.statusCode}). Cannot run-immediate a non-existent job.`);
    }

    if (preflightResult.statusCode < 200 || preflightResult.statusCode >= 300) {
      throw new Error(`Preflight returned unexpected status ${preflightResult.statusCode}. Aborting to be safe.`);
    }

    console.log("  Job found. Safe to proceed.\n");

    console.log("[2/3] Triggering run-immediate...\n");
    const runImmediateUrl = `${endpoint}/v1/${projectId}/jobs/${encodeURIComponent(jobName)}/run-immediate`;
    console.log(`  POST /v1/${maskId(projectId)}/jobs/${jobName}/run-immediate`);

    const postHeaders = {
      "Content-Type": "application/json",
      workspace: workspaceId,
    };

    let runResult;
    try {
      runResult = await signedRequest({
        method: "POST",
        url: runImmediateUrl,
        headers: postHeaders,
        body: "",
        ak,
        sk,
      });
    } catch (err) {
      throw new Error(`Run-immediate request failed: ${err.message}`);
    }

    const success = runResult.statusCode >= 200 && runResult.statusCode < 300;
    console.log(`  Status: ${runResult.statusCode}`);
    console.log(`  Result: ${success ? "TRIGGERED" : "FAILED"}`);

    let responseSummary;
    let executionId = null;
    let asyncResponse = null;
    let parsedBody = null;

    if (runResult.body && runResult.body.trim()) {
      try {
        parsedBody = JSON.parse(runResult.body);
        if (parsedBody.error_code) {
          responseSummary = `${parsedBody.error_code}: ${parsedBody.error_msg || "Unknown error"}`;
        } else {
          responseSummary = "Response received";

          const possibleIdFields = [
            "instanceId", "instance_id", "jobInstanceId", "job_instance_id",
            "runId", "run_id", "executionId", "execution_id",
            "taskId", "task_id", "id",
          ];
          for (const field of possibleIdFields) {
            if (parsedBody[field]) {
              executionId = `${field}=${parsedBody[field]}`;
              break;
            }
          }

          if (parsedBody.status || parsedBody.State) {
            asyncResponse = `status=${parsedBody.status || parsedBody.State}`;
          }
          if (parsedBody.message) {
            asyncResponse = (asyncResponse ? asyncResponse + ", " : "") + `message=${parsedBody.message}`;
          }
        }
      } catch {
        responseSummary = runResult.body.slice(0, 200);
      }
    } else {
      responseSummary = success ? "Triggered successfully (no response body)" : "No response body";
    }

    if (executionId) {
      console.log(`  Execution ID: ${executionId}`);
    }
    if (asyncResponse) {
      console.log(`  Async info: ${asyncResponse}`);
    }
    console.log(`  Summary: ${responseSummary}`);
    console.log("");

    console.log("[3/3] Saving reports...\n");

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const timestamp = new Date().toISOString();

    const jsonReport = {
      timestamp,
      endpoint,
      project_id_masked: maskId(projectId),
      workspace_id_masked: maskId(workspaceId),
      job_name: jobName,
      http_status: runResult.statusCode,
      success,
      response_summary: responseSummary,
      execution_id: executionId,
      async_response: asyncResponse,
      no_secrets_included: true,
      safety: {
        no_publish: true,
        no_scheduled_start: true,
        no_update: true,
        no_delete: true,
        no_overwrite: true,
        only_endpoints_called: [
          `GET /v1/{project_id}/jobs/${jobName}`,
          `POST /v1/{project_id}/jobs/${jobName}/run-immediate`,
        ],
        safety_statement: "No publish, no scheduled start, no update, no delete operation was executed.",
      },
    };

    const mdReport = generateMarkdownReport({
      timestamp,
      endpoint,
      projectIdMasked: maskId(projectId),
      workspaceIdMasked: maskId(workspaceId),
      jobName,
      httpStatus: runResult.statusCode,
      responseSummary,
      executionId,
      asyncResponse,
    });

    const mdPath = path.join(OUT_DIR, "run_immediate_job_report.md");
    const jsonPath = path.join(OUT_DIR, "run_immediate_job_result.json");

    fs.writeFileSync(mdPath, mdReport, "utf-8");
    fs.writeFileSync(jsonPath, JSON.stringify(jsonReport, null, 2), "utf-8");

    console.log("=== Run-Immediate Summary ===\n");
    console.log(`  Job Name:       ${jobName}`);
    console.log(`  HTTP Status:    ${runResult.statusCode}`);
    console.log(`  Success:        ${success}`);
    console.log(`  Response:       ${responseSummary}`);
    if (executionId) {
      console.log(`  Execution ID:   ${executionId}`);
    }
    if (asyncResponse) {
      console.log(`  Async Info:     ${asyncResponse}`);
    }
    console.log("");
    console.log("Safety: No publish, no scheduled start, no update, no delete operation was executed.");
    console.log("Only GET (preflight) and POST run-immediate were called.\n");

    console.log("Reports saved:");
    console.log(`  ${mdPath}`);
    console.log(`  ${jsonPath}`);

    process.exit(success ? 0 : 1);
  } catch (err) {
    console.error(`RUN-IMMEDIATE JOB FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
