const fs = require("fs");
const path = require("path");
const config = require("./config");

const OUT_DIR = path.resolve(__dirname, "..", "out");
const V1_REQUEST_FILE = path.join(
  OUT_DIR,
  "dataarts_create_job_request.v1.dryrun.json"
);

function maskId(id) {
  if (!id || id.length < 8) return "***";
  return id.slice(0, 4) + "***" + id.slice(-4);
}

function main() {
  console.log("=== DataArts Deploy Agent: DEPLOY PLAN (read-only) ===\n");

  try {
    const env = config.load();
    config.validate(env);

    const endpointHost = `dayu-dlf.${env.HUAWEI_REGION}.myhuaweicloud.com`;
    const projectId = env.HUAWEI_PROJECT_ID;
    const workspaceId = env.DATAARTS_WORKSPACE_ID;

    if (!fs.existsSync(V1_REQUEST_FILE)) {
      throw new Error(
        `Missing v1 dry-run request: ${V1_REQUEST_FILE}\nRun "npm run dry-run" first.`
      );
    }

    const v1Request = JSON.parse(fs.readFileSync(V1_REQUEST_FILE, "utf-8"));
    const body = v1Request.body;

    if (!body) {
      throw new Error("V1 request is missing .body. Run `npm run dry-run` first.");
    }
    if (!body.name) {
      throw new Error("V1 request .body.name is missing or null.");
    }

    const jobName = body.name;
    const processType = body.processType;
    const schedule = body.schedule;
    const nodes = body.nodes || [];

    const requestMeta = v1Request._request || {};
    const requestPath = requestMeta.path || `/v1/${projectId}/jobs`;
    const requestWorkspace = (requestMeta.headers && requestMeta.headers.workspace) || workspaceId;

    console.log("Plan Summary");
    console.log("────────────────────────────────────────");
    console.log(`  Endpoint:      https://${endpointHost}`);
    console.log(`  Method:        ${requestMeta.method || "POST"}`);
    console.log(`  Path:          ${requestPath}`);
    console.log(`  project_id:    ${maskId(projectId)}`);
    console.log(`  workspace_id:  ${maskId(requestWorkspace)}`);
    console.log(`  job_name:      ${jobName}`);
    console.log(`  processType:   ${processType}`);
    console.log(
      `  schedule:      type="${schedule?.type || "N/A"}" expression="${schedule?.cron?.expression || "N/A"}" timezone="${schedule?.cron?.expressionTimeZone || "N/A"}"`
    );
    console.log(`  node count:    ${nodes.length}`);
    console.log(`  node names:`);
    for (const node of nodes) {
      const deps = node.preNodeName && node.preNodeName.length > 0
        ? ` -> depends on: ${node.preNodeName.join(", ")}`
        : "";
      console.log(`    - ${node.name}${deps}`);
    }
    console.log("");

    console.log("Safety Confirmations");
    console.log("────────────────────────────────────────");
    console.log(`  [YES] This plan would call: POST /v1/{project_id}/jobs`);
    console.log(`  [YES] This plan would create a NEW job: "${jobName}"`);
    console.log(`  [NO]  This plan would NOT start the job (no /start call)`);
    console.log(`  [NO]  This plan would NOT publish the job (no publish call)`);
    console.log(`  [NO]  This plan would NOT delete anything (no DELETE call)`);
    console.log(`  [NO]  This plan would NOT update anything (no PUT/PATCH call)`);
    console.log("");

    console.log("What This Command Does NOT Do");
    console.log("────────────────────────────────────────");
    console.log("  - Did NOT call POST /v1/{project_id}/jobs");
    console.log("  - Did NOT call POST /v1/{project_id}/jobs/{job_name}/start");
    console.log("  - Did NOT call any DELETE, PUT, or PATCH endpoint");
    console.log("  - Did NOT create, update, delete, or start any DataArts job");
    console.log("  - Did NOT call the Huawei Cloud API at all");
    console.log("  - No write or destructive operation was executed");
    console.log("");

    console.log("Next Step");
    console.log("────────────────────────────────────────");
    console.log("  To create the job, run:");
    console.log("    npm run create-job -- --confirm");
    console.log("");

    process.exit(0);
  } catch (err) {
    console.error(`DEPLOY PLAN FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
