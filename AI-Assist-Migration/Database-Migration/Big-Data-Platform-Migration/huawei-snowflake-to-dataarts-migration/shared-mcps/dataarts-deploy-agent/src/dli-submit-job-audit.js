const fs = require("fs");
const path = require("path");
const { buildNativeRuntimePlan } = require("./runtime/native-runtime-plan");
const {
  buildDliSqlJobRequest,
} = require("./runtime/dli/dli-http-transport");
const {
  auditDliTransportPlan,
  isCreateOrDropDatabaseStatement,
} = require("./runtime/dli/dli-submit-job-auditor");
const { scrubSecrets } = require("./core/secret-scrubber");

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

  const transportPlan = {
    status: "DLI_TRANSPORT_PLAN_READY",
    valid: true,
    migration_id: migrationId,
    dli_queue: dliQueue,
    total_transport_requests: transportRequests.length,
    transport_requests: transportRequests,
    no_sql_executed: true,
    no_cloud_apis_called: true,
  };

  const auditResult = auditDliTransportPlan({
    transportPlan,
    queueName: dliQueue,
  });

  const outDir = path.resolve("out");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const fullResult = {
    ...auditResult,
    migration_id: migrationId,
    dli_queue: dliQueue,
  };

  const safeResult = JSON.parse(scrubSecrets(JSON.stringify(fullResult)));
  const resultJsonPath = path.join(outDir, "dli_submit_job_audit_result.json");
  fs.writeFileSync(resultJsonPath, JSON.stringify(safeResult, null, 2), "utf-8");

  const lines = [];
  lines.push("# DLI Submit-Job Audit Report");
  lines.push("");
  lines.push("> **LOCAL AUDIT ONLY** — No cloud APIs called. No SQL executed. Validates request shape against DLI submit-job API spec.");
  lines.push("");
  lines.push("## Summary");
  lines.push("");
  lines.push(`**Status:** ${auditResult.status}`);
  lines.push(`**Valid:** ${auditResult.valid}`);
  lines.push(`**Migration ID:** ${migrationId}`);
  lines.push(`**DLI Queue:** ${dliQueue}`);
  lines.push(`**Requests audited:** ${auditResult.requests_audited}`);
  lines.push(`**Pass:** ${auditResult.pass_count || 0}`);
  lines.push(`**Warn:** ${auditResult.warn_count || 0}`);
  lines.push(`**Fail:** ${auditResult.fail_count || 0}`);
  lines.push("");

  if (auditResult.findings && auditResult.findings.length > 0) {
    lines.push("## Findings (FAIL)");
    lines.push("");
    for (const f of auditResult.findings) {
      lines.push(`- ${f}`);
    }
    lines.push("");
  }

  if (auditResult.warnings && auditResult.warnings.length > 0) {
    lines.push("## Warnings");
    lines.push("");
    for (const w of auditResult.warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  lines.push("## Per-Request Audit");
  lines.push("");
  lines.push("| # | Phase | Step | Type | Stmt Type | Audit Status |");
  lines.push("|---|-------|------|------|-----------|-------------|");
  if (auditResult.request_audits) {
    for (const ra of auditResult.request_audits) {
      lines.push(`| ${ra.index} | ${ra.phase} | ${ra.step_name} | ${ra.step_type} | ${ra.statement_type} | ${ra.audit_status} |`);
    }
  }
  lines.push("");

  lines.push("## Safety");
  lines.push("");
  lines.push("- Local audit only, no cloud APIs");
  lines.push("- No SQL execution");
  lines.push("- No runtime execution");
  lines.push("- Secrets redacted");
  lines.push("");
  lines.push("## Why Submit-Job May Fail Even When Preflight Passes");
  lines.push("");
  lines.push("- Preflight checks queue accessibility (GET /queues) but submit-job requires `dli:queue:submitJob` IAM permission");
  lines.push("- Missing `currentdb` for non-DDL statements can cause DLI to reject the job");
  lines.push("- Missing `queue_name` causes DLI to use the default queue which may not exist or may lack resources");
  lines.push("- Invalid `engine_type` or malformed `tags` can cause silent rejection");
  lines.push("- Region/project_id must be present for URL construction");
  lines.push("");

  const reportMdPath = path.join(outDir, "dli_submit_job_audit_report.md");
  fs.writeFileSync(reportMdPath, lines.join("\n"), "utf-8");

  const findingCount = (auditResult.findings || []).length;
  const warningCount = (auditResult.warnings || []).length;

  console.log("DLI submit-job audit complete.");
  console.log(`  Requests audited: ${auditResult.requests_audited}`);
  console.log(`  Findings: ${findingCount}`);
  console.log(`  Warnings: ${warningCount}`);
  console.log("Safety: local audit only, no cloud APIs, no SQL execution.");

  if (auditResult.status === "DLI_SUBMIT_JOB_AUDIT_FAIL") {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(scrubSecrets(err.message));
  process.exit(1);
});
