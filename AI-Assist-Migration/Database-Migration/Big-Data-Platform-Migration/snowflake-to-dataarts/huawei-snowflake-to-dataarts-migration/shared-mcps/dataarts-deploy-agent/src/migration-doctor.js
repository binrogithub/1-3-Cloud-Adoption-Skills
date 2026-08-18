const path = require("path");
const fs = require("fs");
const { runMigrationPackageDoctor } = require("./migration/package-doctor");
const { ensureDir, writeJson } = require("./core/json-file");

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
    }
  }

  return parsed;
}

function renderMarkdown(result) {
  const lines = [];

  lines.push("# Migration Package Doctor Report");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Healthy:** ${result.healthy ? "YES" : "NO"}`);
  lines.push(`**Migration ID:** ${result.migration_id || "N/A"}`);
  lines.push(`**Package Dir:** ${result.package_dir || "N/A"}`);
  lines.push("");

  lines.push("## Summary");
  lines.push("");
  lines.push("| Property | Value |");
  lines.push("|----------|-------|");
  lines.push(`| Node Count | ${result.summary.node_count} |`);
  lines.push(`| Validation Check Count | ${result.summary.validation_check_count} |`);
  lines.push(`| Target Runtime | ${result.summary.target_runtime || "N/A"} |`);
  lines.push(`| Target Orchestrator | ${result.summary.target_orchestrator || "N/A"} |`);
  lines.push(`| All Single Statement | ${result.summary.all_single_statement ? "YES" : "NO"} |`);
  lines.push(`| Requires Runtime Validation | ${result.summary.requires_runtime_validation ? "YES" : "NO"} |`);
  lines.push("");

  if (result.findings.length > 0) {
    lines.push("## Findings (Fatal)");
    lines.push("");
    for (const f of result.findings) {
      lines.push(`- ${f}`);
    }
    lines.push("");
  }

  if (result.warnings.length > 0) {
    lines.push("## Warnings (Non-Fatal)");
    lines.push("");
    for (const w of result.warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  if (result.info.length > 0) {
    lines.push("## Info");
    lines.push("");
    for (const i of result.info) {
      lines.push(`- ${i}`);
    }
    lines.push("");
  }

  lines.push("## Safety");
  lines.push("");
  if (result.safety) {
    for (const [key, value] of Object.entries(result.safety)) {
      lines.push(`- ${key}: ${value}`);
    }
  } else {
    lines.push("- No safety policy loaded.");
  }
  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Migration Framework: DOCTOR ===\n");

  const cliArgs = parseCliArgs(process.argv);
  const result = runMigrationPackageDoctor({
    packageDir: cliArgs.packageDir,
  });

  ensureDir(OUT_DIR);

  const resultPath = path.join(OUT_DIR, "migration_doctor_result.json");
  const reportPath = path.join(OUT_DIR, "migration_doctor_report.md");

  writeJson(resultPath, result);
  fs.writeFileSync(reportPath, renderMarkdown(result), "utf-8");

  console.log("Migration package doctor complete.");
  console.log(`  Healthy:      ${result.healthy ? "YES" : "NO"}`);
  console.log(`  Migration ID: ${result.migration_id || "N/A"}`);
  console.log(`  Findings:     ${result.findings.length}`);
  console.log(`  Warnings:     ${result.warnings.length}`);
  console.log("");
  console.log("Reports saved:");
  console.log(`  ${resultPath}`);
  console.log(`  ${reportPath}`);

  process.exit(result.healthy ? 0 : 1);
}

main();
