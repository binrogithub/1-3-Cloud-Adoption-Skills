const path = require("path");
const { buildMvpReport, writeMvpReport, renderMarkdown } = require("./migration/mvp-report");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

function parseCliArgs(argv) {
  const args = argv.slice(2);
  const parsed = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === "--migration-run-id" && args[i + 1]) {
      parsed.migrationRunId = args[++i];
    } else if (arg.startsWith("--migration-run-id=")) {
      parsed.migrationRunId = arg.slice("--migration-run-id=".length);
    } else if (arg === "--runtime-run-id" && args[i + 1]) {
      parsed.runtimeRunId = args[++i];
    } else if (arg.startsWith("--runtime-run-id=")) {
      parsed.runtimeRunId = arg.slice("--runtime-run-id=".length);
    } else if (arg === "--job-name" && args[i + 1]) {
      parsed.jobName = args[++i];
    } else if (arg.startsWith("--job-name=")) {
      parsed.jobName = arg.slice("--job-name=".length);
    } else if (arg === "--out-dir" && args[i + 1]) {
      parsed.outDir = args[++i];
    } else if (arg.startsWith("--out-dir=")) {
      parsed.outDir = arg.slice("--out-dir=".length);
    }
  }

  return parsed;
}

function main() {
  console.log("=== DataArts Migration Framework: MVP Report v0.1 ===\n");

  const cliArgs = parseCliArgs(process.argv);

  if (!cliArgs.migrationRunId && !cliArgs.runtimeRunId) {
    console.error("Error: At least one of --migration-run-id or --runtime-run-id is required.");
    console.error("");
    console.error("Usage:");
    console.error("  npm run migration:mvp-report -- \\");
    console.error("    --migration-run-id <migration_run_id> \\");
    console.error("    --runtime-run-id <runtime_run_id> \\");
    console.error("    --job-name <job_name>");
    process.exit(1);
  }

  console.log(`  Migration Run ID: ${cliArgs.migrationRunId || "N/A"}`);
  console.log(`  Runtime Run ID:   ${cliArgs.runtimeRunId || "N/A"}`);
  console.log(`  Job Name:         ${cliArgs.jobName || "N/A"}`);
  console.log("");

  const { report, evidence, mvpStatus } = buildMvpReport({
    migrationRunId: cliArgs.migrationRunId,
    runtimeRunId: cliArgs.runtimeRunId,
    jobName: cliArgs.jobName,
    outDir: cliArgs.outDir || OUT_DIR,
  });

  const { resultPath, reportPath } = writeMvpReport(report, cliArgs.outDir || OUT_DIR);

  console.log("=== MVP Report Summary ===\n");
  console.log(`  MVP Status:          ${report.mvp_status}`);
  console.log(`  MVP Version:         ${report.mvp_version}`);
  console.log(`  Job Name:            ${report.architecture.job_name || "N/A"}`);
  console.log(`  Migration Run ID:    ${report.run_ids.migration_run_id || "N/A"}`);
  console.log(`  Runtime Run ID:      ${report.run_ids.runtime_run_id || "N/A"}`);
  console.log(`  DataArts Instance:   ${report.run_ids.dataarts_instance_id || "N/A"}`);
  console.log(`  Runtime Validation:  ${report.validation.runtime_validate_status || "N/A"}`);
  console.log(`  Final Equivalence:   ${report.validation.final_equivalence || "N/A"}`);
  console.log(`  Doctor Healthy:      ${report.validation.doctor_is_healthy ?? "N/A"}`);
  console.log(`  Stale Result:        ${report.validation.stale_result_detected ?? "N/A"}`);
  console.log("");
  console.log("  Validation Conditions:");
  for (const [key, value] of Object.entries(report.validation.conditions)) {
    console.log(`    ${key}: ${value ? "MET" : "NOT MET"}`);
  }
  console.log("");
  console.log("  Safety: No cloud APIs called. No SQL executed. No runtime execution. Local evidence only.");
  console.log("");
  console.log("  Reports written:");
  console.log(`    ${resultPath}`);
  console.log(`    ${reportPath}`);
  console.log("");

  if (report.mvp_status !== "CONFIRMED") {
    process.exit(1);
  }

  process.exit(0);
}

main();
