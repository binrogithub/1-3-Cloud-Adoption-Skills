const dotenv = require("dotenv");
const fs = require("fs");
const path = require("path");

const ENV_FILE = path.resolve(__dirname, "..", ".env.dataarts");

const REQUIRED_VARS = [
  "HUAWEI_REGION",
  "HUAWEI_PROJECT_ID",
  "HUAWEI_AK",
  "HUAWEI_SK",
  "DATAARTS_WORKSPACE_ID",
];

const OPTIONAL_VARS = [
  "DATAARTS_JOB_NAME",
  "DATAARTS_ARTIFACTS_DIR",
  "DLI_QUEUE_NAME",
];

const ONESHOT_NOT_REQUIRED = [
  "DATAARTS_JOB_NAME",
  "DATAARTS_ARTIFACTS_DIR",
];

const SENSITIVE_VARS = new Set(["HUAWEI_AK", "HUAWEI_SK"]);

const PLACEHOLDER_PATTERNS = [
  /^REPLACE_ME$/i,
  /^your_.*_here$/i,
  /^changeme$/i,
  /^placeholder$/i,
];

function isPlaceholder(value) {
  return PLACEHOLDER_PATTERNS.some((p) => p.test(value));
}

function load() {
  if (!fs.existsSync(ENV_FILE)) {
    throw new Error(`Missing credentials file: ${ENV_FILE}`);
  }
  const parsed = dotenv.config({ path: ENV_FILE }).parsed;
  if (!parsed) {
    throw new Error(`Failed to parse ${ENV_FILE}`);
  }
  for (const key of [...REQUIRED_VARS, ...OPTIONAL_VARS]) {
    if (process.env[key] !== undefined && process.env[key] !== "") {
      parsed[key] = process.env[key];
    }
  }
  return parsed;
}

function validate(parsed) {
  const missing = REQUIRED_VARS.filter((v) => !parsed[v]);
  if (missing.length > 0) {
    throw new Error(`Missing required env vars: ${missing.join(", ")}`);
  }

  const placeholders = REQUIRED_VARS.filter(
    (v) => parsed[v] && isPlaceholder(parsed[v])
  );
  if (placeholders.length > 0) {
    const details = placeholders.map((v) => `${v}=${parsed[v]}`).join(", ");
    throw new Error(`Placeholder values detected: ${details}. Replace with real values before deploying.`);
  }

  return true;
}

function mask(parsed) {
  const safe = {};
  for (const [k, v] of Object.entries(parsed)) {
    if (SENSITIVE_VARS.has(k)) {
      safe[k] = v.length > 4 ? "***" + v.slice(-4) : "****";
    } else {
      safe[k] = v;
    }
  }
  return safe;
}

function getArtifactsDir(parsed) {
  return path.resolve(parsed.DATAARTS_ARTIFACTS_DIR);
}

module.exports = { load, validate, mask, getArtifactsDir, REQUIRED_VARS, OPTIONAL_VARS, ONESHOT_NOT_REQUIRED, SENSITIVE_VARS, ENV_FILE };
