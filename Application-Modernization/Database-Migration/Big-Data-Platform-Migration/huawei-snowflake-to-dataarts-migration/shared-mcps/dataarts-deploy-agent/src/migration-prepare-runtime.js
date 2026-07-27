const path = require("path");
const { prepareRuntimeArtifacts } = require("./migration/runtime-preparer");

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

function main() {
  console.log("=== DataArts Migration Framework: PREPARE RUNTIME ===\n");

  const cliArgs = parseCliArgs(process.argv);
  const result = prepareRuntimeArtifacts({
    packageDir: cliArgs.packageDir,
  });

  if (!result.valid) {
    console.error("Runtime artifact preparation failed.");
    for (const error of result.errors || []) {
      console.error(`  - ${error}`);
    }
    console.error("");
    console.error(`Status: ${result.status}`);
    process.exit(1);
  }

  console.log("Runtime artifacts ready.");
  console.log(`  Migration ID:    ${result.migration_id}`);
  console.log(`  Runtime artifacts: ${result.runtime_artifacts_dir}`);
  console.log(`  Runtime nodes:    ${result.runtime_nodes_dir}`);
  console.log(`  SQL files:        ${result.copied_sql_files.length}`);
  console.log("Safety: local file generation only, no API write calls, no runtime execution.");

  process.exit(0);
}

main();
