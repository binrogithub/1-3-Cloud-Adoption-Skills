const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const os = require("os");
const {
  loadRuntimeConfig,
  maskRuntimeConfig,
  validateRuntimeConfig,
  REQUIRED_DLI_VARS,
  OPTIONAL_DLI_VARS,
} = require("../../src/config/runtime-config-loader");

const ENV_KEYS = [
  "HUAWEI_REGION",
  "HUAWEI_PROJECT_ID",
  "HUAWEI_AK",
  "HUAWEI_SK",
  "DLI_QUEUE_NAME",
  "DATAARTS_WORKSPACE_ID",
];

function saveEnv() {
  const saved = {};
  for (const key of ENV_KEYS) {
    saved[key] = process.env[key];
    delete process.env[key];
  }
  return saved;
}

function restoreEnv(saved) {
  for (const key of ENV_KEYS) {
    if (saved[key] !== undefined) {
      process.env[key] = saved[key];
    } else {
      delete process.env[key];
    }
  }
}

function createTempEnvFile(content) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "rt-config-test-"));
  const envPath = path.join(tmpDir, ".env.dataarts");
  fs.writeFileSync(envPath, content, "utf-8");
  return { tmpDir, envPath };
}

function cleanupTemp(tmpDir) {
  fs.rmSync(tmpDir, { recursive: true, force: true });
}

test("loads config from process.env", () => {
  const saved = saveEnv();
  process.env.HUAWEI_REGION = "cn-north-7";
  process.env.HUAWEI_PROJECT_ID = "proj-env";
  process.env.HUAWEI_AK = "ak-from-env";
  process.env.HUAWEI_SK = "sk-from-env";
  process.env.DLI_QUEUE_NAME = "env-queue";
  process.env.DATAARTS_WORKSPACE_ID = "ws-env";

  try {
    const config = loadRuntimeConfig({ envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(config.region, "cn-north-7");
    assert.equal(config.project_id, "proj-env");
    assert.equal(config.ak, "ak-from-env");
    assert.equal(config.sk, "sk-from-env");
    assert.equal(config.dli_queue, "env-queue");
    assert.equal(config.dataarts_workspace_id, "ws-env");
    assert.equal(config.source_map.HUAWEI_REGION, "env");
    assert.equal(config.source_map.HUAWEI_PROJECT_ID, "env");
    assert.equal(config.source_map.HUAWEI_AK, "env");
    assert.equal(config.source_map.HUAWEI_SK, "env");
    assert.equal(config.source_map.DLI_QUEUE_NAME, "env");
    assert.equal(config.source_map.DATAARTS_WORKSPACE_ID, "env");
  } finally {
    restoreEnv(saved);
  }
});

test("loads config from .env.dataarts temp fixture", () => {
  const { tmpDir, envPath } = createTempEnvFile(
    "HUAWEI_REGION=cn-north-7\nHUAWEI_PROJECT_ID=proj-dotenv\nHUAWEI_AK=ak-dotenv\nHUAWEI_SK=sk-dotenv\nDLI_QUEUE_NAME=dotenv-queue\nDATAARTS_WORKSPACE_ID=ws-dotenv\n"
  );

  const saved = saveEnv();

  try {
    const config = loadRuntimeConfig({ envFilePath: envPath });
    assert.equal(config.region, "cn-north-7");
    assert.equal(config.project_id, "proj-dotenv");
    assert.equal(config.ak, "ak-dotenv");
    assert.equal(config.sk, "sk-dotenv");
    assert.equal(config.dli_queue, "dotenv-queue");
    assert.equal(config.dataarts_workspace_id, "ws-dotenv");
    assert.equal(config.source_map.HUAWEI_REGION, ".env.dataarts");
    assert.equal(config.source_map.HUAWEI_PROJECT_ID, ".env.dataarts");
    assert.equal(config.source_map.HUAWEI_AK, ".env.dataarts");
    assert.equal(config.source_map.HUAWEI_SK, ".env.dataarts");
    assert.equal(config.env_file_status, ".env.dataarts");
  } finally {
    restoreEnv(saved);
    cleanupTemp(tmpDir);
  }
});

test("process.env overrides .env.dataarts", () => {
  const { tmpDir, envPath } = createTempEnvFile(
    "HUAWEI_REGION=dotenv-region\nHUAWEI_PROJECT_ID=dotenv-proj\nHUAWEI_AK=dotenv-ak\nHUAWEI_SK=dotenv-sk\n"
  );

  const saved = saveEnv();
  process.env.HUAWEI_REGION = "env-region";
  process.env.HUAWEI_PROJECT_ID = "env-proj";
  process.env.HUAWEI_AK = "env-ak";
  process.env.HUAWEI_SK = "env-sk";

  try {
    const config = loadRuntimeConfig({ envFilePath: envPath });
    assert.equal(config.region, "env-region");
    assert.equal(config.project_id, "env-proj");
    assert.equal(config.ak, "env-ak");
    assert.equal(config.sk, "env-sk");
    assert.equal(config.source_map.HUAWEI_REGION, "env");
    assert.equal(config.source_map.HUAWEI_PROJECT_ID, "env");
    assert.equal(config.source_map.HUAWEI_AK, "env");
    assert.equal(config.source_map.HUAWEI_SK, "env");
  } finally {
    restoreEnv(saved);
    cleanupTemp(tmpDir);
  }
});

test("missing config reports errors", () => {
  const saved = saveEnv();

  try {
    const config = loadRuntimeConfig({ envFilePath: "/nonexistent/.env.dataarts" });
    const validation = validateRuntimeConfig(config);
    assert.equal(validation.valid, false);
    assert.ok(validation.errors.some((e) => e.includes("HUAWEI_REGION")));
    assert.ok(validation.errors.some((e) => e.includes("HUAWEI_PROJECT_ID")));
    assert.ok(validation.errors.some((e) => e.includes("HUAWEI_AK")));
    assert.ok(validation.errors.some((e) => e.includes("HUAWEI_SK")));
  } finally {
    restoreEnv(saved);
  }
});

test("maskRuntimeConfig never exposes full AK/SK", () => {
  const config = {
    region: "cn-north-7",
    project_id: "proj-123",
    ak: "MY_FULL_ACCESS_KEY_SECRET",
    sk: "MY_FULL_SECRET_KEY_SECRET",
    ak_present: true,
    sk_present: true,
    dataarts_workspace_id: "ws-123",
    dli_queue: "default",
    source_map: {},
    env_file_status: ".env.dataarts",
    warnings: [],
    errors: [],
  };

  const masked = maskRuntimeConfig(config);
  const json = JSON.stringify(masked);
  assert.ok(!json.includes("MY_FULL_ACCESS_KEY_SECRET"));
  assert.ok(!json.includes("MY_FULL_SECRET_KEY_SECRET"));
  assert.equal(masked.ak_present, "PRESENT");
  assert.equal(masked.sk_present, "PRESENT");
});

test("maskRuntimeConfig shows NOT SET for missing values", () => {
  const config = {
    region: null,
    project_id: null,
    ak: null,
    sk: null,
    ak_present: false,
    sk_present: false,
    dataarts_workspace_id: null,
    dli_queue: "default",
    source_map: {},
    env_file_status: "missing",
    warnings: [],
    errors: [],
  };

  const masked = maskRuntimeConfig(config);
  assert.equal(masked.region, "NOT SET");
  assert.equal(masked.project_id, "NOT SET");
  assert.equal(masked.ak_present, "NOT SET");
  assert.equal(masked.sk_present, "NOT SET");
  assert.equal(masked.dataarts_workspace_id, "NOT SET");
});

test("source_map identifies env/.env.dataarts/missing", () => {
  const { tmpDir, envPath } = createTempEnvFile(
    "HUAWEI_REGION=dotenv-region\nHUAWEI_PROJECT_ID=dotenv-proj\nHUAWEI_AK=dotenv-ak\nHUAWEI_SK=dotenv-sk\n"
  );

  const saved = saveEnv();
  process.env.HUAWEI_REGION = "env-region";
  process.env.HUAWEI_PROJECT_ID = "env-proj";

  try {
    const config = loadRuntimeConfig({ envFilePath: envPath });
    assert.equal(config.source_map.HUAWEI_REGION, "env");
    assert.equal(config.source_map.HUAWEI_PROJECT_ID, "env");
    assert.equal(config.source_map.HUAWEI_AK, ".env.dataarts");
    assert.equal(config.source_map.HUAWEI_SK, ".env.dataarts");
    assert.equal(config.source_map.DLI_QUEUE_NAME, "missing");
    assert.equal(config.source_map.DATAARTS_WORKSPACE_ID, "missing");
  } finally {
    restoreEnv(saved);
    cleanupTemp(tmpDir);
  }
});

test("source_map identifies config.js values", () => {
  const saved = saveEnv();

  try {
    const config = loadRuntimeConfig({
      envFilePath: "/nonexistent/.env.dataarts",
      configJsValues: {
        HUAWEI_REGION: "configjs-region",
        HUAWEI_PROJECT_ID: "configjs-proj",
      },
    });
    assert.equal(config.source_map.HUAWEI_REGION, "config.js");
    assert.equal(config.source_map.HUAWEI_PROJECT_ID, "config.js");
    assert.equal(config.region, "configjs-region");
    assert.equal(config.project_id, "configjs-proj");
  } finally {
    restoreEnv(saved);
  }
});

test("config.js overrides process.env", () => {
  const saved = saveEnv();
  process.env.HUAWEI_REGION = "env-region";

  try {
    const config = loadRuntimeConfig({
      envFilePath: "/nonexistent/.env.dataarts",
      configJsValues: {
        HUAWEI_REGION: "configjs-region",
      },
    });
    assert.equal(config.source_map.HUAWEI_REGION, "config.js");
    assert.equal(config.region, "configjs-region");
  } finally {
    restoreEnv(saved);
  }
});

test("validateRuntimeConfig warns about missing workspace id by default", () => {
  const config = {
    region: "cn-north-7",
    project_id: "proj-123",
    ak: "ak",
    sk: "sk",
    ak_present: true,
    sk_present: true,
    dataarts_workspace_id: null,
    dli_queue: "default",
    source_map: {},
    warnings: [],
    errors: [],
  };

  const validation = validateRuntimeConfig(config);
  assert.equal(validation.valid, true);
  assert.ok(validation.warnings.some((w) => w.includes("DATAARTS_WORKSPACE_ID")));
});

test("validateRuntimeConfig requires workspace id when option set", () => {
  const config = {
    region: "cn-north-7",
    project_id: "proj-123",
    ak: "ak",
    sk: "sk",
    ak_present: true,
    sk_present: true,
    dataarts_workspace_id: null,
    dli_queue: "default",
    source_map: {},
    warnings: [],
    errors: [],
  };

  const validation = validateRuntimeConfig(config, { requireWorkspaceId: true });
  assert.equal(validation.valid, false);
  assert.ok(validation.errors.some((e) => e.includes("DATAARTS_WORKSPACE_ID")));
});

test("validateRuntimeConfig warns about invalid region pattern", () => {
  const config = {
    region: "invalid-region-format",
    project_id: "proj-123",
    ak: "ak",
    sk: "sk",
    ak_present: true,
    sk_present: true,
    dataarts_workspace_id: "ws-123",
    dli_queue: "default",
    source_map: {},
    warnings: [],
    errors: [],
  };

  const validation = validateRuntimeConfig(config);
  assert.equal(validation.valid, true);
  assert.ok(validation.warnings.some((w) => w.includes("does not match expected pattern")));
});

test("raw config does not include AK/SK values", () => {
  const saved = saveEnv();

  try {
    const config = loadRuntimeConfig({
      configJsValues: {
        HUAWEI_REGION: "cn-north-7",
        HUAWEI_PROJECT_ID: "proj-123",
        HUAWEI_AK: "secret-ak-value",
        HUAWEI_SK: "secret-sk-value",
      },
      envFilePath: "/nonexistent/.env.dataarts",
    });

    assert.ok(!config.raw.HUAWEI_AK);
    assert.ok(!config.raw.HUAWEI_SK);
    assert.equal(config.raw.HUAWEI_REGION, "cn-north-7");
    assert.equal(config.raw.HUAWEI_PROJECT_ID, "proj-123");
  } finally {
    restoreEnv(saved);
  }
});

test("DLI_QUEUE_NAME defaults to 'default' when missing", () => {
  const saved = saveEnv();

  try {
    const config = loadRuntimeConfig({ envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(config.dli_queue, "default");
  } finally {
    restoreEnv(saved);
  }
});

test("no full secret appears in JSON output of maskRuntimeConfig", () => {
  const saved = saveEnv();

  try {
    const config = loadRuntimeConfig({
      configJsValues: {
        HUAWEI_REGION: "cn-north-7",
        HUAWEI_PROJECT_ID: "proj-123",
        HUAWEI_AK: "LONG_ACCESS_KEY_12345",
        HUAWEI_SK: "LONG_SECRET_KEY_67890",
        DATAARTS_WORKSPACE_ID: "ws-123",
      },
      envFilePath: "/nonexistent/.env.dataarts",
    });

    const masked = maskRuntimeConfig(config);
    const json = JSON.stringify(masked);
    assert.ok(!json.includes("LONG_ACCESS_KEY_12345"));
    assert.ok(!json.includes("LONG_SECRET_KEY_67890"));
  } finally {
    restoreEnv(saved);
  }
});

test("REQUIRED_DLI_VARS includes expected vars", () => {
  assert.ok(REQUIRED_DLI_VARS.includes("HUAWEI_REGION"));
  assert.ok(REQUIRED_DLI_VARS.includes("HUAWEI_PROJECT_ID"));
  assert.ok(REQUIRED_DLI_VARS.includes("HUAWEI_AK"));
  assert.ok(REQUIRED_DLI_VARS.includes("HUAWEI_SK"));
});

test("OPTIONAL_DLI_VARS includes expected vars", () => {
  assert.ok(OPTIONAL_DLI_VARS.includes("DATAARTS_WORKSPACE_ID"));
  assert.ok(OPTIONAL_DLI_VARS.includes("DLI_QUEUE_NAME"));
});
