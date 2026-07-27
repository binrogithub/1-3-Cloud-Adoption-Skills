const fs = require("fs");
const path = require("path");
const { buildNativeRuntimePlan } = require("./runtime/native-runtime-plan");
const { createRealDliClient, createRealDliSafetyPolicy } = require("./runtime/dli/real-dli-client");
const { loadRuntimePackageArtifacts } = require("./runtime/runtime-package-loader");
const { loadMigrationPackage } = require("./migration/package-loader");

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = { packageDir: null, dliQueue: "default" };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--package-dir" && i + 1 < args.length) {
      result.packageDir = args[i + 1];
      i++;
    } else if (args[i] === "--dli-queue" && i + 1 < args.length) {
      result.dliQueue = args[i + 1];
      i++;
    }
  }

  return result;
}

async function main() {
  const { packageDir, dliQueue } = parseArgs(process.argv);

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

  const client = createRealDliClient({ allowRealExecution: false });

  const plannedSqlExecutions = [];
  const plannedQueryExecutions = [];

  for (const step of nativePlan.phases.runtime_setup) {
    const sql = fs.readFileSync(step.file_path, "utf-8");
    const result = await client.executeSql({ sql, queueName: dliQueue, step });
    plannedSqlExecutions.push({
      execution_order: step.execution_order,
      phase: step.phase,
      name: step.name,
      job_id: result.job_id,
      status: result.status,
      sql_hash: result.sql_hash,
      sql_preview: result.sql_preview,
      real_execution: result.real_execution,
      planned_request: result.planned_request,
    });
  }

  for (const step of nativePlan.phases.target_transform) {
    const sqlPath = step.sql_path;
    let sql = "";
    if (sqlPath && fs.existsSync(sqlPath)) {
      sql = fs.readFileSync(sqlPath, "utf-8");
    }
    const result = await client.executeSql({ sql, queueName: dliQueue, step });
    plannedSqlExecutions.push({
      execution_order: step.execution_order,
      phase: step.phase,
      name: step.name,
      node_id: step.node_id,
      job_id: result.job_id,
      status: result.status,
      sql_hash: result.sql_hash,
      sql_preview: result.sql_preview,
      real_execution: result.real_execution,
      planned_request: result.planned_request,
    });
  }

  for (const step of nativePlan.phases.runtime_validation) {
    const result = await client.querySql({ sql: step.sql, queueName: dliQueue, step });
    plannedQueryExecutions.push({
      execution_order: step.execution_order,
      phase: step.phase,
      name: step.name,
      query_type: step.query_type,
      object_name: step.object_name,
      job_id: result.job_id,
      status: result.status,
      sql_hash: result.sql_hash,
      sql_preview: result.sql_preview,
      real_execution: result.real_execution,
      planned_request: result.planned_request,
    });
  }

  const totalPlannedRequests = plannedSqlExecutions.length + plannedQueryExecutions.length;
  const safety = createRealDliSafetyPolicy();

  const planResult = {
    status: "DLI_CLIENT_PLAN_READY",
    valid: true,
    migration_id: migrationId,
    dli_queue: dliQueue,
    planned_sql_executions: plannedSqlExecutions,
    planned_query_executions: plannedQueryExecutions,
    total_planned_requests: totalPlannedRequests,
    safety,
  };

  const outDir = path.resolve("out");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const resultJsonPath = path.join(outDir, "dli_client_plan_result.json");
  const reportMdPath = path.join(outDir, "dli_client_plan_report.md");

  fs.writeFileSync(resultJsonPath, JSON.stringify(planResult, null, 2), "utf-8");

  const lines = [];
  lines.push("# DLI Client Plan Report");
  lines.push("");
  lines.push("> **PLAN ONLY** — No cloud APIs called. No SQL executed. No runtime execution.");
  lines.push("");
  lines.push("## Summary");
  lines.push("");
  lines.push(`**Status:** ${planResult.status}`);
  lines.push(`**Migration ID:** ${migrationId}`);
  lines.push(`**DLI Queue:** ${dliQueue}`);
  lines.push(`**SQL executions planned:** ${plannedSqlExecutions.length}`);
  lines.push(`**Query executions planned:** ${plannedQueryExecutions.length}`);
  lines.push(`**Total requests planned:** ${totalPlannedRequests}`);
  lines.push("");

  lines.push("## Planned SQL Executions");
  lines.push("");
  lines.push("| Order | Phase | Name | SQL Hash | Status |");
  lines.push("|-------|-------|------|----------|--------|");
  for (const exec of plannedSqlExecutions) {
    lines.push(`| ${exec.execution_order} | ${exec.phase} | ${exec.name} | ${exec.sql_hash} | ${exec.status} |`);
  }
  lines.push("");

  lines.push("## Planned Query Executions");
  lines.push("");
  lines.push("| Order | Name | Query Type | Object | SQL Hash | Status |");
  lines.push("|-------|------|------------|--------|----------|--------|");
  for (const q of plannedQueryExecutions) {
    lines.push(`| ${q.execution_order} | ${q.name} | ${q.query_type} | ${q.object_name} | ${q.sql_hash} | ${q.status} |`);
  }
  lines.push("");

  lines.push("## Safety");
  lines.push("");
  lines.push("- Plan only, no cloud APIs");
  lines.push("- No SQL execution");
  lines.push("- No runtime execution");
  lines.push("- No confirm");
  lines.push("");

  fs.writeFileSync(reportMdPath, lines.join("\n"), "utf-8");

  console.log("DLI client plan ready.");
  console.log(`Migration ID: ${migrationId}`);
  console.log(`SQL executions planned: ${plannedSqlExecutions.length}`);
  console.log(`Query executions planned: ${plannedQueryExecutions.length}`);
  console.log(`Total requests planned: ${totalPlannedRequests}`);
  console.log("Safety: plan only, no cloud APIs, no SQL execution.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
