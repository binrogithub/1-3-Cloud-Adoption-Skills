const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");
const SQL_DIR = path.join(OUT_DIR, "dli_demo_sql");
const ARTIFACTS = path.resolve(ROOT, "..", "snowflake_to_dataarts_demo_output");

const INPUT_FILES = {
  runtime_plan_result: path.join(OUT_DIR, "runtime_plan_result.json"),
  runtime_plan_report: path.join(OUT_DIR, "runtime_plan_report.md"),
  dryrun_request: path.join(OUT_DIR, "dataarts_create_job_request.v1.dryrun.json"),
  sql_01: path.join(ARTIFACTS, "dataarts", "nodes", "01_load_silver_orders.sql"),
  sql_02: path.join(ARTIFACTS, "dataarts", "nodes", "02_build_gold_daily_sales.sql"),
  sql_03: path.join(ARTIFACTS, "dataarts", "nodes", "03_audit_pipeline.sql"),
  compat_report: path.join(ARTIFACTS, "analysis", "compatibility_report.md"),
};

const SOURCE_ROWS = [
  { order_id: 1, customer_id: 101, order_date: "2026-06-20", order_amount: 120.50 },
  { order_id: 2, customer_id: 102, order_date: "2026-06-20", order_amount: 300.00 },
  { order_id: 3, customer_id: 101, order_date: "2026-06-21", order_amount: 80.25 },
  { order_id: 4, customer_id: 103, order_date: "2026-06-21", order_amount: 450.10 },
  { order_id: 5, customer_id: 104, order_date: "2026-06-21", order_amount: 99.99 },
];

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

function generateCreateDatabaseSql() {
  return `CREATE DATABASE IF NOT EXISTS demo_migration;\n`;
}

function generateCreateRawOrdersSql() {
  return `CREATE TABLE IF NOT EXISTS demo_migration.raw_orders (
  order_id      INT,
  customer_id   INT,
  order_date    DATE,
  order_amount  DECIMAL(10,2),
  ingested_at   TIMESTAMP
);\n`;
}

function generateInsertRawOrdersSql() {
  const lines = [
    "INSERT INTO demo_migration.raw_orders (order_id, customer_id, order_date, order_amount, ingested_at)",
    "VALUES",
  ];
  const valueLines = SOURCE_ROWS.map((r, i) => {
    const comma = i < SOURCE_ROWS.length - 1 ? "," : ";";
    return `  (${r.order_id}, ${r.customer_id}, '${r.order_date}', ${r.order_amount.toFixed(2)}, CURRENT_TIMESTAMP())${comma}`;
  });
  return lines.concat(valueLines).join("\n") + "\n";
}

function generateCreateTaskAuditSql() {
  return `CREATE TABLE IF NOT EXISTS demo_migration.task_audit (
  pipeline_name  STRING,
  step_name      STRING,
  status         STRING,
  message        STRING,
  created_at     TIMESTAMP
);\n`;
}

function generateRuntimeSqlRecommendationMd() {
  const lines = [];
  lines.push("# Runtime SQL Recommendation");
  lines.push("");
  lines.push("## MERGE Risk in load_silver_orders");
  lines.push("");
  lines.push("The original `01_load_silver_orders.sql` uses `MERGE INTO`, which requires DLI Delta table format.");
  lines.push("For this demo with only 5 source rows, MERGE is unnecessary and risky if the DLI table format");
  lines.push("does not support it.");
  lines.push("");
  lines.push("## Recommended Demo-Safe Replacement");
  lines.push("");
  lines.push("Replace the MERGE with a full-refresh CTAS (Create Table As Select):");
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
  lines.push("### Why this is safe for the demo");
  lines.push("");
  lines.push("- All 5 source rows have `order_amount > 0`, so no data is lost.");
  lines.push("- CTAS is fully supported in DLI without Delta format requirements.");
  lines.push("- The result is identical to the MERGE for a fresh/empty target table.");
  lines.push("- This avoids the DLI Delta table format dependency entirely.");
  lines.push("");
  lines.push("### When NOT to use this in production");
  lines.push("");
  lines.push("- Production pipelines need incremental MERGE for upserts.");
  lines.push("- CTAS destroys and recreates the table on every run.");
  lines.push("- Use MERGE with Delta tables or INSERT OVERWRITE for partitioned tables in production.");
  lines.push("");
  return lines.join("\n");
}

function generateMarkdownReport(data) {
  const { timestamp, runtimePlanResult, sql01, sql02, sql03, compatReport } = data;

  const lines = [];

  lines.push("# DLI Demo Data Preparation Plan");
  lines.push("");
  lines.push(`**Timestamp:** ${timestamp}`);
  lines.push(`**Status:** PLAN_GENERATED — SQL scripts generated locally, no execution performed`);
  lines.push("");

  lines.push("## A. Objective");
  lines.push("");
  lines.push("The goal is to prepare the DLI-side demo data required to run the DataArts job");
  lines.push("`snowflake_to_dataarts_demo_v2` and validate functional equivalence with the original");
  lines.push("Snowflake Task Graph pipeline.");
  lines.push("");
  lines.push("This plan generates the DDL and DML SQL scripts needed to create the `demo_migration`");
  lines.push("database, its tables, and load the 5-row source dataset — but does **not** execute them.");
  lines.push("");

  lines.push("## B. Runtime Target");
  lines.push("");
  lines.push("| Field | Value |");
  lines.push("|-------|-------|");
  lines.push("| Preferred target engine | DLI |");
  lines.push("| DLI queue/resource | Must be confirmed before SQL execution |");
  lines.push("| DLI queue status | **NOT CONFIGURED — BLOCKER** |");
  lines.push("");

  lines.push("## C. Required Database and Tables");
  lines.push("");
  lines.push("The following DLI database and tables must be prepared:");
  lines.push("");
  lines.push("| # | Fully Qualified Name | Purpose |");
  lines.push("|---|----------------------|---------|");
  lines.push("| 1 | `demo_migration.raw_orders` | Source data landing table (5 rows from Snowflake) |");
  lines.push("| 2 | `demo_migration.silver_orders` | Clean/filtered orders (populated by load_silver_orders node) |");
  lines.push("| 3 | `demo_migration.gold_daily_sales` | Aggregated daily sales (populated by build_gold_daily_sales node) |");
  lines.push("| 4 | `demo_migration.task_audit` | Pipeline audit log (populated by audit_pipeline node) |");
  lines.push("");

  lines.push("## D. Source Data to Load into raw_orders");
  lines.push("");
  lines.push("The following 5 rows were used in the Snowflake source and must be loaded into `demo_migration.raw_orders`:");
  lines.push("");
  lines.push("| order_id | customer_id | order_date | order_amount |");
  lines.push("|----------|-------------|------------|--------------|");
  for (const r of SOURCE_ROWS) {
    lines.push(`| ${r.order_id} | ${r.customer_id} | ${r.order_date} | ${r.order_amount.toFixed(2)} |`);
  }
  lines.push("");
  lines.push("The `ingested_at` column will be set to `CURRENT_TIMESTAMP()` at insertion time.");
  lines.push("");

  lines.push("## E. SQL Preparation Plan");
  lines.push("");
  lines.push("The following SQL scripts have been generated under `out/dli_demo_sql/`:");
  lines.push("");
  lines.push("| # | File | Purpose |");
  lines.push("|---|------|---------|");
  lines.push("| 00 | `00_create_database.sql` | Create the `demo_migration` database if not exists |");
  lines.push("| 01 | `01_create_raw_orders.sql` | Create the `raw_orders` table |");
  lines.push("| 02 | `02_insert_raw_orders.sql` | Insert the 5 Snowflake source rows |");
  lines.push("| 03 | `03_create_task_audit.sql` | Create the `task_audit` table |");
  lines.push("| 04 | `04_runtime_sql_recommendation.md` | MERGE risk explanation and demo-safe replacement |");
  lines.push("");

  lines.push("### 00_create_database.sql");
  lines.push("");
  lines.push("```sql");
  lines.push("CREATE DATABASE IF NOT EXISTS demo_migration;");
  lines.push("```");
  lines.push("");

  lines.push("### 01_create_raw_orders.sql");
  lines.push("");
  lines.push("```sql");
  lines.push("CREATE TABLE IF NOT EXISTS demo_migration.raw_orders (");
  lines.push("  order_id      INT,");
  lines.push("  customer_id   INT,");
  lines.push("  order_date    DATE,");
  lines.push("  order_amount  DECIMAL(10,2),");
  lines.push("  ingested_at   TIMESTAMP");
  lines.push(");");
  lines.push("```");
  lines.push("");

  lines.push("### 02_insert_raw_orders.sql");
  lines.push("");
  lines.push("```sql");
  lines.push("INSERT INTO demo_migration.raw_orders (order_id, customer_id, order_date, order_amount, ingested_at)");
  lines.push("VALUES");
  for (let i = 0; i < SOURCE_ROWS.length; i++) {
    const r = SOURCE_ROWS[i];
    const comma = i < SOURCE_ROWS.length - 1 ? "," : ";";
    lines.push(`  (${r.order_id}, ${r.customer_id}, '${r.order_date}', ${r.order_amount.toFixed(2)}, CURRENT_TIMESTAMP())${comma}`);
  }
  lines.push("```");
  lines.push("");

  lines.push("### 03_create_task_audit.sql");
  lines.push("");
  lines.push("```sql");
  lines.push("CREATE TABLE IF NOT EXISTS demo_migration.task_audit (");
  lines.push("  pipeline_name  STRING,");
  lines.push("  step_name      STRING,");
  lines.push("  status         STRING,");
  lines.push("  message        STRING,");
  lines.push("  created_at     TIMESTAMP");
  lines.push(");");
  lines.push("```");
  lines.push("");

  lines.push("### 04_runtime_sql_recommendation.md");
  lines.push("");
  lines.push("Explains the MERGE risk in `load_silver_orders` and recommends the demo-safe replacement:");
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

  lines.push("## F. Runtime Blockers");
  lines.push("");
  lines.push("The following blockers prevent immediate execution of the SQL scripts:");
  lines.push("");
  lines.push("| # | Blocker |");
  lines.push("|---|---------|");
  lines.push("| 1 | DLI queue not yet confirmed |");
  lines.push("| 2 | DLI SQL execution API/command not yet implemented |");
  lines.push("| 3 | DataArts job still not published |");
  lines.push("| 4 | DataArts job still not started |");
  lines.push("| 5 | SQL runtime adaptation not applied to job yet |");
  lines.push("");

  lines.push("## G. Expected Validation After Successful Run");
  lines.push("");
  lines.push("If the demo pipeline runs successfully with the 5-row source dataset:");
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

  lines.push("## H. Safety Statement");
  lines.push("");
  lines.push("> **No Huawei Cloud API call was made.**");
  lines.push(">");
  lines.push("> - No DLI SQL was executed.");
  lines.push("> - No DataArts job was published.");
  lines.push("> - No DataArts job was started.");
  lines.push("> - No resources were created, updated, or deleted.");
  lines.push(">");
  lines.push("> This command performed a read-only assessment of local files only.");
  lines.push("> All generated SQL scripts are local files and have not been submitted to any cloud service.");
  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Deploy Agent: PREPARE DLI DEMO DATA — PLAN (read-only, local-only) ===\n");

  try {
    console.log("[1/7] Reading input files...\n");

    const runtimePlanResult = readFileJson(INPUT_FILES.runtime_plan_result, "runtime plan result");
    const runtimePlanReport = readFileText(INPUT_FILES.runtime_plan_report, "runtime plan report");
    const dryrunRequest = readFileJson(INPUT_FILES.dryrun_request, "v1 dry-run request");
    const sql01 = readFileText(INPUT_FILES.sql_01, "SQL node 01");
    const sql02 = readFileText(INPUT_FILES.sql_02, "SQL node 02");
    const sql03 = readFileText(INPUT_FILES.sql_03, "SQL node 03");
    const compatReport = readFileText(INPUT_FILES.compat_report, "compatibility report");

    console.log("  [READ] runtime_plan_result.json");
    console.log("  [READ] runtime_plan_report.md");
    console.log("  [READ] dataarts_create_job_request.v1.dryrun.json");
    console.log("  [READ] 01_load_silver_orders.sql");
    console.log("  [READ] 02_build_gold_daily_sales.sql");
    console.log("  [READ] 03_audit_pipeline.sql");
    console.log("  [READ] compatibility_report.md");
    console.log("");

    console.log("[2/7] Validating runtime plan status...\n");
    console.log(`  Runtime status: ${runtimePlanResult.status}`);
    console.log(`  Runtime ready:  ${runtimePlanResult.runtime_ready}`);
    console.log(`  Blockers:       ${runtimePlanResult.blockers.length}`);
    console.log("");

    console.log("[3/7] Generating SQL scripts...\n");

    if (!fs.existsSync(SQL_DIR)) {
      fs.mkdirSync(SQL_DIR, { recursive: true });
    }

    const sql00 = generateCreateDatabaseSql();
    const sql01Create = generateCreateRawOrdersSql();
    const sql02Insert = generateInsertRawOrdersSql();
    const sql03Audit = generateCreateTaskAuditSql();
    const recMd = generateRuntimeSqlRecommendationMd();

    const sqlFiles = {
      "00_create_database.sql": sql00,
      "01_create_raw_orders.sql": sql01Create,
      "02_insert_raw_orders.sql": sql02Insert,
      "03_create_task_audit.sql": sql03Audit,
      "04_runtime_sql_recommendation.md": recMd,
    };

    for (const [filename, content] of Object.entries(sqlFiles)) {
      const filePath = path.join(SQL_DIR, filename);
      fs.writeFileSync(filePath, content, "utf-8");
      console.log(`  [WRITE] out/dli_demo_sql/${filename}`);
    }
    console.log("");

    console.log("[4/7] Assessing runtime blockers...\n");

    const blockers = [
      "DLI queue not yet confirmed",
      "DLI SQL execution API/command not yet implemented",
      "DataArts job still not published",
      "DataArts job still not started",
      "SQL runtime adaptation not applied to job yet",
    ];

    for (const b of blockers) {
      console.log(`  [BLOCKER] ${b}`);
    }
    console.log("");

    console.log("[5/7] Generating plan report...\n");

    const timestamp = new Date().toISOString();

    const mdReport = generateMarkdownReport({
      timestamp,
      runtimePlanResult,
      sql01,
      sql02,
      sql03,
      compatReport,
    });

    const mdPath = path.join(OUT_DIR, "prepare_dli_demo_data_plan_report.md");
    fs.writeFileSync(mdPath, mdReport, "utf-8");
    console.log(`  [WRITE] out/prepare_dli_demo_data_plan_report.md`);
    console.log("");

    console.log("[6/7] Generating plan result JSON...\n");

    const planResult = {
      timestamp,
      status: "PLAN_GENERATED",
      runtime_ready_after_plan: false,
      generated_sql_files: Object.keys(sqlFiles).map((f) => `out/dli_demo_sql/${f}`),
      blockers,
      next_recommended_command: "npm run prepare-dli-demo-data (execute SQL against DLI)",
      safety: {
        no_api_calls_made: true,
        no_dli_sql_executed: true,
        no_dataarts_job_published: true,
        no_dataarts_job_started: true,
        no_resources_created: true,
        no_resources_updated: true,
        no_resources_deleted: true,
        no_secrets_included: true,
      },
    };

    const jsonPath = path.join(OUT_DIR, "prepare_dli_demo_data_plan_result.json");
    fs.writeFileSync(jsonPath, JSON.stringify(planResult, null, 2), "utf-8");
    console.log(`  [WRITE] out/prepare_dli_demo_data_plan_result.json`);
    console.log("");

    console.log("[7/7] Summary\n");

    console.log("=== DLI Demo Data Preparation Plan Summary ===\n");
    console.log(`  Status:              PLAN_GENERATED`);
    console.log(`  Runtime Ready:       false`);
    console.log(`  SQL Files Generated: ${Object.keys(sqlFiles).length}`);
    console.log(`  Blockers:            ${blockers.length}`);
    console.log(`  Next Step:           ${planResult.next_recommended_command}`);
    console.log("");

    console.log("=== Generated SQL Files ===\n");
    for (const f of Object.keys(sqlFiles)) {
      console.log(`  out/dli_demo_sql/${f}`);
    }
    console.log("");

    console.log("=== Blockers ===\n");
    for (const b of blockers) {
      console.log(`  - ${b}`);
    }
    console.log("");

    console.log("=== Safety ===\n");
    console.log("  No Huawei Cloud API call was made.");
    console.log("  No DLI SQL was executed.");
    console.log("  No DataArts job was published.");
    console.log("  No DataArts job was started.");
    console.log("  No resources were created, updated, or deleted.");
    console.log("");

    console.log("Reports saved:");
    console.log(`  ${mdPath}`);
    console.log(`  ${jsonPath}`);

    process.exit(0);
  } catch (err) {
    console.error(`PREPARE DLI DEMO DATA PLAN FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
