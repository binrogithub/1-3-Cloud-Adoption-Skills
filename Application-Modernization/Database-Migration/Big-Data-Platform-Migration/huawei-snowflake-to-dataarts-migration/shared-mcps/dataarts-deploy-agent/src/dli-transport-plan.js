const fs = require("fs");
const path = require("path");
const { buildNativeRuntimePlan } = require("./runtime/native-runtime-plan");
const { createRealDliClient } = require("./runtime/dli/real-dli-client");
const {
  buildDliSqlJobRequest,
  buildDliJobStatusRequest,
  buildDliJobResultRequest,
} = require("./runtime/dli/dli-http-transport");
const { scrubSecrets } = require("./core/secret-scrubber");
const { isCreateOrDropDatabaseStatement } = require("./runtime/dli/dli-submit-job-auditor");

function resolveDatabaseForSql(sql, defaultDatabase) {
  if (!defaultDatabase) return undefined;
  if (isCreateOrDropDatabaseStatement(sql)) return undefined;
  return defaultDatabase;
}

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = { packageDir: null, dliQueue: "default", database: "demo_migration" };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--package-dir" && i + 1 < args.length) {
      result.packageDir = args[i + 1];
      i++;
    } else if (args[i] === "--dli-queue" && i + 1 < args.length) {
      result.dliQueue = args[i + 1];
      i++;
    } else if (args[i] === "--database" && i + 1 < args.length) {
      result.database = args[i + 1];
      i++;
    }
  }

  return result;
}

async function main() {
  const { packageDir, dliQueue, database } = parseArgs(process.argv);

  if (!packageDir) {
    console.error("Error: --package-dir is required");
    process.exit(1);
  }

  const resolvedPackageDir = path.resolve(packageDir);
  const nativePlan = buildNativeRuntimePlan({ packageDir: resolvedPackageDir, dliQueue });

  if (!nativePlan.valid) {
    console.error("Error: native runtime plan is invalid");
    console.error(nativePlan.errors.join("\n"));
    process.exit(1);
  }

  const migrationId = nativePlan.migration_id;
  const transportRequests = [];

  for (const step of nativePlan.phases.runtime_setup) {
    const sql = fs.readFileSync(step.file_path, "utf-8");
    const planned = buildDliSqlJobRequest({ sql, queueName: dliQueue, step, database: resolveDatabaseForSql(sql, database) });
    transportRequests.push({
      phase: step.phase,
      step_name: step.name,
      step_type: step.type,
      transport_request: planned,
    });
  }

  for (const step of nativePlan.phases.target_transform) {
    const sqlPath = step.sql_path;
    let sql = "";
    if (sqlPath && fs.existsSync(sqlPath)) {
      sql = fs.readFileSync(sqlPath, "utf-8");
    }
    const planned = buildDliSqlJobRequest({ sql, queueName: dliQueue, step, database: resolveDatabaseForSql(sql, database) });
    transportRequests.push({
      phase: step.phase,
      step_name: step.name,
      step_type: step.type,
      transport_request: planned,
    });
  }

  for (const step of nativePlan.phases.runtime_validation) {
    const submitPlanned = buildDliSqlJobRequest({ sql: step.sql, queueName: dliQueue, step, database: resolveDatabaseForSql(step.sql, database) });
    transportRequests.push({
      phase: step.phase,
      step_name: step.name,
      step_type: step.type,
      query_type: step.query_type,
      transport_request: submitPlanned,
    });
  }

  const planResult = {
    status: "DLI_TRANSPORT_PLAN_READY",
    valid: true,
    migration_id: migrationId,
    dli_queue: dliQueue,
    total_transport_requests: transportRequests.length,
    transport_requests: transportRequests,
    no_sql_executed: true,
    no_cloud_apis_called: true,
  };

  const outDir = path.resolve("out");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const resultJsonPath = path.join(outDir, "dli_transport_plan_result.json");
  const reportMdPath = path.join(outDir, "dli_transport_plan_report.md");

  const safeResult = JSON.parse(scrubSecrets(JSON.stringify(planResult)));
  fs.writeFileSync(resultJsonPath, JSON.stringify(safeResult, null, 2), "utf-8");

  const lines = [];
  lines.push("# DLI Transport Plan Report");
  lines.push("");
  lines.push("> **TRANSPORT PLAN ONLY** — No cloud APIs called. No SQL executed. Shows exact HTTP requests that would be made.");
  lines.push("");
  lines.push("## Summary");
  lines.push("");
  lines.push(`**Status:** ${planResult.status}`);
  lines.push(`**Migration ID:** ${migrationId}`);
  lines.push(`**DLI Queue:** ${dliQueue}`);
  lines.push(`**Total transport requests:** ${transportRequests.length}`);
  lines.push("");

  lines.push("## Transport Requests");
  lines.push("");
  lines.push("| # | Phase | Step | Method | Operation | Endpoint |");
  lines.push("|---|-------|------|--------|-----------|----------|");
  for (let i = 0; i < transportRequests.length; i++) {
    const tr = transportRequests[i];
    const req = tr.transport_request;
    lines.push(`| ${i + 1} | ${tr.phase} | ${tr.step_name} | ${req.method || "N/A"} | ${req.operation || "N/A"} | ${req.endpoint || "N/A"} |`);
  }
  lines.push("");

  lines.push("## Safety");
  lines.push("");
  lines.push("- Transport plan only, no cloud APIs");
  lines.push("- No SQL execution");
  lines.push("- No runtime execution");
  lines.push("- No confirm");
  lines.push("- Three-flag execution guard required for real execution");
  lines.push("");

  fs.writeFileSync(reportMdPath, lines.join("\n"), "utf-8");

  console.log("DLI transport plan ready.");
  console.log(`Migration ID: ${migrationId}`);
  console.log(`Total transport requests: ${transportRequests.length}`);
  console.log("Safety: transport plan only, no cloud APIs, no SQL execution.");
}

main().catch((err) => {
  console.error(scrubSecrets(err.message));
  process.exit(1);
});
