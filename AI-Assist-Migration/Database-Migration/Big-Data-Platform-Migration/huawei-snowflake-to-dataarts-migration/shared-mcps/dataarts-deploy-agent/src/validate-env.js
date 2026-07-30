const config = require("./config");

function main() {
  console.log("=== DataArts Deploy Agent: Environment Validation ===\n");

  try {
    console.log(`Credentials file: ${config.ENV_FILE}`);
    const parsed = config.load();
    console.log(`Parsed ${Object.keys(parsed).length} variable(s) from .env.dataarts\n`);

    config.validate(parsed);
    console.log("All required variables present and non-placeholder.\n");

    const safe = config.mask(parsed);
    console.log("Configuration (masked):");
    for (const [k, v] of Object.entries(safe)) {
      console.log(`  ${k} = ${v}`);
    }

    const artifactsDir = config.getArtifactsDir(parsed);
    const fs = require("fs");
    if (fs.existsSync(artifactsDir)) {
      console.log(`\nDATAARTS_ARTIFACTS_DIR exists: ${artifactsDir}`);
    } else {
      console.log(`\nWARNING: DATAARTS_ARTIFACTS_DIR does not exist: ${artifactsDir}`);
    }

    console.log("\nValidation: PASS");
    process.exit(0);
  } catch (err) {
    console.error(`Validation FAILED: ${err.message}`);
    process.exit(1);
  }
}

main();
