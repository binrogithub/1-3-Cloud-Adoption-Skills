const path = require("path");
const { executeNativeDliPlan } = require("./runtime/native-dli-executor");
const { createMockDliClient } = require("./runtime/dli/mock-dli-client");
const { loadRuntimePackageArtifacts } = require("./runtime/runtime-package-loader");
const { loadMigrationPackage } = require("./migration/package-loader");

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
  console.log("=== DataArts Migration Framework: NATIVE DLI MOCK EXECUTION ===\n");

  const cliArgs = parseCliArgs(process.argv);

  if (!cliArgs.packageDir) {
    console.error("Error: --package-dir is required");
    process.exit(1);
  }

  const resolvedPackageDir = path.resolve(cliArgs.packageDir);
  const dliQueue = cliArgs.dliQueue || "default";

  const pkg = loadMigrationPackage(resolvedPackageDir);
  if (!pkg.valid) {
    console.error("Error: Invalid migration package");
    for (const e of pkg.errors) {
      console.error(`  - ${e}`);
    }
    process.exit(1);
  }

  const runtimeArtifacts = loadRuntimePackageArtifacts({
    packageDir: resolvedPackageDir,
    migrationId: pkg.migration_id,
  });

  const validationQueries = runtimeArtifacts.valid
    ? (runtimeArtifacts.validation_queries.queries || [])
    : [];

  const mockClient = createMockDliClient({ validationQueries });

  const result = executeNativeDliPlan({
    packageDir: cliArgs.packageDir,
    dliQueue,
    mode: "MOCK",
    dliClient: mockClient,
    outDir: cliArgs.outDir || "./out",
  });

  if (!result.valid) {
    console.error("Native DLI mock execution failed.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    console.error("");
    console.error(`Status: ${result.status}`);
    process.exit(1);
  }

  console.log("Native DLI mock execution complete.");
  console.log(`  Run ID: ${result.run_id}`);
  console.log(`  Migration ID: ${result.migration_id}`);
  console.log(`  Setup steps: ${result.setup_results.length}`);
  console.log(`  Target steps: ${result.target_results.length}`);
  console.log(`  Validation checks: ${result.comparison_results.length}`);
  console.log(`  Final equivalence: ${result.final_equivalence}`);
  console.log("Safety: mock execution only, no cloud APIs, no real SQL execution, no runtime execution.");

  process.exit(0);
}

main();
