const path = require("path");
const { runRuntimeEngine } = require("./runtime/runtime-engine");

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
    }
  }

  return parsed;
}

function main() {
  console.log("=== DataArts Runtime Engine: DRY-RUN ===\n");

  const cliArgs = parseCliArgs(process.argv);
  const result = runRuntimeEngine({
    packageDir: cliArgs.packageDir,
    jobName: cliArgs.jobName,
    dliQueue: cliArgs.dliQueue,
    mode: "DRY_RUN",
  });

  if (!result.valid) {
    console.error("Runtime engine dry-run failed.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    console.error("");
    console.error(`Status: ${result.status}`);
    process.exit(1);
  }

  console.log("Runtime engine dry-run ready.");
  console.log(`  Run ID:           ${result.run_id}`);
  console.log(`  Migration ID:     ${result.migration_id}`);
  console.log(`  Job Name:         ${result.job_name}`);
  console.log(`  DLI Queue:        ${result.dli_queue}`);
  console.log(`  Runtime Artifacts: ${result.runtime_artifacts_dir}`);
  console.log(`  Commands planned: ${result.command_sequence.length}`);
  console.log("Safety: dry-run only, no commands executed, no API write calls, no runtime execution.");

  process.exit(0);
}

main();
