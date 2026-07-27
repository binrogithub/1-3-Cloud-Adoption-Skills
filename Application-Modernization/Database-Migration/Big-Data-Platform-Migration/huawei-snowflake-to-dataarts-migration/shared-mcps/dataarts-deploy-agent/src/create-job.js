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

function isJobAlreadyExists(statusCode, responseBody) {
  if (statusCode === 200) return true;
  const bodyLower = (responseBody || "").toLowerCase();
  if (statusCode === 400 && (bodyLower.includes("already exist") || bodyLower.includes("duplicate"))) {
    return true;
  }
  if (statusCode === 409) return true;
  return false;
}

function isJobNotExist(statusCode, responseBody) {
  const bodyLower = (responseBody || "").toLowerCase();
  if (statusCode === 400 && (bodyLower.includes("dlf.0100") || bodyLower.includes("does not exist") || bodyLower.includes("not found"))) {
    return true;
  }
  if (statusCode === 404) return true;
  return false;
}

function validateV1RequestBody(v1Request) {
  if (!v1Request.body) {
    throw new Error("V1 request is missing .body. Run `npm run dry-run` first.");
  }
  if (!v1Request.body.name) {
    throw new Error("V1 request .body.name is missing or null.");
  }
  if (!v1Request.body.processType) {
    throw new Error("V1 request .body.processType is missing or null.");
  }
  if (!v1Request.body.schedule) {
    throw new Error("V1 request .body.schedule is missing or null.");
  }
  if (!Array.isArray(v1Request.body.nodes) || v1Request.body.nodes.length === 0) {
    throw new Error("V1 request .body.nodes is missing or empty.");
  }
}

function buildApiRequestBody(body) {
  const apiNodes = body.nodes.map((node, i) => {
    const properties = [...(node.properties || [])];
    if (!properties.some((p) => p.name === "queueName")) {
      properties.push({ name: "queueName", value: "default" });
    }
    if (!properties.some((p) => p.name === "database")) {
      properties.push({ name: "database", value: "demo_migration" });
    }
    if (!properties.some((p) => p.name === "statementOrScript")) {
      properties.push({ name: "statementOrScript", value: "STATEMENT" });
    }

    return {
      name: node.name,
      type: node.type || "DLISQL",
      location: node.location || { x: String(100 + i * 300), y: "100" },
      preNodeName: node.preNodeName || [],
      properties,
      pollingInterval: 20,
      maxExecutionTime: 360,
      retryInterval: 120,
      retryTimes: 0,
      failPolicy: "FAIL_CHILD",
    };
  });

  const schedule = body.schedule || {};
  const cron = schedule.cron || {};

  return {
    name: body.name,
    processType: body.processType || "BATCH",
    directory: "/",
    description: body.description || "",
    schedule: {
      type: schedule.type || "CRON",
      cron: {
        startTime: cron.startTime || "2026-01-01T00:00:00+00",
        endTime: cron.endTime || "2099-12-31T23:59:59+00",
        expression: cron.expression || "0 0-59/5 * * * ?",
        period: cron.period || "5 minutes",
        expressionTimeZone: cron.expressionTimeZone || "GMT+0",
        dependPrePeriod: cron.dependPrePeriod !== undefined ? cron.dependPrePeriod : false,
        concurrent: cron.concurrent !== undefined ? cron.concurrent : 1,
      },
    },
    nodes: apiNodes,
    basicConfig: {
      owner: "dataarts-deploy-agent",
      priority: 0,
      executeUser: "",
      instanceTimeout: 0,
      customFields: {},
    },
  };
}

function generateMarkdownReport({ timestamp, endpointHost, projectIdMasked, workspaceIdMasked, jobName, httpStatus, created, responseSummary }) {
  const lines = [];
  lines.push("# Create Job Report");
  lines.push("");
  lines.push(`**Timestamp:** ${timestamp}`);
  lines.push(`**Result:** ${created ? "CREATED" : "NOT CREATED"}`);
  lines.push("");
  lines.push("## Environment");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| Endpoint | https://${endpointHost} |`);
  lines.push(`| project_id | ${projectIdMasked} |`);
  lines.push(`| workspace_id | ${workspaceIdMasked} |`);
  lines.push(`| job_name | ${jobName} |`);
  lines.push("");
  lines.push("## Result");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| HTTP Status | ${httpStatus} |`);
  lines.push(`| Created | ${created ? "Yes" : "No"} |`);
  lines.push(`| Response Summary | ${responseSummary} |`);
  lines.push("");
  lines.push("## Safety Statement");
  lines.push("");
  lines.push("> **No start, publish, update, delete, or run operation was executed.**");
  lines.push(">");
  lines.push("> This command only called `POST /v1/{project_id}/jobs` to create the job.");
  lines.push("> It did NOT call `/start`, `/publish`, any DELETE, PUT, or PATCH endpoint.");
  lines.push("> The job was created in a stopped, unpublished state.");
  lines.push("");
  lines.push("## What This Does NOT Do");
  lines.push("");
  lines.push("- Did NOT call `POST /v1/{project_id}/jobs/{job_name}/start`");
  lines.push("- Did NOT call any DELETE, PUT, or PATCH endpoint");
  lines.push("- Did NOT publish the job");
  lines.push("- Did NOT start or run the pipeline");
  lines.push("- No destructive or runtime operation was executed");
  lines.push("");
  return lines.join("\n");
}

async function main() {
  console.log("=== DataArts Deploy Agent: CREATE JOB ===\n");

  const args = process.argv.slice(2);
  if (!args.includes("--confirm")) {
    console.error("ABORTED: --confirm flag is required.");
    console.error("");
    console.error("This command will create a DataArts job on Huawei Cloud.");
    console.error("To proceed, run:");
    console.error("  npm run create-job -- --confirm");
    process.exit(1);
  }

  try {
    const env = config.load();
    config.validate(env);

    const endpointHost = `dayu-dlf.${env.HUAWEI_REGION}.myhuaweicloud.com`;
    const projectId = env.HUAWEI_PROJECT_ID;
    const workspaceId = env.DATAARTS_WORKSPACE_ID;
    const ak = env.HUAWEI_AK;
    const sk = env.HUAWEI_SK;

    console.log(`Endpoint:  https://${endpointHost}`);
    console.log(`Project:   ${maskId(projectId)}`);
    console.log(`Workspace: ${maskId(workspaceId)}`);
    console.log("");

    if (!fs.existsSync(V1_REQUEST_FILE)) {
      throw new Error(
        `Missing v1 dry-run request: ${V1_REQUEST_FILE}\nRun "npm run dry-run" first.`
      );
    }

    const v1Request = JSON.parse(fs.readFileSync(V1_REQUEST_FILE, "utf-8"));

    validateV1RequestBody(v1Request);

    const jobName = v1Request.body.name;
    const requestMeta = v1Request._request || {};
    const requestPath = requestMeta.path || `/v1/${projectId}/jobs`;
    const requestWorkspace = (requestMeta.headers && requestMeta.headers.workspace) || workspaceId;

    console.log(`Job name:  ${jobName}`);
    console.log(`Request path: ${requestPath}`);
    console.log(`Request workspace: ${maskId(requestWorkspace)}`);
    console.log("");

    const apiRequestBody = buildApiRequestBody(v1Request.body);

    const getJobUrl = `https://${endpointHost}/v1/${projectId}/jobs/${encodeURIComponent(jobName)}`;
    console.log("Preflight: Checking if job already exists...");
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

    if (isJobAlreadyExists(preflightResult.statusCode, preflightResult.body)) {
      console.error("");
      console.error(`ABORTED: Job "${jobName}" already exists.`);
      console.error("This command will NOT overwrite or update an existing job.");
      console.error("To update, use a different tool or delete the job manually first.");
      process.exit(1);
    }

    if (isJobNotExist(preflightResult.statusCode, preflightResult.body)) {
      console.log("  Job does not exist (DLF.0100 / not found). Safe to create.");
    } else if (preflightResult.statusCode >= 200 && preflightResult.statusCode < 300) {
      console.error("");
      console.error(`ABORTED: Job "${jobName}" already exists (HTTP ${preflightResult.statusCode}).`);
      console.error("This command will NOT overwrite or update an existing job.");
      process.exit(1);
    } else {
      console.log(`  Unexpected status ${preflightResult.statusCode}. Proceeding with caution.`);
    }

    console.log("");
    console.log("Creating job...");
    const createJobUrl = `https://${endpointHost}/v1/${projectId}/jobs`;
    console.log(`  POST /v1/${maskId(projectId)}/jobs`);

    const createHeaders = {
      "Content-Type": "application/json",
      workspace: workspaceId,
    };
    const createBody = JSON.stringify(apiRequestBody);

    let createResult;
    try {
      createResult = await signedRequest({
        method: "POST",
        url: createJobUrl,
        headers: createHeaders,
        body: createBody,
        ak,
        sk,
      });
    } catch (err) {
      throw new Error(`Create request failed: ${err.message}`);
    }

    const created = createResult.statusCode >= 200 && createResult.statusCode < 300;
    console.log(`  Status: ${createResult.statusCode}`);
    console.log(`  Result: ${created ? "CREATED" : "NOT CREATED"}`);

    let responseSummary;
    if (createResult.statusCode === 204) {
      responseSummary = "Job created successfully (204 No Content)";
    } else if (createResult.body && createResult.body.trim()) {
      try {
        const parsed = JSON.parse(createResult.body);
        responseSummary = parsed.error_code
          ? `${parsed.error_code}: ${parsed.error_msg || "Unknown error"}`
          : `Job created: ${parsed.name || jobName}`;
      } catch {
        responseSummary = createResult.body.slice(0, 200);
      }
    } else {
      responseSummary = created ? "Job created successfully (204 No Content)" : "No response body";
    }
    console.log(`  Summary: ${responseSummary}`);

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const timestamp = new Date().toISOString();

    const jsonReport = {
      timestamp,
      endpoint: `https://${endpointHost}`,
      project_id_masked: maskId(projectId),
      workspace_id_masked: maskId(workspaceId),
      job_name: jobName,
      http_status: createResult.statusCode,
      created,
      response_summary: responseSummary,
      no_secrets_included: true,
      safety: {
        no_start: true,
        no_publish: true,
        no_update: true,
        no_delete: true,
        no_run: true,
      },
    };
    fs.writeFileSync(
      path.join(OUT_DIR, "create_job_result.json"),
      JSON.stringify(jsonReport, null, 2),
      "utf-8"
    );

    const mdReport = generateMarkdownReport({
      timestamp,
      endpointHost,
      projectIdMasked: maskId(projectId),
      workspaceIdMasked: maskId(workspaceId),
      jobName,
      httpStatus: createResult.statusCode,
      created,
      responseSummary,
    });
    fs.writeFileSync(
      path.join(OUT_DIR, "create_job_report.md"),
      mdReport,
      "utf-8"
    );

    console.log("");
    console.log("Safety: No start, publish, update, delete, or run operation was executed.");
    console.log("");
    console.log(`Reports saved:`);
    console.log(`  ${path.join(OUT_DIR, "create_job_result.json")}`);
    console.log(`  ${path.join(OUT_DIR, "create_job_report.md")}`);

    process.exit(created ? 0 : 1);
  } catch (err) {
    console.error(`CREATE JOB FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
