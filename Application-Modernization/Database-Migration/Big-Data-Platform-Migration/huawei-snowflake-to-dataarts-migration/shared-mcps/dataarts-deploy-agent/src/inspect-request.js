const fs = require("fs");
const path = require("path");

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
  console.log("=== DataArts Deploy Agent: INSPECT REQUEST ===\n");

  if (!fs.existsSync(V1_REQUEST_FILE)) {
    console.error(`Missing v1 request: ${V1_REQUEST_FILE}`);
    console.error("Run `npm run dry-run` first.");
    process.exit(1);
  }

  let request;
  try {
    request = JSON.parse(fs.readFileSync(V1_REQUEST_FILE, "utf-8"));
  } catch (e) {
    console.error("FAIL: Invalid JSON in v1 request file");
    process.exit(1);
  }

  const meta = request._meta || {};
  const req = request._request || {};
  const body = request.body || {};

  console.log("Meta");
  console.log("────────────────────────────────────────");
  console.log(`  generated_by:    ${meta.generated_by || "N/A"}`);
  console.log(`  generated_at:    ${meta.generated_at || "N/A"}`);
  console.log(`  mode:            ${meta.mode || "N/A"}`);
  console.log(`  source_platform: ${meta.source_platform || "N/A"}`);
  console.log(`  target_platform: ${meta.target_platform || "N/A"}`);
  console.log("");

  console.log("Request");
  console.log("────────────────────────────────────────");
  console.log(`  method:           ${req.method || "N/A"}`);
  console.log(`  endpoint:         ${req.endpoint || "N/A"}`);
  console.log(`  path:             ${req.path || "N/A"}`);
  console.log(`  workspace:        ${req.headers && req.headers.workspace ? maskId(req.headers.workspace) : "N/A"}`);
  console.log("");

  console.log("Body");
  console.log("────────────────────────────────────────");
  console.log(`  name:             ${body.name || "N/A"}`);
  console.log(`  processType:      ${body.processType || "N/A"}`);
  console.log(`  description:      ${(body.description || "").slice(0, 80)}`);
  console.log("");

  if (body.schedule) {
    console.log("  Schedule");
    console.log(`    type:              ${body.schedule.type || "N/A"}`);
    if (body.schedule.cron) {
      console.log(`    startTime:         ${body.schedule.cron.startTime || "N/A"}`);
      console.log(`    expression:        ${body.schedule.cron.expression || "N/A"}`);
      console.log(`    expressionTimeZone:${body.schedule.cron.expressionTimeZone ? " " + body.schedule.cron.expressionTimeZone : " N/A"}`);
      console.log(`    dependPrePeriod:   ${body.schedule.cron.dependPrePeriod}`);
      console.log(`    concurrent:        ${body.schedule.cron.concurrent}`);
    }
  } else {
    console.log("  Schedule: (missing)");
  }
  console.log("");

  const nodes = body.nodes || [];
  console.log(`  Nodes (${nodes.length})`);
  for (const node of nodes) {
    console.log(`    - name:         ${node.name}`);
    console.log(`      type:         ${node.type}`);
    console.log(`      preNodeName:  [${(node.preNodeName || []).join(", ")}]`);
    const sqlProp = (node.properties || []).find((p) => p.name === "sql");
    console.log(`      sql:          ${sqlProp ? `${sqlProp.value.length} chars` : "(missing)"}`);
  }
  console.log("");

  console.log("Safety: No secrets displayed. No API calls made.");
  process.exit(0);
}

main();
