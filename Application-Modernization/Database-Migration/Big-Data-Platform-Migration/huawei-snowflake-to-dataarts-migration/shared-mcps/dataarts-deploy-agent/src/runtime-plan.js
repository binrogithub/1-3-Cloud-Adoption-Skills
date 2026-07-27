const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");
const ARTIFACTS = path.resolve(ROOT, "..", "snowflake_to_dataarts_demo_output");

const INPUT_FILES = {
  verify_result: path.join(OUT_DIR, "verify_job_result.json"),
  export_result: path.join(OUT_DIR, "exported_job", "export_job_definition_result.json"),
  dryrun_request: path.join(OUT_DIR, "dataarts_create_job_request.v1.dryrun.json"),
  sql_01: path.join(ARTIFACTS, "dataarts", "nodes", "01_load_silver_orders.sql"),
  sql_02: path.join(ARTIFACTS, "dataarts", "nodes", "02_build_gold_daily_sales.sql"),
  sql_03: path.join(ARTIFACTS, "dataarts", "nodes", "03_audit_pipeline.sql"),
  compat_report: path.join(ARTIFACTS, "analysis", "compatibility_report.md"),
};

function readFileJson(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing ${label}: ${filePath}`);
  }
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

function readFileText(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing ${label}: ${filePath}`);
  }
  return fs.readFileSync(filePath, "utf-8");
}

function classifySql(sql, nodeName) {
  const upper = sql.toUpperCase();
  if (upper.includes("MERGE INTO")) {
    return { operation: "MERGE INTO", risk: "Medium", riskDetail: "DLI MERGE support depends on table format (Delta required). If unsupported, recommend replacing with demo-safe INSERT OVERWRITE or CTAS." };
  }
  if (upper.includes("DROP TABLE") && upper.includes("CREATE TABLE")) {
    return { operation: "DROP TABLE IF EXISTS + CREATE TABLE AS SELECT", risk: "Low", riskDetail: "Destructive replacement of gold table. Acceptable for demo, not production." };
  }
  if (upper.includes("INSERT INTO")) {
    return { operation: "INSERT INTO", risk: "Low", riskDetail: "Simple INSERT. Low risk." };
  }
  return { operation: "UNKNOWN", risk: "Unknown", riskDetail: "Could not classify SQL operation." };
}

function generateMarkdownReport(data) {
  const {
    timestamp,
    jobName,
    processType,
    schedule,
    nodes,
    dependencyChain,
    verifyResult,
    exportResult,
    sqlClassifications,
    blockers,
    prerequisites,
  } = data;

  const lines = [];

  lines.push("# Runtime Plan Report");
  lines.push("");
  lines.push(`**Timestamp:** ${timestamp}`);
  lines.push(`**Status:** RUNTIME NOT READY — blockers exist that must be resolved before pipeline execution`);
  lines.push("");

  lines.push("## A. Current Job Status");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push(`| Job name | ${jobName} |`);
  lines.push(`| processType | ${processType} |`);
  lines.push(`| Schedule | ${schedule} |`);
  lines.push(`| Nodes | ${nodes.join(", ")} |`);
  lines.push(`| Dependency chain | ${dependencyChain} |`);
  lines.push("| Created | Yes (HTTP 204) |");
  lines.push(`| Verified | Yes (${verifyResult.summary.pass} PASS, ${verifyResult.summary.warn} WARN, ${verifyResult.summary.fail} FAIL) |`);
  lines.push(`| Exported | Yes (HTTP ${exportResult.http_status}, ${exportResult.response_format}) |`);
  lines.push("| Published | No |");
  lines.push("| Started | No |");
  lines.push("");

  lines.push("## B. Runtime Prerequisites");
  lines.push("");
  lines.push("Before the DataArts job can be executed, the following prerequisites must be satisfied:");
  lines.push("");
  for (const p of prerequisites) {
    lines.push(`- ${p.status === "MET" ? "[MET]" : "[BLOCKER]"} ${p.item}`);
  }
  lines.push("");

  lines.push("## C. SQL Compatibility Assessment");
  lines.push("");
  lines.push("Each SQL node was inspected and classified for runtime risk:");
  lines.push("");
  lines.push("| Node | Operation | Risk | Detail |");
  lines.push("|------|-----------|------|--------|");
  for (const sc of sqlClassifications) {
    lines.push(`| ${sc.node} | ${sc.operation} | ${sc.risk} | ${sc.riskDetail} |`);
  }
  lines.push("");

  lines.push("### Node Details");
  lines.push("");

  lines.push("#### 01_load_silver_orders.sql");
  lines.push("- **Operation:** MERGE INTO demo_migration.silver_orders");
  lines.push("- **Risk:** DLI MERGE support depends on table format (Delta/OBS tables required).");
  lines.push("- **If unsupported:** Recommend replacing MERGE with demo-safe INSERT OVERWRITE or CTAS.");
  lines.push("");

  lines.push("#### 02_build_gold_daily_sales.sql");
  lines.push("- **Operation:** DROP TABLE IF EXISTS + CREATE TABLE AS SELECT");
  lines.push("- **Risk:** Destructive replacement of gold_daily_sales table on each run.");
  lines.push("- **Acceptable for demo, not production.** Production should use INSERT OVERWRITE or incremental logic.");
  lines.push("");

  lines.push("#### 03_audit_pipeline.sql");
  lines.push("- **Operation:** INSERT INTO demo_migration.task_audit");
  lines.push("- **Risk:** Low. Simple INSERT with constant values.");
  lines.push("");

  lines.push("## D. Recommended Demo-Safe Runtime Adaptation");
  lines.push("");
  lines.push("Because this is a demo and the source data has only 5 rows, the following simplified DLI-compatible SQL strategy is recommended:");
  lines.push("");
  lines.push("### Replace MERGE with full refresh for silver_orders");
  lines.push("");
  lines.push("```sql");
  lines.push("DROP TABLE IF EXISTS demo_migration.silver_orders;");
  lines.push("CREATE TABLE demo_migration.silver_orders AS");
  lines.push("SELECT");
  lines.push("  order_id,");
  lines.push("  customer_id,");
  lines.push("  order_date,");
  lines.push("  order_amount,");
  lines.push("  CURRENT_TIMESTAMP() AS processed_at");
  lines.push("FROM demo_migration.raw_orders");
  lines.push("WHERE order_amount > 0;");
  lines.push("```");
  lines.push("");
  lines.push("### Keep gold CTAS (unchanged)");
  lines.push("");
  lines.push("```sql");
  lines.push("DROP TABLE IF EXISTS demo_migration.gold_daily_sales;");
  lines.push("CREATE TABLE demo_migration.gold_daily_sales AS");
  lines.push("SELECT");
  lines.push("  order_date,");
  lines.push("  COUNT(*)      AS order_count,");
  lines.push("  SUM(order_amount)  AS total_amount,");
  lines.push("  AVG(order_amount)  AS avg_amount,");
  lines.push("  CURRENT_TIMESTAMP() AS processed_at");
  lines.push("FROM demo_migration.silver_orders");
  lines.push("GROUP BY order_date;");
  lines.push("```");
  lines.push("");
  lines.push("### Keep audit INSERT (unchanged)");
  lines.push("");
  lines.push("```sql");
  lines.push("INSERT INTO demo_migration.task_audit (");
  lines.push("  pipeline_name, step_name, status, message");
  lines.push(") VALUES (");
  lines.push("  'snowflake_to_dataarts_demo',");
  lines.push("  'task_graph_completed',");
  lines.push("  'SUCCESS',");
  lines.push("  'DataArts pipeline finished successfully (migrated from Snowflake)'");
  lines.push(");");
  lines.push("```");
  lines.push("");
  lines.push("> **Note:** This is demo-safe but not production incremental logic. A production pipeline would use MERGE for incremental upserts and INSERT OVERWRITE for partitioned gold tables.");
  lines.push("");

  lines.push("## E. Expected Validation Results After Run");
  lines.push("");
  lines.push("If the demo runs successfully with the 5-row source dataset, the following results are expected:");
  lines.push("");
  lines.push("| Table | Expected Row Count | Notes |");
  lines.push("|-------|--------------------|-------|");
  lines.push("| demo_migration.raw_orders | 5 | Source data (5 orders) |");
  lines.push("| demo_migration.silver_orders | 5 | All 5 orders have order_amount > 0 |");
  lines.push("| demo_migration.gold_daily_sales | 2 | Two distinct order_dates |");
  lines.push("| demo_migration.task_audit | >= 1 | At least 1 SUCCESS row |");
  lines.push("");
  lines.push("### Expected Gold Aggregates");
  lines.push("");
  lines.push("| order_date | order_count | total_amount |");
  lines.push("|------------|-------------|--------------|");
  lines.push("| 2026-06-20 | 2 | 420.50 |");
  lines.push("| 2026-06-21 | 3 | 630.34 |");
  lines.push("");

  lines.push("## F. Recommended Next Commands (Not Implemented Yet)");
  lines.push("");
  lines.push("The following commands are documented for future implementation. They are **not** implemented yet:");
  lines.push("");
  lines.push("| Command | Purpose |");
  lines.push("|---------|---------|");
  lines.push("| `npm run prepare-dli-demo-data` | Create DLI database, tables, and load 5 source rows into raw_orders |");
  lines.push("| `npm run adapt-sql-for-demo-runtime` | Replace MERGE with demo-safe CTAS in load_silver_orders SQL |");
  lines.push("| `npm run publish:plan` | Assess publish readiness (already exists) |");
  lines.push("| `npm run publish-job -- --confirm` | Publish the DataArts job |");
  lines.push("| `npm run start:plan` | Assess start readiness |");
  lines.push("| `npm run start-job -- --confirm` | Start the DataArts job |");
  lines.push("| `npm run runtime-validate` | Validate table contents after pipeline run |");
  lines.push("");

  lines.push("## G. Safety Statement");
  lines.push("");
  lines.push("> **No Huawei Cloud API write operation was executed.**");
  lines.push(">");
  lines.push("> - No DataArts job was published.");
  lines.push("> - No DataArts job was started.");
  lines.push("> - No DLI SQL was executed.");
  lines.push("> - No resources were created, updated, or deleted.");
  lines.push(">");
  lines.push("> This command performed a read-only assessment of local files only.");
  lines.push("> No Huawei Cloud API calls were made.");
  lines.push("> No write, publish, start, or destructive operation was executed.");
  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Deploy Agent: RUNTIME PLAN (read-only, local-only) ===\n");

  try {
    console.log("[1/6] Reading input files...\n");

    const verifyResult = readFileJson(INPUT_FILES.verify_result, "verify-job result");
    const exportResult = readFileJson(INPUT_FILES.export_result, "export-job result");
    const dryrunRequest = readFileJson(INPUT_FILES.dryrun_request, "v1 dry-run request");
    const sql01 = readFileText(INPUT_FILES.sql_01, "SQL node 01");
    const sql02 = readFileText(INPUT_FILES.sql_02, "SQL node 02");
    const sql03 = readFileText(INPUT_FILES.sql_03, "SQL node 03");
    const compatReport = readFileText(INPUT_FILES.compat_report, "compatibility report");

    console.log("  [READ] verify_job_result.json");
    console.log("  [READ] export_job_definition_result.json");
    console.log("  [READ] dataarts_create_job_request.v1.dryrun.json");
    console.log("  [READ] 01_load_silver_orders.sql");
    console.log("  [READ] 02_build_gold_daily_sales.sql");
    console.log("  [READ] 03_audit_pipeline.sql");
    console.log("  [READ] compatibility_report.md");
    console.log("");

    const v1Body = dryrunRequest.body || dryrunRequest;
    const jobName = v1Body.name;
    const processType = v1Body.processType;
    const schedule = (v1Body.schedule && v1Body.schedule.cron && v1Body.schedule.cron.expression) || "N/A";
    const nodes = (v1Body.nodes || []).map((n) => n.name);
    const depEdges = [];
    for (const n of v1Body.nodes || []) {
      if (n.preNodeName && n.preNodeName.length > 0) {
        for (const dep of n.preNodeName) {
          depEdges.push(`${dep} -> ${n.name}`);
        }
      }
    }
    const dependencyChain = depEdges.length > 0 ? depEdges.join(", ") : "(none)";

    console.log("[2/6] Classifying SQL nodes...\n");

    const sqlClassifications = [
      { node: "load_silver_orders", ...classifySql(sql01, "load_silver_orders") },
      { node: "build_gold_daily_sales", ...classifySql(sql02, "build_gold_daily_sales") },
      { node: "audit_pipeline", ...classifySql(sql03, "audit_pipeline") },
    ];

    for (const sc of sqlClassifications) {
      console.log(`  [${sc.risk}] ${sc.node}: ${sc.operation}`);
    }
    console.log("");

    console.log("[3/6] Assessing runtime prerequisites...\n");

    const prerequisites = [
      { item: "DLI or DWS execution engine must be confirmed", status: "BLOCKER" },
      { item: "If target engine is DLI, a DLI queue/resource must exist", status: "BLOCKER" },
      { item: "Database demo_migration must exist", status: "BLOCKER" },
      { item: "Table demo_migration.raw_orders must exist or be created", status: "BLOCKER" },
      { item: "Table demo_migration.silver_orders must exist or be created", status: "BLOCKER" },
      { item: "Table demo_migration.gold_daily_sales must exist or be created", status: "BLOCKER" },
      { item: "Table demo_migration.task_audit must exist or be created", status: "BLOCKER" },
      { item: "raw_orders must contain the same 5 source rows used in Snowflake", status: "BLOCKER" },
      { item: "task_audit must be available before audit_pipeline runs", status: "BLOCKER" },
    ];

    const blockers = prerequisites.filter((p) => p.status === "BLOCKER").map((p) => p.item);

    for (const p of prerequisites) {
      console.log(`  [${p.status}] ${p.item}`);
    }
    console.log("");

    console.log("[4/6] Assessing SQL risks...\n");

    const sqlRisks = sqlClassifications.map((sc) => ({
      node: sc.node,
      operation: sc.operation,
      risk: sc.risk,
      detail: sc.riskDetail,
    }));

    const hasMediumRisk = sqlRisks.some((r) => r.risk === "Medium");
    if (hasMediumRisk) {
      console.log("  [MEDIUM] MERGE INTO in load_silver_orders requires Delta table format or demo-safe adaptation");
    }
    console.log(`  Total SQL risks: ${sqlRisks.length} (${sqlRisks.filter((r) => r.risk === "Medium").length} medium, ${sqlRisks.filter((r) => r.risk === "Low").length} low)`);
    console.log("");

    console.log("[5/6] Generating reports...\n");

    const timestamp = new Date().toISOString();

    const runtimeReady = false;
    const recommendedNextStep = "prepare-dli-demo-data (create DLI database, tables, load source data)";

    const runtimePlanResult = {
      timestamp,
      status: "RUNTIME_NOT_READY",
      job_name: jobName,
      runtime_ready: runtimeReady,
      blockers,
      prerequisites: prerequisites.map((p) => ({ item: p.item, status: p.status })),
      sql_risks: sqlRisks,
      recommended_next_step: recommendedNextStep,
      safety: {
        no_api_calls_made: true,
        no_publish: true,
        no_start: true,
        no_run: true,
        no_update: true,
        no_delete: true,
        no_dli_sql_executed: true,
        no_resources_created: true,
        no_resources_modified: true,
        no_secrets_included: true,
      },
    };

    const mdReport = generateMarkdownReport({
      timestamp,
      jobName,
      processType,
      schedule,
      nodes,
      dependencyChain,
      verifyResult,
      exportResult,
      sqlClassifications,
      blockers,
      prerequisites,
    });

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const mdPath = path.join(OUT_DIR, "runtime_plan_report.md");
    const jsonPath = path.join(OUT_DIR, "runtime_plan_result.json");

    fs.writeFileSync(mdPath, mdReport, "utf-8");
    fs.writeFileSync(jsonPath, JSON.stringify(runtimePlanResult, null, 2), "utf-8");

    console.log(`  [WRITE] ${path.relative(ROOT, mdPath)}`);
    console.log(`  [WRITE] ${path.relative(ROOT, jsonPath)}`);
    console.log("");

    console.log("[6/6] Summary\n");

    console.log("=== Runtime Readiness Summary ===\n");
    console.log(`  Job Name:          ${jobName}`);
    console.log(`  Runtime Ready:     ${runtimeReady}`);
    console.log(`  Blockers:          ${blockers.length}`);
    console.log(`  SQL Risks:         ${sqlRisks.length} (${sqlRisks.filter((r) => r.risk === "Medium").length} medium, ${sqlRisks.filter((r) => r.risk === "Low").length} low)`);
    console.log(`  Next Step:         ${recommendedNextStep}`);
    console.log("");

    console.log("=== Blockers ===\n");
    for (const b of blockers) {
      console.log(`  - ${b}`);
    }
    console.log("");

    console.log("=== SQL Risks ===\n");
    for (const r of sqlRisks) {
      console.log(`  [${r.risk}] ${r.node}: ${r.operation}`);
    }
    console.log("");

    console.log("Safety: No Huawei Cloud API write operation was executed.");
    console.log("No DataArts job was published, started, or run.");
    console.log("No DLI SQL was executed. No resources were created, updated, or deleted.\n");

    console.log("Reports saved:");
    console.log(`  ${mdPath}`);
    console.log(`  ${jsonPath}`);

    process.exit(0);
  } catch (err) {
    console.error(`RUNTIME PLAN FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
