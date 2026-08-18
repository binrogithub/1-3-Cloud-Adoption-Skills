const path = require("path");
const { simulateNativeDliExecution } = require("./runtime/native-dli-simulator");

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

function main() {
  console.log("=== DataArts Migration Framework: NATIVE DLI SIMULATION ===\n");

  const cliArgs = parseCliArgs(process.argv);

  if (!cliArgs.packageDir) {
    console.error("Error: --package-dir is required");
    process.exit(1);
  }

  const result = simulateNativeDliExecution({
    packageDir: cliArgs.packageDir,
    dliQueue: cliArgs.dliQueue || "default",
    outDir: cliArgs.outDir || "./out",
  });

  if (!result.valid) {
    console.error("Native DLI simulation failed.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    console.error("");
    console.error(`Status: ${result.status}`);
    process.exit(1);
  }

  console.log("Native DLI simulation complete.");
  console.log(`  Run ID: ${result.run_id}`);
  console.log(`  Migration ID: ${result.migration_id}`);
  console.log(`  Setup steps: ${result.setup_steps}`);
  console.log(`  Target steps: ${result.target_steps}`);
  console.log(`  Validation steps: ${result.validation_steps}`);
  console.log(`  Total steps simulated: ${result.steps_simulated}`);
  console.log(`  Final equivalence: ${result.final_equivalence}`);
  console.log("Safety: simulation only, no cloud APIs, no SQL execution, no runtime execution.");

  process.exit(0);
}

main();
