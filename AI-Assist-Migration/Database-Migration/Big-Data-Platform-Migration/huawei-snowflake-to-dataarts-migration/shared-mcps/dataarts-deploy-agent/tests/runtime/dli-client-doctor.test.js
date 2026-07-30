const test = require("node:test");
const assert = require("node:assert/strict");
const { runDliClientDoctor } = require("../../src/runtime/dli/dli-client-doctor");

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

test("dli doctor healthy when required config is present", () => {
  const result = runDliClientDoctor({
    config: {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "test_ak",
      HUAWEI_SK: "test_sk",
      DATAARTS_WORKSPACE_ID: "ws-123",
    },
  });

  assert.equal(result.healthy, true);
  assert.equal(result.status, "DLI_CLIENT_DOCTOR_HEALTHY");
  assert.equal(result.client_interface_valid, true);
  assert.equal(result.config.valid, true);
  assert.equal(result.config.region, "cn-north-7");
  assert.equal(result.config.has_ak, true);
  assert.equal(result.config.has_sk, true);
  assert.equal(result.findings.length, 0);
  assert.ok(result.source_map);
  assert.ok(result.env_file_status);
});

test("dli doctor unhealthy when required config missing", () => {
  const saved = saveEnv();
  try {
    const result = runDliClientDoctor({ config: {}, envFilePath: "/nonexistent/.env.dataarts" });
    assert.equal(result.healthy, false);
    assert.equal(result.status, "DLI_CLIENT_DOCTOR_UNHEALTHY");
    assert.ok(result.findings.length > 0);
    assert.ok(result.findings.some((f) => f.includes("HUAWEI_REGION")));
  } finally {
    restoreEnv(saved);
  }
});

test("dli doctor validates client interface", () => {
  const result = runDliClientDoctor({
    config: {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "ak",
      HUAWEI_SK: "sk",
    },
  });

  assert.equal(result.client_interface_valid, true);
});

test("dli doctor safety has no_real_sql_execution", () => {
  const result = runDliClientDoctor({
    config: {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "ak",
      HUAWEI_SK: "sk",
    },
  });

  assert.equal(result.safety.no_real_sql_execution, true);
  assert.equal(result.safety.no_cloud_write_calls, true);
  assert.equal(result.safety.no_confirm, true);
});

test("dli doctor does not expose secrets", () => {
  const result = runDliClientDoctor({
    config: {
      HUAWEI_REGION: "cn-north-7",
      HUAWEI_PROJECT_ID: "proj-123",
      HUAWEI_AK: "super_secret_ak",
      HUAWEI_SK: "super_secret_sk",
    },
  });

  const json = JSON.stringify(result);
  assert.ok(!json.includes("super_secret_ak"));
  assert.ok(!json.includes("super_secret_sk"));
});

test("dli doctor warns about missing workspace id", () => {
  const saved = saveEnv();
  try {
    const result = runDliClientDoctor({
      config: {
        HUAWEI_REGION: "cn-north-7",
        HUAWEI_PROJECT_ID: "proj-123",
        HUAWEI_AK: "ak",
        HUAWEI_SK: "sk",
      },
      envFilePath: "/nonexistent/.env.dataarts",
    });

    assert.ok(result.warnings.some((w) => w.includes("DATAARTS_WORKSPACE_ID")));
  } finally {
    restoreEnv(saved);
  }
});

test("dli doctor with no options uses env defaults", () => {
  const result = runDliClientDoctor();
  assert.ok(result.status);
  assert.ok(result.safety);
  assert.equal(typeof result.healthy, "boolean");
  assert.equal(typeof result.client_interface_valid, "boolean");
});

test("dli doctor uses unified config and includes source_map", () => {
  const fs = require("fs");
  const path = require("path");
  const os = require("os");
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "doctor-dotenv-test-"));
  const envPath = path.join(tmpDir, ".env.dataarts");
  fs.writeFileSync(envPath, "HUAWEI_REGION=cn-north-7\nHUAWEI_PROJECT_ID=proj-dotenv\nHUAWEI_AK=dotenv-ak\nHUAWEI_SK=dotenv-sk\nDATAARTS_WORKSPACE_ID=ws-dotenv\n", "utf-8");

  const saved = saveEnv();

  try {
    const result = runDliClientDoctor({ envFilePath: envPath });
    assert.equal(result.healthy, true);
    assert.equal(result.source_map.HUAWEI_REGION, ".env.dataarts");
    assert.equal(result.source_map.HUAWEI_AK, ".env.dataarts");
    assert.equal(result.env_file_status, ".env.dataarts");
  } finally {
    restoreEnv(saved);
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
