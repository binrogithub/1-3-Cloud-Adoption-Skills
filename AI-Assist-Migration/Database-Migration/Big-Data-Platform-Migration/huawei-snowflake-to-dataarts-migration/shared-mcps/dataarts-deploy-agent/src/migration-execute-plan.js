const path = require("path");
const fs = require("fs");
const { buildExecutionPlan } = require("./migration/execution-plan-builder");
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

  lines.push("# Migration Execution Plan Report");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`**Migration ID:** ${result.migration_id || "N/A"}`);
  lines.push(`**Package Dir:** ${result.package_dir || "N/A"}`);
  lines.push("");

  if (result.target) {
    lines.push("## Target");
    lines.push("");
    lines.push(`- Orchestrator: ${result.target.orchestrator}`);
    lines.push(`- Runtime: ${result.target.runtime}`);
    lines.push("");
  }

  lines.push("## Summary");
  lines.push("");
  lines.push(`- Nodes: ${result.summary.node_count}`);
  lines.push(`- Validation Checks: ${result.summary.validation_check_count}`);
  lines.push("");

  if (result.runtime_artifacts_dir) {
    lines.push("## Runtime Artifacts");
    lines.push("");
    lines.push(`- Artifacts Dir: \`${result.runtime_artifacts_dir}\``);
    lines.push(`- Nodes Dir: \`${result.runtime_nodes_dir}\``);
    lines.push("");
  }

  if (result.planned_execution_steps.length > 0) {
    lines.push("## Planned Execution Steps");
    lines.push("");
    lines.push("| Step | Name | Category | Description | Execution Required |");
    lines.push("|------|------|----------|-------------|-------------------|");
    for (const step of result.planned_execution_steps) {
      lines.push(`| ${step.step_number} | ${step.step_name} | ${step.category} | ${step.description} | ${step.execution_required ? "YES" : "NO"} |`);
    }
    lines.push("");
  }

  if (result.warnings.length > 0) {
    lines.push("## Warnings");
    lines.push("");
    for (const w of result.warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  if (result.errors.length > 0) {
    lines.push("## Errors");
    lines.push("");
    for (const e of result.errors) {
      lines.push(`- ${e}`);
    }
    lines.push("");
  }

  lines.push("## Safety");
  lines.push("");
  lines.push("- No publish");
  lines.push("- No schedules");
  lines.push("- No delete");
  lines.push("- No update");
  lines.push("- No overwrite");
  lines.push("- Run-immediate only");
  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Migration Framework: EXECUTION PLAN ===\n");

  const cliArgs = parseCliArgs(process.argv);
  const result = buildExecutionPlan({
    packageDir: cliArgs.packageDir,
  });

  ensureDir(OUT_DIR);

  const resultPath = path.join(OUT_DIR, "execution_plan_result.json");
  const reportPath = path.join(OUT_DIR, "execution_plan_report.md");

  writeJson(resultPath, result);
  fs.writeFileSync(reportPath, renderMarkdown(result), "utf-8");

  if (!result.valid) {
    console.error("Execution plan failed.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    console.error("");
    console.error(`Status: ${result.status}`);
    process.exit(1);
  }

  console.log("Execution plan ready.");
  console.log("");
  console.log(`Migration ID: ${result.migration_id}`);
  console.log("");
  console.log("Target:");
  console.log(`${result.target.orchestrator} / ${result.target.runtime}`);
  console.log("");
  console.log("Runtime artifacts:");
  console.log(`${result.runtime_artifacts_dir}`);
  console.log("");
  console.log(`Nodes: ${result.summary.node_count}`);
  console.log(`Validation checks: ${result.summary.validation_check_count}`);
  console.log("");
  console.log(`Execution steps: ${result.planned_execution_steps.length}`);
  console.log("");
  console.log("Safety:");
  console.log("  No publish");
  console.log("  No schedules");
  console.log("  No delete");
  console.log("  No update");
  console.log("  No overwrite");
  console.log("  Run-immediate only");

  process.exit(0);
}

main();
