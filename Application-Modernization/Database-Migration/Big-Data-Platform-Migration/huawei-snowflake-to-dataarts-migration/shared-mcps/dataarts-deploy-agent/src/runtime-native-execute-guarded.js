const path = require("path");
const { executeNativeDliGuarded } = require("./runtime/native-dli-guarded-executor");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

function parseCliArgs(argv) {
  const args = argv.slice(2);
  const parsed = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === "--package-dir" && args[i + 1]) {
      parsed.packageDir = args[++i];
    } else if (arg.startsWith("--package-dir=")) {
      parsed.packageDir = arg.slice("--package-dir=".length);
    } else if (arg === "--dli-queue" && args[i + 1]) {
      parsed.dliQueue = args[++i];
    } else if (arg.startsWith("--dli-queue=")) {
      parsed.dliQueue = arg.slice("--dli-queue=".length);
    } else if (arg === "--out-dir" && args[i + 1]) {
      parsed.outDir = args[++i];
    } else if (arg.startsWith("--out-dir=")) {
      parsed.outDir = arg.slice("--out-dir=".length);
    } else if (arg === "--plan-only") {
      parsed.planOnly = true;
    } else if (arg === "--allow-real-execution") {
      parsed.allowRealExecution = true;
    } else if (arg === "--confirm-native-dli") {
      parsed.confirmNativeDli = true;
    } else if (arg === "--i-understand-this-executes-sql") {
      parsed.understandExecutesSql = true;
    } else if (arg === "--database" && args[i + 1]) {
      parsed.database = args[++i];
    } else if (arg.startsWith("--database=")) {
      parsed.database = arg.slice("--database=".length);
    } else if (arg === "--resume-from" && args[i + 1]) {
      parsed.resumeFrom = args[++i];
    } else if (arg.startsWith("--resume-from=")) {
      parsed.resumeFrom = arg.slice("--resume-from=".length);
    } else if (arg === "--max-launching-jobs" && args[i + 1]) {
      parsed.maxLaunchingJobs = parseInt(args[++i], 10);
    } else if (arg.startsWith("--max-launching-jobs=")) {
      parsed.maxLaunchingJobs = parseInt(arg.slice("--max-launching-jobs=".length), 10);
    }
  }

  return parsed;
}

async function main() {
  console.log("=== DataArts Migration Framework: NATIVE DLI GUARDED EXECUTION ===\n");

  const cliArgs = parseCliArgs(process.argv);

  if (!cliArgs.packageDir) {
    console.error("Error: --package-dir is required");
    process.exit(1);
  }

  const dliQueue = cliArgs.dliQueue || "default";
  const planOnly = cliArgs.planOnly === true;

  const mode = planOnly ? "PLAN_ONLY" : "REAL";

  const result = await executeNativeDliGuarded({
    packageDir: cliArgs.packageDir,
    dliQueue,
    mode,
    planOnly,
    allowRealExecution: cliArgs.allowRealExecution === true,
    confirmNativeDli: cliArgs.confirmNativeDli === true,
    understandExecutesSql: cliArgs.understandExecutesSql === true,
    outDir: cliArgs.outDir || "./out",
    database: cliArgs.database || "demo_migration",
    resumeFrom: cliArgs.resumeFrom || "runtime_setup",
    maxLaunchingJobs: cliArgs.maxLaunchingJobs !== undefined ? cliArgs.maxLaunchingJobs : 10,
  });

  if (result.status === "NATIVE_DLI_GUARDED_PLAN_READY") {
    console.log("Native DLI guarded execution plan ready.");
    console.log(`  Migration ID: ${result.migration_id}`);
    console.log(`  Resume from: ${result.resume_from}`);
    console.log(`  SQL executions planned: ${result.planned_sql_executions}`);
    console.log(`  Query executions planned: ${result.planned_query_executions}`);
    console.log(`  Total DLI requests planned: ${result.total_planned_requests}`);
    if (result.resume_plan) {
      const rp = result.resume_plan;
      for (const [phaseName, steps] of Object.entries(rp.phases)) {
        const skipped = steps.filter((s) => s.status === "SKIPPED_RESUME").length;
        const planned = steps.filter((s) => s.status === "PLANNED").length;
        console.log(`  ${phaseName}: ${planned} planned, ${skipped} skipped (resume)`);
      }
    }
    console.log("Safety: plan-only, no SQL execution, no runtime execution.");
    process.exit(0);
  }

  if (result.status === "NATIVE_DLI_REAL_EXECUTION_NOT_IMPLEMENTED") {
    console.log("Native DLI real execution is guarded but not implemented.");
    console.log("  No SQL was executed.");
    process.exit(1);
  }

  if (result.status === "NATIVE_DLI_GUARDED_EXECUTION_BLOCKED") {
    console.error("Native DLI guarded execution blocked by guardrail flags.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    process.exit(1);
  }

  if (result.status === "NATIVE_DLI_GUARDED_PREFLIGHT_UNHEALTHY") {
    console.error("Native DLI guarded execution blocked: preflight unhealthy.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    process.exit(1);
  }

  if (result.status === "NATIVE_DLI_QUEUE_CONGESTED") {
    console.error("Native DLI guarded execution blocked: queue congested.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    process.exit(1);
  }

  if (result.status === "INVALID_INPUT") {
    console.error("Invalid input.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    process.exit(1);
  }

  if (result.status === "NATIVE_DLI_GUARDED_EXECUTION_SUCCEEDED") {
    console.log("Native DLI guarded execution SUCCEEDED.");
    console.log(`  Migration ID: ${result.migration_id}`);
    console.log(`  Final equivalence: ${result.final_equivalence}`);
    console.log(`  Equivalence confirmed: ${result.equivalence_confirmed}`);
    console.log(`  Real runtime confirmed: ${result.real_runtime_confirmed}`);
    if (result.execution_summary) {
      const s = result.execution_summary;
      console.log(`  Setup: ${s.setup_succeeded}/${s.setup_steps} succeeded${s.setup_skipped ? `, ${s.setup_skipped} skipped` : ""}`);
      console.log(`  Target: ${s.target_succeeded}/${s.target_steps} succeeded${s.target_skipped ? `, ${s.target_skipped} skipped` : ""}`);
      console.log(`  Validation: ${s.validation_succeeded}/${s.validation_steps} passed`);
    }
    process.exit(0);
  }

  if (result.status === "NATIVE_DLI_GUARDED_VALIDATION_FAILED") {
    console.error("Native DLI guarded execution completed but validation FAILED.");
    console.log(`  Migration ID: ${result.migration_id}`);
    console.log(`  Final equivalence: ${result.final_equivalence}`);
    if (result.execution_summary) {
      const s = result.execution_summary;
      console.log(`  Setup: ${s.setup_succeeded}/${s.setup_steps} succeeded${s.setup_skipped ? `, ${s.setup_skipped} skipped` : ""}`);
      console.log(`  Target: ${s.target_succeeded}/${s.target_steps} succeeded${s.target_skipped ? `, ${s.target_skipped} skipped` : ""}`);
      console.log(`  Validation: ${s.validation_succeeded}/${s.validation_steps} passed`);
    }
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    process.exit(1);
  }

  console.error("Native DLI guarded execution failed.");
  for (const error of result.errors || []) {
    console.error(`  - ${error}`);
  }
  console.error("");
  console.error(`Status: ${result.status}`);
  process.exit(1);
}

main().catch((err) => {
  console.error("Fatal error:", err.message);
  process.exit(1);
});
