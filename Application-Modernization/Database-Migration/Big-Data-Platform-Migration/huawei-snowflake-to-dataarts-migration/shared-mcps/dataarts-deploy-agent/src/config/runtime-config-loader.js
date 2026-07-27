const dotenv = require("dotenv");
const fs = require("fs");
const path = require("path");

const ENV_FILE = path.resolve(__dirname, "..", "..", ".env.dataarts");

const REQUIRED_DLI_VARS = [
  "HUAWEI_REGION",
  "HUAWEI_PROJECT_ID",
  "HUAWEI_AK",
  "HUAWEI_SK",
];

const OPTIONAL_DLI_VARS = [
  "DATAARTS_WORKSPACE_ID",
  "DLI_QUEUE_NAME",
];

const SENSITIVE_VARS = new Set(["HUAWEI_AK", "HUAWEI_SK"]);

function loadDotEnvDataarts(envFilePath) {
  const resolved = envFilePath || ENV_FILE;
  if (!fs.existsSync(resolved)) {
    return { parsed: {}, source: "missing", path: resolved };
  }
  try {
    const content = fs.readFileSync(resolved, "utf-8");
    const parsed = dotenv.parse(content);
    return { parsed, source: ".env.dataarts", path: resolved };
  } catch {
    return { parsed: {}, source: "error", path: resolved };
  }
}

function resolveSource(configJsValue, envValue, dotenvValue) {
  if (configJsValue !== undefined && configJsValue !== "") return "config.js";
  if (envValue !== undefined && envValue !== "") return "env";
  if (dotenvValue !== undefined && dotenvValue !== "") return ".env.dataarts";
  return "missing";
}

function loadRuntimeConfig(options = {}) {
  const warnings = [];
  const errors = [];

  const envFileResult = loadDotEnvDataarts(options.envFilePath);
  const dotenvParsed = envFileResult.parsed || {};

  let configJsValues = {};
  if (options.configJsValues && typeof options.configJsValues === "object") {
    configJsValues = options.configJsValues;
  }

  const allVars = [...REQUIRED_DLI_VARS, ...OPTIONAL_DLI_VARS];

  const resolved = {};
  const sourceMap = {};

  for (const key of allVars) {
    const envVal = process.env[key];
    const dotenvVal = dotenvParsed[key];
    const configJsVal = configJsValues[key];

    const source = resolveSource(configJsVal, envVal, dotenvVal);

    let value;
    if (configJsVal !== undefined && configJsVal !== "") {
      value = configJsVal;
    } else if (envVal !== undefined && envVal !== "") {
      value = envVal;
    } else if (dotenvVal !== undefined && dotenvVal !== "") {
      value = dotenvVal;
    } else {
      value = null;
    }

    resolved[key] = value;
    sourceMap[key] = source;
  }

  if (envFileResult.source === "missing") {
    warnings.push(`.env.dataarts not found at ${envFileResult.path}`);
  } else if (envFileResult.source === "error") {
    warnings.push(`Failed to parse .env.dataarts at ${envFileResult.path}`);
  }

  const region = resolved.HUAWEI_REGION;
  const projectId = resolved.HUAWEI_PROJECT_ID;
  const ak = resolved.HUAWEI_AK;
  const sk = resolved.HUAWEI_SK;
  const workspaceId = resolved.DATAARTS_WORKSPACE_ID;
  const dliQueue = resolved.DLI_QUEUE_NAME || "default";

  return {
    region,
    project_id: projectId,
    ak,
    sk,
    ak_present: !!ak,
    sk_present: !!sk,
    dataarts_workspace_id: workspaceId,
    dli_queue: dliQueue,
    source_map: sourceMap,
    env_file_status: envFileResult.source,
    raw: {
      HUAWEI_REGION: region,
      HUAWEI_PROJECT_ID: projectId,
      DATAARTS_WORKSPACE_ID: workspaceId,
      DLI_QUEUE_NAME: dliQueue,
    },
    warnings,
    errors,
  };
}

function maskRuntimeConfig(config) {
  const masked = {
    region: config.region || "NOT SET",
    project_id: config.project_id ? "PRESENT" : "NOT SET",
    ak_present: config.ak_present ? "PRESENT" : "NOT SET",
    sk_present: config.sk_present ? "PRESENT" : "NOT SET",
    dataarts_workspace_id: config.dataarts_workspace_id ? "PRESENT" : "NOT SET",
    dli_queue: config.dli_queue || "default",
    source_map: { ...config.source_map },
    env_file_status: config.env_file_status,
    warnings: [...(config.warnings || [])],
    errors: [...(config.errors || [])],
  };

  return masked;
}

function validateRuntimeConfig(config, options = {}) {
  const errors = [...(config.errors || [])];
  const warnings = [...(config.warnings || [])];
  const requireWorkspaceId = options.requireWorkspaceId || false;

  if (!config.region) errors.push("HUAWEI_REGION is required");
  if (!config.project_id) errors.push("HUAWEI_PROJECT_ID is required");
  if (!config.ak) errors.push("HUAWEI_AK is required");
  if (!config.sk) errors.push("HUAWEI_SK is required");

  if (!config.dli_queue || config.dli_queue === "default") {
    if (!config.source_map || config.source_map.DLI_QUEUE_NAME === "missing") {
      warnings.push("DLI_QUEUE_NAME not set, using default queue");
    }
  }

  if (requireWorkspaceId && !config.dataarts_workspace_id) {
    errors.push("DATAARTS_WORKSPACE_ID is required");
  } else if (!config.dataarts_workspace_id) {
    warnings.push("DATAARTS_WORKSPACE_ID is not set (optional for DLI-only operations)");
  }

  if (config.region && !/^[a-z]{2}-[a-z]+-\d+[a-z]?$/.test(config.region)) {
    warnings.push(`HUAWEI_REGION "${config.region}" does not match expected pattern (e.g. cn-north-7)`);
  }

  const valid = errors.length === 0;

  return {
    valid,
    errors,
    warnings,
  };
}

module.exports = {
  loadRuntimeConfig,
  maskRuntimeConfig,
  validateRuntimeConfig,
  REQUIRED_DLI_VARS,
  OPTIONAL_DLI_VARS,
  SENSITIVE_VARS,
  ENV_FILE,
};
