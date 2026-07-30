const path = require("path");
const fs = require("fs");
const { batchValidateMigrationPackages } = require("./migration/batch-validator");
const { ensureDir, writeJson } = require("./core/json-file");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

function parseCliArgs(argv) {
  const args = argv.slice(2);
  const parsed = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === "--packages-dir" && args[i + 1]) {
      parsed.packagesDir = args[++i];
    } else if (arg.startsWith("--packages-dir=")) {
      parsed.packagesDir = arg.slice("--packages-dir=".length);
    } else if (arg === "--adapter" && args[i + 1]) {
      parsed.adapter = args[++i];
    } else if (arg.startsWith("--adapter=")) {
      parsed.adapter = arg.slice("--adapter=".length);
    } else if (arg === "--dli-queue" && args[i + 1]) {
      parsed.dliQueue = args[++i];
    } else if (arg.startsWith("--dli-queue=")) {
      parsed.dliQueue = arg.slice("--dli-queue=".length);
    }
  }

  return parsed;
}

function renderMarkdown(result) {
  const lines = [];

  lines.push("# Batch Migration Validation Report");
  lines.push("");

  lines.push("## Executive Summary");
  lines.push("");
  lines.push(`- **Status:** ${result.status}`);
  lines.push(`- **Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`- **Packages Directory:** ${result.packages_dir || "N/A"}`);
  lines.push(`- **Adapter:** ${result.adapter || "N/A"}`);
  lines.push(`- **DLI Queue:** ${result.dli_queue || "N/A"}`);
  lines.push(`- **Package Count:** ${result.package_count}`);
  lines.push("");

  lines.push("## Validation Summary");
  lines.push("");
  lines.push("| Metric | Count |");
  lines.push("|--------|-------|");
  lines.push(`| Dry-run validated | ${result.summary.dry_run_validated} |`);
  lines.push(`| Invalid | ${result.summary.invalid} |`);
  lines.push(`| Blocked (doctor unhealthy) | ${result.summary.blocked} |`);
  lines.push(`| Failed (prepare/plan/dry-run) | ${result.summary.failed} |`);
  lines.push(`| Total warnings | ${result.summary.warnings} |`);
  lines.push("");

  lines.push("## Package Validation Table");
  lines.push("");
  lines.push("| Package | Migration ID | Validation Status | Valid | Runtime | Nodes | Checks | Warnings | Findings |");
  lines.push("|---------|-------------|-----------------|------|---------|-------|--------|----------|----------|");
  for (const pkg of result.packages) {
    lines.push(
      `| ${pkg.package_name} | ${pkg.migration_id || "N/A"} | ${pkg.validation_status} | ${pkg.valid ? "YES" : "NO"} | ${pkg.target_runtime || "N/A"} | ${pkg.node_count} | ${pkg.validation_check_count} | ${(pkg.warnings || []).length} | ${(pkg.findings || []).length} |`
    );
  }
  lines.push("");

  lines.push("## Per-Stage Status");
  lines.push("");
  for (const pkg of result.packages) {
    lines.push(`### ${pkg.package_name}`);
    lines.push("");
    lines.push("| Stage | Status | Valid | Details |");
    lines.push("|-------|--------|------|---------|");
    lines.push(`| package_load | ${pkg.stages.package_load.status} | ${pkg.stages.package_load.valid ? "YES" : "NO"} | - |`);
    lines.push(`| plan | ${pkg.stages.plan.status} | ${pkg.stages.plan.valid ? "YES" : "NO"} | - |`);
    lines.push(`| doctor | ${pkg.stages.doctor.status} | ${pkg.stages.doctor.healthy ? "HEALTHY" : "UNHEALTHY"} | findings: ${pkg.stages.doctor.findings_count}, warnings: ${pkg.stages.doctor.warnings_count} |`);
    lines.push(`| prepare_runtime | ${pkg.stages.prepare_runtime.status} | ${pkg.stages.prepare_runtime.valid ? "YES" : "NO"} | ${pkg.stages.prepare_runtime.runtime_artifacts_dir || "N/A"} |`);
    lines.push(`| execute_plan | ${pkg.stages.execute_plan.status} | ${pkg.stages.execute_plan.valid ? "YES" : "NO"} | steps: ${pkg.stages.execute_plan.steps} |`);
    lines.push(`| execute_dry_run | ${pkg.stages.execute_dry_run.status} | ${pkg.stages.execute_dry_run.valid ? "YES" : "NO"} | adapter: ${pkg.stages.execute_dry_run.adapter} |`);
    lines.push("");
    if (pkg.stages.execute_dry_run.planned_command) {
      lines.push(`  **Planned command:** \`${pkg.stages.execute_dry_run.planned_command}\``);
      lines.push("");
    }
  }

  const pkgsWithWarnings = result.packages.filter((p) => (p.warnings || []).length > 0);
  const pkgsWithFindings = result.packages.filter((p) => (p.findings || []).length > 0);

  if (pkgsWithWarnings.length > 0) {
    lines.push("## Warnings by Package");
    lines.push("");
    lines.push("> Warnings are non-fatal. Full-refresh and MERGE+DLI warnings do not fail validation.");
    lines.push("");
    for (const pkg of pkgsWithWarnings) {
      lines.push(`### ${pkg.package_name}`);
      lines.push("");
      for (const w of pkg.warnings) {
        lines.push(`- ${w}`);
      }
      lines.push("");
    }
  }

  if (pkgsWithFindings.length > 0) {
    lines.push("## Findings by Package");
    lines.push("");
    lines.push("> Findings are fatal. Packages with findings are blocked.");
    lines.push("");
    for (const pkg of pkgsWithFindings) {
      lines.push(`### ${pkg.package_name}`);
      lines.push("");
      for (const f of pkg.findings) {
        lines.push(`- ${f}`);
      }
      lines.push("");
    }
  }

  lines.push("## Safety Statement");
  lines.push("");
  lines.push("- **Batch validation only:** This command performs local/dry-run validation only.");
  lines.push("- **Dry-run only:** No confirm mode is used.");
  lines.push("- **No cloud API calls:** No cloud APIs are called.");
  lines.push("- **No runtime execution:** No jobs are started or executed.");
  lines.push("- **No SQL execution:** No SQL is executed against any target.");
  lines.push("- **No confirm:** The confirm flag is never used.");
  lines.push("");

  lines.push("## Next Recommendations");
  lines.push("");
  const validated = result.packages.filter((p) => p.validation_status === "BATCH_DRY_RUN_VALIDATED");
  const invalid = result.packages.filter((p) => p.validation_status === "INVALID_PACKAGE");
  const blocked = result.packages.filter((p) => p.validation_status === "DOCTOR_UNHEALTHY");
  const failed = result.packages.filter(
    (p) =>
      p.validation_status === "RUNTIME_PREPARE_FAILED" ||
      p.validation_status === "EXECUTION_PLAN_FAILED" ||
      p.validation_status === "DRY_RUN_FAILED"
  );

  if (validated.length > 0) {
    lines.push(`- ${validated.length} package(s) passed batch dry-run validation. Ready for runtime confirmation via \`migration:execute --confirm\`.`);
  }
  if (invalid.length > 0) {
    lines.push(`- ${invalid.length} package(s) are invalid. Fix package structure and manifest errors.`);
  }
  if (blocked.length > 0) {
    lines.push(`- ${blocked.length} package(s) are blocked by doctor findings. Resolve findings before proceeding.`);
  }
  if (failed.length > 0) {
    lines.push(`- ${failed.length} package(s) failed during prepare/plan/dry-run. Investigate errors and retry.`);
  }
  if (result.packages.length === 0) {
    lines.push("- No packages found. Check the packages directory path.");
  }
  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Migration Framework: BATCH VALIDATION ===\n");

  const cliArgs = parseCliArgs(process.argv);

  if (!cliArgs.packagesDir) {
    console.error("Error: --packages-dir is required");
    process.exit(1);
  }

  const result = batchValidateMigrationPackages({
    packagesDir: cliArgs.packagesDir,
    adapter: cliArgs.adapter || "legacy-demo",
    dliQueue: cliArgs.dliQueue || "default",
    outDir: OUT_DIR,
  });

  ensureDir(OUT_DIR);

  const resultPath = path.join(OUT_DIR, "batch_validation_result.json");
  const reportPath = path.join(OUT_DIR, "batch_validation_report.md");

  writeJson(resultPath, result);
  fs.writeFileSync(reportPath, renderMarkdown(result), "utf-8");

  if (!result.valid && result.status === "INVALID_INPUT") {
    console.error("Batch validation failed: invalid input.");
    for (const error of result.errors) {
      console.error(`  - ${error}`);
    }
    process.exit(1);
  }

  if (result.status === "NO_PACKAGES_FOUND") {
    console.error("Batch validation: no packages found.");
    process.exit(1);
  }

  console.log("Batch validation complete.");
  console.log(`Packages:          ${result.package_count}`);
  console.log(`Dry-run validated: ${result.summary.dry_run_validated}`);
  console.log(`Failed:            ${result.summary.failed}`);
  console.log(`Blocked:           ${result.summary.blocked}`);
  console.log(`Invalid:           ${result.summary.invalid}`);
  console.log("");
  console.log("Safety: dry-run only, no confirm, no cloud APIs, no SQL, no runtime execution.");
  console.log("");
  console.log("Reports saved:");
  console.log(`  ${resultPath}`);
  console.log(`  ${reportPath}`);

  process.exit(result.valid ? 0 : 1);
}

main();
