const path = require("path");
const { buildMigrationPlan } = require("./migration/plan-builder");
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

function renderMarkdown(plan) {
  const lines = [];

  lines.push("# Migration Plan Report");
  lines.push("");
  lines.push(`**Status:** ${plan.status}`);
  lines.push(`**Migration ID:** ${plan.migration_id || "N/A"}`);
  lines.push(`**Package Dir:** ${plan.package_dir || "N/A"}`);
  lines.push("");

  if (!plan.valid) {
    lines.push("## Errors");
    lines.push("");
    for (const error of plan.errors || []) {
      lines.push(`- ${error}`);
    }
    lines.push("");
    return lines.join("\n");
  }

  lines.push("## Source");
  lines.push("");
  lines.push(`- Type: ${plan.source.type}`);
  lines.push(`- Task graph path: ${plan.source.task_graph_path}`);
  lines.push(`- Task graph bytes: ${plan.source.task_graph_bytes}`);
  lines.push("");

  lines.push("## Target");
  lines.push("");
  lines.push(`- Orchestrator: ${plan.target.orchestrator}`);
  lines.push(`- Runtime: ${plan.target.runtime}`);
  lines.push(`- Node type: ${plan.target.node_type}`);
  lines.push(`- Node count: ${plan.target.node_count}`);
  lines.push("");

  lines.push("## Runtime Nodes");
  lines.push("");
  lines.push("| Order | Node | Type | SQL File | Statements | Depends On |");
  lines.push("|-------|------|------|----------|------------|------------|");
  for (const node of plan.nodes) {
    lines.push(
      `| ${node.order} | ${node.name} | ${node.type} | ${node.sql_file} | ${node.statement_count} | ${(node.depends_on || []).join(", ") || "-"} |`
    );
  }
  lines.push("");

  lines.push("## Validation");
  lines.push("");
  lines.push(`- Expected runtime status: ${plan.validation.expected_runtime_status}`);
  lines.push(`- Expected final equivalence: ${plan.validation.expected_final_equivalence}`);
  lines.push(`- Validation checks: ${plan.validation.check_count}`);
  lines.push("");

  lines.push("## Planned Steps");
  lines.push("");
  lines.push("| Step | Name | Type | Description |");
  lines.push("|------|------|------|-------------|");
  for (const step of plan.planned_steps) {
    lines.push(`| ${step.step} | ${step.name} | ${step.type} | ${step.description} |`);
  }
  lines.push("");

  lines.push("## Safety");
  lines.push("");
  lines.push("- No publish.");
  lines.push("- No /start.");
  lines.push("- No delete.");
  lines.push("- No update.");
  lines.push("- No overwrite.");
  lines.push("- No runtime execution in plan mode.");
  lines.push("- No API write calls in plan mode.");
  lines.push("");

  if (plan.warnings?.length) {
    lines.push("## Warnings");
    lines.push("");
    for (const warning of plan.warnings) {
      lines.push(`- ${warning}`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Migration Framework: PLAN ===\n");

  const cliArgs = parseCliArgs(process.argv);
  const plan = buildMigrationPlan({
    packageDir: cliArgs.packageDir,
  });

  ensureDir(OUT_DIR);

  const resultPath = path.join(OUT_DIR, "migration_plan_result.json");
  const reportPath = path.join(OUT_DIR, "migration_plan_report.md");

  writeJson(resultPath, plan);
  require("fs").writeFileSync(reportPath, renderMarkdown(plan), "utf-8");

  if (!plan.valid) {
    console.error("Migration plan failed.");
    for (const error of plan.errors || []) {
      console.error(`  - ${error}`);
    }
    console.error("");
    console.error(`Result: ${resultPath}`);
    console.error(`Report: ${reportPath}`);
    process.exit(1);
  }

  console.log("Migration plan ready.");
  console.log("");
  console.log(`  Migration ID: ${plan.migration_id}`);
  console.log(`  Target:       ${plan.target.orchestrator}/${plan.target.runtime}`);
  console.log(`  Nodes:        ${plan.target.node_count}`);
  console.log(`  Checks:       ${plan.validation.check_count}`);
  console.log(`  Steps:        ${plan.planned_steps.length}`);
  console.log("");
  console.log("Safety: plan-only, no API write calls, no runtime execution.");
  console.log("");
  console.log("Reports saved:");
  console.log(`  ${resultPath}`);
  console.log(`  ${reportPath}`);

  process.exit(0);
}

main();
