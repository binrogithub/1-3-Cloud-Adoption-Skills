const path = require("path");
const fs = require("fs");
const { batchAssessMigrationPackages } = require("./migration/batch-assessor");
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
    }
  }

  return parsed;
}

function renderMarkdown(result) {
  const lines = [];

  lines.push("# Batch Migration Assessment Report");
  lines.push("");

  lines.push("## Executive Summary");
  lines.push("");
  lines.push(`- **Status:** ${result.status}`);
  lines.push(`- **Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`- **Packages Directory:** ${result.packages_dir || "N/A"}`);
  lines.push(`- **Package Count:** ${result.package_count}`);
  lines.push("");

  lines.push("## Readiness Summary");
  lines.push("");
  lines.push("| Status | Count |");
  lines.push("|--------|-------|");
  lines.push(`| RUNTIME_CONFIRMED | ${result.summary.runtime_confirmed} |`);
  lines.push(`| DRY_RUN_VALIDATED | ${result.summary.dry_run_validated} |`);
  lines.push(`| READY_FOR_DRY_RUN | ${result.summary.ready_for_dry_run} |`);
  lines.push(`| NEEDS_REVIEW | ${result.summary.needs_review} |`);
  lines.push(`| BLOCKED | ${result.summary.blocked} |`);
  lines.push(`| INVALID_PACKAGE | ${result.summary.invalid} |`);
  lines.push("");

  lines.push("## Package Table");
  lines.push("");
  lines.push("| Package | Migration ID | Readiness | Valid | Nodes | Checks | Warnings | Findings | Equiv. Status | Equiv. Confirmed |");
  lines.push("|---------|-------------|-----------|------|-------|--------|----------|----------|---------------|------------------|");
  for (const pkg of result.packages) {
    lines.push(
      `| ${pkg.package_name} | ${pkg.migration_id || "N/A"} | ${pkg.readiness_status} | ${pkg.valid ? "YES" : "NO"} | ${pkg.node_count} | ${pkg.validation_check_count} | ${pkg.warnings_count} | ${pkg.findings_count} | ${pkg.expected_equivalence_status || "N/A"} | ${pkg.equivalence_confirmed === true ? "YES" : pkg.equivalence_confirmed === false ? "NO" : "N/A"} |`
    );
  }
  lines.push("");

  const pkgsWithWarnings = result.packages.filter((p) => p.warnings.length > 0);
  const pkgsWithFindings = result.packages.filter((p) => p.findings.length > 0);

  if (pkgsWithWarnings.length > 0) {
    lines.push("## Warnings by Package");
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
  lines.push("- **Batch assessment only:** No cloud API calls, no SQL execution, no runtime execution.");
  lines.push("- This command is read-only and local.");
  lines.push("");

  lines.push("## Next Recommendations");
  lines.push("");
  const readyPackages = result.packages.filter((p) => p.readiness_status === "READY_FOR_DRY_RUN" || p.readiness_status === "DRY_RUN_VALIDATED");
  const needsReview = result.packages.filter((p) => p.readiness_status === "NEEDS_REVIEW");
  const blocked = result.packages.filter((p) => p.readiness_status === "BLOCKED");

  if (readyPackages.length > 0) {
    lines.push(`- ${readyPackages.length} package(s) are ready for dry-run validation. Run \`migration:execute --dry-run\` for each.`);
  }
  if (needsReview.length > 0) {
    lines.push(`- ${needsReview.length} package(s) need review due to MERGE+DLI or full-refresh warnings. Confirm these are acceptable.`);
  }
  if (blocked.length > 0) {
    lines.push(`- ${blocked.length} package(s) are blocked by doctor findings. Fix findings before proceeding.`);
  }
  if (result.summary.runtime_confirmed > 0) {
    lines.push(`- ${result.summary.runtime_confirmed} package(s) are runtime-confirmed. No further action needed.`);
  }
  if (result.packages.length === 0) {
    lines.push("- No packages found. Check the packages directory path.");
  }
  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Migration Framework: BATCH ASSESSMENT ===\n");

  const cliArgs = parseCliArgs(process.argv);

  if (!cliArgs.packagesDir) {
    console.error("Error: --packages-dir is required");
    process.exit(1);
  }

  const result = batchAssessMigrationPackages({
    packagesDir: cliArgs.packagesDir,
    outDir: OUT_DIR,
  });

  ensureDir(OUT_DIR);

  const resultPath = path.join(OUT_DIR, "batch_assessment_result.json");
  const reportPath = path.join(OUT_DIR, "batch_assessment_report.md");

  writeJson(resultPath, result);
  fs.writeFileSync(reportPath, renderMarkdown(result), "utf-8");

  if (!result.valid && result.status === "INVALID_INPUT") {
    console.error("Batch assessment failed: invalid input.");
    for (const error of result.errors) {
      console.error(`  - ${error}`);
    }
    process.exit(1);
  }

  console.log("Batch assessment complete.");
  console.log(`Packages:        ${result.package_count}`);
  console.log(`Runtime confirmed: ${result.summary.runtime_confirmed}`);
  console.log(`Dry-run validated: ${result.summary.dry_run_validated}`);
  console.log(`Ready for dry-run: ${result.summary.ready_for_dry_run}`);
  console.log(`Needs review:    ${result.summary.needs_review}`);
  console.log(`Blocked:         ${result.summary.blocked}`);
  console.log(`Invalid:         ${result.summary.invalid}`);
  console.log("");
  console.log("Safety: assessment only, no cloud APIs, no SQL, no runtime execution.");
  console.log("");
  console.log("Reports saved:");
  console.log(`  ${resultPath}`);
  console.log(`  ${reportPath}`);

  process.exit(result.valid ? 0 : 1);
}

main();
