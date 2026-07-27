const fs = require("fs");
const path = require("path");
const config = require("./config");
const runtimeTarget = require("./runtime-target");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

const EXPECTED_SQL_FILE_COUNT = 5;

const RUNTIME_EXPECTATIONS = {
  raw_orders: 5,
  silver_orders: 5,
  gold_daily_sales: 2,
  task_audit_success_count: ">=1",
  gold_aggregates: [
    { date: "2026-06-20", order_count: 2, total_amount: 420.5 },
    { date: "2026-06-21", order_count: 3, total_amount: 630.34 },
  ],
};

const PLANNED_COMMANDS = [
  { step: 1, name: "validate-env", cmd: "npm run validate-env", desc: "Validate environment and credentials" },
  { step: 2, name: "dry-run", cmd: "npm run dry-run", desc: "Generate dry-run V1 request payload" },
  { step: 3, name: "inspect-request", cmd: "npm run inspect-request", desc: "Inspect generated request payload" },
  { step: 4, name: "audit-payload", cmd: "npm run audit-payload", desc: "Audit payload for safety" },
  { step: 5, name: "live-validate", cmd: "npm run live-validate", desc: "Live API read-only validation" },
  { step: 6, name: "deploy:plan", cmd: "npm run deploy:plan", desc: "Deployment plan (read-only)" },
  { step: 7, name: "reset-dli-demo-data", cmd: "npm run reset-dli-demo-data -- --confirm", desc: "Reset DLI demo data (DROP + CREATE + INSERT)" },
  { step: 8, name: "dli:validate-demo-data", cmd: "npm run dli:validate-demo-data", desc: "Validate DLI demo data after reset" },
  { step: 9, name: "create-job", cmd: "npm run create-job -- --confirm", desc: "Create DataArts job (POST)" },
  { step: 10, name: "verify-job", cmd: "npm run verify-job", desc: "Verify created job structure" },
  { step: 11, name: "export-job-definition", cmd: "npm run export-job-definition", desc: "Export job definition for audit" },
  { step: 12, name: "run-immediate:plan", cmd: "npm run run-immediate:plan", desc: "Plan run-immediate (read-only)" },
  { step: 13, name: "run-immediate-job", cmd: "npm run run-immediate-job -- --confirm", desc: "Execute job via run-immediate (one-time)" },
  { step: 14, name: "runtime-validate", cmd: "npm run runtime-validate", desc: "Validate DLI output equivalence" },
];

function countSqlStatements(sql) {
  const trimmed = sql.trim();
  if (!trimmed) return 0;
  const lines = trimmed
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("--"));
  const joined = lines.join(" ");
  const semicolons = (joined.match(/;/g) || []).length;
  return Math.max(1, semicolons);
}

function main() {
  console.log("=== DataArts Deploy Agent: ONE-SHOT DEMO PLAN (read-only) ===\n");

  try {
    console.log("[1/7] Loading and validating environment...\n");
    const env = config.load();
    config.validate(env);

    const safe = config.mask(env);
    console.log("Configuration (masked):");
    for (const [k, v] of Object.entries(safe)) {
      console.log(`  ${k} = ${v}`);
    }
    console.log("");

    console.log("[2/7] Resolving dynamic runtime target...\n");

    const target = runtimeTarget.resolve();

    if (!target.valid) {
      console.error("ABORTED: Runtime target is invalid:\n");
      for (const err of target.errors) {
        console.error(`  - ${err}`);
      }
      console.error("");
      console.error("Provide --job-name and --artifacts-dir via CLI args, MCP arguments, or env vars.");
      process.exit(1);
    }

    const { jobName, artifactsDir, dliQueue } = target;

    console.log(`  job_name     = ${jobName}`);
    console.log(`  artifact_dir = ${artifactsDir}`);
    console.log(`  dli_queue    = ${dliQueue}`);
    console.log("");

    console.log("[3/7] Reading artifact folder...\n");

    const resolvedArtifactsDir = path.resolve(ROOT, artifactsDir);
    if (!fs.existsSync(resolvedArtifactsDir)) {
      throw new Error(`Artifact folder does not exist: ${resolvedArtifactsDir}`);
    }
    console.log(`  Artifact folder: ${resolvedArtifactsDir}`);

    const sqlDir = path.join(resolvedArtifactsDir, "dataarts", "nodes");
    if (!fs.existsSync(sqlDir)) {
      throw new Error(`SQL nodes folder does not exist: ${sqlDir}`);
    }
    console.log(`  SQL nodes folder: ${sqlDir}`);

    const sqlFiles = fs.readdirSync(sqlDir).filter((f) => f.endsWith(".sql")).sort();
    console.log(`  SQL files found: ${sqlFiles.length}`);
    for (const f of sqlFiles) {
      console.log(`    - ${f}`);
    }
    console.log("");

    console.log("[4/7] Validating SQL files...\n");

    if (sqlFiles.length !== EXPECTED_SQL_FILE_COUNT) {
      throw new Error(
        `Expected ${EXPECTED_SQL_FILE_COUNT} SQL files, found ${sqlFiles.length} in ${sqlDir}`
      );
    }
    console.log(`  SQL file count: ${sqlFiles.length} (OK, expected ${EXPECTED_SQL_FILE_COUNT})`);

    const sqlStatements = [];
    for (const f of sqlFiles) {
      const filePath = path.join(sqlDir, f);
      const content = fs.readFileSync(filePath, "utf-8");
      const stmtCount = countSqlStatements(content);
      sqlStatements.push({ file: f, statementCount: stmtCount });
      console.log(`  ${f}: ${stmtCount} statement(s)`);
    }

    const singleStatementFiles = sqlStatements.filter((s) => s.statementCount === 1);
    if (singleStatementFiles.length === sqlFiles.length) {
      console.log("  All SQL files contain exactly 1 statement (OK)");
    } else {
      console.log("  WARNING: Some SQL files contain multiple statements");
    }
    console.log("");

    console.log("[5/7] Confirming runtime validation expectations...\n");

    console.log("  Expected data counts:");
    console.log(`    raw_orders = ${RUNTIME_EXPECTATIONS.raw_orders}`);
    console.log(`    silver_orders = ${RUNTIME_EXPECTATIONS.silver_orders}`);
    console.log(`    gold_daily_sales = ${RUNTIME_EXPECTATIONS.gold_daily_sales}`);
    console.log(`    task_audit_success_count ${RUNTIME_EXPECTATIONS.task_audit_success_count}`);
    console.log("");

    console.log("  Expected gold aggregates:");
    for (const ga of RUNTIME_EXPECTATIONS.gold_aggregates) {
      console.log(`    ${ga.date}: order_count = ${ga.order_count}, total_amount = ${ga.total_amount}`);
    }
    console.log("");

    console.log("[6/7] Printing full planned sequence...\n");

    console.log("  ┌──────────────────────────────────────────────────────────────────────────┐");
    console.log("  │ ONE-SHOT DEMO: PLANNED EXECUTION SEQUENCE                               │");
    console.log("  ├──────────────────────────────────────────────────────────────────────────┤");
    for (const cmd of PLANNED_COMMANDS) {
      const stepStr = String(cmd.step).padStart(2, " ");
      console.log(`  │ [${stepStr}/14] ${cmd.name.padEnd(25)} ${cmd.desc.padEnd(40)} │`);
    }
    console.log("  ├──────────────────────────────────────────────────────────────────────────┤");
    console.log("  │ Stop immediately on any critical failure.                               │");
    console.log("  │ No publish, no /start, no delete, no update, no overwrite.              │");
    console.log("  └──────────────────────────────────────────────────────────────────────────┘");
    console.log("");

    console.log("[7/7] Generating plan reports...\n");

    const timestamp = new Date().toISOString();

    const planJson = {
      timestamp,
      status: "PLAN_READY",
      job_name: jobName,
      artifact_dir: artifactsDir,
      artifact_dir_resolved: resolvedArtifactsDir,
      dli_queue: dliQueue,
      sql_files: sqlStatements,
      all_single_statement: singleStatementFiles.length === sqlFiles.length,
      runtime_expectations: RUNTIME_EXPECTATIONS,
      planned_commands: PLANNED_COMMANDS.map((c) => ({
        step: c.step,
        name: c.name,
        cmd: c.cmd,
        desc: c.desc,
      })),
      no_api_write_calls: true,
      safety: {
        no_publish: true,
        no_scheduled_start: true,
        no_delete: true,
        no_update: true,
        no_overwrite: true,
        only_run_immediate_for_execution: true,
        stop_on_critical_failure: true,
        abort_if_job_exists: true,
      },
    };

    const lines = [];
    lines.push("# One-Shot Demo Plan Report");
    lines.push("");
    lines.push(`**Timestamp:** ${timestamp}`);
    lines.push(`**Status:** PLAN READY`);
    lines.push(`**Job Name:** ${jobName}`);
    lines.push(`**Artifact Dir:** ${artifactsDir}`);
    lines.push(`**DLI Queue:** ${dliQueue}`);
    lines.push("");

    lines.push("## Runtime Target (Dynamic)");
    lines.push("");
    lines.push("| Field | Value | Source |");
    lines.push("|-------|-------|--------|");
    lines.push(`| job_name | ${jobName} | CLI / MCP / env |`);
    lines.push(`| artifact_dir | ${artifactsDir} | CLI / MCP / env |`);
    lines.push(`| dli_queue | ${dliQueue} | CLI / MCP / env / default |`);
    lines.push("");

    lines.push("## SQL Files");
    lines.push("");
    lines.push("| File | Statements |");
    lines.push("|------|------------|");
    for (const s of sqlStatements) {
      lines.push(`| ${s.file} | ${s.statementCount} |`);
    }
    lines.push("");

    lines.push("## Runtime Validation Expectations");
    lines.push("");
    lines.push("| Check | Expected |");
    lines.push("|-------|----------|");
    lines.push(`| raw_orders count | ${RUNTIME_EXPECTATIONS.raw_orders} |`);
    lines.push(`| silver_orders count | ${RUNTIME_EXPECTATIONS.silver_orders} |`);
    lines.push(`| gold_daily_sales count | ${RUNTIME_EXPECTATIONS.gold_daily_sales} |`);
    lines.push(`| task_audit_success_count | ${RUNTIME_EXPECTATIONS.task_audit_success_count} |`);
    for (const ga of RUNTIME_EXPECTATIONS.gold_aggregates) {
      lines.push(`| ${ga.date} order_count | ${ga.order_count} |`);
      lines.push(`| ${ga.date} total_amount | ${ga.total_amount} |`);
    }
    lines.push("");

    lines.push("## Planned Execution Sequence");
    lines.push("");
    lines.push("| Step | Command | Description |");
    lines.push("|------|---------|-------------|");
    for (const cmd of PLANNED_COMMANDS) {
      lines.push(`| ${cmd.step} | \`${cmd.cmd}\` | ${cmd.desc} |`);
    }
    lines.push("");

    lines.push("## Safety Statement");
    lines.push("");
    lines.push("> **No Huawei Cloud API write operation was executed.**");
    lines.push(">");
    lines.push("> This plan performed read-only local analysis only.");
    lines.push("> No publish, no /start, no delete, no update, no overwrite operation was executed.");
    lines.push("> The actual one-shot will use only run-immediate for one-time execution.");
    lines.push("> It will stop immediately on any critical failure.");
    lines.push("> If the target job already exists, it will abort safely.");
    lines.push("");

    const mdReport = lines.join("\n");

    if (!fs.existsSync(OUT_DIR)) {
      fs.mkdirSync(OUT_DIR, { recursive: true });
    }

    const mdPath = path.join(OUT_DIR, "demo_one_shot_plan_report.md");
    const jsonPath = path.join(OUT_DIR, "demo_one_shot_plan_result.json");

    fs.writeFileSync(mdPath, mdReport, "utf-8");
    fs.writeFileSync(jsonPath, JSON.stringify(planJson, null, 2), "utf-8");

    console.log("=== One-Shot Demo Plan Summary ===\n");
    console.log(`  Status:        PLAN READY`);
    console.log(`  Job Name:      ${jobName}`);
    console.log(`  Artifact Dir:  ${artifactsDir}`);
    console.log(`  DLI Queue:     ${dliQueue}`);
    console.log(`  SQL Files:     ${sqlFiles.length} (${singleStatementFiles.length === sqlFiles.length ? "all single-statement" : "multi-statement detected"})`);
    console.log(`  Commands:      ${PLANNED_COMMANDS.length}`);
    console.log("");
    console.log("Safety: No API write calls. Read-only local analysis only.");
    console.log("");
    console.log("Reports saved:");
    console.log(`  ${mdPath}`);
    console.log(`  ${jsonPath}`);
    console.log("");
    console.log("Next step: npm run demo:one-shot -- --confirm --job-name <name> --artifacts-dir <dir> --dli-queue <queue>");

    process.exit(0);
  } catch (err) {
    console.error(`ONE-SHOT PLAN FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
