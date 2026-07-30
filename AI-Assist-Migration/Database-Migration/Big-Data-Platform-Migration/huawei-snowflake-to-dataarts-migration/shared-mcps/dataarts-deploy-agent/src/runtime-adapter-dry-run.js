const path = require("path");
const fs = require("fs");
const { executeWithRuntimeAdapter } = require("./runtime/adapters/runtime-adapter");
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
    } else if (arg === "--job-name" && args[i + 1]) {
      parsed.jobName = args[++i];
    } else if (arg.startsWith("--job-name=")) {
      parsed.jobName = arg.slice("--job-name=".length);
    } else if (arg === "--dli-queue" && args[i + 1]) {
      parsed.dliQueue = args[++i];
    } else if (arg.startsWith("--dli-queue=")) {
      parsed.dliQueue = arg.slice("--dli-queue=".length);
    } else if (arg === "--adapter" && args[i + 1]) {
      parsed.adapter = args[++i];
    } else if (arg.startsWith("--adapter=")) {
      parsed.adapter = arg.slice("--adapter=".length);
    }
  }

  return parsed;
}

function renderMarkdown(result) {
  const lines = [];

  lines.push("# Runtime Adapter Dry-Run Report");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`**Adapter:** ${result.adapter || "N/A"}`);
  lines.push(`**Mode:** ${result.mode || "N/A"}`);
  lines.push(`**Run ID:** ${result.run_id || "N/A"}`);
  lines.push(`**Migration ID:** ${result.migration_id || "N/A"}`);
  lines.push(`**Job Name:** ${result.job_name || "N/A"}`);
  lines.push(`**DLI Queue:** ${result.dli_queue || "N/A"}`);
  lines.push("");

  if (result.runtime_artifacts_dir) {
    lines.push("## Runtime Directories");
    lines.push("");
    lines.push(`- Artifacts: \`${result.runtime_artifacts_dir}\``);
    lines.push(`- Nodes: \`${result.runtime_nodes_dir || "N/A"}\``);
    lines.push("");
  }

  if (result.command_sequence && result.command_sequence.length > 0) {
    lines.push("## Command Sequence");
    lines.push("");
    lines.push("| Step | Name | Category | Command | Executed in Dry-Run |");
    lines.push("|------|------|----------|---------|---------------------|");
    for (const cmd of result.command_sequence) {
      lines.push(
        `| ${cmd.step} | ${cmd.name} | ${cmd.category} | \`${cmd.cmd}\` | ${cmd.executed_in_dry_run ? "YES" : "NO"} |`
      );
    }
    lines.push("");
  }

  if (result.planned_legacy_command) {
    lines.push("## Planned Legacy Command");
    lines.push("");
    lines.push(`\`\`\`${result.planned_legacy_command}\`\`\``);
    lines.push("");
  }

  if (result.normalized_result) {
    lines.push("## Normalized Result");
    lines.push("");
    lines.push("```json");
    lines.push(JSON.stringify(result.normalized_result, null, 2));
    lines.push("```");
    lines.push("");
  }

  if (result.koocli_diagnostics) {
    lines.push("## KooCLI Diagnostics");
    lines.push("");
    lines.push(`- Installed: ${result.koocli_diagnostics.installed ? "YES" : "NO"}`);
    lines.push(`- Version: ${result.koocli_diagnostics.version || "N/A"}`);
    lines.push("");
  }

  if (result.future_command_plan) {
    lines.push("## Future Command Plan");
    lines.push("");
    lines.push(`- Migration ID: ${result.future_command_plan.migration_id || "N/A"}`);
    lines.push(`- Job Name: ${result.future_command_plan.job_name || "N/A"}`);
    lines.push(`- Categories: ${result.future_command_plan.categories.length}`);
    lines.push("");
    for (const cat of result.future_command_plan.categories) {
      lines.push(`### ${cat.category}`);
      lines.push("");
      lines.push(`${cat.description}`);
      lines.push("");
      for (const cmd of cat.commands) {
        lines.push(`- \`${cmd.cmd}\` — ${cmd.purpose} [${cmd.implementation_status}]`);
      }
      lines.push("");
    }
  }

  if (result.warnings && result.warnings.length > 0) {
    lines.push("## Warnings");
    lines.push("");
    for (const w of result.warnings) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  if (result.errors && result.errors.length > 0) {
    lines.push("## Errors");
    lines.push("");
    for (const e of result.errors) {
      lines.push(`- ${e}`);
    }
    lines.push("");
  }

  lines.push("## Safety");
  lines.push("");
  lines.push("- Adapter dry-run only");
  lines.push("- No commands executed");
  lines.push("- No API write calls");
  lines.push("- No runtime execution");
  lines.push("- Local evidence only");
  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Runtime Adapter: DRY-RUN ===\n");

  const cliArgs = parseCliArgs(process.argv);
  const result = executeWithRuntimeAdapter({
    adapter: cliArgs.adapter,
    packageDir: cliArgs.packageDir,
    jobName: cliArgs.jobName,
    dliQueue: cliArgs.dliQueue,
    mode: "DRY_RUN",
  });

  ensureDir(OUT_DIR);

  writeJson(path.join(OUT_DIR, "runtime_adapter_dry_run_result.json"), result);

  const report = renderMarkdown(result);
  fs.writeFileSync(path.join(OUT_DIR, "runtime_adapter_dry_run_report.md"), report, "utf-8");

  if (result.run_id) {
    const runDir = path.join(OUT_DIR, "runs", result.run_id);
    ensureDir(runDir);
    writeJson(path.join(runDir, "runtime_adapter_dry_run_result.json"), result);
    fs.writeFileSync(path.join(runDir, "runtime_adapter_dry_run_report.md"), report, "utf-8");
  }

  if (!result.valid) {
    console.error("Runtime adapter dry-run failed.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    console.error("");
    console.error(`Status: ${result.status}`);
    process.exit(1);
  }

  console.log("Runtime adapter dry-run ready.");
  console.log(`  Adapter: ${result.adapter}`);

  if (result.run_id) {
    console.log(`  Run ID: ${result.run_id}`);
  }

  console.log(`  Migration ID: ${result.migration_id}`);
  console.log(`  Job Name: ${result.job_name}`);

  if (result.command_sequence && result.command_sequence.length > 0) {
    console.log(`  Commands planned: ${result.command_sequence.length}`);
  }

  if (result.planned_legacy_command) {
    console.log(`  Planned legacy command: ${result.planned_legacy_command}`);
  }

  console.log("Safety: adapter dry-run only, no commands executed, no API write calls, no runtime execution.");

  process.exit(0);
}

main();
