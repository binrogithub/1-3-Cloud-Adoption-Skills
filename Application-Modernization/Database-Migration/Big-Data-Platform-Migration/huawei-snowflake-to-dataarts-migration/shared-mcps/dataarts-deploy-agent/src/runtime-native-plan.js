const path = require("path");
const fs = require("fs");
const { buildNativeRuntimePlan } = require("./runtime/native-runtime-plan");
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
    } else if (arg === "--dli-queue" && args[i + 1]) {
      parsed.dliQueue = args[++i];
    } else if (arg.startsWith("--dli-queue=")) {
      parsed.dliQueue = arg.slice("--dli-queue=".length);
    } else if (arg === "--out-dir" && args[i + 1]) {
      parsed.outDir = args[++i];
    } else if (arg.startsWith("--out-dir=")) {
      parsed.outDir = arg.slice("--out-dir=".length);
    }
  }

  return parsed;
}

function renderMarkdown(plan) {
  const lines = [];

  lines.push("# Native DLI Runtime Plan");
  lines.push("");
  lines.push("## Executive Summary");
  lines.push("");
  lines.push(`**Status:** ${plan.status}`);
  lines.push(`**Valid:** ${plan.valid ? "YES" : "NO"}`);
  lines.push(`**Migration ID:** ${plan.migration_id || "N/A"}`);
  lines.push(`**Package Dir:** \`${plan.package_dir || "N/A"}\``);
  lines.push(`**DLI Queue:** ${plan.dli_queue || "N/A"}`);
  lines.push("");
  lines.push("### Summary");
  lines.push("");
  lines.push("| Metric | Count |");
  lines.push("|--------|-------|");
  lines.push(`| Setup SQL | ${plan.summary.setup_sql_count} |`);
  lines.push(`| Target SQL | ${plan.summary.target_sql_count} |`);
  lines.push(`| Validation Queries | ${plan.summary.validation_query_count} |`);
  lines.push(`| Total Steps | ${plan.summary.total_steps} |`);
  lines.push("");

  lines.push("## Phase Table");
  lines.push("");
  lines.push("| Phase | Step Count | Type |");
  lines.push("|-------|------------|------|");
  lines.push(`| runtime_setup | ${plan.phases.runtime_setup.length} | DLI_SQL |`);
  lines.push(`| target_transform | ${plan.phases.target_transform.length} | DLI_SQL |`);
  lines.push(`| runtime_validation | ${plan.phases.runtime_validation.length} | DLI_QUERY |`);
  lines.push(`| equivalence_summary | ${plan.phases.equivalence_summary.length} | LOCAL_COMPARISON |`);
  lines.push("");

  lines.push("## Runtime Setup Steps");
  lines.push("");
  lines.push("| Order | Name | Type | Executed |");
  lines.push("|-------|------|------|----------|");
  for (const step of plan.phases.runtime_setup) {
    lines.push(`| ${step.execution_order} | ${step.name} | ${step.type} | ${step.executed ? "YES" : "NO"} |`);
  }
  lines.push("");

  lines.push("## Target Transform Steps");
  lines.push("");
  lines.push("| Order | Name | Node ID | Type | Depends On | Executed |");
  lines.push("|-------|------|---------|------|------------|----------|");
  for (const step of plan.phases.target_transform) {
    lines.push(`| ${step.execution_order} | ${step.name} | ${step.node_id} | ${step.type} | ${(step.depends_on || []).join(", ")} | ${step.executed ? "YES" : "NO"} |`);
  }
  lines.push("");

  lines.push("## Validation Query Steps");
  lines.push("");
  lines.push("| Order | Name | Query Type | Object Name | Expected | Executed |");
  lines.push("|-------|------|------------|------------|----------|----------|");
  for (const step of plan.phases.runtime_validation) {
    const expectedStr = typeof step.expected === "object" ? JSON.stringify(step.expected) : String(step.expected);
    lines.push(`| ${step.execution_order} | ${step.name} | ${step.query_type} | ${step.object_name} | ${expectedStr} | ${step.executed ? "YES" : "NO"} |`);
  }
  lines.push("");

  lines.push("## Equivalence Summary Step");
  lines.push("");
  lines.push("| Order | Name | Type | Executed |");
  lines.push("|-------|------|------|----------|");
  for (const step of plan.phases.equivalence_summary) {
    lines.push(`| ${step.execution_order} | ${step.name} | ${step.type} | ${step.executed ? "YES" : "NO"} |`);
  }
  lines.push("");

  if (plan.warnings && plan.warnings.length > 0) {
    lines.push("## Warnings");
    lines.push("");
    for (const w of plan.warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  if (plan.errors && plan.errors.length > 0) {
    lines.push("## Errors");
    lines.push("");
    for (const e of plan.errors) {
      lines.push(`- ${e}`);
    }
    lines.push("");
  }

  lines.push("## Safety");
  lines.push("");
  lines.push("- Native runtime plan only");
  lines.push("- No cloud API calls");
  lines.push("- No SQL execution");
  lines.push("- No runtime execution");
  lines.push("- No confirm");
  lines.push("- No commands executed");
  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Migration Framework: NATIVE RUNTIME PLAN ===\n");

  const cliArgs = parseCliArgs(process.argv);

  if (!cliArgs.packageDir) {
    console.error("Error: --package-dir is required");
    process.exit(1);
  }

  const plan = buildNativeRuntimePlan({
    packageDir: cliArgs.packageDir,
    dliQueue: cliArgs.dliQueue || "default",
    outDir: cliArgs.outDir || "./out",
  });

  ensureDir(OUT_DIR);

  const resultPath = path.join(OUT_DIR, "native_runtime_plan_result.json");
  const reportPath = path.join(OUT_DIR, "native_runtime_plan_report.md");

  writeJson(resultPath, plan);
  fs.writeFileSync(reportPath, renderMarkdown(plan), "utf-8");

  if (!plan.valid) {
    console.error("Native runtime plan failed.");
    for (const error of plan.errors || []) {
      console.error(`  - ${error}`);
    }
    console.error("");
    console.error(`Status: ${plan.status}`);
    process.exit(1);
  }

  console.log("Native runtime plan ready.");
  console.log(`  Migration ID: ${plan.migration_id}`);
  console.log(`  DLI Queue: ${plan.dli_queue}`);
  console.log(`  Setup SQL: ${plan.summary.setup_sql_count}`);
  console.log(`  Target SQL: ${plan.summary.target_sql_count}`);
  console.log(`  Validation queries: ${plan.summary.validation_query_count}`);
  console.log(`  Total steps: ${plan.summary.total_steps}`);
  console.log("Safety: native plan only, no cloud APIs, no SQL execution, no runtime execution.");

  process.exit(0);
}

main();
