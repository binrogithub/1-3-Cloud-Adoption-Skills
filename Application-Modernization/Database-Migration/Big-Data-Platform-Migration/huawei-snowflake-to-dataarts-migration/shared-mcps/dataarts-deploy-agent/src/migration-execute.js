const path = require("path");
const fs = require("fs");
const { executeMigration } = require("./migration/executor");
const { ensureDir, writeJson } = require("./core/json-file");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "out");

function parseCliArgs(argv) {
  const args = argv.slice(2);
  const parsed = { dryRun: false, confirm: false, simulate: false, mock: false };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === "--dry-run") {
      parsed.dryRun = true;
    } else if (arg === "--confirm") {
      parsed.confirm = true;
    } else if (arg === "--simulate") {
      parsed.simulate = true;
    } else if (arg === "--mock") {
      parsed.mock = true;
    } else if (arg === "--package-dir" && args[i + 1]) {
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

  lines.push("# Migration Execute Report");
  lines.push("");
  lines.push(`**Status:** ${result.status}`);
  lines.push(`**Valid:** ${result.valid ? "YES" : "NO"}`);
  lines.push(`**Mode:** ${result.mode || "N/A"}`);
  lines.push(`**Adapter:** ${result.adapter || "N/A"}`);
  lines.push(`**Run ID:** ${result.run_id || "N/A"}`);
  lines.push(`**Migration Run ID:** ${result.migration_run_id || "N/A"}`);
  lines.push(`**Runtime Run ID:** ${result.runtime_run_id || "N/A"}`);
  lines.push(`**Migration ID:** ${result.migration_id || "N/A"}`);
  lines.push(`**Job Name:** ${result.job_name || "N/A"}`);
  lines.push(`**DLI Queue:** ${result.dli_queue || "N/A"}`);
  lines.push("");

  if (result.instance_id) {
    lines.push(`**Instance ID:** ${result.instance_id}`);
    lines.push("");
  }

  if (result.dataarts_instance_id) {
    lines.push(`**DataArts Instance ID:** ${result.dataarts_instance_id}`);
    lines.push("");
  }

  if (result.runtime_validate_status) {
    lines.push(`**Runtime Validation:** ${result.runtime_validate_status}`);
    lines.push("");
  }

  if (result.final_equivalence) {
    lines.push(`**Final Equivalence:** ${result.final_equivalence}`);
    lines.push("");
  }

  if (result.runtime_artifacts_dir) {
    lines.push("## Runtime Artifacts");
    lines.push("");
    lines.push(`- Artifacts Dir: \`${result.runtime_artifacts_dir}\``);
    lines.push("");
  }

  if (result.command) {
    lines.push("## Executed Command");
    lines.push("");
    lines.push(`\`\`\`${result.command}\`\`\``);
    lines.push(`**Exit Code:** ${result.exit_code != null ? result.exit_code : "N/A"}`);
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

  if (result.mode === "CONFIRM") {
    lines.push("- Confirm required: YES");
    lines.push("- Adapter layer: YES");
    lines.push("- Legacy demo runtime: YES");
    lines.push("- No publish");
    lines.push("- No schedules");
    lines.push("- No delete");
    lines.push("- No update");
    lines.push("- No overwrite");
    lines.push("- Run-immediate only");
  } else if (result.mode === "MOCK") {
    lines.push("- Mock execution only");
    lines.push("- No cloud API calls");
    lines.push("- No real SQL execution");
    lines.push("- No runtime execution");
    lines.push("- No commands executed");
    lines.push("- Equivalence is MOCK_EQUIVALENT, not EQUIVALENT");
    lines.push("- equivalence_confirmed is false");
    lines.push("- real_runtime_confirmed is false");
  } else if (result.mode === "SIMULATE") {
    lines.push("- Simulation only");
    lines.push("- No cloud API calls");
    lines.push("- No SQL execution");
    lines.push("- No runtime execution");
    lines.push("- No commands executed");
    lines.push("- Equivalence is SIMULATED_EQUIVALENT, not EQUIVALENT");
  } else {
    lines.push("- Dry-run only");
    lines.push("- No commands executed");
    lines.push("- No API write calls");
    lines.push("- No runtime execution");
  }

  lines.push("");

  return lines.join("\n");
}

function main() {
  console.log("=== DataArts Migration Framework: EXECUTE ===\n");

  const cliArgs = parseCliArgs(process.argv);

  if (cliArgs.confirm && !cliArgs.adapter) {
    console.error("Error: --confirm requires --adapter legacy-demo");
    console.error("Confirm execution is currently supported only with adapter=legacy-demo.");
    process.exit(1);
  }

  if (cliArgs.confirm && cliArgs.adapter !== "legacy-demo") {
    console.error(`Error: --confirm is currently supported only with --adapter legacy-demo (got: ${cliArgs.adapter})`);
    process.exit(1);
  }

  if (cliArgs.simulate && cliArgs.adapter && cliArgs.adapter !== "native-dli") {
    console.error(`Error: --simulate is currently supported only with --adapter native-dli (got: ${cliArgs.adapter})`);
    process.exit(1);
  }

  if (cliArgs.mock && cliArgs.adapter && cliArgs.adapter !== "native-dli") {
    console.error(`Error: --mock is currently supported only with --adapter native-dli (got: ${cliArgs.adapter})`);
    process.exit(1);
  }

  if (cliArgs.mock) {
    console.log("SAFETY: Mock execution mode — no cloud APIs, no real SQL execution, no runtime execution.");
    console.log("");
  } else if (cliArgs.simulate) {
    console.log("SAFETY: Simulation mode — no cloud APIs, no SQL execution, no runtime execution.");
    console.log("");
  } else if (cliArgs.confirm) {
    console.log("SAFETY: Controlled execution via legacy-demo adapter.");
    console.log("  - No publish, no schedules, no delete, no update, no overwrite.");
    console.log("  - Run-immediate only.");
    console.log("  - Adapter layer enforced.");
    console.log("  - Abort if job exists.");
    console.log("");
  }

  const result = executeMigration({
    packageDir: cliArgs.packageDir,
    jobName: cliArgs.jobName,
    dliQueue: cliArgs.dliQueue,
    dryRun: cliArgs.dryRun,
    confirm: cliArgs.confirm,
    simulate: cliArgs.simulate,
    mock: cliArgs.mock,
    adapter: cliArgs.adapter,
  });

  ensureDir(OUT_DIR);

  const resultPath = path.join(OUT_DIR, "migration_execute_result.json");
  const reportPath = path.join(OUT_DIR, "migration_execute_report.md");

  writeJson(resultPath, result);
  fs.writeFileSync(reportPath, renderMarkdown(result), "utf-8");

  if (!result.valid) {
    console.error("Migration execute failed.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    console.error("");
    console.error(`Status: ${result.status}`);

    if (result.mode === "CONFIRM") {
      console.error("Safety: downstream stale results must not be trusted unless doctor is healthy.");
    }

    process.exit(1);
  }

  if (result.mode === "CONFIRM") {
    console.log("Migration execution complete.");
    console.log(`  Adapter: ${result.adapter}`);
    console.log(`  Run ID: ${result.run_id}`);
    console.log(`  Migration ID: ${result.migration_id}`);
    console.log(`  Job Name: ${result.job_name}`);
    console.log(`  Instance ID: ${result.instance_id || "N/A"}`);
    console.log(`  DataArts Instance ID: ${result.dataarts_instance_id || "N/A"}`);
    console.log(`  Runtime Validation: ${result.runtime_validate_status || "N/A"}`);
    console.log(`  Final Equivalence: ${result.final_equivalence || "N/A"}`);
    console.log("Safety: no publish, no schedules, no delete, no update, no overwrite, run-immediate only.");
  } else if (result.mode === "MOCK") {
    console.log("Migration execute mock complete.");
    console.log(`  Adapter: ${result.adapter}`);
    console.log(`  Run ID: ${result.run_id}`);
    console.log(`  Migration ID: ${result.migration_id}`);
    console.log(`  Job Name: ${result.job_name}`);
    console.log(`  Final Equivalence: ${result.final_equivalence}`);
    console.log(`  Equivalence Confirmed: ${result.equivalence_confirmed}`);
    console.log(`  Real Runtime Confirmed: ${result.real_runtime_confirmed}`);
    console.log("Safety: mock execution only, no cloud APIs, no real SQL execution, no runtime execution.");
  } else if (result.mode === "SIMULATE") {
    console.log("Migration execute simulation complete.");
    console.log(`  Adapter: ${result.adapter}`);
    console.log(`  Run ID: ${result.run_id}`);
    console.log(`  Migration ID: ${result.migration_id}`);
    console.log(`  Job Name: ${result.job_name}`);
    console.log(`  Final Equivalence: ${result.final_equivalence}`);
    console.log(`  Equivalence Confirmed: ${result.equivalence_confirmed}`);
    console.log("Safety: simulation only, no cloud APIs, no SQL execution, no runtime execution.");
  } else {
    console.log("Migration execute dry-run ready.");
    console.log(`  Adapter: ${result.adapter}`);
    console.log(`  Run ID: ${result.run_id}`);
    console.log(`  Migration ID: ${result.migration_id}`);
    console.log(`  Job Name: ${result.job_name}`);
    console.log(`  Runtime Artifacts: ${result.runtime_artifacts_dir}`);
    if (result.planned_legacy_command) {
      console.log(`  Planned legacy command: ${result.planned_legacy_command}`);
    }
    console.log(`  Commands planned: ${(result.command_sequence || []).length}`);
    console.log("Safety: dry-run only, no commands executed, no API write calls, no runtime execution.");
  }

  process.exit(0);
}

main();
