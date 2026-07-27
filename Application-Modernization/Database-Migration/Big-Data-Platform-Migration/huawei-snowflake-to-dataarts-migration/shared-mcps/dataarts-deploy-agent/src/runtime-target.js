const config = require("./config");

const ROOT = require("path").resolve(__dirname, "..");

function parseCliArgs(argv) {
  const args = argv.slice(2);
  const parsed = {};
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--job-name" && args[i + 1]) {
      parsed.jobName = args[++i];
    } else if (arg === "--artifacts-dir" && args[i + 1]) {
      parsed.artifactsDir = args[++i];
    } else if (arg === "--dli-queue" && args[i + 1]) {
      parsed.dliQueue = args[++i];
    } else if (arg.startsWith("--job-name=")) {
      parsed.jobName = arg.slice("--job-name=".length);
    } else if (arg.startsWith("--artifacts-dir=")) {
      parsed.artifactsDir = arg.slice("--artifacts-dir=".length);
    } else if (arg.startsWith("--dli-queue=")) {
      parsed.dliQueue = arg.slice("--dli-queue=".length);
    }
  }
  return parsed;
}

function resolve(options = {}) {
  const cliArgs = parseCliArgs(options.argv || process.argv);

  const jobName =
    options.jobName ||
    cliArgs.jobName ||
    process.env.DATAARTS_JOB_NAME ||
    null;

  const artifactsDir =
    options.artifactsDir ||
    cliArgs.artifactsDir ||
    process.env.DATAARTS_ARTIFACTS_DIR ||
    null;

  const dliQueue =
    options.dliQueue ||
    cliArgs.dliQueue ||
    (process.env.DLI_QUEUE_NAME || "").trim() ||
    null;

  const errors = [];

  if (!jobName) {
    errors.push("job_name is required. Provide --job-name <name> via CLI, MCP argument, or DATAARTS_JOB_NAME env var.");
  }

  if (!artifactsDir) {
    errors.push("artifact_dir is required. Provide --artifacts-dir <dir> via CLI, MCP argument, or DATAARTS_ARTIFACTS_DIR env var.");
  }

  if (errors.length > 0) {
    return { valid: false, errors, jobName: null, artifactsDir: null, dliQueue: null };
  }

  return {
    valid: true,
    errors: [],
    jobName,
    artifactsDir,
    dliQueue: dliQueue || "default",
  };
}

function loadEnvForValidation() {
  const env = config.load();
  config.validate(env);
  return env;
}

module.exports = { resolve, parseCliArgs, loadEnvForValidation, ROOT };
